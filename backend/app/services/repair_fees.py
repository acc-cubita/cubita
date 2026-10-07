"""سهم نسخه‌دار تکنسین؛ بدهی واقعی فقط با فاکتور خرید خدمات ایجاد می‌شود."""
from decimal import Decimal, ROUND_HALF_UP
from fastapi import HTTPException
from sqlalchemy import func
from app.models.inventory import Contact, Item
from app.models.invoices import PurchaseInvoice
from app.models.tenant import Membership
from app.models.repair import RepairFeeRule, RepairTechnicianFee, RepairWork
from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn
from app.services import repair as core, inventory, open_items, chart_codes as cc
from app.services.common import get_account


def create_rule(db,p,data):
    member=db.query(Membership).filter_by(tenant_id=p.tenant_id,user_id=data.technician_id,status='active').with_for_update(of=Membership).one_or_none()
    if member is None: raise HTTPException(422,'تکنسین عضو فعال همین کسب‌وکار نیست.')
    contact=db.get(Contact,data.payee_id);service=db.get(Item,data.service_id)
    if contact is None or not contact.is_active or contact.is_system:
        raise HTTPException(422,'طرف حساب فعال تکنسین را انتخاب کنید.')
    if service is None or not service.is_active or not service.is_service:
        raise HTTPException(422,'خدمت فعال برای ثبت هزینهٔ سهم انتخاب کنید.')
    version=(db.query(func.max(RepairFeeRule.version)).filter_by(technician_id=data.technician_id).scalar() or 0)+1
    row=RepairFeeRule(**data.model_dump(),version=version,created_by_id=p.user.id)
    db.add(row);db.flush();return row


def latest(db,technician_id):
    rule=db.query(RepairFeeRule).filter_by(technician_id=technician_id).order_by(RepairFeeRule.version.desc()).first()
    if rule is None or not rule.enabled: raise HTTPException(409,'قاعدهٔ فعال سهم برای این تکنسین ثبت نشده است.')
    return rule


def calculation(db,row,rule):
    from app.services.repair_business import participation_basis
    works,labor,weighted,shares,has_shares=participation_basis(db,row,rule.technician_id)
    if not works: raise HTTPException(409,'برای این تکنسین کار واقعی در پرونده ثبت نشده است.')
    if rule.mode=='fixed_case': expected=rule.value
    elif rule.mode=='per_operation': expected=rule.value*weighted
    else: expected=labor*rule.value/Decimal(100)
    expected=expected.quantize(Decimal(1),rounding=ROUND_HALF_UP)
    invoices=db.query(PurchaseInvoice).join(RepairTechnicianFee,RepairTechnicianFee.purchase_invoice_id==PurchaseInvoice.id).filter(RepairTechnicianFee.case_id==row.id,RepairTechnicianFee.technician_id==rule.technician_id,PurchaseInvoice.voided_at.is_(None)).all()
    posted=sum((i.total_amount for i in invoices),Decimal(0))
    if expected<posted: raise HTTPException(409,'سهم محاسبه‌شده از هزینهٔ ثبت‌شده کمتر است؛ فاکتور قبلی باید در گردش اصلاح فاکتور بررسی شود.')
    snapshot={'basis':'approved_participation_weighted_gross_labor' if has_shares else 'lead_technician_actual_work_gross_labor_before_invoice_discount','work_ids':[str(w.id) for w in works],
        'labor_rial':str(labor),'operations':len(works),'expected_rial':str(expected),'already_posted_rial':str(posted),
        'rule_version':rule.version,'mode':rule.mode,'value':str(rule.value)}
    if has_shares: snapshot.update(participation=shares,weighted_operations=str(weighted))
    return expected-posted,snapshot


def draft(db,p,row,data):
    core.check_version(row,data.version)
    if row.status not in {'ready','delivered','closed','unrepairable','cancelled'}:
        raise HTTPException(409,'ابتدا نتیجهٔ کار پرونده را ثبت کنید.')
    rule=latest(db,data.technician_id)
    existing=db.query(RepairTechnicianFee).filter_by(case_id=row.id,rule_id=rule.id,work_version=row.work_version).first()
    if existing: return existing
    amount,snapshot=calculation(db,row,rule)
    if amount<=0: raise HTTPException(409,'سهم پرداختنی تازه‌ای برای این تکنسین باقی نمانده است.')
    fee=RepairTechnicianFee(case_id=row.id,rule_id=rule.id,technician_id=rule.technician_id,work_version=row.work_version,
        amount_rial=amount,calculation=snapshot,created_by_id=p.user.id)
    db.add(fee);db.flush();core.event(db,p,row,'technician_fee_drafted',{'fee_id':str(fee.id),'amount_rial':str(amount),'rule_version':rule.version})
    return fee


def approve(db,p,row,fee,data):
    core.check_version(row,data.version)
    if fee.purchase_invoice_id: return fee
    rule=latest(db,fee.technician_id)
    if rule.id!=fee.rule_id or row.work_version!=fee.work_version:
        raise HTTPException(409,'کار یا قاعدهٔ سهم تغییر کرده است؛ پیش‌نویس تازه محاسبه کنید.')
    amount,snapshot=calculation(db,row,rule)
    if amount!=fee.amount_rial or snapshot!=fee.calculation:
        raise HTTPException(409,'هزینهٔ سهم تغییر کرده است؛ پیش‌نویس قبلی قابل تأیید نیست.')
    if data.on<row.admission_date: raise HTTPException(422,'تاریخ هزینه نمی‌تواند پیش از پذیرش باشد.')
    invoice=inventory.post_purchase_invoice(db,PurchaseInvoiceIn(invoice_date=data.on,contact_id=rule.payee_id,kind='service',currency_code='IRR',
        description=f'سهم تکنسین؛ پذیرش {row.number}؛ قاعده نسخه {rule.version}',lines=[PurchaseInvoiceLineIn(item_id=rule.service_id,
        qty=Decimal(1),unit_cost=amount,expense_account_id=get_account(db,cc.SERVICE_EXPENSE).id,duty_amount=Decimal(0))]),p.user)
    fee.purchase_invoice_id=invoice.id;fee.approved_by_id=p.user.id
    core.event(db,p,row,'technician_fee_approved',{'fee_id':str(fee.id),'purchase_invoice_id':str(invoice.id),'amount_rial':str(amount)})
    return fee


def projection(db,fee):
    result=core.out(fee);result.update(status='draft',remaining_rial=None,settled_rial=None,invoice_number=None)
    if fee.purchase_invoice_id:
        invoice=db.get(PurchaseInvoice,fee.purchase_invoice_id)
        if invoice is None: raise HTTPException(409,'فاکتور هزینهٔ سهم پیدا نشد.')
        result['invoice_number']=invoice.number
        if invoice.voided_at: result['status']='voided'
        else:
            effect=open_items.resolve_item(db,account_id=get_account(db,cc.ACCOUNTS_PAYABLE).id,contact_id=invoice.contact_id,source_type='purchase_invoice',source_id=invoice.id)
            settled=open_items.settled_amounts(db,[('purchase_invoice',invoice.id)]).get(('purchase_invoice',invoice.id),Decimal(0))
            remaining=max(effect['document_amount']-settled,Decimal(0))
            result.update(status='settled' if remaining==0 else 'payable',settled_rial=str(settled),remaining_rial=str(remaining))
    return result
