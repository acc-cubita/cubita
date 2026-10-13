"""ضمانت تغییرناپذیر و پذیرش مجدد؛ ثبت ضمانت سند مالی تولید نمی‌کند."""
from fastapi import HTTPException
from app.models.repair import RepairWarranty, RepairWarrantyClaim, RepairWork, RepairPart, RepairDelivery
from app.services import repair as core
from app.models.repair_completion import RepairWarrantyTransfer
from app.services import repair_identity as identity


def latest_transfer(db,p,warranty_id):
    return db.query(RepairWarrantyTransfer).filter_by(tenant_id=p.tenant_id,warranty_id=warranty_id).order_by(RepairWarrantyTransfer.revision.desc()).first()


def transfer_preview(db,p,row,warranty_id):
    from app.models.inventory import Contact
    warranty=db.query(RepairWarranty).filter_by(tenant_id=p.tenant_id,case_id=row.id,id=warranty_id).one_or_none()
    if warranty is None: raise HTTPException(404,'ضمانت این پرونده پیدا نشد.')
    device=identity.canonical(db,p,identity.device(db,p,row.device_id))
    owner=identity.latest(db,p,device.id,'ownership')
    person=db.query(Contact).filter_by(tenant_id=p.tenant_id,id=owner.contact_id).one_or_none() if owner else None
    previous=latest_transfer(db,p,warranty_id)
    return {'device_version':device.version,'ownership_id':owner.id if owner else None,
            'contact_id':person.id if person else None,'recipient_name':person.name if person else '',
            'previous_revision':previous.revision if previous else 0,'warranty':core.out(warranty)}


def transfer(db,p,row,warranty_id,data):
    core.check_version(row,data.version)
    warranty=db.query(RepairWarranty).filter_by(tenant_id=p.tenant_id,case_id=row.id,id=warranty_id).one_or_none()
    if warranty is None:
        raise HTTPException(404,'ضمانت این پرونده پیدا نشد.')
    if not p.has_permission('repair_warranty_transfer','approve'):
        raise HTTPException(403,'انتقال ضمانت به مجوز مستقل مدیر فنی نیاز دارد.')
    device=identity.canonical(db,p,identity.device(db,p,row.device_id))
    device=identity.device(db,p,device.id,lock=True)
    core.check_version(device,data.device_version)
    if identity.canonical(db,p,device).id!=device.id:
        raise HTTPException(409,'هویت دستگاه تغییر کرده؛ شناسنامهٔ اصلی را دوباره بررسی کنید.')
    owner=identity.latest(db,p,device.id,'ownership')
    if owner is None or owner.id!=data.ownership_id:
        raise HTTPException(409,'مالک فعلی تأیید نشده یا تغییر کرده؛ ابتدا تصمیم مالکیت را بررسی کنید.')
    previous=latest_transfer(db,p,warranty.id)
    if data.previous_revision!=(previous.revision if previous else 0):
        raise HTTPException(409,'انتقال ضمانت تغییر کرده؛ آخرین تأیید را دریافت کنید.')
    if previous and previous.ownership_id==owner.id:
        raise HTTPException(409,'این مالکیت قبلاً برای همین ضمانت تأیید شده است.')
    result=RepairWarrantyTransfer(case_id=row.id,warranty_id=warranty.id,revision=data.previous_revision+1,
        ownership_id=owner.id,contact_id=owner.contact_id,reason=data.reason,approved_by_id=p.user.id)
    db.add(result);db.flush()
    core.event(db,p,row,'warranty_transferred',{'transfer_id':str(result.id),'warranty_id':str(warranty.id),'ownership_id':str(owner.id),'reason':data.reason})
    return result


def issue(db, p, row, data):
    core.check_version(row, data.version)
    delivery = db.query(RepairDelivery).filter_by(case_id=row.id).one_or_none()
    if delivery is None or row.status not in {'delivered','closed'}:
        raise HTTPException(409, 'ضمانت فقط پس از تحویل واقعی ثبت می‌شود.')
    if data.valid_from < delivery.delivered_at.date():
        raise HTTPException(422, 'شروع ضمانت نمی‌تواند پیش از تحویل باشد.')
    model = RepairWork if data.scope == 'service' else RepairPart
    source = db.query(model).filter_by(id=data.source_id, case_id=row.id).one_or_none()
    if source is None:
        raise HTTPException(422, 'خدمت یا قطعه باید متعلق به همین پرونده باشد.')
    if data.scope == 'part':
        from app.services.repair_parts import quantities
        if quantities(db,source)[0] <= 0:
            raise HTTPException(422, 'قطعه مصرف‌شده برای ضمانت انتخاب کنید.')
        if source.owner != 'company':
            raise HTTPException(422, 'ضمانت قطعه فقط برای قطعه تأمین‌شده توسط تعمیرگاه ثبت می‌شود.')
    result = RepairWarranty(**data.model_dump(exclude={'version'}), case_id=row.id, created_by_id=p.user.id)
    db.add(result); db.flush()
    core.event(db,p,row,'warranty_issued',{'warranty_id':str(result.id),'scope':result.scope,'title':result.title})
    return result


def revisit(db,p,original,data):
    warranty = db.query(RepairWarranty).filter_by(id=data.warranty_id,case_id=original.id).one_or_none()
    if warranty is None:
        raise HTTPException(404, 'ضمانت این پرونده پیدا نشد.')
    main=identity.canonical(db,p,identity.device(db,p,original.device_id))
    main=identity.device(db,p,main.id,lock=True)
    if identity.canonical(db,p,main).id!=main.id:
        raise HTTPException(409,'هویت دستگاه هم‌زمان ادغام شده؛ مراجعه را با شناسنامهٔ اصلی دوباره بررسی کنید.')
    if data.admission.device is not None or data.admission.device_id not in {original.device_id,main.id}:
        raise HTTPException(422, 'مراجعه ضمانت باید برای همان دستگاه ثبت شود.')
    approved=latest_transfer(db,p,warranty.id)
    if approved or data.admission.contact_id!=original.contact_id:
        owner=identity.latest(db,p,main.id,'ownership')
        if not approved or not owner or approved.ownership_id!=owner.id or approved.contact_id!=data.admission.contact_id:
            raise HTTPException(422,'مراجعهٔ این مالک نیازمند تأیید انتقال همین ضمانت توسط مدیر فنی است.')
    if data.cost_policy != 'customer':
        if data.classification != 'repeat_fault' or data.responsibility == 'customer':
            raise HTTPException(422, 'پوشش ضمانت فقط برای خرابی تکراری با مسئولیت غیرمشتری است.')
        if not warranty.valid_from <= data.admission.admission_date <= warranty.valid_until:
            raise HTTPException(422, 'تاریخ مراجعه خارج از دوره ضمانت است.')
    row = core.create(db,p,data.admission)
    claim = RepairWarrantyClaim(original_case_id=original.id,warranty_id=warranty.id,revisit_case_id=row.id,
        classification=data.classification,responsibility=data.responsibility,cost_policy=data.cost_policy,
        reason=data.reason,recorded_by_id=p.user.id)
    db.add(claim); db.flush()
    # سابقه قبلی بازنویسی نمی‌شود؛ رابطه از پرونده تازه خوانده می‌شود.
    core.event(db,p,row,'warranty_revisit',{'original_case_id':str(original.id),'warranty_id':str(warranty.id),
        'transfer_id':str(approved.id) if approved else None,
        'classification':claim.classification,'responsibility':claim.responsibility,'cost_policy':claim.cost_policy,'reason':claim.reason})
    return row


def assert_customer_charge(db,row,amount):
    if not amount:
        return
    claim = db.query(RepairWarrantyClaim).filter_by(revisit_case_id=row.id).one_or_none()
    if claim and claim.cost_policy != 'customer':
        raise HTTPException(409, 'این مراجعه تحت پوشش ضمانت است؛ هزینه آن به مشتری منتقل نمی‌شود.')


def overview(db,p,row):
    warranties=db.query(RepairWarranty).filter_by(case_id=row.id).order_by(RepairWarranty.created_at.desc()).limit(200).all()
    original=db.query(RepairWarrantyClaim).filter_by(revisit_case_id=row.id).one_or_none()
    visits=db.query(RepairWarrantyClaim).filter_by(original_case_id=row.id).filter(
        RepairWarrantyClaim.revisit_case_id.in_(core.visible(db,p).with_entities(core.RepairCase.id))).limit(200).all()
    # Revisions, not timestamps, decide the current owner. Multiple decisions
    # can share a transaction timestamp (imports/tests and batched operations).
    transfers=db.query(RepairWarrantyTransfer).filter_by(tenant_id=p.tenant_id,case_id=row.id).distinct(RepairWarrantyTransfer.warranty_id).order_by(RepairWarrantyTransfer.warranty_id,RepairWarrantyTransfer.revision.desc()).limit(200).all()
    return {'warranties':[core.out(w) for w in warranties], 'origin':core.out(original) if original else None,
            'revisits':[core.out(v) for v in visits],'transfers':[core.out(t) for t in transfers]}
