"""پذیرش امانت بدون ثبت انبار یا حسابداری؛ دسترسی پرونده همیشه از شعبه می‌گذرد."""
from uuid import UUID
from datetime import datetime, timezone
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import func
from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.deps import Principal
from app.models.inventory import Contact, Item
from app.models.tenant import Membership
from app.models.repair import RepairBranch, RepairBranchAccess, RepairCase, RepairDevice, RepairDeviceType, RepairEvent, RepairTask, RepairFault, RepairEstimate, RepairEstimateDecision

STATE_LABELS = {"accepted":"پذیرش‌شده", "diagnosing":"عیب‌یابی", "awaiting_customer":"منتظر مشتری", "repairing":"در حال تعمیر", "awaiting_part":"منتظر قطعه", "testing":"در حال آزمون", "ready":"آماده تحویل", "unrepairable":"غیرقابل تعمیر", "cancelled":"لغوشده", "delivered":"تحویل‌شده", "closed":"بسته"}
TRANSITIONS = {
    "accepted": {"diagnosing", "cancelled"},
    "diagnosing": {"awaiting_customer", "repairing", "awaiting_part", "unrepairable", "cancelled"},
    "awaiting_customer": {"diagnosing", "repairing", "cancelled"},
    "repairing": {"awaiting_part", "awaiting_customer", "testing", "unrepairable", "cancelled"},
    "awaiting_part": {"repairing", "diagnosing", "cancelled"},
    "testing": {"repairing", "ready", "unrepairable"},
    "ready": {"repairing"}, "unrepairable": {"diagnosing"}, "cancelled": set(), "delivered": set(), "closed": set(),
}
from app.services.numbering import next_document_number


def branch_query(db: Session, p: Principal):
    q = db.query(RepairBranch)
    if not p.has_permission("repair", "approve"):
        q = q.filter(RepairBranch.id.in_(db.query(RepairBranchAccess.branch_id).filter(RepairBranchAccess.user_id == p.user.id)))
    return q


def branch(db: Session, p: Principal, branch_id: UUID):
    row = branch_query(db, p).filter(RepairBranch.id == branch_id).one_or_none()
    if row is None:
        raise HTTPException(404, "شعبه در دسترس نیست؛ دسترسی شعبه را از مدیر بخواهید.")
    return row


def visible(db: Session, p: Principal):
    return db.query(RepairCase).filter(RepairCase.branch_id.in_(branch_query(db, p).with_entities(RepairBranch.id)))


def case(db: Session, p: Principal, case_id: UUID, *, lock=False):
    q = visible(db, p).filter(RepairCase.id == case_id)
    if lock:
        q = q.with_for_update().populate_existing()
    row = q.one_or_none()
    if row is None:
        raise HTTPException(404, "پذیرش در دسترس نیست؛ شماره یا دسترسی شعبه را بررسی کنید.")
    return row


def grant(db, p, branch_id, data):
    branch(db, p, branch_id)
    db.query(RepairBranch.id).filter_by(id=branch_id).with_for_update(of=RepairBranch).one()
    ids = set(data.user_ids)
    members = {
        row[0] for row in db.query(Membership.user_id).filter(Membership.tenant_id == p.tenant_id, Membership.status == "active", Membership.user_id.in_(ids)).all()
    }
    if ids != members:
        raise HTTPException(422, "دسترسی شعبه فقط به اعضای فعال همین کسب‌وکار داده می‌شود.")
    db.query(RepairBranchAccess).filter_by(branch_id=branch_id).delete(synchronize_session=False)
    db.add_all([RepairBranchAccess(branch_id=branch_id, user_id=u) for u in ids])
    db.flush()


def device_type(db, type_id):
    row = db.get(RepairDeviceType, type_id)
    if row is None or not row.is_active:
        raise HTTPException(422, "نوع دستگاه معتبر و فعال را انتخاب کنید.")
    return row


def create(db: Session, p: Principal, data):
    b = branch(db, p, data.branch_id)
    if not b.is_active:
        raise HTTPException(422, "شعبه بسته است؛ شعبهٔ فعال انتخاب کنید.")
    contact = db.get(Contact, data.contact_id)
    if contact is None or not contact.is_active or contact.is_system:
        raise HTTPException(422, "مشتری فعال از فهرست اشخاص انتخاب کنید.")
    if data.device_id:
        d = db.get(RepairDevice, data.device_id)
        if d is None or not visible(db, p).filter(RepairCase.device_id == d.id).first():
            raise HTTPException(404, "شناسنامه دستگاه در دسترس نیست.")
        t = device_type(db, d.type_id)
    else:
        t = device_type(db, data.device.type_id)
        if set(data.device.attributes) - set(t.fields) or any(len(v) > 2000 for v in data.device.attributes.values()):
            raise HTTPException(422, "فیلدهای دستگاه با تنظیمات نوع دستگاه سازگار نیست.")
        d = RepairDevice(**data.device.model_dump())
        db.add(d)
        db.flush()
    if set(data.intake_checklist) - set(t.checklist):
        raise HTTPException(422, "چک‌لیست پذیرش با نوع دستگاه سازگار نیست.")
    values = data.model_dump(exclude={"device_id", "device"})
    row = RepairCase(**values, device_id=d.id, number=next_document_number(db, "repair_admission"),
        owner_snapshot={"name": contact.name, "phone": contact.phone or ""},
        device_snapshot={"type_id": str(d.type_id), "category": t.name, "brand": d.brand, "model": d.model, "serial": d.serial, "imei": d.imei, "attributes": d.attributes},
        created_by_id=p.user.id)
    db.add(row)
    db.flush()
    from app.services.repair_completion import register_admission
    register_admission(db,p,row)
    db.add(RepairEvent(case_id=row.id, actor_id=p.user.id, action="admitted", detail={"location": row.storage_location}))
    db.flush()
    from app.services.repair_notifications import from_event
    from_event(db,row,'admitted')
    return row


def open_cases(db, p, row):
    d = db.get(RepairDevice, row.device_id)
    identity = [RepairCase.device_id == d.id]
    if d.serial or d.imei:
        matching = db.query(RepairDevice.id).filter(or_(*([RepairDevice.serial == d.serial] if d.serial else []), *([RepairDevice.imei == d.imei] if d.imei else [])))
        identity.append(RepairCase.device_id.in_(matching))
    return visible(db, p).filter(or_(*identity), RepairCase.id != row.id, RepairCase.status.notin_(["closed", "delivered", "cancelled"])).all()


def out(row):
    return {c.name: str(getattr(row,c.name)) if isinstance(getattr(row,c.name),Decimal) else getattr(row, c.name) for c in row.__table__.columns if c.name not in {"tenant_id"}}


def detail(db, p, row):
    from app.services.repair_access import expire
    secret = expire(db,p,row)
    data = out(row)
    from app.services.repair_completion import metadata
    meta=metadata(db,row)
    data['intake_details']=out(meta) if meta else None
    data["has_device_secret"] = secret is not None
    data["open_case_warnings"] = [{"id": c.id, "number": c.number} for c in open_cases(db, p, row)]
    data["visits"] = [{"id": c.id, "number": c.number, "admission_date": c.admission_date, "status": c.status} for c in visible(db, p).filter(RepairCase.device_id == row.device_id).order_by(RepairCase.number.desc()).all()]
    data["events"] = [out(e) for e in db.query(RepairEvent).filter_by(case_id=row.id).order_by(RepairEvent.created_at).all()]
    data["tasks"] = [out(t) for t in db.query(RepairTask).filter_by(case_id=row.id).order_by(RepairTask.created_at).all()]
    data["estimates"] = [out(e) for e in db.query(RepairEstimate).filter_by(case_id=row.id).order_by(RepairEstimate.version.desc()).all()]
    data["estimate_decisions"] = [out(d) for d in db.query(RepairEstimateDecision).filter_by(case_id=row.id).order_by(RepairEstimateDecision.created_at.desc()).all()]
    from app.services.repair_parts import projection
    from app.models.repair import RepairPart, RepairWork, RepairOutsource, RepairQualityCheck, RepairRemovedPart
    data["parts"] = [projection(db,part) for part in db.query(RepairPart).filter_by(case_id=row.id).order_by(RepairPart.created_at).all()]
    data["work"] = [out(w) for w in db.query(RepairWork).filter_by(case_id=row.id).order_by(RepairWork.created_at).all()]
    data["outsources"] = [out(o) for o in db.query(RepairOutsource).filter_by(case_id=row.id).order_by(RepairOutsource.created_at).all()]
    data["quality_checks"] = [out(q) for q in db.query(RepairQualityCheck).filter_by(case_id=row.id).order_by(RepairQualityCheck.created_at.desc()).all()]
    data["removed_parts"] = [out(r) for r in db.query(RepairRemovedPart).filter_by(case_id=row.id).order_by(RepairRemovedPart.created_at).all()]
    data["allowed_statuses"] = [{"key": s, "label": STATE_LABELS[s]} for s in sorted(TRANSITIONS[row.status]) if s not in {"delivered", "closed"}]
    return data


def relocate(db, p, row, data):
    check_version(row, data.version)
    from app.services.repair_custody import assert_present
    assert_present(db, row)
    old = row.storage_location
    row.storage_location = data.storage_location
    row.version += 1
    db.add(RepairEvent(case_id=row.id, actor_id=p.user.id, action="relocated", detail={"from": old, "to": row.storage_location}))
    db.flush()
    return row


def check_version(row, expected):
    if row.version != expected:
        raise HTTPException(409, "پرونده توسط کاربر دیگری تغییر کرده؛ آن را تازه کنید و دوباره تصمیم بگیرید.")


def event(db, p, row, action, detail):
    row.version += 1
    db.add(RepairEvent(case_id=row.id, actor_id=p.user.id, action=action, detail=detail))
    db.flush()
    from app.services.repair_notifications import from_event
    from_event(db,row,action)


def transition(db, p, row, data):
    from app.services.repair_custody import assert_present
    assert_present(db,row)
    check_version(row, data.version)
    if data.status in {"delivered", "closed"}:
        raise HTTPException(409, "این وضعیت به کنترل کیفیت یا تحویل واقعی نیاز دارد؛ عملیات مربوط هنوز فعال نشده است.")
    if data.status == "ready":
        from app.services.repair_parts import ready
        ready(db,row)
    if row.status in {"delivered", "closed", "cancelled"}:
        raise HTTPException(409, "پروندهٔ پایان‌یافته با تغییر وضعیت بازنویسی نمی‌شود.")
    if data.exceptional:
        if not p.has_permission("repair", "approve") or not data.reason:
            raise HTTPException(403, "گذار استثنایی به مجوز مدیریت تعمیرگاه و دلیل نیاز دارد.")
    elif data.status not in TRANSITIONS[row.status]:
        raise HTTPException(409, "این تغییر وضعیت مجاز نیست؛ وضعیت فعلی را بررسی کنید.")
    if data.status in {"awaiting_customer", "awaiting_part", "unrepairable", "cancelled"} and not data.reason:
        raise HTTPException(422, "دلیل توقف، لغو یا غیرقابل‌تعمیر بودن را ثبت کنید.")
    if data.status == "repairing":
        approved_estimate(db, row)
    if data.status == "cancelled":
        from app.services.repair_finance import active_invoice
        if active_invoice(db,row): raise HTTPException(409,'پرونده فاکتور فعال دارد؛ پیش از لغو سند مالی را اصلاح کنید.')
        from app.models.repair import RepairPart, RepairOutsource
        from app.services.repair_parts import quantities
        for part in db.query(RepairPart).filter_by(case_id=row.id).all():
            if part.status == "reserved" or (part.owner == "company" and (quantities(db,part)[0] > 0 or quantities(db,part)[1] > 0)):
                raise HTTPException(409,"پیش از لغو، رزروها و قطعات مصرف‌شده یا تحویل‌شده را با اسناد اصلاحی تعیین تکلیف کنید.")
        if db.query(RepairOutsource).filter_by(case_id=row.id,returned_at=None).first():
            raise HTTPException(409,"پیش از لغو، بازگشت برون‌سپاری را ثبت کنید.")
        from app.models.repair import RepairDeviceSecret
        db.query(RepairDeviceSecret).filter_by(case_id=row.id).delete(synchronize_session=False)
    before = row.status
    row.status = data.status
    row.pause_reason = data.reason if data.status in {"awaiting_customer", "awaiting_part"} else ""
    if row.status=='cancelled':
        from app.services.repair_contracts import release_unused
        release_unused(db,p,row,data.reason)
    event(db, p, row, "status_changed", {"from": before, "to": row.status, "reason": data.reason, "exceptional": data.exceptional})
    return row


def technicians(db, p, branch_id):
    branch(db, p, branch_id)
    result = []
    for m in db.query(Membership).filter(Membership.tenant_id == p.tenant_id, Membership.status == "active").all():
        if m.expires_at is not None and m.expires_at <= datetime.now(timezone.utc): continue
        candidate = Principal(m.user, m)
        if candidate.user.active and candidate.has_permission("repair", "view") and branch_query(db, candidate).filter_by(id=branch_id).first():
            result.append({"id": m.user_id, "name": m.user.name})
    return result


def assign(db, p, row, data):
    check_version(row, data.version)
    if row.status in {"cancelled", "delivered", "closed"}:
        raise HTTPException(409, "پروندهٔ پایان‌یافته قابل ارجاع نیست.")
    if data.user_id and data.user_id not in {t["id"] for t in technicians(db, p, row.branch_id)}:
        raise HTTPException(422, "تکنسین باید عضو فعال با دسترسی تعمیرگاه و همین شعبه باشد.")
    from app.services.repair_completion import check_capacity
    check_capacity(db,p,row,data)
    before = row.assigned_to_id
    row.assigned_to_id = data.user_id
    event(db, p, row, "assigned", {"from": str(before) if before else None, "to": str(data.user_id) if data.user_id else None, "reason": data.reason})
    return row


def add_task(db, p, row, data):
    check_version(row, data.version)
    if row.status in {"cancelled", "delivered", "closed"}:
        raise HTTPException(409, "پروندهٔ پایان‌یافته کار تازه نمی‌پذیرد.")
    task = RepairTask(case_id=row.id, created_by_id=p.user.id, **data.model_dump(exclude={"version"}))
    db.add(task); db.flush()
    event(db, p, row, "task_added", {"task_id": str(task.id), "title": task.title})
    return task


def task(db, p, case_id, task_id):
    case(db, p, case_id)
    row = db.query(RepairTask).filter_by(case_id=case_id, id=task_id).one_or_none()
    if row is None:
        raise HTTPException(404, "کار مربوط به این پرونده یافت نشد.")
    return row


def task_status(db, p, row, task_row, data):
    check_version(row, data.version)
    if row.status in {"cancelled", "delivered", "closed"}:
        raise HTTPException(409, "کار پروندهٔ پایان‌یافته قابل تغییر نیست.")
    if (task_row.status, data.status) not in {("pending", "working"), ("working", "done")}:
        raise HTTPException(409, "ابتدا کار را شروع کنید؛ کار پایان‌یافته دوباره تغییر نمی‌کند.")
    task_row.status = data.status
    now = datetime.now(timezone.utc)
    if data.status == "working": task_row.started_at = now
    else: task_row.completed_at = now
    event(db, p, row, "task_" + data.status, {"task_id": str(task_row.id)})
    return row


def editable_case(row):
    if row.status in {"cancelled", "delivered", "closed"}:
        raise HTTPException(409, "پروندهٔ پایان‌یافته قابل بازنویسی نیست؛ مراجعهٔ تازه ایجاد کنید.")


def diagnose(db, p, row, data):
    check_version(row, data.version)
    editable_case(row)
    device = db.get(RepairDevice, row.device_id)
    category = device_type(db, device.type_id)
    if set(data.checklist) - set(category.diagnostic_checklist):
        raise HTTPException(422, "چک‌لیست عیب‌یابی با نوع دستگاه سازگار نیست.")
    faults = db.query(RepairFault).filter(RepairFault.id.in_(data.fault_ids), RepairFault.is_active.is_(True), or_(RepairFault.type_id.is_(None), RepairFault.type_id == category.id)).all()
    if len(faults) != len(set(data.fault_ids)):
        raise HTTPException(422, "عیب‌های معتبر همین نوع دستگاه را انتخاب کنید.")
    old = {"initial": row.initial_diagnosis, "final": row.final_diagnosis, "fault_ids": row.fault_ids, "checklist": row.diagnosis_checklist}
    row.initial_diagnosis, row.final_diagnosis = data.initial_diagnosis, data.final_diagnosis
    row.fault_ids = [str(i) for i in data.fault_ids]
    row.diagnosis_checklist = data.checklist
    row.work_version += 1
    if row.status == 'ready': row.status = 'repairing'
    event(db,p,row,"diagnosed", {"before":old,"after":{"initial":row.initial_diagnosis,"final":row.final_diagnosis,"fault_ids":row.fault_ids,"checklist":row.diagnosis_checklist}})
    return row


def new_estimate(db,p,row,data):
    check_version(row,data.version)
    editable_case(row)
    if data.valid_until < date.today():
        raise HTTPException(422, "مهلت اعتبار برآورد نباید گذشته باشد.")
    if not row.initial_diagnosis and not row.final_diagnosis:
        raise HTTPException(409, "پیش از برآورد، نتیجهٔ عیب‌یابی را ثبت کنید.")
    options = []
    for option in data.options:
        lines, total = [], Decimal(0)
        for line in option.lines:
            values = line.model_dump(mode="json")
            if line.item_id:
                item = db.get(Item,line.item_id)
                if item is None or not item.is_active or (line.kind == "part" and item.is_service) or (line.kind == "labor" and not item.is_service):
                    raise HTTPException(422, "کالا یا خدمت برآورد باید معتبر و با نوع ردیف سازگار باشد.")
                values["item_name"] = item.name
            amount = (line.qty * line.unit_price).quantize(Decimal(1),rounding=ROUND_HALF_UP)
            values["amount"] = str(amount)
            total += amount
            lines.append(values)
        if total > Decimal("99999999999999999"):
            raise HTTPException(422, "جمع مبلغ برآورد بیش از سقف مجاز است.")
        options.append({"title":option.title,"lines":lines,"total":str(total)})
    version = (db.query(func.max(RepairEstimate.version)).filter_by(case_id=row.id).scalar() or 0) + 1
    estimate = RepairEstimate(case_id=row.id,version=version,options=options,valid_until=data.valid_until,duration_days=data.duration_days,
        customer_ceiling=data.customer_ceiling,diagnosis_snapshot=row.final_diagnosis or row.initial_diagnosis,created_by_id=p.user.id)
    db.add(estimate); db.flush()
    event(db,p,row,"estimate_created",{"estimate_id":str(estimate.id),"estimate_version":version})
    return estimate


def estimate(db,p,case_id,estimate_id):
    case(db,p,case_id)
    row = db.query(RepairEstimate).filter_by(case_id=case_id,id=estimate_id).one_or_none()
    if row is None:
        raise HTTPException(404,"برآورد مربوط به این پرونده پیدا نشد.")
    return row


def decide(db,p,row,est,data):
    check_version(row,data.version)
    editable_case(row)
    latest = db.query(func.max(RepairEstimate.version)).filter_by(case_id=row.id).scalar()
    if est.version != latest:
        raise HTTPException(409,"برآورد تازه‌تری وجود دارد؛ تأیید باید برای آخرین نسخه ثبت شود.")
    if db.query(RepairEstimateDecision).filter_by(estimate_id=est.id).first():
        raise HTTPException(409,"تصمیم این نسخه قبلاً ثبت شده؛ برای تصمیم تازه نسخهٔ جدید برآورد بسازید.")
    ceiling = None
    if data.decision == "approved":
        if est.valid_until < date.today():
            raise HTTPException(409,"اعتبار برآورد تمام شده؛ نسخهٔ تازه صادر کنید.")
        if data.option_index is None or data.option_index >= len(est.options):
            raise HTTPException(422,"گزینهٔ مشخص برآورد را انتخاب کنید.")
        amount = Decimal(est.options[data.option_index]["total"])
        ceiling = data.authorized_ceiling if data.authorized_ceiling is not None else amount
        if ceiling < amount or (est.customer_ceiling is not None and ceiling > est.customer_ceiling):
            raise HTTPException(422,"سقف تأیید باید مبلغ گزینه را پوشش دهد و از سقف اعلامی مشتری بیشتر نباشد؛ برآورد تازه صادر کنید.")
    elif not data.reason:
        raise HTTPException(422,"دلیل رد برآورد را ثبت کنید.")
    values = data.model_dump(exclude={"version","authorized_ceiling"})
    if data.decision == "rejected": values["option_index"] = None
    decision = RepairEstimateDecision(case_id=row.id,estimate_id=est.id,authorized_ceiling=ceiling,recorded_by_id=p.user.id,**values)
    db.add(decision); db.flush()
    event(db,p,row,"estimate_"+data.decision,{"estimate_id":str(est.id),"version":est.version,"option":data.option_index,"method":data.method,"customer_name":data.customer_name})
    return decision


def approved_estimate(db,row):
    est = db.query(RepairEstimate).filter_by(case_id=row.id).order_by(RepairEstimate.version.desc()).first()
    decision = db.query(RepairEstimateDecision).filter_by(estimate_id=est.id).first() if est else None
    if decision is None or decision.decision != "approved":
        raise HTTPException(409,"آخرین نسخهٔ برآورد هنوز تأیید مشتری ندارد؛ پیش از تعمیر تأیید آن را ثبت کنید.")
    return est,decision
