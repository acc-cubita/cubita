"""Company-shared, nonpersonal identity; case history remains branch scoped."""
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import or_
from app.models.inventory import Contact
from app.models.repair import RepairDevice, RepairDeviceIdentityEvent, RepairCase
from app.services import repair as core


def device(db, p, device_id, *, lock=False):
    query = db.query(RepairDevice).filter_by(id=device_id, tenant_id=p.tenant_id)
    if lock:
        query = query.with_for_update().populate_existing()
    row = query.one_or_none()
    if row is None:
        raise HTTPException(404, "دستگاه در این شرکت پیدا نشد؛ شناسه را بررسی کنید.")
    return row


def latest(db, p, device_id, kind):
    return db.query(RepairDeviceIdentityEvent).filter_by(
        tenant_id=p.tenant_id, device_id=device_id, kind=kind
    ).order_by(RepairDeviceIdentityEvent.revision.desc()).first()


def canonical(db, p, row):
    seen = set()
    while True:
        if row.id in seen:
            raise HTTPException(409, "زنجیرهٔ هویت دستگاه نیازمند بررسی مدیر است.")
        seen.add(row.id)
        link = latest(db, p, row.id, "merge")
        if link is None:
            return row
        row = device(db, p, link.target_device_id)


def public_identity(db, p, row):
    # Do not serialize attributes: legacy free-text fields may contain personal data.
    main = canonical(db, p, row)
    return {"id": row.id, "identifier": "RD-" + str(row.id), "version": row.version,
            "type_id": row.type_id, "brand": row.brand, "model": row.model,
            "serial": row.serial, "imei": row.imei, "canonical_id": main.id,
            "hardware_revision":row.hardware_revision, "industry_identifiers":row.industry_identifiers,
            "qr_payload": "cubita:repair-device:" + str(row.id)}


def search(db, p, q, limit):
    normalized = q.strip().translate(str.maketrans('يك۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', 'یک01234567890123456789'))
    if not normalized:
        return []
    needle = '%' + normalized.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
    conditions = [column.ilike(needle, escape='\\') for column in (RepairDevice.serial, RepairDevice.imei, RepairDevice.model)]
    for key in ('manufacturer_part_number','chassis_number','board_number','engine_number','asset_tag','mac_address'):
        conditions.append(RepairDevice.industry_identifiers[key].astext.ilike(needle,escape='\\'))
    raw = normalized.removeprefix('cubita:repair-device:').removeprefix('RD-')
    try:
        conditions.append(RepairDevice.id == UUID(raw))
    except ValueError:
        pass
    rows = db.query(RepairDevice).filter(RepairDevice.tenant_id == p.tenant_id, or_(*conditions)).order_by(RepairDevice.id).limit(limit).all()
    return [public_identity(db, p, row) for row in rows]


def history(db, p, row):
    # Include aliases, but never use identity access as authority to read a case.
    main = canonical(db, p, row)
    ids = {main.id}
    links = db.query(RepairDeviceIdentityEvent).filter_by(tenant_id=p.tenant_id, kind='merge').all()
    changed = True
    while changed:
        before = len(ids)
        ids.update(link.device_id for link in links if link.target_device_id in ids)
        changed = len(ids) != before
    return core.visible(db, p).filter(RepairCase.device_id.in_(ids)).order_by(RepairCase.number.desc())


def merge_preview(db, p, source_id, data, *, lock=False):
    if source_id == data.target_device_id:
        raise HTTPException(422, "مبدأ و مقصد باید دو دستگاه متفاوت باشند.")
    # Stable lock order prevents A→B / B→A deadlock; a target merge also increments its version.
    rows = {key: device(db, p, key, lock=lock) for key in sorted([source_id, data.target_device_id], key=str)}
    source, target = rows[source_id], rows[data.target_device_id]
    core.check_version(source, data.version)
    core.check_version(target, data.target_version)
    if canonical(db, p, source).id != source.id or canonical(db, p, target).id != target.id:
        raise HTTPException(409, "یکی از هویت‌ها قبلاً ادغام شده؛ شناسنامهٔ اصلی را باز کنید.")
    if source.type_id != target.type_id:
        raise HTTPException(422, "نوع دستگاه‌ها متفاوت است؛ هویت‌ها را جدا نگه دارید.")
    return source, target


def merge_owners(db,p,source,target):
    result={}
    for key,row in (('source',source),('target',target)):
        owner=latest(db,p,row.id,'ownership')
        contact=db.query(Contact).filter_by(tenant_id=p.tenant_id,id=owner.contact_id).one_or_none() if owner else None
        result[key]={'id':owner.id,'contact_id':owner.contact_id,'name':contact.name if contact else 'شخص بایگانی‌شده'} if owner else None
    return result


def merge(db, p, source_id, data):
    source, target = merge_preview(db, p, source_id, data, lock=True)
    owners=merge_owners(db,p,source,target)
    if any(owners.values()):
        expected=(data.source_ownership_id,data.target_ownership_id)
        actual=tuple(owners[key]['id'] if owners[key] else None for key in ('source','target'))
        if expected!=actual or data.resolved_owner_contact_id not in {owner['contact_id'] for owner in owners.values() if owner}:
            raise HTTPException(409,'مالکیت‌ها را در پیش‌نمایش بررسی و مالک نهایی را صریح انتخاب کنید؛ هیچ مالکیتی خودکار منتقل نمی‌شود.')
        person=db.query(Contact).filter_by(tenant_id=p.tenant_id,id=data.resolved_owner_contact_id,is_active=True,is_system=False).one_or_none()
        if person is None:
            raise HTTPException(422,'مالک نهایی باید شخص فعال باشد؛ ابتدا وضعیت شخص را بررسی کنید.')
    elif data.resolved_owner_contact_id or data.source_ownership_id or data.target_ownership_id:
        raise HTTPException(409,'برای هویت فاقد مالک تأییدشده، ابتدا تصمیم مستقل مالکیت ثبت کنید.')
    source.version += 1
    target.version += 1
    event = RepairDeviceIdentityEvent(device_id=source.id, revision=source.version, kind='merge',
        target_device_id=target.id, reason=data.reason, evidence=data.evidence, recorded_by_id=p.user.id)
    db.add(event)
    if any(owners.values()):
        # A new decision on the target preserves both former histories and never
        # rewrites the owner_snapshot or financial contact of an existing case.
        db.add(RepairDeviceIdentityEvent(device_id=target.id,revision=target.version,kind='ownership',
            contact_id=data.resolved_owner_contact_id,reason=data.reason,evidence=data.evidence,recorded_by_id=p.user.id))
    db.flush()
    return event


def ownership(db, p, device_id, data, *, case_id=None, claim_id=None):
    row = device(db, p, device_id, lock=True)
    core.check_version(row, data.version)
    if canonical(db, p, row).id != row.id:
        raise HTTPException(409, "مالکیت را روی شناسنامهٔ اصلی ثبت کنید.")
    contact = db.query(Contact).filter_by(id=data.contact_id, tenant_id=p.tenant_id, is_active=True, is_system=False).one_or_none()
    if contact is None:
        raise HTTPException(422, "مالک را از اشخاص فعال همین شرکت انتخاب کنید.")
    previous = latest(db, p, row.id, 'ownership')
    if (previous.id if previous else None) != data.previous_ownership_id:
        raise HTTPException(409, "مالکیت تغییر کرده؛ سابقه را دوباره بخوانید و تصمیم تازه ثبت کنید.")
    row.version += 1
    event = RepairDeviceIdentityEvent(device_id=row.id, revision=row.version, kind='ownership', case_id=case_id, claim_id=claim_id,
        contact_id=contact.id, reason=data.reason, evidence=data.evidence, recorded_by_id=p.user.id)
    db.add(event)
    db.flush()
    return event


def profile(db,p,device_id,data):
    row=device(db,p,device_id,lock=True)
    core.check_version(row,data.version)
    if canonical(db,p,row).id!=row.id:
        raise HTTPException(409,'مشخصات را روی شناسنامهٔ اصلی ثبت کنید.')
    before={'hardware_revision':row.hardware_revision,'industry_identifiers':dict(row.industry_identifiers)}
    row.hardware_revision=data.hardware_revision
    row.industry_identifiers=dict(data.industry_identifiers)
    row.version+=1
    event=RepairDeviceIdentityEvent(device_id=row.id,revision=row.version,kind='profile',reason=data.reason,
        evidence='',profile_snapshot={'before':before,'after':data.model_dump(exclude={'version','reason'})},recorded_by_id=p.user.id)
    db.add(event);db.flush()
    return event
