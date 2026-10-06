import hashlib
from datetime import date, datetime, timedelta, timezone
from html import escape
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import HTMLResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import Principal, get_principal, require_module, require_permission
from app.models.repair import RepairAttachment, RepairBranch, RepairCase, RepairDeviceType, RepairFault, RepairEstimateDecision
from app.models.inventory import Item
from app.models.tenant import Membership
from app.models.user import User
from app.pagination import PageParams, paginate
from app.schemas.repair import AdmissionIn, AssignmentIn, BranchAccessIn, BranchIn, DeviceTypeIn, LocationIn, TaskIn, TaskStatusIn, WorkflowIn, DiagnosisIn, EstimateIn, EstimateDecisionIn, FaultIn, FeePolicyIn
from app.services import repair as svc
from app.services.idempotency import idempotent, read_key

router = APIRouter(prefix="/api/repair", tags=["repair"], dependencies=[Depends(require_module("repair")), Depends(require_permission("repair", "view"))])


def keyed(request):
    if not read_key(request):
        raise HTTPException(400, "برای جلوگیری از ثبت تکراری، Idempotency-Key لازم است.")


@router.get("/members", dependencies=[Depends(require_permission("repair", "approve"))])
def members(db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    return [{"id": u.id, "name": u.name} for u in db.query(User).join(Membership, Membership.user_id == User.id).filter(Membership.tenant_id == p.tenant_id, Membership.status == "active", User.active.is_(True)).order_by(User.name).all()]


@router.get("/branches/{branch_id}/access", dependencies=[Depends(require_permission("repair", "approve"))])
def read_access(branch_id: UUID, db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    svc.branch(db, p, branch_id)
    from app.models.repair import RepairBranchAccess
    return {"user_ids": [row[0] for row in db.query(RepairBranchAccess.user_id).filter_by(branch_id=branch_id).all()]}


@router.get("/branches")
def branches(db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    return [svc.out(b) for b in svc.branch_query(db, p).order_by(RepairBranch.name).all()]


@router.post("/branches", status_code=201, dependencies=[Depends(require_permission("repair", "approve"))])
def add_branch(data: BranchIn, db: Session = Depends(get_db)):
    if db.query(RepairBranch).filter_by(name=data.name).first():
        raise HTTPException(409, "این شعبه قبلاً ثبت شده است.")
    row = RepairBranch(name=data.name)
    db.add(row)
    db.flush()
    result = svc.out(row)
    return result


@router.put("/branches/{branch_id}/access", dependencies=[Depends(require_permission("repair", "approve"))])
def access(branch_id: UUID, data: BranchAccessIn, db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    svc.grant(db, p, branch_id, data)
    return {"user_ids": data.user_ids}


@router.get("/device-types")
def types(db: Session = Depends(get_db)):
    return [svc.out(t) for t in db.query(RepairDeviceType).filter_by(is_active=True).order_by(RepairDeviceType.name).all()]


@router.post("/device-types", status_code=201, dependencies=[Depends(require_permission("repair", "approve"))])
def add_type(data: DeviceTypeIn, db: Session = Depends(get_db)):
    if db.query(RepairDeviceType).filter_by(name=data.name).first():
        raise HTTPException(409, "این نوع دستگاه قبلاً ثبت شده است.")
    row = RepairDeviceType(**data.model_dump())
    db.add(row)
    db.flush()
    result = svc.out(row)
    return result


@router.get("/cases")
def cases(q: str = Query("", max_length=200), branch_id: UUID | None = None, date_from: date | None = None, date_to: date | None = None,
          mine: bool = False, overdue: bool = False, inactive_days: int | None = Query(None, ge=1, le=365), status: str | None = None,
          params: PageParams = Depends(), db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    query = svc.visible(db, p)
    if mine:
        query = query.filter(RepairCase.assigned_to_id == p.user.id)
    if status:
        if status not in svc.STATE_LABELS:
            raise HTTPException(422, "وضعیت تعمیر معتبر انتخاب کنید.")
        query = query.filter(RepairCase.status == status)
    if overdue:
        query = query.filter(RepairCase.due_date < date.today(), RepairCase.status.notin_(["closed", "delivered", "cancelled"]))
    if inactive_days:
        query = query.filter(RepairCase.updated_at < datetime.now(timezone.utc) - timedelta(days=inactive_days), RepairCase.status.notin_(["closed", "delivered", "cancelled"]))
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "بازهٔ تاریخ را اصلاح کنید.")
    if q.strip():
        needle = "%" + q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        tests = [RepairCase.owner_snapshot["name"].astext.ilike(needle), RepairCase.owner_snapshot["phone"].astext.ilike(needle)]
        tests += [RepairCase.device_snapshot[k].astext.ilike(needle) for k in ("category", "brand", "model", "serial", "imei")]
        if q.isdecimal() and len(q) < 10:
            tests.append(RepairCase.number == int(q))
        query = query.filter(or_(*tests))
    if branch_id:
        svc.branch(db, p, branch_id)
        query = query.filter_by(branch_id=branch_id)
    if date_from:
        query = query.filter(RepairCase.admission_date >= date_from)
    if date_to:
        query = query.filter(RepairCase.admission_date <= date_to)
    rows, cursor = paginate(query, [RepairCase.number], params)
    return {"items": [svc.out(r) for r in rows], "next_cursor": cursor}


@router.post("/cases", status_code=201, dependencies=[Depends(require_permission("repair", "create"))])
def admit(data: AdmissionIn, request: Request, db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    keyed(request)
    row = idempotent(db, request, p.user, operation="repair.admission", payload=data,
        run=lambda: svc.create(db, p, data), replay=lambda rid: svc.case(db, p, rid))
    result = svc.detail(db, p, row)
    return result


@router.get("/technicians")
def technicians(branch_id: UUID, db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    return svc.technicians(db, p, branch_id)


@router.get("/catalog")
def catalog(params: PageParams = Depends(), db: Session = Depends(get_db)):
    rows, cursor = paginate(db.query(Item).filter(Item.is_active.is_(True)), [Item.id], params)
    return {"items":[{"id":i.id,"name":i.name,"is_service":i.is_service,"unit":i.unit} for i in rows],"next_cursor":cursor}


@router.get("/faults")
def faults(db: Session = Depends(get_db)):
    return [svc.out(f) for f in db.query(RepairFault).filter_by(is_active=True).order_by(RepairFault.name).all()]


@router.post("/faults", status_code=201, dependencies=[Depends(require_permission("repair", "approve"))])
def add_fault(data: FaultIn, db: Session = Depends(get_db)):
    if data.type_id:
        svc.device_type(db,data.type_id)
    if db.query(RepairFault).filter_by(name=data.name).first():
        raise HTTPException(409,"این عیب قبلاً در فهرست ثبت شده است.")
    row = RepairFault(**data.model_dump()); db.add(row); db.flush()
    return svc.out(row)


@router.put("/device-types/{type_id}", dependencies=[Depends(require_permission("repair", "approve"))])
def update_type(type_id: UUID, data: DeviceTypeIn, db: Session = Depends(get_db)):
    row = svc.device_type(db,type_id)
    if db.query(RepairDeviceType).filter(RepairDeviceType.name == data.name, RepairDeviceType.id != type_id).first():
        raise HTTPException(409,"نوع دیگری با این نام وجود دارد.")
    for k,v in data.model_dump().items(): setattr(row,k,v)
    db.flush()
    return svc.out(row)


@router.put("/branches/{branch_id}/fees", dependencies=[Depends(require_permission("repair", "approve"))])
def fees(branch_id: UUID, data: FeePolicyIn, db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    row = svc.branch(db,p,branch_id)
    row.diagnostic_fee, row.cancellation_fee = data.diagnostic_fee, data.cancellation_fee
    row.discount_ceiling = data.discount_ceiling
    db.flush()
    return svc.out(row)


@router.post("/cases/{case_id}/diagnosis", dependencies=[Depends(require_permission("repair", "update"))])
def diagnosis(case_id: UUID, data: DiagnosisIn, db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    return svc.detail(db,p,svc.diagnose(db,p,svc.case(db,p,case_id,lock=True),data))


@router.post("/cases/{case_id}/estimates", status_code=201, dependencies=[Depends(require_permission("repair", "update"))])
def estimate(case_id: UUID, data: EstimateIn, request: Request, db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    keyed(request)
    svc.case(db,p,case_id)
    row = idempotent(db,request,p.user,operation="repair.estimate:"+str(case_id),payload=data,
        run=lambda:svc.new_estimate(db,p,svc.case(db,p,case_id,lock=True),data), replay=lambda rid:svc.estimate(db,p,case_id,rid))
    return svc.out(row)


@router.post("/cases/{case_id}/estimates/{estimate_id}/decision", status_code=201, dependencies=[Depends(require_permission("repair", "approve"))])
def decision(case_id: UUID, estimate_id: UUID, data: EstimateDecisionIn, request: Request, db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    keyed(request)
    svc.estimate(db,p,case_id,estimate_id)
    def replay(rid):
        row = db.query(RepairEstimateDecision).filter_by(id=rid,case_id=case_id,estimate_id=estimate_id).one_or_none()
        if row is None: raise HTTPException(404,"تصمیم مربوط به این برآورد یافت نشد.")
        return row
    row = idempotent(db,request,p.user,operation="repair.decision:"+str(estimate_id),payload=data,
        run=lambda:svc.decide(db,p,svc.case(db,p,case_id,lock=True),svc.estimate(db,p,case_id,estimate_id),data),replay=replay)
    return svc.out(row)


@router.post("/cases/{case_id}/status", dependencies=[Depends(require_permission("repair", "update"))])
def change_status(case_id: UUID, data: WorkflowIn, db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    return svc.detail(db, p, svc.transition(db, p, svc.case(db, p, case_id, lock=True), data))


@router.post("/cases/{case_id}/assignment", dependencies=[Depends(require_permission("repair", "update"))])
def assignment(case_id: UUID, data: AssignmentIn, db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    return svc.detail(db, p, svc.assign(db, p, svc.case(db, p, case_id, lock=True), data))


@router.post("/cases/{case_id}/tasks", status_code=201, dependencies=[Depends(require_permission("repair", "update"))])
def add_task(case_id: UUID, data: TaskIn, request: Request, db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    keyed(request)
    svc.case(db, p, case_id)
    row = idempotent(db, request, p.user, operation="repair.task:" + str(case_id), payload=data,
        run=lambda: svc.add_task(db, p, svc.case(db, p, case_id, lock=True), data),
        replay=lambda rid: svc.task(db, p, case_id, rid))
    return svc.out(row)


@router.post("/cases/{case_id}/tasks/{task_id}/status", dependencies=[Depends(require_permission("repair", "update"))])
def update_task(case_id: UUID, task_id: UUID, data: TaskStatusIn, db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    return svc.detail(db, p, svc.task_status(db, p, svc.case(db, p, case_id, lock=True), svc.task(db, p, case_id, task_id), data))


@router.get("/cases/{case_id}")
def case(case_id: UUID, db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    return svc.detail(db, p, svc.case(db, p, case_id))


@router.put("/cases/{case_id}/location", dependencies=[Depends(require_permission("repair", "update"))])
def location(case_id: UUID, data: LocationIn, db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    row = svc.relocate(db, p, svc.case(db, p, case_id, lock=True), data)
    result = svc.detail(db, p, row)
    return result


@router.post("/cases/{case_id}/attachments", dependencies=[Depends(require_permission("repair", "update"))])
async def attach(case_id: UUID, file: UploadFile, db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    svc.case(db, p, case_id, lock=True)
    content = await file.read(5 * 1024 * 1024 + 1)
    if not content or len(content) > 5 * 1024 * 1024:
        raise HTTPException(422, "پیوست باید غیرخالی و حداکثر پنج مگابایت باشد.")
    signatures = {"image/jpeg": content.startswith(b"\xff\xd8\xff"), "image/png": content.startswith(b"\x89PNG\r\n\x1a\n"), "application/pdf": content.startswith(b"%PDF-")}
    if not signatures.get(file.content_type):
        raise HTTPException(422, "فقط تصویر PNG/JPEG یا PDF معتبر قابل پیوست است.")
    digest = hashlib.sha256(content).hexdigest()
    row = db.query(RepairAttachment).filter_by(case_id=case_id, sha256=digest).first()
    if row is None:
        row = RepairAttachment(case_id=case_id, filename=(file.filename or "پیوست").replace("\\", "/").split("/")[-1][:200], content_type=file.content_type,
                               sha256=digest, size=len(content), content=content, uploaded_by_id=p.user.id)
        db.add(row)
        db.flush()
    result = {"id": row.id, "filename": row.filename, "size": row.size, "content_type": row.content_type}
    return result


@router.get("/cases/{case_id}/attachments")
def attachments(case_id: UUID, db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    svc.case(db, p, case_id)
    return [{"id": a.id, "filename": a.filename, "size": a.size, "content_type": a.content_type,"customer_visible":a.customer_visible} for a in db.query(RepairAttachment).filter_by(case_id=case_id).all()]


@router.get("/cases/{case_id}/attachments/{attachment_id}")
def download(case_id: UUID, attachment_id: UUID, db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    svc.case(db, p, case_id)
    row = db.query(RepairAttachment).filter_by(case_id=case_id, id=attachment_id).one_or_none()
    if row is None:
        raise HTTPException(404, "پیوست پیدا نشد.")
    return Response(row.content, media_type=row.content_type, headers={"Content-Disposition": "attachment", "X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"})


@router.get("/cases/{case_id}/receipt", response_class=HTMLResponse)
def receipt(case_id: UUID, db: Session = Depends(get_db), p: Principal = Depends(get_principal)):
    row = svc.case(db, p, case_id)
    from app.services.printing import format_jalali
    fields = {"شماره پذیرش": str(row.number), "مالک": row.owner_snapshot["name"], "تماس": row.owner_snapshot["phone"],
              "تحویل‌دهنده": row.delivering_name, "دستگاه": " / ".join(str(row.device_snapshot[k]) for k in ("category", "brand", "model")),
              "سریال": row.device_snapshot["serial"], "IMEI": row.device_snapshot["imei"], "ایراد اعلام‌شده": row.reported_issue,
              "وضعیت ظاهری": row.appearance, "لوازم همراه": row.accessories, "شرایط پذیرش": row.terms,
              "تاریخ پذیرش": format_jalali(row.admission_date), "موعد اولیه": format_jalali(row.due_date)}
    body = "".join(f"<dt>{escape(k)}</dt><dd>{escape(v)}</dd>" for k, v in fields.items())
    # Code39 فقط شمارهٔ داخلی است؛ شناسهٔ چاپ‌شده مجوز دسترسی به پرونده نیست.
    patterns = {"*": "nwnnwnwnn", "0": "nnnwwnwnn", "1": "wnnwnnnnw", "2": "nnwwnnnnw", "3": "wnwwnnnnn", "4": "nnnwwnnnw", "5": "wnnwwnnnn", "6": "nnwwwnnnn", "7": "nnnwnnwnw", "8": "wnnwnnwnn", "9": "nnwwnnwnn"}
    x, bars = 10, []
    for char in "*" + str(row.number) + "*":
        for i, width in enumerate(patterns[char]):
            w = 3 if width == "w" else 1
            if i % 2 == 0:
                bars.append(f'<rect x="{x}" y="0" width="{w}" height="48"/>')
            x += w
        x += 1
    barcode = f'<svg role="img" aria-label="برچسب پذیرش" viewBox="0 0 {x+10} 60" width="240" height="70">{"".join(bars)}</svg>'
    return HTMLResponse(f'<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><title>رسید پذیرش {row.number}</title><style>body{{font-family:Tahoma;margin:30px}}dt{{font-weight:bold;margin-top:12px}}dd{{white-space:pre-wrap}}svg{{display:block}}</style><h1>تعمیرگاه — رسید پذیرش</h1>{barcode}<p>شماره پذیرش: {row.number}</p><dl>{body}</dl><p>دستگاه، امانت مشتری است. این رسید فاکتور یا رسید دریافت وجه نیست.</p></html>', headers={"Cache-Control": "no-store"})
