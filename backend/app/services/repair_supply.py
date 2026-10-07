"""Supplier metadata and company-stock extraction using native warehouse documents."""
from datetime import datetime,timezone
from decimal import Decimal,ROUND_FLOOR
from uuid import UUID
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from app.models.inventory import Item,Contact,StockLedger
from app.models.invoices import PurchaseInvoice,PurchaseInvoiceLine,WarehouseIssue,WarehouseReceipt
from app.models.returns import PurchaseReturn,PurchaseReturnLine
from app.models.advanced_inventory import StockBatch,StockBatchSerial
from app.models.accounting import JournalEntry,JournalLine
from app.models.repair import RepairPart
from app.models.repair_completion import RepairPartAssessment,RepairSupplierClaim,RepairHarvest
from app.schemas.invoices import DirectWarehouseIssueIn,WarehouseIssueLineIn,WarehouseReceiptIn,WarehouseReceiptLineIn
from app.services import repair as core,repair_parts,units,warehouses,warehouse_issues,warehouse_receipts,serials
from app.services.common import get_account,make_journal_entry,assert_postable_account
from app.services.inventory import work_in_process_account,lock_items
from app.services.voiding import reverse_journal_entry
from app.services.period_close import assert_period_open


def assessment(db,p,row,part_id,data):
    core.check_version(row,data.version);core.editable_case(row)
    part=repair_parts.get_part(db,p,row.id,part_id)
    if part.owner!='company': raise HTTPException(422,'اطلاعات خرید و ضمانت تأمین‌کننده فقط برای قطعهٔ شرکت ثبت می‌شود.')
    previous=db.query(RepairPartAssessment).filter_by(part_id=part.id).order_by(RepairPartAssessment.revision.desc()).first()
    if (previous.revision if previous else 0)!=data.previous_revision: raise HTTPException(409,'ارزیابی قطعه تغییر کرده؛ نسخهٔ تازه را دریافت کنید.')
    supplier={}
    if data.purchase_invoice_id or data.purchase_line_id:
        if not p.has_permission('invoices','view'): raise HTTPException(403,'مشاهدهٔ خرید نیازمند مجوز فاکتور است.')
        invoice=db.get(PurchaseInvoice,data.purchase_invoice_id) if data.purchase_invoice_id else None
        line=db.get(PurchaseInvoiceLine,data.purchase_line_id) if data.purchase_line_id else None
        if invoice is None or invoice.voided_at or invoice.kind!='goods' or line is None or line.invoice_id!=invoice.id or line.item_id!=part.item_id:
            raise HTTPException(422,'ردیف خرید واقعی همین قطعه را انتخاب کنید.')
        contact=db.get(Contact,invoice.contact_id) if invoice.contact_id else None
        if contact is None: raise HTTPException(422,'خرید باید تأمین‌کنندهٔ مشخص داشته باشد.')
        supplier={'id':str(contact.id),'name':contact.name,'invoice_number':invoice.number}
        if data.warranty_until and data.warranty_until<invoice.invoice_date: raise HTTPException(422,'ضمانت پیش از تاریخ خرید پایان نمی‌یابد.')
    elif data.warranty_until or data.warranty_terms:
        raise HTTPException(422,'ضمانت تأمین‌کننده باید به خرید واقعی متصل باشد.')
    result=RepairPartAssessment(case_id=row.id,part_id=part.id,revision=data.previous_revision+1,supplier_snapshot=supplier,recorded_by_id=p.user.id,**data.model_dump(exclude={'version','previous_revision'}))
    db.add(result);db.flush();core.event(db,p,row,'part_assessed',{'assessment_id':str(result.id),'part_id':str(part.id),'revision':result.revision});return result


def supplier_claim(db,p,row,data):
    core.check_version(row,data.version)
    record=db.query(RepairPartAssessment).filter_by(id=data.assessment_id,case_id=row.id).one_or_none()
    if record is None or not record.purchase_invoice_id or not record.warranty_until: raise HTTPException(422,'ارزیابی دارای خرید و ضمانت تأمین‌کننده را انتخاب کنید.')
    if record.warranty_until<datetime.now(timezone.utc).date(): raise HTTPException(409,'مهلت ضمانت تأمین‌کننده پایان یافته است.')
    if db.query(RepairSupplierClaim.id).filter_by(assessment_id=record.id,status='submitted').first(): raise HTTPException(409,'مطالبهٔ باز این ضمانت قبلاً ثبت شده است.')
    result=RepairSupplierClaim(case_id=row.id,assessment_id=record.id,reason=data.reason,recorded_by_id=p.user.id)
    db.add(result);db.flush();core.event(db,p,row,'supplier_claimed',{'claim_id':str(result.id),'assessment_id':str(record.id)});return result


def resolve_claim(db,p,row,claim_id,data):
    core.check_version(row,data.version)
    claim=db.query(RepairSupplierClaim).filter_by(id=claim_id,case_id=row.id).with_for_update().one_or_none()
    if claim is None: raise HTTPException(404,'مطالبه پیدا نشد.')
    core.check_version(claim,data.claim_version)
    if claim.status!='submitted': raise HTTPException(409,'پاسخ ثبت‌شده بازنویسی نمی‌شود.')
    record=db.get(RepairPartAssessment,claim.assessment_id);part=db.get(RepairPart,record.part_id)
    if data.status=='refunded':
        returned=db.get(PurchaseReturn,data.purchase_return_id) if data.purchase_return_id else None
        if returned is None or returned.voided_at or returned.purchase_invoice_id!=record.purchase_invoice_id or not db.query(PurchaseReturnLine.id).filter_by(return_id=returned.id,purchase_invoice_line_id=record.purchase_line_id).first():
            raise HTTPException(422,'استرداد فقط با سند واقعی برگشت همان خرید ثبت می‌شود.')
    elif data.purchase_return_id: raise HTTPException(422,'سند برگشت فقط برای استرداد خرید انتخاب می‌شود.')
    if data.status=='replaced':
        replacement=db.query(RepairPart).filter_by(id=data.replacement_part_id,case_id=row.id,owner='company').one_or_none()
        if replacement is None or replacement.id==part.id or replacement.substitute_for_id!=part.id: raise HTTPException(422,'درخواست قطعهٔ جایگزین همین پرونده را انتخاب کنید.')
    elif data.replacement_part_id: raise HTTPException(422,'قطعهٔ جایگزین فقط در پاسخ جایگزینی انتخاب می‌شود.')
    claim.status=data.status;claim.response=data.response;claim.purchase_return_id=data.purchase_return_id;claim.replacement_part_id=data.replacement_part_id;claim.resolved_by_id=p.user.id;claim.version+=1
    core.event(db,p,row,'supplier_claim_resolved',{'claim_id':str(claim.id),'status':claim.status});return claim


def stock_item(db,item_id):
    item=db.get(Item,item_id)
    if item is None or not item.is_active or item.is_service: raise HTTPException(422,'کالای انباری فعال شرکت را انتخاب کنید؛ دستگاه مشتری و دارایی ثابت قابل استخراج نیستند.')
    return item


def create_harvest(db,p,branch_id,data):
    core.branch(db,p,branch_id)
    warehouses.assert_usable(db,data.source_warehouse_id,action='استخراج قطعات');warehouses.assert_usable(db,data.output_warehouse_id,action='رسید قطعات')
    item=stock_item(db,data.item_id)
    conversion=units.convert_transaction(db,item,data.qty,data.unit_id,context='production',batch_id=data.batch_id)
    if conversion.target_qty!=1: raise HTTPException(422,'هر استخراج باید دقیقاً یک دستگاه در واحد پایهٔ کالا باشد.')
    if item.is_serial_tracked and len(data.serials)!=1: raise HTTPException(422,'سریال واقعی دستگاه سریالی الزامی است.')
    outputs=[]
    for output in data.outputs:
        part=stock_item(db,output.item_id)
        if part.id==item.id: raise HTTPException(422,'دستگاه ورودی نمی‌تواند قطعهٔ خروجی خودش باشد.')
        converted=units.convert_transaction(db,part,output.qty,output.unit_id,context='production')
        if converted.target_qty.as_tuple().exponent < -8: raise HTTPException(422,'مقدار پایهٔ خروجی حداکثر هشت رقم اعشار دارد.')
        if output.serials and (converted.target_qty!=len(output.serials) or converted.target_qty!=converted.target_qty.to_integral_value()): raise HTTPException(422,'تعداد سریال‌های خروجی باید با مقدار پایه برابر باشد.')
        if part.is_serial_tracked and not output.serials: raise HTTPException(422,'سریال قطعات سریالی الزامی است.')
        outputs.append({**output.model_dump(mode='json'),'qty_primary':str(converted.target_qty),'conversion':converted.snapshot()})
    if data.waste_account_id:
        assert_postable_account(db,data.waste_account_id,subject='حساب ضایعات')
        from app.models.accounting import Account
        account=db.get(Account,data.waste_account_id)
        if account.type!='expense': raise HTTPException(422,'حساب ضایعات باید از نوع هزینه باشد.')
    result=RepairHarvest(branch_id=branch_id,item_id=item.id,on=data.on,source_warehouse_id=data.source_warehouse_id,output_warehouse_id=data.output_warehouse_id,
        device_input={'qty':str(data.qty),'unit_id':str(data.unit_id) if data.unit_id else None,'batch_id':str(data.batch_id) if data.batch_id else None,'serials':data.serials,'conversion':conversion.snapshot()},outputs=outputs,waste_percent=data.waste_percent,waste_account_id=data.waste_account_id,reason=data.reason,recorded_by_id=p.user.id)
    db.add(result);db.flush();return result


def harvest_row(db,p,harvest_id,lock=False):
    query=db.query(RepairHarvest).filter_by(id=harvest_id)
    row=(query.with_for_update() if lock else query).one_or_none()
    if row is None: raise HTTPException(404,'استخراج پیدا نشد.')
    core.branch(db,p,row.branch_id);return row


def exact_cost_splits(qty,amount):
    """Two native receipt lots preserve value even when amount/qty is recurring."""
    low=(amount/qty).to_integral_value(rounding=ROUND_FLOOR)
    high_qty=amount-low*qty
    return [(n,c) for n,c in ((qty-high_qty,low),(high_qty,low+1)) if n>0]


def approve_harvest(db,p,row,data):
    core.check_version(row,data.version)
    if row.status!='draft': raise HTTPException(409,'استخراج قبلاً ثبت یا باطل شده است.')
    with db.begin_nested():
        lock_items(db,[row.item_id]+[UUID(o['item_id']) for o in row.outputs])
        item=stock_item(db,row.item_id)
        if str(item.primary_unit_id)!=row.device_input['conversion']['target_unit_id']: raise HTTPException(409,'واحد پایهٔ دستگاه تغییر کرده؛ پیش‌نویس تازه لازم است.')
        for output in row.outputs:
            part=stock_item(db,UUID(output['item_id']))
            if str(part.primary_unit_id)!=output['conversion']['target_unit_id']: raise HTTPException(409,'واحد پایهٔ قطعه تغییر کرده؛ پیش‌نویس تازه لازم است.')
        if row.waste_account_id: assert_postable_account(db,row.waste_account_id,subject='حساب ضایعات')
        frozen=units.conversion_from_snapshot(row.device_input['conversion'])
        issue=warehouse_issues.create_direct_warehouse_issue(db,DirectWarehouseIssueIn(issue_date=row.on,issue_type='production',warehouse_id=row.source_warehouse_id,description='استخراج قطعات شرکت: '+row.reason,
            lines=[WarehouseIssueLineIn(item_id=item.id,qty=1,unit_id=item.primary_unit_id,batch_allocations=[{'batch_id':row.device_input['batch_id'],'qty':'1'}] if row.device_input['batch_id'] else None)]),p.user,frozen_conversions={0:frozen})
        cost=sum((l.amount for l in issue.lines),Decimal(0))
        allocated_batches={move.batch_id for move in db.query(StockLedger).filter_by(source_type='warehouse_issue',source_id=issue.id) if move.batch_id}
        for name in row.device_input['serials']:
            tagged=db.query(StockBatchSerial).join(StockBatch).filter(StockBatch.item_id==item.id,StockBatchSerial.serial==name).with_for_update(of=StockBatchSerial).one_or_none()
            if tagged is None or tagged.batch_id not in allocated_batches or not serials.current_state(tagged)['in_stock']:
                raise HTTPException(409,'سریال دستگاه باید در همان بچ واقعی خروج و موجود در انبار مبدأ باشد؛ بچ و سریال را دوباره انتخاب کنید.')
        if row.device_input['serials']: serials.assign(db,serials=row.device_input['serials'],item_id=item.id,source_type='warehouse_issue',source_id=issue.id,entry_date=row.on,event_type='issue',user=p.user)
        outputs=[];lines=[];allocated=Decimal(0)
        for output in row.outputs:
            part=stock_item(db,UUID(output['item_id']));qty=Decimal(output['qty_primary'])
            amount=(cost*Decimal(output['percent'])/100).to_integral_value(rounding=ROUND_FLOOR)
            allocated+=amount
            splits=exact_cost_splits(qty,amount)
            if output['serials'] and any(n!=n.to_integral_value() for n,_ in splits): raise HTTPException(409,'تخصیص بهای قطعهٔ سریالی باید برای هر واحد مقدار صحیح داشته باشد؛ درصدها را اصلاح و پیش‌نویس تازه ایجاد کنید.')
            indexes=[]
            for n,unit_cost in splits:
                indexes.append(len(lines)+1);lines.append(WarehouseReceiptLineIn(item_id=part.id,qty=n,unit_id=part.primary_unit_id,unit_cost=unit_cost,description='قطعهٔ استخراج‌شده؛ '+row.reason))
            outputs.append({**output,'allocated_cost':str(amount),'receipt_sequences':indexes})
        waste=cost-allocated
        if not row.waste_percent and waste:
            # The last part absorbs the integer-rial allocation remainder.
            last=outputs[-1];amount=Decimal(last['allocated_cost'])+waste;qty=Decimal(last['qty_primary']);part=stock_item(db,UUID(last['item_id']))
            lines=lines[:last['receipt_sequences'][0]-1];last['receipt_sequences']=[]
            for n,c in exact_cost_splits(qty,amount):
                if last['serials'] and n!=n.to_integral_value(): raise HTTPException(409,'تخصیص سریالی به تقسیم صحیح بهای واحد نیاز دارد.')
                last['receipt_sequences'].append(len(lines)+1);lines.append(WarehouseReceiptLineIn(item_id=part.id,qty=n,unit_id=part.primary_unit_id,unit_cost=c,description='قطعهٔ استخراج‌شده؛ '+row.reason))
            last['allocated_cost']=str(amount);waste=Decimal(0)
        receipt=warehouse_receipts.create_warehouse_receipt(db,None,WarehouseReceiptIn(receipt_date=row.on,warehouse_id=row.output_warehouse_id,receipt_type='production',description='استخراج قطعات شرکت؛ خروج '+str(issue.number),lines=lines),p.user)
        db.flush();db.refresh(receipt)
        if sum((l.landed_amount for l in receipt.lines),Decimal(0))+waste!=cost: raise HTTPException(409,'جمع بهای رسید قطعات و ضایعات با خروج دستگاه برابر نیست؛ استخراج ثبت نشد.')
        for output in outputs:
            batches=[];names=list(output['serials'])
            for seq in output['receipt_sequences']:
                line=next(l for l in receipt.lines if l.seq==seq)
                batch=db.query(StockBatch).join(StockLedger,StockLedger.batch_id==StockBatch.id).filter(StockLedger.source_type=='warehouse_receipt',StockLedger.source_id==receipt.id,StockLedger.source_line_id==line.id).one()
                batches.append(str(batch.id))
                for name in names[:int(line.qty)]:
                    if db.query(StockBatchSerial.id).join(StockBatch).filter(StockBatch.item_id==line.item_id,StockBatchSerial.serial==name).first(): raise HTTPException(409,'سریال قطعه قبلاً ثبت شده است.')
                    tagged=StockBatchSerial(batch_id=batch.id,serial=name);db.add(tagged);db.flush();serials.record(db,tagged,event_type='receipt',source_type='warehouse_receipt',source_id=receipt.id,entry_date=row.on,user=p.user)
                names=names[int(line.qty):]
            output['batch_ids']=batches
        waste_entry=None
        if waste:
            waste_entry=make_journal_entry(db,row.on,'ضایعات استخراج قطعات: '+row.reason,'repair_harvest',p.user,[JournalLine(account_id=row.waste_account_id,debit=waste,credit=0),JournalLine(account_id=work_in_process_account(db).id,debit=0,credit=waste)])
            waste_entry.source_id=row.id
        row.issue_id=issue.id;row.receipt_id=receipt.id;row.waste_entry_id=waste_entry.id if waste_entry else None;row.device_cost=cost;row.waste_cost=waste;row.outputs=outputs;row.status='posted';row.approved_by_id=p.user.id;row.version+=1;db.flush()
    return row


def void_harvest(db,p,row,data):
    core.check_version(row,data.version)
    if row.status!='posted': raise HTTPException(409,'فقط استخراج ثبت‌شده قابل ابطال است.')
    if data.on<row.on: raise HTTPException(422,'ابطال پیش از استخراج مجاز نیست.')
    assert_period_open(db,data.on)
    with db.begin_nested():
        lock_items(db,[row.item_id]+[UUID(o['item_id']) for o in row.outputs])
        batch_ids=[UUID(b) for output in row.outputs for b in output['batch_ids']]
        downstream=db.query(StockLedger.id).filter(StockLedger.batch_id.in_(batch_ids),StockLedger.source_id!=row.receipt_id).first()
        if downstream:
            raise HTTPException(409,'قطعات استخراج‌شده گردش بعدی دارند؛ ابتدا اسناد وابسته را اصلاح کنید. ابطال با موجودی بچ دیگری مجاز نیست.')
        warehouse_receipts.void_warehouse_receipt(db,row.receipt_id,reason=data.reason,user=p.user,void_date=data.on,allow_repair_harvest=True)
        warehouse_issues.void_warehouse_issue(db,row.issue_id,reason=data.reason,user=p.user,void_date=data.on,allow_repair_harvest=True)
        if row.waste_entry_id: reverse_journal_entry(db,db.get(JournalEntry,row.waste_entry_id),void_date=data.on,user=p.user,description='ابطال ضایعات استخراج: '+data.reason)
        for output in row.outputs:
            for tagged in db.query(StockBatchSerial).filter(StockBatchSerial.batch_id.in_([UUID(i) for i in output['batch_ids']])).all():
                serials.record(db,tagged,event_type='return_out',source_type='void_warehouse_receipt',source_id=row.receipt_id,entry_date=data.on,user=p.user)
        for tagged in db.query(StockBatchSerial).join(StockBatch).filter(StockBatch.item_id==row.item_id,StockBatchSerial.serial.in_(row.device_input['serials'])).all():
            serials.record(db,tagged,event_type='return_in',source_type='void_warehouse_issue',source_id=row.issue_id,entry_date=data.on,user=p.user)
        row.status='voided';row.voided_by_id=p.user.id;row.void_reason=data.reason;row.version+=1;db.flush()
    return row
