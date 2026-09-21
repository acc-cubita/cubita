"""کاربرانِ ستاد — فقط `owner`.

عمداً **همه‌ی** مسیرهای این فایل نقشِ `owner` می‌خواهند، صرف‌نظر از مجوز. اگر با
`require_staff("staff", ...)` گیت می‌شد، یک `admin` می‌توانست به خودش مجوزِ
`staff` بدهد و بعد خودش را `owner` کند — یعنی گاردِ نقش تزئینی می‌شد.

**قاعده‌ی ضدِقفل:** همیشه باید دستِ‌کم یک `owner`ِ فعال بماند. بدونِ آن، یک
اشتباهِ ساده (غیرفعال‌کردنِ آخرین مالک) پنل را برای همیشه می‌بست و راهِ برگشت
فقط SSH بود.
"""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import StaffPrincipal, require_staff
from app.models.tenant import PlatformAdmin
from app.models.user import User
from app.rate_limit import limit_admin_write
from app.schemas.admin_staff import (
    StaffCreateIn,
    StaffResetPasswordIn,
    StaffRoleIn,
    StaffRowOut,
    StaffStatusIn,
)
from app.security import hash_password, set_password
from app.services import staff_audit
from app.staff_roles import STAFF_ROLE_LABELS, permissions_for

router = APIRouter(
    prefix="/api/admin/staff",
    tags=["admin-staff"],
    dependencies=[Depends(require_staff(role="owner"))],
)


def _row(db: Session, admin: PlatformAdmin) -> StaffRowOut:
    user = db.get(User, admin.user_id)
    return StaffRowOut(
        id=admin.id,
        user_id=admin.user_id,
        name=user.name if user else "—",
        email=user.email if user else "—",
        role=admin.role,
        role_label=STAFF_ROLE_LABELS.get(admin.role, admin.role),
        is_active=admin.is_active,
        last_login_at=admin.last_login_at,
        created_at=admin.created_at,
    )


def _load(db: Session, staff_id: UUID) -> PlatformAdmin:
    admin = db.get(PlatformAdmin, staff_id)
    if admin is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "کاربرِ ستاد یافت نشد")
    return admin


def _guard_last_owner(db: Session, admin: PlatformAdmin) -> None:
    """نمی‌گذارد آخرین مالکِ فعال برداشته یا تنزل داده شود."""
    if admin.role != "owner" or not admin.is_active:
        return
    others = (
        db.query(PlatformAdmin)
        .filter(
            PlatformAdmin.role == "owner",
            PlatformAdmin.is_active.is_(True),
            PlatformAdmin.id != admin.id,
        )
        .count()
    )
    if others == 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "این تنها مالکِ فعالِ سامانه است؛ اول یک مالکِ دیگر بسازید",
        )


@router.get("", response_model=list[StaffRowOut])
def list_staff(db: Session = Depends(get_db)):
    rows = db.query(PlatformAdmin).order_by(PlatformAdmin.created_at).all()
    return [_row(db, r) for r in rows]


@router.post("", response_model=StaffRowOut, status_code=201, dependencies=[Depends(limit_admin_write)])
def create_staff(
    data: StaffCreateIn,
    db: Session = Depends(get_db),
    staff: StaffPrincipal = Depends(require_staff(role="owner")),
):
    """کاربرِ ستادِ تازه.

    اگر کاربری با این ایمیل باشد همان استفاده می‌شود (یک نفر می‌تواند هم مالکِ
    کسب‌وکارِ خودش باشد و هم کارمندِ ستاد)؛ وگرنه کاربرِ تازه ساخته می‌شود.
    """
    email = str(data.email).strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(
            name=data.name,
            email=email,
            hashed_password=hash_password(data.password),
            active=True,
        )
        db.add(user)
        db.flush()
    elif db.query(PlatformAdmin).filter(PlatformAdmin.user_id == user.id).first() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "این کاربر از قبل کارمندِ ستاد است")

    admin = PlatformAdmin(
        user_id=user.id, role=data.role, is_active=True, created_by_id=staff.user.id
    )
    db.add(admin)
    db.flush()

    staff_audit.record(
        db,
        staff,
        "staff_create",
        summary=f"کاربرِ ستادِ تازه: {email} با نقشِ {STAFF_ROLE_LABELS.get(data.role, data.role)}",
        target_type="staff",
        target_id=admin.id,
        target_label=email,
        details={"role": data.role},
    )
    return _row(db, admin)


@router.patch("/{staff_id}/role", response_model=StaffRowOut, dependencies=[Depends(limit_admin_write)])
def set_role(
    staff_id: UUID,
    data: StaffRoleIn,
    db: Session = Depends(get_db),
    staff: StaffPrincipal = Depends(require_staff(role="owner")),
):
    admin = _load(db, staff_id)
    if data.role != "owner":
        _guard_last_owner(db, admin)
    previous = admin.role
    admin.role = data.role
    #: مجوزِ اختصاصی با عوض‌شدنِ نقش پاک می‌شود، وگرنه نقشِ تازه بی‌اثر می‌ماند.
    admin.permissions = None
    db.flush()

    row = _row(db, admin)
    staff_audit.record(
        db,
        staff,
        "staff_role_change",
        summary=f"نقشِ {row.email} از {previous} شد {data.role}",
        target_type="staff",
        target_id=admin.id,
        target_label=row.email,
        details={"from": previous, "to": data.role},
    )
    return row


@router.patch("/{staff_id}/status", response_model=StaffRowOut, dependencies=[Depends(limit_admin_write)])
def set_status(
    staff_id: UUID,
    data: StaffStatusIn,
    db: Session = Depends(get_db),
    staff: StaffPrincipal = Depends(require_staff(role="owner")),
):
    admin = _load(db, staff_id)
    if not data.active:
        _guard_last_owner(db, admin)
    admin.is_active = data.active
    admin.disabled_at = None if data.active else datetime.now(timezone.utc)
    db.flush()

    row = _row(db, admin)
    staff_audit.record(
        db,
        staff,
        "staff_disable",
        summary=("فعال‌سازیِ" if data.active else "غیرفعال‌سازیِ") + f" کاربرِ ستاد {row.email}",
        target_type="staff",
        target_id=admin.id,
        target_label=row.email,
        details={"active": data.active},
    )
    return row


@router.post(
    "/{staff_id}/reset-password", response_model=StaffRowOut, dependencies=[Depends(limit_admin_write)]
)
def reset_password(
    staff_id: UUID,
    data: StaffResetPasswordIn,
    db: Session = Depends(get_db),
    staff: StaffPrincipal = Depends(require_staff(role="owner")),
):
    """بازنشانیِ رمزِ یک کارمندِ ستاد توسطِ مالک.

    در فازِ ۱ تنها راهِ بازیابیِ رمزِ ستاد همین است (بازیابیِ ایمیلی به
    `app_url`ِ اپِ مشتری می‌رود و آنجا عضویت می‌خواهد). به همین دلیل باید
    **همیشه دستِ‌کم دو مالک** وجود داشته باشد.
    """
    admin = _load(db, staff_id)
    user = db.get(User, admin.user_id)
    set_password(user, data.password)
    db.flush()

    row = _row(db, admin)
    staff_audit.record(
        db,
        staff,
        "staff_reset_password",
        summary=f"بازنشانیِ رمزِ کارمندِ ستاد {row.email}",
        target_type="staff",
        target_id=admin.id,
        target_label=row.email,
    )
    return row
