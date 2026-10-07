"""Approved collaborators and append-only staff/customer followup."""
from decimal import Decimal
from fastapi import HTTPException
from app.models.repair import RepairWork,RepairTechnicianFee,RepairCustomerMessage,RepairBranch
from app.models.invoices import PurchaseInvoice
from app.models.repair_completion import RepairParticipation,RepairCustomerFollowup,RepairNotificationPolicy
from app.services import repair as core,repair_parts


def approve_participation(db,p,row,work_id,data):
    core.check_version(row,data.version);core.editable_case(row)
    work=db.query(RepairWork).filter_by(id=work_id,case_id=row.id).one_or_none()
    if work is None: raise HTTPException(404,'عملیات پرونده پیدا نشد.')
    participants={str(work.technician_id),*work.collaborators}
    if {str(s.technician_id) for s in data.shares}!=participants: raise HTTPException(422,'درصدها باید برای تکنسین و همهٔ همکاران همین عملیات ثبت شوند.')
    valid={str(t['id']) for t in core.technicians(db,p,row.branch_id)}
    if not participants.issubset(valid): raise HTTPException(422,'همکاران باید اعضای فعال مجاز شعبه باشند.')
    latest=db.query(RepairParticipation).filter_by(work_id=work.id).order_by(RepairParticipation.revision.desc()).first()
    if (latest.revision if latest else 0)!=data.previous_revision: raise HTTPException(409,'درصدهای عملیات تغییر کرده؛ نسخهٔ تازه را دریافت کنید.')
    for fee in db.query(RepairTechnicianFee).filter_by(case_id=row.id).all():
        if fee.purchase_invoice_id and str(work.id) in fee.calculation.get('work_ids',[]):
            invoice=db.get(PurchaseInvoice,fee.purchase_invoice_id)
            if invoice and not invoice.voided_at: raise HTTPException(409,'این عملیات سهمِ دارای بدهی تأییدشده دارد؛ ابتدا اصلاح فاکتور قبلی را در گردش اصلی اسناد انجام دهید.')
    result=RepairParticipation(case_id=row.id,work_id=work.id,revision=data.previous_revision+1,shares=[s.model_dump(mode='json') for s in data.shares],reason=data.reason,approved_by_id=p.user.id)
    db.add(result);db.flush();repair_parts.dirty(row)
    core.event(db,p,row,'participation_approved',{'participation_id':str(result.id),'work_id':str(work.id),'revision':result.revision,'reason':data.reason});return result


def participation_basis(db,row,technician_id):
    works=[];snapshots=[];labor=Decimal(0);weighted=Decimal(0)
    any_shares=False
    for work in db.query(RepairWork).filter_by(case_id=row.id).order_by(RepairWork.id):
        record=db.query(RepairParticipation).filter_by(work_id=work.id).order_by(RepairParticipation.revision.desc()).first()
        if record:
            any_shares=True
            percent=next((Decimal(s['percent']) for s in record.shares if s['technician_id']==str(technician_id)),Decimal(0))
        else: percent=Decimal(100) if work.technician_id==technician_id else Decimal(0)
        if percent:
            works.append(work);labor+=work.charge_amount*percent/100;weighted+=percent/100
            snapshots.append({'work_id':str(work.id),'participation_id':str(record.id) if record else None,'revision':record.revision if record else 0,'percent':str(percent)})
    return works,labor,weighted,snapshots,any_shares


def followup(db,p,row,data):
    core.check_version(row,data.version)
    message=db.query(RepairCustomerMessage).filter_by(id=data.message_id,case_id=row.id).one_or_none() if data.message_id else None
    if data.message_id and message is None: raise HTTPException(404,'پیام مشتریِ این پرونده پیدا نشد.')
    previous=db.query(RepairCustomerFollowup).filter_by(id=data.previous_id,case_id=row.id).one_or_none() if data.previous_id else None
    if data.previous_id:
        if previous is None or previous.kind!=data.kind or previous.message_id!=data.message_id: raise HTTPException(422,'مرحلهٔ قبلی باید از همین پرونده، پیام و نوع پیگیری باشد.')
        if db.query(RepairCustomerFollowup.id).filter_by(previous_id=previous.id).first(): raise HTTPException(409,'این پیگیری مرحلهٔ تازه دارد؛ آخرین مرحله را دریافت کنید.')
        if previous.kind=='complaint':
            allowed={'received':{'investigating','awaiting_customer','resolved'},'investigating':{'investigating','awaiting_customer','resolved'},'awaiting_customer':{'investigating','awaiting_customer','resolved'},'resolved':{'closed','investigating'},'closed':set()}
            if data.complaint_stage not in allowed[previous.complaint_stage]: raise HTTPException(409,'ترتیب رسیدگی شکایت معتبر نیست.')
    elif data.kind=='complaint' and data.complaint_stage!='received': raise HTTPException(422,'شکایت تازه از مرحلهٔ دریافت شروع می‌شود.')
    if data.responsible_id and data.responsible_id not in {t['id'] for t in core.technicians(db,p,row.branch_id)}: raise HTTPException(422,'مسئول رسیدگی عضو مجاز شعبه باشد.')
    result=RepairCustomerFollowup(**data.model_dump(exclude={'version'}),case_id=row.id,recorded_by_id=p.user.id)
    db.add(result);db.flush();core.event(db,p,row,'customer_followup',{'followup_id':str(result.id),'kind':data.kind,'complaint_stage':data.complaint_stage});return result


def notification_policy(db,p,branch_id):
    core.branch(db,p,branch_id)
    return db.query(RepairNotificationPolicy).filter_by(branch_id=branch_id).order_by(RepairNotificationPolicy.revision.desc()).first()


def save_notification_policy(db,p,branch_id,data):
    core.branch(db,p,branch_id);db.query(RepairBranch).filter_by(id=branch_id).with_for_update().one()
    old=notification_policy(db,p,branch_id)
    if (old.revision if old else 0)!=data.previous_revision: raise HTTPException(409,'تنظیم اعلان تغییر کرده؛ نسخهٔ تازه را دریافت کنید.')
    row=RepairNotificationPolicy(branch_id=branch_id,revision=data.previous_revision+1,approved_by_id=p.user.id,**data.model_dump(exclude={'previous_revision'}))
    db.add(row);db.flush();return row
