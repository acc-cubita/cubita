"""گردش فیزیکی قطعه از موتور موجود انبار؛ رکورد تعمیرگاه فقط پیوند و کاربرد را می‌داند."""
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import func
from app.models.inventory import Contact, Item, Warehouse, StockLedger
from app.models.advanced_inventory import StockBatch, StockBatchSerial
from app.models.invoices import PurchaseInvoice, WarehouseIssue, WarehouseIssueLine
from app.models.repair import RepairDevice, RepairDeviceSecret, RepairOutsource, RepairPart, RepairPartMovement, RepairPurchaseRequest, RepairQualityCheck, RepairRemovedPart, RepairTask, RepairWork
from app.schemas.invoices import DirectWarehouseIssueIn, WarehouseIssueLineIn
from app.schemas.issue_returns import IssueReturnIn, IssueReturnLineIn
from app.schemas.transfers import StockTransferIn, StockTransferLineIn
from app.schemas.returns import PurchaseReturnIn, PurchaseReturnLineIn
from app.services import chart_codes as cc, issue_returns, items, reservations, returns, serials, transfers, units, warehouse_issues, warehouses
from app.services.common import get_account
from app.services import repair as core


def get_part(db,p,case_id,part_id):
    core.case(db,p,case_id)
    row = db.query(RepairPart).filter_by(case_id=case_id,id=part_id).populate_existing().one_or_none()
    if row is None: raise HTTPException(404,"قطعهٔ این پرونده پیدا نشد.")
    return row


def quantities(db,part):
    totals = {action:Decimal(qty) for action,qty in db.query(RepairPartMovement.action,func.sum(RepairPartMovement.qty)).filter_by(part_id=part.id).group_by(RepairPartMovement.action).all()}
    consumed = totals.get('consume',Decimal(0)) - totals.get('return_consumed',Decimal(0))
    if part.owner == 'company':
        # Native returns can be posted outside the repair UI. The warehouse
        # documents remain authoritative; do not subtract repair returns twice.
        line_ids = [m.document_line_id for m in db.query(RepairPartMovement).filter_by(part_id=part.id, action='consume').all() if m.document_line_id]
        lines = db.query(WarehouseIssueLine).join(WarehouseIssue, WarehouseIssue.id == WarehouseIssueLine.issue_id).filter(WarehouseIssueLine.id.in_(line_ids), WarehouseIssue.voided_at.is_(None)).all() if line_ids else []
        returned = warehouse_issues.returned_by_issue_line(db, [line.id for line in lines])
        consumed = sum((Decimal(line.qty) - returned.get(line.id, Decimal(0)) for line in lines), Decimal(0))
    custody = totals.get('dispatch',Decimal(0)) - sum((totals.get(a,Decimal(0)) for a in ('consume','return_unused','waste')),Decimal(0))
    if part.owner == 'customer': custody = part.qty - sum((totals.get(a,Decimal(0)) for a in ('consume','return_unused')),Decimal(0))
    return consumed,custody


def projection(db,part):
    out = core.out(part)
    used,custody = quantities(db,part)
    out.update(consumed_qty=str(used),custody_qty=str(custody),movements=[core.out(m) for m in db.query(RepairPartMovement).filter_by(part_id=part.id).order_by(RepairPartMovement.created_at).all()])
    req = db.query(RepairPurchaseRequest).filter_by(part_id=part.id).first()
    out['purchase_request'] = core.out(req) if req else None
    return out


def dirty(row):
    row.work_version += 1
    if row.status == 'ready': row.status = 'repairing'


def authorized_total(db,row,*,extra=Decimal(0),planned=False):
    est,approval = core.approved_estimate(db,row)
    labor = db.query(func.sum(RepairWork.charge_amount)).filter_by(case_id=row.id).scalar() or Decimal(0)
    if planned and not labor:
        labor = sum((Decimal(l['amount']) for l in est.options[approval.option_index]['lines'] if l['kind'] != 'part'),Decimal(0))
    parts = Decimal(0)
    for part in db.query(RepairPart).filter_by(case_id=row.id,owner='company',charge_to_customer=True).all():
        if part.status == 'cancelled': continue
        parts += (part.qty if planned else quantities(db,part)[0]) * part.unit_price
    total = labor + parts + extra
    if total > approval.authorized_ceiling:
        raise HTTPException(409,"هزینهٔ واقعی از سقف تأیید مشتری بیشتر می‌شود؛ نسخهٔ تازهٔ برآورد و تأیید آن را ثبت کنید.")
    return total


def request_part(db,p,row,data):
    from app.services.repair_warranty import assert_customer_charge
    assert_customer_charge(db,row,data.unit_price if data.charge_to_customer else 0)
    core.check_version(row,data.version); core.editable_case(row)
    from app.services.repair_contracts import assert_part
    assert_part(db,row,data)
    if data.owner == 'customer':
        if not data.title or data.item_id or data.source_warehouse_id or data.work_warehouse_id or data.unit_price or data.observations or data.batch_id:
            raise HTTPException(422,"قطعهٔ مشتری با عنوان و مقدار ثبت می‌شود؛ کالا، انبار، قیمت و تبدیل واحد شرکت را به آن نسبت ندهید.")
        part = RepairPart(case_id=row.id,owner='customer',title=data.title,qty=data.qty,unit_snapshot={'source_unit_name':data.customer_unit,'target_unit_name':data.customer_unit,'source_qty':str(data.qty),'target_qty':str(data.qty)},charge_to_customer=False,unit_price=0,created_by_id=p.user.id)
    else:
        if data.item_id is None or data.source_warehouse_id is None or data.work_warehouse_id is None or data.source_warehouse_id == data.work_warehouse_id:
            raise HTTPException(422,"کالا و دو انبار متفاوتِ مبدأ و محل تعمیر را انتخاب کنید.")
        item = db.get(Item,data.item_id)
        if item is None or not item.is_active or item.is_service:
            raise HTTPException(422,"قطعه باید کالای فعال شرکت باشد.")
        warehouses.assert_usable(db,data.source_warehouse_id,action='درخواست قطعه')
        warehouses.assert_usable(db,data.work_warehouse_id,action='نگهداری قطعه در تعمیرگاه')
        if data.charge_to_customer: items.assert_sellable(db,[item])
        if data.batch_id:
            batch = db.get(StockBatch,data.batch_id)
            if batch is None or batch.item_id != item.id or batch.warehouse_id != data.source_warehouse_id:
                raise HTTPException(422,"بار باید متعلق به همین قطعه و انبار مبدأ باشد.")
        conversion = units.convert_transaction(db,item,data.qty,data.unit_id,context='inventory',batch_id=data.batch_id,observations=data.observations)
        original = None
        if data.substitute_for_id:
            original = get_part(db,p,row.id,data.substitute_for_id)
            if not data.compatibility_reason or original.status not in {'requested','cancelled'}:
                raise HTTPException(409,"جایگزین به دلیل سازگاری و قطعهٔ قبلیِ تحویل‌نشده نیاز دارد؛ رزرو قبلی را ابتدا آزاد کنید.")
            original.status = 'cancelled'
            db.flush()
        authorized_total(db,row,extra=conversion.target_qty*data.unit_price if data.charge_to_customer else Decimal(0),planned=True)
        part = RepairPart(case_id=row.id,owner='company',item_id=item.id,title=item.name,qty=conversion.target_qty,unit_snapshot=conversion.snapshot(),unit_price=data.unit_price,
            charge_to_customer=data.charge_to_customer,source_warehouse_id=data.source_warehouse_id,work_warehouse_id=data.work_warehouse_id,batch_id=data.batch_id,
            substitute_for_id=original.id if original else None,compatibility_reason=data.compatibility_reason,created_by_id=p.user.id)
    db.add(part);db.flush()
    dirty(row);core.event(db,p,row,'part_requested',{'part_id':str(part.id),'title':part.title,'owner':part.owner})
    return part


def move(db,p,row,part,data):
    core.check_version(row,data.version);core.editable_case(row)
    if data.action not in {'reserve','release'}:
        from app.services.repair_custody import assert_present
        assert_present(db,row)
    if data.on < row.admission_date:
        raise HTTPException(422,"تاریخ گردش قطعه نباید پیش از پذیرش باشد.")
    consumed,custody = quantities(db,part)
    qty = data.qty
    if data.serials and data.action in {'consume','waste','return_consumed'}:
        if qty is None or len(set(data.serials)) != len(data.serials) or Decimal(len(data.serials)) != qty:
            raise HTTPException(422,"تعداد سریال‌های یکتا باید برابر مقدار پایهٔ گردش باشد.")
    doc_type,doc_id,line_id = '',None,None
    if data.action in {'reserve','dispatch','release'} and data.qty is not None:
        raise HTTPException(422,"رزرو، تحویل و آزادسازی برای تمام مقدار درخواست‌اند؛ مقدار جزئی نفرستید.")
    if part.owner == 'customer':
        if data.action not in {'consume','return_unused'} or qty is None or qty > custody or part.status == 'cancelled':
            raise HTTPException(409,"قطعهٔ مشتری فقط در حد باقیمانده مصرف یا به مشتری بازگردانده می‌شود؛ گردش شرکت ندارد.")
        part.status = 'settled' if qty == custody else 'requested'
    else:
        if not p.has_permission('inventory','create'):
            raise HTTPException(403,"گردش قطعهٔ شرکت به مجوز ثبت انبار نیاز دارد.")
        item = db.get(Item,part.item_id)
        if data.action == 'reserve':
            if part.status != 'requested': raise HTTPException(409,"فقط درخواستِ رزرو‌نشده قابل رزرو است.")
            reservations.reserve(db,item=item,warehouse_id=part.source_warehouse_id,qty=part.qty,on=data.on,source_type='repair_part',source_id=part.id,batch_id=part.batch_id,user=p.user)
            part.status,qty = 'reserved',part.qty
        elif data.action == 'release':
            if part.status != 'reserved': raise HTTPException(409,"قطعه رزرو فعال ندارد.")
            qty = reservations.release(db,source_type='repair_part',source_id=part.id,on=data.on,user=p.user)
            part.status = 'cancelled'
        elif data.action == 'dispatch':
            if part.status != 'reserved': raise HTTPException(409,"پیش از تحویل قطعه، رزرو آن را ثبت کنید.")
            reservations.consume(db,source_type='repair_part',source_id=part.id,on=data.on,user=p.user)
            transfer = transfers.post_stock_transfer(db,StockTransferIn(transfer_date=data.on,from_warehouse_id=part.source_warehouse_id,to_warehouse_id=part.work_warehouse_id,
                description=f'تحویل قطعه به تعمیرگاه؛ پذیرش {row.number}',lines=[StockTransferLineIn(item_id=part.item_id,qty=part.qty,unit_id=item.primary_unit_id,
                    batch_allocations=[{'batch_id':part.batch_id,'qty':part.qty}] if part.batch_id else None)]),p.user)
            incoming=db.query(StockLedger).filter_by(source_type='transfer_in',source_id=transfer.id,item_id=part.item_id).all()
            if part.batch_id:
                batches={m.batch_id for m in incoming}
                if len(batches)!=1 or None in batches: raise HTTPException(409,'ردیابی بار انتقال‌شده کامل نیست؛ تحویل ثبت نشد.')
                part.work_batch_id=next(iter(batches))
            reservations.reserve(db,item=item,warehouse_id=part.work_warehouse_id,qty=part.qty,on=data.on,source_type='repair_part_custody',source_id=part.id,batch_id=part.work_batch_id,user=p.user)
            part.status,qty,doc_type,doc_id = 'dispatched',part.qty,'stock_transfer',transfer.id
        elif data.action in {'consume','return_unused','waste'}:
            if qty is None or qty > custody or part.status != 'dispatched':
                raise HTTPException(409,"مقدار باید در حد قطعهٔ تحویل‌شده و تسویه‌نشده باشد.")
            if data.action == 'consume':
                from app.services.repair_contracts import assert_part
                assert_part(db,row,part,data.on)
            if data.action == 'consume': authorized_total(db,row,extra=qty*part.unit_price if part.charge_to_customer else Decimal(0))
            if data.action == 'waste' and not data.reason: raise HTTPException(422,"دلیل ضایعات را ثبت کنید.")
            reservations.release(db,source_type='repair_part_custody',source_id=part.id,on=data.on,qty=qty,user=p.user)
            if data.action == 'return_unused':
                transfer = transfers.post_stock_transfer(db,StockTransferIn(transfer_date=data.on,from_warehouse_id=part.work_warehouse_id,to_warehouse_id=part.source_warehouse_id,
                    description=f'برگشت قطعهٔ مصرف‌نشده؛ پذیرش {row.number}',lines=[StockTransferLineIn(item_id=part.item_id,qty=qty,unit_id=item.primary_unit_id,batch_allocations=[{'batch_id':part.work_batch_id,'qty':qty}] if part.work_batch_id else None)]),p.user)
                doc_type,doc_id = 'stock_transfer',transfer.id
            else:
                sale = data.action == 'consume' and part.charge_to_customer
                issue = warehouse_issues.create_direct_warehouse_issue(db,DirectWarehouseIssueIn(issue_date=data.on,issue_type='sale' if sale else 'consumption',
                    warehouse_id=part.work_warehouse_id,receiver_id=row.contact_id,account_id=None if sale else get_account(db,cc.COGS).id,
                    description=f'مصرف قطعه در تعمیر؛ پذیرش {row.number}',lines=[WarehouseIssueLineIn(item_id=part.item_id,qty=qty,unit_id=item.primary_unit_id,batch_allocations=[{'batch_id':part.work_batch_id,'qty':qty}] if part.work_batch_id else None)]),p.user)
                doc_type,doc_id,line_id = 'warehouse_issue',issue.id,issue.lines[0].id
                if data.serials:
                    if len(set(data.serials)) != len(data.serials) or Decimal(len(data.serials)) != qty: raise HTTPException(422,"تعداد سریال‌ها باید برابر مقدار پایهٔ مصرف باشد.")
                    serials.assign(db,serials=data.serials,item_id=part.item_id,source_type='warehouse_issue',source_id=issue.id,entry_date=data.on,event_type='issue',user=p.user)
            if qty == custody: part.status = 'settled'
        elif data.action == 'return_consumed':
            original = db.query(RepairPartMovement).filter_by(id=data.source_movement_id,part_id=part.id,action='consume').one_or_none() if data.source_movement_id else None
            if original is None or original.document_type != 'warehouse_issue' or qty is None or not data.reason:
                raise HTTPException(422,"مبنای مصرف، مقدار و دلیل برگشت را مشخص کنید.")
            issue = db.get(WarehouseIssue,original.document_id)
            if issue.sales_invoice_id:
                raise HTTPException(409,"مصرف فاکتورشده باید از مسیر فاکتور برگشتی اصلاح شود؛ برگشت مستقل دوباره موجودی را افزایش می‌دهد.")
            result = issue_returns.create_issue_return(db,IssueReturnIn(return_date=data.on,return_type=issue.issue_type,warehouse_id=part.source_warehouse_id,deliverer_id=row.contact_id,
                description=data.reason,lines=[IssueReturnLineIn(warehouse_issue_line_id=original.document_line_id,qty=qty,unit_id=item.primary_unit_id,return_condition=data.return_condition)]),p.user)
            doc_type,doc_id,line_id = 'warehouse_issue_return',result.id,result.lines[0].id
            if data.serials:
                if not set(data.serials).issubset(set(original.serials)) or len(set(data.serials)) != len(data.serials) or Decimal(len(data.serials)) != qty:
                    raise HTTPException(422,"سریال برگشت باید از سریال‌های همان مصرف و برابر مقدار برگشت باشد.")
                tagged=db.query(StockBatchSerial).join(StockBatch).filter(StockBatch.item_id==part.item_id,StockBatchSerial.serial.in_(data.serials)).with_for_update(of=StockBatchSerial).all()
                if len(tagged)!=len(data.serials) or any(serials.current_state(s)['in_stock'] for s in tagged): raise HTTPException(409,'سریال قبلاً به انبار بازگشته است؛ برگشت دوباره مجاز نیست.')
                serials.assign(db,serials=data.serials,item_id=part.item_id,source_type='warehouse_issue_return',source_id=result.id,entry_date=data.on,event_type='return_in',user=p.user)
        elif data.action == 'supplier_return':
            if not p.has_permission('invoices','create'): raise HTTPException(403,'برگشت به تأمین‌کننده به مجوز ثبت خرید نیز نیاز دارد.')
            totals = {a:Decimal(q) for a,q in db.query(RepairPartMovement.action,func.sum(RepairPartMovement.qty)).filter_by(part_id=part.id).group_by(RepairPartMovement.action).all()}
            available = totals.get('return_unused',Decimal(0)) + totals.get('return_consumed',Decimal(0)) - totals.get('supplier_return',Decimal(0))
            if qty is None or qty > available or not data.reason: raise HTTPException(422,'ابتدا قطعه را از تعمیرگاه به انبار برگردانید؛ مقدار برگشت و دلیل باید معتبر باشد.')
            invoice = db.get(PurchaseInvoice,data.purchase_invoice_id) if data.purchase_invoice_id else None
            source = next((l for l in invoice.lines if l.id == data.purchase_invoice_line_id and l.item_id == part.item_id),None) if invoice else None
            if invoice is None or invoice.is_voided or invoice.kind != 'goods' or invoice.warehouse_id != part.source_warehouse_id or source is None:
                raise HTTPException(422,'فاکتور خرید و ردیف همین قطعه در انبار مبدأ را انتخاب کنید.')
            result = returns.post_purchase_return(db,PurchaseReturnIn(return_date=data.on,purchase_invoice_id=invoice.id,description=data.reason,
                lines=[PurchaseReturnLineIn(item_id=part.item_id,purchase_invoice_line_id=source.id,qty=qty,unit_id=item.primary_unit_id)]),p.user)
            doc_type,doc_id = 'purchase_return',result.id
            if data.serials:
                if len(set(data.serials))!=len(data.serials) or Decimal(len(data.serials))!=qty: raise HTTPException(422,'تعداد سریال برگشت باید برابر مقدار پایه باشد.')
                serials.assign(db,serials=data.serials,item_id=part.item_id,source_type='purchase_return',source_id=result.id,entry_date=data.on,event_type='return_out',user=p.user)
    movement = RepairPartMovement(part_id=part.id,action=data.action,qty=qty,document_type=doc_type,document_id=doc_id,document_line_id=line_id,reason=data.reason,serials=data.serials,actor_id=p.user.id)
    db.add(movement);db.flush()
    dirty(row);core.event(db,p,row,'part_'+data.action,{'part_id':str(part.id),'movement_id':str(movement.id),'qty':str(qty),'document_id':str(doc_id) if doc_id else None})
    return movement


def work(db,p,row,data):
    from app.services.repair_custody import assert_present
    assert_present(db,row)
    from app.services.repair_warranty import assert_customer_charge
    assert_customer_charge(db,row,data.charge_amount)
    core.check_version(row,data.version);core.editable_case(row)
    core.approved_estimate(db,row)
    valid = {t['id'] for t in core.technicians(db,p,row.branch_id)}
    if data.technician_id not in valid or set(data.collaborators) - valid:
        raise HTTPException(422,"تکنسین و همکاران باید اعضای فعال مجاز همین شعبه باشند.")
    if data.service_id:
        service = db.get(Item,data.service_id)
        if service is None or not service.is_service or not service.is_active: raise HTTPException(422,"خدمت فعال از فهرست کالا و خدمات انتخاب کنید.")
    elif data.charge_amount: raise HTTPException(422,"کار دارای اجرت باید به خدمت موجود کوبیتا وصل شود.")
    authorized_total(db,row,extra=data.charge_amount)
    values = data.model_dump(exclude={'version','collaborators','started_at','completed_at'})
    start,end = None,None
    if data.started_at or data.completed_at:
        try:
            start,end = datetime.fromisoformat(data.started_at),datetime.fromisoformat(data.completed_at)
        except (TypeError,ValueError): raise HTTPException(422,"شروع و پایان را با تاریخ و زمان معتبر ثبت کنید.")
        if start.tzinfo is None or end.tzinfo is None or end < start or end > datetime.now(timezone.utc): raise HTTPException(422,"زمان کار باید دارای منطقه زمانی، به‌ترتیب و در گذشته باشد.")
        values['work_minutes'] = int((end-start).total_seconds()+59)//60
    from app.services.repair_contracts import assert_work
    assert_work(db,row,data.charge_amount,values['work_minutes'],end.date() if end else datetime.now(timezone.utc).date())
    entry = RepairWork(case_id=row.id,started_at=start,completed_at=end,collaborators=[str(u) for u in data.collaborators],created_by_id=p.user.id,**values)
    db.add(entry);db.flush();dirty(row);core.event(db,p,row,'work_recorded',{'work_id':str(entry.id),'technician_id':str(entry.technician_id),'minutes':entry.work_minutes})
    return entry


def quality(db,p,row,data):
    from app.services.repair_custody import assert_present
    assert_present(db,row)
    core.check_version(row,data.version);core.editable_case(row)
    category = core.device_type(db,db.get(RepairDevice,row.device_id).type_id)
    if set(data.checklist) - set(category.quality_checklist): raise HTTPException(422,"چک‌لیست کنترل کیفیت با نوع دستگاه سازگار نیست.")
    if data.passed:
        if any(not data.checklist.get(label) for label in category.quality_checklist): raise HTTPException(409,"همهٔ موارد کنترل کیفیت را بررسی و تأیید کنید.")
        if db.query(RepairTask).filter(RepairTask.case_id == row.id,RepairTask.status != 'done').first(): raise HTTPException(409,"کار ناتمام دارد؛ پیش از تأیید نهایی آن را تعیین تکلیف کنید.")
        if db.query(RepairOutsource).filter_by(case_id=row.id,returned_at=None).first(): raise HTTPException(409,"دستگاه یا کار برون‌سپاری هنوز بازنگشته است.")
        for part in db.query(RepairPart).filter_by(case_id=row.id).all():
            if part.status == 'reserved' or (part.owner == 'company' and quantities(db,part)[1] > 0): raise HTTPException(409,"رزرو یا قطعهٔ تحویل‌شدهٔ تسویه‌نشده دارد؛ مصرف، برگشت یا آزادسازی را ثبت کنید.")
    entry = RepairQualityCheck(case_id=row.id,work_version=row.work_version,checked_by_id=p.user.id,**data.model_dump(exclude={'version'}))
    db.add(entry);db.flush()
    if data.passed:
        db.query(RepairDeviceSecret).filter_by(case_id=row.id).delete(synchronize_session=False)
    elif row.status == 'ready':
        row.status = 'testing'
    core.event(db,p,row,'quality_checked',{'quality_id':str(entry.id),'passed':entry.passed})
    return entry


def ready(db,row):
    check = db.query(RepairQualityCheck).filter_by(case_id=row.id).order_by(RepairQualityCheck.created_at.desc()).first()
    if check is None or not check.passed or check.work_version != row.work_version: raise HTTPException(409,"آماده‌تحویل شدن به کنترل کیفیت موفقِ آخرین کار تعمیر نیاز دارد.")
    authorized_total(db,row)


def outsource(db,p,row,data):
    core.check_version(row,data.version);core.editable_case(row)
    vendor = db.get(Contact,data.vendor_id)
    if vendor is None or not vendor.is_active or not vendor.is_supplier: raise HTTPException(422,"تأمین‌کنندهٔ فعال از اشخاص انتخاب کنید.")
    if data.due_date < row.admission_date: raise HTTPException(422,"موعد بازگشت نباید پیش از پذیرش باشد.")
    entry = RepairOutsource(case_id=row.id,created_by_id=p.user.id,**data.model_dump(exclude={'version'}))
    db.add(entry);db.flush();dirty(row);core.event(db,p,row,'outsourced',{'outsource_id':str(entry.id),'vendor_id':str(entry.vendor_id)})
    return entry


def outsource_return(db,p,row,outsource_id,data):
    core.check_version(row,data.version);core.editable_case(row)
    entry = db.query(RepairOutsource).filter_by(case_id=row.id,id=outsource_id).one_or_none()
    if entry is None or entry.returned_at: raise HTTPException(409,"برون‌سپاری باز مربوط به این پرونده پیدا نشد.")
    if data.purchase_invoice_id:
        invoice = db.query(PurchaseInvoice).filter_by(id=data.purchase_invoice_id).with_for_update(of=PurchaseInvoice).one_or_none()
        if invoice is None or invoice.is_voided or invoice.kind != 'service' or invoice.contact_id != entry.vendor_id: raise HTTPException(422,"فاکتور خرید خدمات معتبر همان تأمین‌کننده را انتخاب کنید.")
        if db.query(RepairOutsource).filter_by(purchase_invoice_id=invoice.id).first(): raise HTTPException(409,"این فاکتور قبلاً به برون‌سپاری دیگری وصل شده است.")
        entry.purchase_invoice_id = invoice.id
    entry.returned_at,entry.return_result = datetime.now(timezone.utc),data.result
    dirty(row);core.event(db,p,row,'outsource_returned',{'outsource_id':str(entry.id),'invoice_id':str(data.purchase_invoice_id) if data.purchase_invoice_id else None})
    return entry


def removed(db,p,row,data):
    core.check_version(row,data.version);core.editable_case(row)
    entry = RepairRemovedPart(case_id=row.id,recorded_by_id=p.user.id,**data.model_dump(exclude={'version'}))
    db.add(entry);db.flush();core.event(db,p,row,'removed_part_recorded',{'part_id':str(entry.id),'disposition':entry.disposition,'customer_name':entry.customer_name})
    return entry


def purchase_request(db,p,row,part,data):
    core.check_version(row,data.version);core.editable_case(row)
    if part.owner != 'company' or part.status != 'requested': raise HTTPException(409,"درخواست خرید فقط برای قطعهٔ شرکتِ هنوز رزرو‌نشده ثبت می‌شود.")
    if db.query(RepairPurchaseRequest).filter_by(part_id=part.id).first(): raise HTTPException(409,"این قطعه درخواست خرید دارد.")
    entry = RepairPurchaseRequest(part_id=part.id,due_date=data.due_date,reason=data.reason,created_by_id=p.user.id)
    db.add(entry);db.flush();core.event(db,p,row,'purchase_requested',{'part_id':str(part.id),'request_id':str(entry.id)})
    return entry


def update_purchase_request(db,p,row,part,data):
    core.check_version(row,data.version);core.editable_case(row)
    entry = db.query(RepairPurchaseRequest).filter_by(part_id=part.id).one_or_none()
    if entry is None or entry.status in {'received','cancelled'}: raise HTTPException(409,"درخواست خرید باز پیدا نشد.")
    if data.status == 'received':
        invoice = db.query(PurchaseInvoice).filter_by(id=data.purchase_invoice_id).with_for_update(of=PurchaseInvoice).one_or_none() if data.purchase_invoice_id else None
        if invoice is None or invoice.is_voided or invoice.kind != 'goods' or invoice.warehouse_id != part.source_warehouse_id or not any(l.item_id == part.item_id for l in invoice.lines): raise HTTPException(422,"فاکتور خرید کالای معتبر برای همین قطعه و انبار مبدأ را انتخاب کنید.")
        bought = sum((units.document_conversion(db,l,l.item).target_qty for l in invoice.lines if l.item_id == part.item_id),Decimal(0))
        allocated = db.query(func.sum(RepairPart.qty)).join(RepairPurchaseRequest,RepairPurchaseRequest.part_id == RepairPart.id).filter(RepairPurchaseRequest.purchase_invoice_id == invoice.id,RepairPart.item_id == part.item_id).scalar() or Decimal(0)
        if allocated + part.qty > bought: raise HTTPException(409,'مقدار این درخواست از مقدار خریدِ تخصیص‌نیافتهٔ همین فاکتور بیشتر است.')
        entry.purchase_invoice_id = invoice.id
    elif data.purchase_invoice_id: raise HTTPException(422,"پیوند فاکتور فقط هنگام دریافت کالا ثبت می‌شود.")
    entry.status = data.status
    core.event(db,p,row,'purchase_request_updated',{'request_id':str(entry.id),'status':entry.status})
    return entry
