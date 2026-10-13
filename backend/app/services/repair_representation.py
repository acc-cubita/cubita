from datetime import datetime,timezone,timedelta
from fastapi import HTTPException
from app.models.inventory import Contact
from app.models.repair import RepairEvent
from app.models.repair_completion import RepairRepresentativeAuthorization as Authorization
from app.services import repair as core
from app.services.sms import normalize_phone


def revoked(db,row,record):
    return db.query(RepairEvent).filter(RepairEvent.tenant_id==row.tenant_id,RepairEvent.case_id==row.id,
        RepairEvent.action=='representation_revoked',RepairEvent.detail['representation_id'].astext==str(record.id)).first()


def get(db,row,rid):
    record=db.query(Authorization).filter_by(tenant_id=row.tenant_id,case_id=row.id,id=rid).one_or_none()
    if record is None:raise HTTPException(404,'اختیار نماینده برای این پرونده پیدا نشد.')
    return record


def approve(db,p,row,data):
    core.check_version(row,data.version)
    phone=normalize_phone(data.phone)
    if not phone:raise HTTPException(422,'شمارهٔ همراه معتبر نماینده را وارد کنید.')
    if data.expires_at.tzinfo is None or not datetime.now(timezone.utc)<data.expires_at<=datetime.now(timezone.utc)+timedelta(days=365):
        raise HTTPException(422,'پایان اعتبار باید دارای منطقهٔ زمانی و در یک سال آینده باشد.')
    if data.contact_id and db.query(Contact).filter_by(tenant_id=p.tenant_id,id=data.contact_id,is_active=True,is_system=False).one_or_none() is None:
        raise HTTPException(422,'نماینده را از اشخاص فعال همین شرکت انتخاب کنید.')
    record=Authorization(case_id=row.id,principal_contact_id=row.contact_id,contact_id=data.contact_id,
        name=data.name,phone=phone,operation=data.operation,evidence=data.evidence,expires_at=data.expires_at,approved_by_id=p.user.id)
    db.add(record);db.flush()
    core.event(db,p,row,'representation_approved',{'representation_id':str(record.id),'operation':record.operation})
    return record


def revoke(db,p,row,rid,data):
    core.check_version(row,data.version)
    record=get(db,row,rid)
    if revoked(db,row,record):raise HTTPException(409,'این اختیار قبلاً لغو شده است.')
    core.event(db,p,row,'representation_revoked',{'representation_id':str(record.id),'reason':data.reason})
    db.flush()
    return record


def validate(db,row,rid,operation,name,phone,contact_id=None):
    record=get(db,row,rid)
    if record.principal_contact_id!=row.contact_id or record.operation!=operation or record.expires_at<=datetime.now(timezone.utc) or revoked(db,row,record):
        raise HTTPException(409,'اختیار نماینده منقضی، لغوشده یا مربوط به عملیات دیگری است؛ مدرک معتبر تازه لازم است.')
    if record.name!=name or record.phone!=normalize_phone(phone) or (contact_id is not None and record.contact_id!=contact_id):
        raise HTTPException(409,'گیرنده با نمایندهٔ مصوب برابر نیست؛ گیرنده یا مدرک اختیار را بررسی کنید.')
    return record


def public(db,row,record,*,evidence=False):
    return {'id':record.id,'operation':record.operation,'name':record.name,'phone':record.phone,
        'contact_id':record.contact_id,'expires_at':record.expires_at.astimezone(timezone.utc),
        'revoked':bool(revoked(db,row,record)),**({'evidence':record.evidence} if evidence else {})}
