"""مجوزهای «کوبیتا سازمانی» — کارتابلِ ستاد (`admin.cubita.ir`).

ساخت (با کدِ فعال‌سازیِ یک‌باره‌نما)، ویرایشِ سقف و انقضا، صدورِ آفلاین از روی کدِ
درخواستِ مشتری، انتقال به دستگاهِ دیگر، ابطال، و کدِ تازه. هر کنشِ تغییردهنده
`staff_audit.record` دارد (`tests/test_staff_audit_coverage.py`).

خطای صدور (`LicenseError`) با `JSONResponse` برمی‌گردد نه استثنا، تا تراکنش commit
شود و رویدادِ «رد» در تاریخچه‌ی مجوز بماند — همان چیزی که پشتیبانی بعداً می‌پرسد.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import StaffPrincipal, require_staff
from app.licensing.token import LicenseError
from app.models.enterprise_license_registry import EnterpriseLicenseEvent, EnterpriseLicenseRecord
from app.rate_limit import limit_admin_write
from app.schemas.enterprise_admin import (
    ActivationCodeOut,
    LicenseCreatedOut,
    LicenseCreateIn,
    LicenseDetailOut,
    LicenseEventOut,
    LicenseIssueIn,
    LicenseRecordOut,
    LicenseTokenOut,
    LicenseUpdateIn,
)
from app.services import enterprise_licenses as svc
from app.services import staff_audit

router = APIRouter(prefix="/api/admin/licenses", tags=["admin-licenses"])


def _get(db: Session, license_id: UUID) -> EnterpriseLicenseRecord:
    record = db.get(EnterpriseLicenseRecord, license_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "مجوز پیدا نشد")
    return record


def _detail(db: Session, record: EnterpriseLicenseRecord) -> LicenseDetailOut:
    events = (
        db.query(EnterpriseLicenseEvent)
        .filter(EnterpriseLicenseEvent.license_id == record.id)
        .order_by(EnterpriseLicenseEvent.created_at.desc())
        .limit(100)
        .all()
    )
    base = LicenseRecordOut.of(record).model_dump()
    return LicenseDetailOut(
        **base,
        events=[LicenseEventOut(kind=e.kind, actor=e.actor, detail=e.detail, created_at=e.created_at) for e in events],
    )


@router.get("", response_model=list[LicenseRecordOut])
def list_licenses(
    q: str | None = Query(default=None, max_length=100),
    db: Session = Depends(get_db),
    _: StaffPrincipal = Depends(require_staff("licenses", "view")),
):
    query = db.query(EnterpriseLicenseRecord)
    if q and q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                EnterpriseLicenseRecord.org_name.ilike(like),
                EnterpriseLicenseRecord.lic_id.ilike(like),
                EnterpriseLicenseRecord.contact.ilike(like),
                EnterpriseLicenseRecord.code_hint.ilike(like),
            )
        )
    rows = query.order_by(EnterpriseLicenseRecord.created_at.desc()).limit(200).all()
    return [LicenseRecordOut.of(r) for r in rows]


@router.post("", response_model=LicenseCreatedOut, status_code=201, dependencies=[Depends(limit_admin_write)])
def create_license(
    data: LicenseCreateIn,
    db: Session = Depends(get_db),
    staff: StaffPrincipal = Depends(require_staff("licenses", "create")),
):
    record, code = svc.create(
        db,
        org_name=data.org_name,
        contact=data.contact,
        seats=data.seats,
        days=data.days,
        grace_days=data.grace_days,
        mods=data.mods,
        feat=data.feat,
        note=data.note,
        actor=staff.email,
    )
    staff_audit.record(
        db,
        staff,
        "license_create",
        summary=f"صدورِ مجوزِ سازمانی برای «{record.org_name}»",
        target_type="enterprise_license",
        target_id=record.id,
        target_label=record.lic_id,
        details={"seats": data.seats, "days": data.days, "feat": data.feat},
    )
    return LicenseCreatedOut(license=LicenseRecordOut.of(record), activation_code=code)


@router.get("/{license_id}", response_model=LicenseDetailOut)
def get_license(
    license_id: UUID,
    db: Session = Depends(get_db),
    _: StaffPrincipal = Depends(require_staff("licenses", "view")),
):
    return _detail(db, _get(db, license_id))


@router.patch("/{license_id}", response_model=LicenseDetailOut, dependencies=[Depends(limit_admin_write)])
def update_license(
    license_id: UUID,
    data: LicenseUpdateIn,
    db: Session = Depends(get_db),
    staff: StaffPrincipal = Depends(require_staff("licenses", "edit")),
):
    record = _get(db, license_id)
    changes: dict = {}
    if data.org_name is not None:
        record.org_name = data.org_name.strip()
        changes["org_name"] = record.org_name
    if data.contact is not None:
        record.contact = data.contact.strip() or None
        changes["contact"] = record.contact
    if data.clear_seats:
        record.seats = None
        changes["seats"] = None
    elif data.seats is not None:
        record.seats = data.seats
        changes["seats"] = data.seats
    if data.make_perpetual:
        record.expires_at = None
        changes["expires_at"] = None
    elif data.extend_days:
        now = datetime.now(timezone.utc)
        base = record.expires_at if record.expires_at and record.expires_at > now else now
        record.expires_at = base + timedelta(days=data.extend_days)
        changes["expires_at"] = record.expires_at.isoformat()
    if data.grace_days is not None:
        record.grace_days = data.grace_days
        changes["grace_days"] = data.grace_days
    if data.all_features:
        record.feat = None
        changes["feat"] = None
    elif data.feat is not None:
        record.feat = data.feat
        changes["feat"] = data.feat
    if data.note is not None:
        record.note = data.note.strip() or None
        changes["note"] = record.note
    if not changes:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "تغییری فرستاده نشد")
    db.add(EnterpriseLicenseEvent(license_id=record.id, kind="update", actor=staff.email, detail=changes))
    db.flush()
    staff_audit.record(
        db,
        staff,
        "license_update",
        summary=f"ویرایشِ مجوزِ «{record.org_name}»",
        target_type="enterprise_license",
        target_id=record.id,
        target_label=record.lic_id,
        details=changes,
    )
    return _detail(db, record)


@router.post("/{license_id}/issue", response_model=LicenseTokenOut, dependencies=[Depends(limit_admin_write)])
def issue_offline(
    license_id: UUID,
    data: LicenseIssueIn,
    db: Session = Depends(get_db),
    staff: StaffPrincipal = Depends(require_staff("licenses", "issue")),
):
    record = _get(db, license_id)
    try:
        token = svc.bind_and_issue(db, record, data.request_code, staff.email)
    except LicenseError as exc:
        return JSONResponse(status_code=400, content={"detail": str(exc)})
    staff_audit.record(
        db,
        staff,
        "license_issue",
        summary=f"صدورِ آفلاینِ مجوزِ «{record.org_name}»",
        target_type="enterprise_license",
        target_id=record.id,
        target_label=record.lic_id,
    )
    return LicenseTokenOut(token=token)


@router.post("/{license_id}/transfer", response_model=LicenseDetailOut, dependencies=[Depends(limit_admin_write)])
def transfer_license(
    license_id: UUID,
    db: Session = Depends(get_db),
    staff: StaffPrincipal = Depends(require_staff("licenses", "transfer")),
):
    record = _get(db, license_id)
    svc.transfer(db, record, staff.email)
    staff_audit.record(
        db,
        staff,
        "license_transfer",
        summary=f"آزادکردنِ مجوزِ «{record.org_name}» برای دستگاهِ تازه",
        target_type="enterprise_license",
        target_id=record.id,
        target_label=record.lic_id,
    )
    return _detail(db, record)


@router.post("/{license_id}/revoke", response_model=LicenseDetailOut, dependencies=[Depends(limit_admin_write)])
def revoke_license(
    license_id: UUID,
    db: Session = Depends(get_db),
    staff: StaffPrincipal = Depends(require_staff("licenses", "revoke")),
):
    record = _get(db, license_id)
    svc.revoke(db, record, staff.email)
    staff_audit.record(
        db,
        staff,
        "license_revoke",
        summary=f"ابطالِ مجوزِ «{record.org_name}»",
        target_type="enterprise_license",
        target_id=record.id,
        target_label=record.lic_id,
    )
    return _detail(db, record)


@router.post("/{license_id}/code", response_model=ActivationCodeOut, dependencies=[Depends(limit_admin_write)])
def regenerate_code(
    license_id: UUID,
    db: Session = Depends(get_db),
    staff: StaffPrincipal = Depends(require_staff("licenses", "edit")),
):
    record = _get(db, license_id)
    code = svc.regenerate_code(db, record, staff.email)
    staff_audit.record(
        db,
        staff,
        "license_code_regenerate",
        summary=f"کدِ فعال‌سازیِ تازه برای «{record.org_name}» (کدِ قبلی باطل شد)",
        target_type="enterprise_license",
        target_id=record.id,
        target_label=record.lic_id,
    )
    return ActivationCodeOut(activation_code=code)
