"""پیوند پرونده به فروش و خزانهٔ موجود؛ هیچ دفتر مالی جدیدی ندارد."""
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import func
from app.models.inventory import Contact, Item
from app.models.invoices import SalesInvoice, WarehouseIssue
from app.models.returns import SalesReturn
from app.models.receipt import Receipt
from app.models.payment import Payment
from app.models.repair import RepairBranch, RepairDelivery, RepairDeviceSecret, RepairDocument, RepairPart, RepairPartMovement, RepairRemovedPart, RepairTask, RepairWork
from app.schemas.invoices import SalesInvoiceIn, SalesInvoiceLineIn
from app.schemas.receipts import ReceiptIn
from app.schemas.payments import PaymentIn
from app.schemas.settlement import SettlementIn
from app.services import inventory, open_items, payments, receipts, repair as core, repair_parts, settlements, warehouse_issues
from app.services import chart_codes as cc
from app.services.common import get_account

MODELS={'sales_invoice':SalesInvoice,'receipt':Receipt,'payment':Payment,'sales_return':SalesReturn}


def link(db,p,row,kind,document,*,snapshot=None):
    existing=db.query(RepairDocument).filter_by(document_type=kind,document_id=document.id).first()
    if existing:
        if existing.case_id != row.id: raise HTTPException(409,'این سند به پروندهٔ دیگری تعلق دارد.')
        return existing
    entry=RepairDocument(case_id=row.id,document_type=kind,document_id=document.id,work_version=row.work_version,snapshot=snapshot or {},linked_by_id=p.user.id)
    db.add(entry);db.flush()
    return entry


def documents(db,row):
    return db.query(RepairDocument).filter_by(case_id=row.id).order_by(RepairDocument.created_at).all()


def financial(db,row):
    """اثر همان اسناد واقعی روی دریافتنی؛ ابطال و تخصیص‌های مشترک لحاظ می‌شوند."""
    account=get_account(db,cc.ACCOUNTS_RECEIVABLE)
    entries=[];balance=Decimal(0)
    for ref in documents(db,row):
        model=MODELS.get(ref.document_type)
        if not model: continue
        doc=db.get(model,ref.document_id)
        if doc is None: raise HTTPException(409,'سند مرتبط یافت نشد؛ پیوند مالی باید بررسی شود.')
        voided=doc.voided_at is not None
        amount=settled=remaining=Decimal(0)
        if not voided:
            if not doc.journal_entry_id: raise HTTPException(409,'سند تجاری مرتبط هنوز سند حسابداری ندارد.')
            effect=open_items.resolve_item(db,account_id=account.id,contact_id=row.contact_id,source_type=ref.document_type,source_id=doc.id)
            amount=effect['document_amount']
            settled=open_items.settled_amounts(db,[(ref.document_type,doc.id)]).get((ref.document_type,doc.id),Decimal(0))
            remaining=max(amount-settled,Decimal(0))
            balance+=amount if effect['side']=='debit' else -amount
        entries.append({'id':ref.id,'document_id':doc.id,'document_type':ref.document_type,'number':doc.number,'voided':voided,'amount':str(amount),'settled_amount':str(settled),'remaining_amount':str(remaining),'work_version':ref.work_version})
    # تخصیص خارج پرونده نمی‌تواند رسید مصرف‌شده را دوباره برای تحویل قابل استفاده کند.
    debit=sum((Decimal(d['remaining_amount']) for d in entries if d['document_type'] in {'sales_invoice','payment'} and not d['voided']),Decimal(0))
    credit=sum((Decimal(d['remaining_amount']) for d in entries if d['document_type'] in {'receipt','sales_return'} and not d['voided']),Decimal(0))
    return {'currency':'IRR','document_balance':str(balance),'remaining_balance':str(debit-credit),'documents':entries}


def allocate(db,p,row,on):
    # همان قفل طرف حسابِ موتور تسویه؛ ترتیب case → contact در همهٔ این عملیات.
    db.query(Contact.id).filter_by(id=row.contact_id).with_for_update(of=Contact).one()
    account=get_account(db,cc.ACCOUNTS_RECEIVABLE)
    refs=[r for r in documents(db,row) if r.document_type in MODELS]
    items=[]
    for ref in refs:
        doc=db.query(MODELS[ref.document_type]).filter_by(id=ref.document_id).with_for_update(of=MODELS[ref.document_type]).one()
        if doc.voided_at is not None or not doc.journal_entry_id: continue
        item=open_items.resolve_item(db,account_id=account.id,contact_id=row.contact_id,source_type=ref.document_type,source_id=doc.id)
        remaining=item['document_amount']-open_items.settled_amounts(db,[(ref.document_type,doc.id)]).get((ref.document_type,doc.id),Decimal(0))
        if remaining>0: items.append({'source_type':ref.document_type,'source_id':doc.id,'side':item['side'],'amount':remaining})
    debits=[i for i in items if i['side']=='debit'];credits=[i for i in items if i['side']=='credit']
    for debit in debits:
        for credit in credits:
            amount=min(debit['amount'],credit['amount'])
            if amount<=0: continue
            data=SettlementIn(settlement_date=on,contact_id=row.contact_id,account_id=account.id,description=f'تسویهٔ تعمیرگاه؛ پذیرش {row.number}',items=[{**debit,'amount':amount},{**credit,'amount':amount}])
            settlement=settlements.create_settlement(db,data,p.user)
            link(db,p,row,'settlement',settlement)
            debit['amount']-=amount;credit['amount']-=amount


def active_invoice(db,row):
    refs=db.query(RepairDocument.document_id).filter_by(case_id=row.id,document_type='sales_invoice')
    return db.query(SalesInvoice).filter(SalesInvoice.id.in_(refs),SalesInvoice.voided_at.is_(None)).first()


def invoice(db,p,row,data):
    core.check_version(row,data.version)
    if row.status=='closed': raise HTTPException(409,'برای اصلاح پروندهٔ بسته ابتدا سند مالی قبلی را با دلیل ابطال کنید.')
    if data.on<row.admission_date: raise HTTPException(422,'تاریخ فاکتور نباید پیش از پذیرش باشد.')
    if active_invoice(db,row): raise HTTPException(409,'پرونده فاکتور فعال دارد؛ اصلاح از سند اصلی و ابطال انجام می‌شود.')
    if row.status in {'ready','delivered'}: repair_parts.ready(db,row)
    elif row.status in {'unrepairable','cancelled'}:
        for part in db.query(RepairPart).filter_by(case_id=row.id).all():
            if part.status=='reserved' or repair_parts.quantities(db,part)[1]>0: raise HTTPException(409,'پیش از صورتحساب تشخیص یا انصراف، قطعات را تعیین تکلیف کنید.')
        repair_parts.authorized_total(db,row)
    else: raise HTTPException(409,'ابتدا نتیجهٔ تعمیر و کنترل کیفیت یا عدم تعمیر را ثبت کنید.')
    branch=db.get(RepairBranch,row.branch_id)
    if data.discount and (not p.has_permission('repair','approve') or not data.discount_reason or data.discount>branch.discount_ceiling):
        raise HTTPException(403,'تخفیف به مجوز مدیریت، دلیل و سقف تنظیم‌شدهٔ شعبه نیاز دارد.')
    lines=[];issue_ids=set();work_ids=[]
    for work in db.query(RepairWork).filter_by(case_id=row.id).order_by(RepairWork.created_at,RepairWork.id).all():
        if not work.charge_amount: continue
        item=db.get(Item,work.service_id)
        if item is None or not item.is_service: raise HTTPException(409,'اجرت باید به خدمت موجود وصل باشد.')
        lines.append(SalesInvoiceLineIn(item_id=item.id,unit_id=item.primary_unit_id,qty=1,unit_price=work.charge_amount,description=work.customer_result or work.description))
        work_ids.append(str(work.id))
    moves=db.query(RepairPartMovement,RepairPart).join(RepairPart,RepairPart.id==RepairPartMovement.part_id).filter(RepairPart.case_id==row.id,RepairPart.charge_to_customer.is_(True),RepairPartMovement.action=='consume').order_by(RepairPartMovement.created_at,RepairPartMovement.id).all()
    for move,part in moves:
        issue=db.get(WarehouseIssue,move.document_id)
        if issue is None or issue.is_voided or issue.sales_invoice_id: raise HTTPException(409,'خروج قطعه معتبر یا آزاد برای صدور فاکتور نیست.')
        net=warehouse_issues._net_issue_qty(db,issue)
        source=next(l for l in issue.lines if l.id==move.document_line_id)
        if net[source.id]<=0: continue
        item=db.get(Item,part.item_id)
        lines.append(SalesInvoiceLineIn(item_id=part.item_id,qty=net[source.id],unit_id=item.primary_unit_id,unit_price=part.unit_price,source_issue_line_id=source.id,description=f'قطعهٔ تعمیر: {part.title}'))
        issue_ids.add(issue.id)
    if not lines: raise HTTPException(409,'کار دارای اجرت یا قطعهٔ قابل مطالبه ثبت نشده؛ فاکتور صوری صادر نمی‌شود.')
    payload=SalesInvoiceIn(invoice_date=data.on,contact_id=row.contact_id,lines=lines,invoice_discount=data.discount,tax_rate=data.tax_rate,description=f'تعمیرگاه؛ پذیرش {row.number}')
    result=warehouse_issues.post_sales_invoice_from_issues(db,payload,sorted(issue_ids,key=str),p.user) if issue_ids else inventory.post_sales_invoice(db,payload,p.user,move_inventory=False,issue_accounting=True)
    _,approval=core.approved_estimate(db,row)
    final=open_items.resolve_item(db,account_id=get_account(db,cc.ACCOUNTS_RECEIVABLE).id,contact_id=row.contact_id,source_type='sales_invoice',source_id=result.id)['document_amount']
    if final>approval.authorized_ceiling: raise HTTPException(409,'مبلغ نهایی با مالیات از سقف مجاز مشتری بیشتر است؛ تأیید تازه لازم است.')
    ref=link(db,p,row,'sales_invoice',result,snapshot={'work_ids':work_ids,'discount_reason':data.discount_reason})
    allocate(db,p,row,data.on)
    core.event(db,p,row,'invoice_issued',{'invoice_id':str(result.id),'number':result.number})
    return ref


def cash(db,p,row,data,*,refund=False):
    core.check_version(row,data.version)
    if row.status=='closed': raise HTTPException(409,'پرونده بسته است؛ اصلاح مالی باید در سند اصلی ثبت و پیوند آن بازبینی شود.')
    if data.on<row.admission_date: raise HTTPException(422,'تاریخ دریافت یا پرداخت نباید پیش از پذیرش باشد.')
    kwargs={'amount':data.amount,'description':data.reason}
    if refund:
        balance=Decimal(financial(db,row)['remaining_balance'])
        if balance>=0 or data.amount>-balance: raise HTTPException(409,'بازپرداخت باید در حد بستانکاری واقعی پرونده باشد.')
        if data.method=='card': raise HTTPException(422,'بازپرداخت با صندوق یا حوالهٔ بانکی ثبت می‌شود.')
        components={'cash':[{'cashbox_id':data.cashbox_id,**kwargs}]} if data.method=='cash' else {'bank_withdrawals':[{'bank_account_id':data.bank_account_id,'number':data.reference_no,**kwargs}]}
        if data.method=='transfer' and not data.bank_account_id: raise HTTPException(422,'حساب بانکی واقعی را انتخاب کنید.')
        result=payments.create_payment(db,PaymentIn(payment_type='customer',contact_id=row.contact_id,payment_date=data.on,description=data.reason,**components),p.user)
        kind='payment'
    else:
        if data.method=='cash': components={'cash':[{'cashbox_id':data.cashbox_id,**kwargs}]}
        elif data.method=='transfer':
            if not data.bank_account_id: raise HTTPException(422,'حساب بانکی واقعی را انتخاب کنید.')
            components={'transfers':[{'bank_account_id':data.bank_account_id,'reference_no':data.reference_no,**kwargs}]}
        else:
            if not data.pos_terminal_id or not data.reference_no: raise HTTPException(422,'کارت‌خوان و کد پیگیری واقعی را وارد کنید.')
            components={'cards':[{'pos_terminal_id':data.pos_terminal_id,'reference_no':data.reference_no,**kwargs}]}
        result=receipts.create_receipt(db,ReceiptIn(contact_id=row.contact_id,receipt_date=data.on,description=data.reason,**components),p.user)
        kind='receipt'
    ref=link(db,p,row,kind,result)
    allocate(db,p,row,data.on)
    core.event(db,p,row,'refund_recorded' if refund else 'receipt_recorded',{'document_id':str(result.id),'number':int(result.number)})
    return ref


def attach_document(db,p,row,data):
    core.check_version(row,data.version)
    if data.document_type=='sales_invoice': raise HTTPException(422,'فاکتور تعمیر باید از عملیات همین پرونده صادر شود تا خروج تکرار نشود.')
    model=MODELS[data.document_type]
    doc=db.query(model).filter_by(id=data.document_id).with_for_update(of=model).one_or_none()
    contact_id = db.get(SalesInvoice,doc.sales_invoice_id).contact_id if doc and data.document_type=='sales_return' else getattr(doc,'contact_id',None)
    if doc is None or contact_id!=row.contact_id or doc.voided_at or not doc.journal_entry_id: raise HTTPException(422,'سند فعال حسابداری‌شدهٔ همین مشتری را انتخاب کنید.')
    if data.document_type=='sales_return':
        if not db.query(RepairDocument).filter_by(case_id=row.id,document_type='sales_invoice',document_id=doc.sales_invoice_id).first(): raise HTTPException(422,'برگشت باید مربوط به فاکتور همین تعمیر باشد.')
    if data.document_type in {'receipt','payment'}:
        if doc.currency_code not in {None,'','IRR'}: raise HTTPException(422,'سند تعمیرگاه باید ریالی باشد.')
        account=get_account(db,cc.ACCOUNTS_RECEIVABLE)
        open_items.resolve_item(db,account_id=account.id,contact_id=row.contact_id,source_type=data.document_type,source_id=doc.id)
    ref=link(db,p,row,data.document_type,doc)
    on=getattr(doc,'receipt_date',None) or getattr(doc,'payment_date',None) or getattr(doc,'return_date',None)
    allocate(db,p,row,on)
    core.event(db,p,row,'document_linked',{'document_type':data.document_type,'document_id':str(doc.id),'reason':data.reason})
    return ref


def delivery(db,p,row,data):
    from app.services.repair_custody import assert_present
    assert_present(db,row)
    core.check_version(row,data.version)
    if db.query(RepairDelivery).filter_by(case_id=row.id).first(): raise HTTPException(409,'تحویل این دستگاه قبلاً ثبت شده است.')
    if row.status not in {'ready','unrepairable','cancelled'}: raise HTTPException(409,'برای تحویل، تعمیر و کنترل کیفیت را پایان دهید یا نتیجهٔ غیرقابل‌تعمیر/لغو را ثبت کنید.')
    if not data.checklist or not all(data.checklist.values()): raise HTTPException(409,'بررسی دستگاه، لوازم و اختیار تحویل‌گیرنده را پیش از تحویل تأیید کنید.')
    if set(data.checklist) != {'device','accessories','receiver_authorized'}: raise HTTPException(422,'چک‌لیست تحویل معتبر نیست.')
    if row.status=='ready': repair_parts.ready(db,row)
    for part in db.query(RepairPart).filter_by(case_id=row.id).all():
        if part.status=='reserved' or repair_parts.quantities(db,part)[1]>0: raise HTTPException(409,'قطعهٔ نزد تعمیرگاه یا رزرو باز دارد؛ حتی قطعهٔ مشتری باید تعیین تکلیف شود.')
    if db.query(RepairRemovedPart).filter_by(case_id=row.id,disposition='retained').first(): raise HTTPException(409,'قطعهٔ بازشده هنوز نزد تعمیرگاه است؛ تکلیف تحویل یا اسقاط با رضایت را ثبت کنید.')
    actual=sum((w.charge_amount for w in db.query(RepairWork).filter_by(case_id=row.id)),Decimal(0))
    actual+=sum((repair_parts.quantities(db,part)[0]*part.unit_price for part in db.query(RepairPart).filter_by(case_id=row.id) if part.charge_to_customer),Decimal(0))
    active=active_invoice(db,row)
    if actual and not active: raise HTTPException(409,'کار قابل مطالبه باید فاکتور واقعی فعال داشته باشد.')
    if active:
        ref=db.query(RepairDocument).filter_by(case_id=row.id,document_type='sales_invoice',document_id=active.id).one()
        if ref.work_version!=row.work_version: raise HTTPException(409,'کار پس از فاکتور تغییر کرده؛ ابتدا فاکتور را اصلاح کنید.')
    balance=Decimal(financial(db,row)['remaining_balance'])
    if balance>0 and (not data.credit_reason or not p.has_permission('repair_credit','approve')): raise HTTPException(403,'تحویل با بدهی به مجوز تحویل اعتباری و دلیل نیاز دارد.')
    result=RepairDelivery(case_id=row.id,delivered_at=datetime.now(timezone.utc),outstanding_snapshot=balance,handed_by_id=p.user.id,**data.model_dump(exclude={'version'}))
    db.add(result);db.flush()
    db.query(RepairDeviceSecret).filter_by(case_id=row.id).delete(synchronize_session=False)
    row.status='delivered'
    core.event(db,p,row,'device_delivered',{'delivery_id':str(result.id),'receiver_name':result.receiver_name,'credit_reason':data.credit_reason})
    return result


def close(db,p,row,data):
    from app.models.repair import RepairLoan
    if db.query(RepairLoan).filter_by(case_id=row.id,returned_at=None).first(): raise HTTPException(409,'دستگاه جایگزین هنوز امانت است؛ بازگشت واقعی آن را ثبت کنید.')
    core.check_version(row,data.version)
    if row.status!='delivered': raise HTTPException(409,'پرونده تنها پس از تحویل فیزیکی بسته می‌شود.')
    if Decimal(financial(db,row)['remaining_balance'])!=0: raise HTTPException(409,'دریافت، بازپرداخت یا تسویهٔ پرونده هنوز پایان نیافته است.')
    if db.query(RepairTask).filter(RepairTask.case_id==row.id,RepairTask.status!='done').first(): raise HTTPException(409,'کار ناتمام پرونده را پایان دهید.')
    from app.services.repair_contracts import finish
    finish(db,row)
    row.status='closed';core.event(db,p,row,'case_closed',{})
    return row


def correct(db,p,row,ref_id,data):
    core.check_version(row,data.version)
    ref=db.query(RepairDocument).filter_by(case_id=row.id,id=ref_id).one_or_none()
    if ref is None or ref.document_type not in {'sales_invoice','receipt','payment','sales_return'}: raise HTTPException(404,'سند مالی قابل اصلاح این پرونده پیدا نشد.')
    permission='invoices' if ref.document_type in {'sales_invoice','sales_return'} else 'checks_bank'
    action='delete' if permission=='invoices' else 'update'
    if not p.has_permission(permission,action) or not p.has_permission('checks_bank','create'): raise HTTPException(403,'ابطال به مجوز اصلاح سند اصلی و تسویه نیاز دارد.')
    from app.models.settlement import Settlement,SettlementAllocation
    from app.services import voiding
    doc=db.query(MODELS[ref.document_type]).filter_by(id=ref.document_id).with_for_update(of=MODELS[ref.document_type]).one()
    if doc.voided_at: raise HTTPException(409,'این سند قبلاً باطل شده است.')
    # تنها تخصیص‌های ساخته‌شده در همین پرونده آزاد می‌شوند؛ سند خارجی خودکار تغییر نمی‌کند.
    own_ids=db.query(RepairDocument.document_id).filter_by(case_id=row.id,document_type='settlement')
    related=db.query(Settlement).join(SettlementAllocation).filter(Settlement.id.in_(own_ids),Settlement.voided_at.is_(None),SettlementAllocation.source_type==ref.document_type,SettlementAllocation.source_id==doc.id).order_by(Settlement.id).with_for_update(of=Settlement).all()
    for entry in related: settlements.void_settlement(db,entry.id,reason=data.reason,user=p.user)
    voiding.guard_no_active_allocations(db,ref.document_type,doc.id,'سند تعمیر')
    if ref.document_type=='sales_invoice': voiding.void_sales_invoice(db,doc.id,reason=data.reason,user=p.user,void_date=data.on)
    elif ref.document_type=='sales_return': voiding.void_sales_return(db,doc.id,reason=data.reason,user=p.user,void_date=data.on)
    elif ref.document_type=='receipt': receipts.void_receipt(db,doc.id,reason=data.reason,user=p.user,void_date=data.on)
    else: payments.void_payment(db,doc.id,reason=data.reason,user=p.user,void_date=data.on)
    if row.status=='closed': row.status='delivered'
    core.event(db,p,row,'document_voided',{'document_id':str(doc.id),'document_type':ref.document_type,'reason':data.reason})
    return ref
