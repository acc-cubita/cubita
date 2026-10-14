"""A filed ownership claim grants no ownership or delivery authority."""
from fastapi import HTTPException
from app.models.inventory import Contact
from app.models.repair import RepairDeviceIdentityEvent as Event
from app.schemas.repair_identity import DeviceOwnershipIn
from app.services import repair as core, repair_identity as identity


def main_device(db,p,row):
    main=identity.canonical(db,p,identity.device(db,p,row.device_id))
    main=identity.device(db,p,main.id,lock=True)
    if identity.canonical(db,p,main).id!=main.id:
        raise HTTPException(409,'هویت دستگاه تغییر کرده؛ دوباره بررسی کنید.')
    return main


def submit(db,p,row,data):
    core.check_version(row,data.version)
    main=main_device(db,p,row);core.check_version(main,data.device_version)
    contact=db.query(Contact).filter_by(tenant_id=p.tenant_id,id=data.contact_id,is_active=True,is_system=False).one_or_none()
    if contact is None:
        raise HTTPException(422,'مدعی را از اشخاص فعال همین شرکت انتخاب کنید.')
    main.version+=1
    claim=Event(device_id=main.id,case_id=row.id,revision=main.version,kind='ownership_claim',
        contact_id=contact.id,reason=data.reason,evidence=data.evidence,recorded_by_id=p.user.id)
    db.add(claim);db.flush()
    core.event(db,p,row,'ownership_claim_filed',{'claim_id':str(claim.id)})
    return claim


def resolve(db,p,row,claim_id,data):
    core.check_version(row,data.version)
    claim=db.query(Event).filter_by(tenant_id=p.tenant_id,case_id=row.id,id=claim_id,kind='ownership_claim').one_or_none()
    if claim is None:
        raise HTTPException(404,'ادعای مربوط به این پرونده پیدا نشد.')
    main=main_device(db,p,row);core.check_version(main,data.device_version)
    if main.id!=claim.device_id:
        raise HTTPException(409,'هویت دستگاه ادغام شده؛ ادعا را روی هویت اصلی دوباره ثبت کنید.')
    if db.query(Event).filter_by(tenant_id=p.tenant_id,claim_id=claim.id).first():
        raise HTTPException(409,'این ادعا قبلاً تعیین تکلیف شده است.')
    owner=identity.latest(db,p,main.id,'ownership')
    if (owner.id if owner else None)!=data.previous_ownership_id:
        raise HTTPException(409,'مالک فعلی تغییر کرده؛ مالکیت را دوباره بررسی کنید.')
    if data.decision=='approved':
        result=identity.ownership(db,p,main.id,DeviceOwnershipIn(version=main.version,contact_id=claim.contact_id,
            previous_ownership_id=data.previous_ownership_id,reason=data.reason,evidence=data.evidence),case_id=row.id,claim_id=claim.id)
    else:
        main.version+=1
        result=Event(device_id=main.id,case_id=row.id,claim_id=claim.id,revision=main.version,kind='ownership_rejected',
            contact_id=claim.contact_id,reason=data.reason,evidence=data.evidence,recorded_by_id=p.user.id)
        db.add(result)
    db.flush()
    core.event(db,p,row,'ownership_claim_decided',{'claim_id':str(claim.id),'decision':data.decision})
    return result
