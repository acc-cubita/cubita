"""ضمانت تغییرناپذیر و پذیرش مجدد؛ ثبت ضمانت سند مالی تولید نمی‌کند."""
from fastapi import HTTPException
from app.models.repair import RepairWarranty, RepairWarrantyClaim, RepairWork, RepairPart, RepairDelivery
from app.services import repair as core


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
    if data.admission.device_id != original.device_id or data.admission.device is not None:
        raise HTTPException(422, 'مراجعه ضمانت باید برای همان دستگاه ثبت شود.')
    if data.admission.contact_id != original.contact_id:
        raise HTTPException(422, 'تغییر مالک در مراجعه ضمانت نیازمند پذیرش مستقل است.')
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
    return {'warranties':[core.out(w) for w in warranties], 'origin':core.out(original) if original else None,
            'revisits':[core.out(v) for v in visits]}
