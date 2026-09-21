"""ورود و هویتِ کارمندِ ستاد — درِ ورودیِ admin.cubita.ir.

عمداً از `/api/auth` جداست. آن مسیر عضویت در یک کسب‌وکار می‌خواهد و توکنِ
مستأجری می‌دهد؛ اینجا نه عضویتی لازم است و نه توکن مستأجری می‌گیرد.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import StaffPrincipal, client_ip, get_staff_principal, require_staff
from app.models.tenant import PlatformAdmin, Tenant
from app.models.user import User
from app.rate_limit import limit_admin_login, limit_admin_login_for_email
from app.schemas.admin_staff import (
    DiagnosticsOut,
    StaffChangePasswordIn,
    StaffLoginIn,
    StaffMeOut,
    StaffTokenOut,
)
from app.security import create_staff_token, record_login, set_password, verify_password
from app.services import staff_audit
from app.staff_roles import STAFF_ROLE_LABELS

router = APIRouter(prefix="/api/admin/auth", tags=["admin-auth"])

#: پاسخِ **یکسان** برای هر شکستِ ورود. تفکیکِ «رمز غلط» از «کارمندِ ستاد نیست»
#: به مهاجم می‌گوید کدام ایمیل‌ها کارمندند — فهرستی که هیچ‌جای دیگری در دسترس نیست.
_DENIED = "ایمیل یا رمز عبور نادرست است"


def _alembic_version(db: Session) -> str | None:
    """`None` اگر جدول نباشد — نه ۵۰۰ و **نه rollback**.

    schemaِ تست‌ها با `create_all` ساخته می‌شود و `alembic_version` ندارد. یک
    اندپوینتِ *تشخیصی* که خودش می‌شکند، دقیقاً در لحظه‌ای بی‌فایده است که لازمش داریم.

    عمداً با `to_regclass` سنجیده می‌شود و نه با `try/except`: کوئریِ شکست‌خورده
    تراکنش را به حالتِ خطا می‌برد و `rollback`ِ بعدی‌اش کارِ ثبت‌نشده‌ی همان
    درخواست را دور می‌ریزد. این دقیقاً یک بار همین‌جا اتفاق افتاد و شمارشِ
    کارمندان را صفر نشان داد.
    """
    if db.execute(text("SELECT to_regclass('alembic_version')")).scalar() is None:
        return None
    return db.execute(text("SELECT version_num FROM alembic_version")).scalar()


def _me_out(staff: StaffPrincipal) -> StaffMeOut:
    admin = staff.admin
    return StaffMeOut(
        id=admin.id if admin is not None else staff.user.id,
        user_id=staff.user.id,
        name=staff.user.name,
        email=staff.user.email,
        role=staff.role,
        role_label=STAFF_ROLE_LABELS.get(staff.role, staff.role),
        permissions=staff.permissions,
        last_login_at=admin.last_login_at if admin is not None else staff.user.last_login_at,
        via=staff.via,
    )


@router.post("/login", response_model=StaffTokenOut, dependencies=[Depends(limit_admin_login)])
def login(data: StaffLoginIn, request: Request, db: Session = Depends(get_db)):
    limit_admin_login_for_email(str(data.email))

    user = db.query(User).filter(User.email == str(data.email)).first()
    if user is None or not user.active or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, _DENIED)

    admin = (
        db.query(PlatformAdmin)
        .filter(PlatformAdmin.user_id == user.id, PlatformAdmin.is_active.is_(True))
        .first()
    )
    if admin is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, _DENIED)

    record_login(user)
    admin.last_login_at = datetime.now(timezone.utc)
    db.flush()

    # فقط ورودهای **موفق** ثبت می‌شوند. ثبتِ شکست‌ها این جدول را به سیلابی
    # می‌سپرد که خودِ مهاجم کنترلش می‌کند؛ تلاشِ ناموفق جایش لاگِ برنامه است.
    staff = StaffPrincipal(user, admin, ip=client_ip(request))
    staff_audit.record(db, staff, "login", summary=f"ورودِ {user.email} به پنلِ مدیریت")

    return StaffTokenOut(access_token=create_staff_token(user))


@router.get("/me", response_model=StaffMeOut)
def me(staff: StaffPrincipal = Depends(get_staff_principal)):
    return _me_out(staff)


@router.post("/change-password", response_model=StaffMeOut)
def change_password(
    data: StaffChangePasswordIn,
    db: Session = Depends(get_db),
    staff: StaffPrincipal = Depends(get_staff_principal),
):
    """رمزِ خودِ کارمند. رمزِ فعلی لازم است — توکنِ دزدیده‌شده نباید بتواند قفل را عوض کند."""
    if not verify_password(data.current_password, staff.user.hashed_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "رمزِ فعلی نادرست است")

    # `set_password` نسلِ توکن را جلو می‌برد، پس همه‌ی نشست‌های دیگر — از جمله
    # نشست‌های مستأجریِ همین کاربر — همان لحظه باطل می‌شوند.
    set_password(staff.user, data.new_password)
    staff_audit.record(
        db, staff, "password_change", summary=f"تغییرِ رمزِ {staff.email} توسطِ خودش"
    )
    db.flush()
    return _me_out(staff)


#: `/api/admin/diagnostics` زیرِ پیشوندِ `/auth` نمی‌نشیند، پس روترِ دومِ کوچک.
diagnostics_router = APIRouter(prefix="/api/admin", tags=["admin-auth"])


@diagnostics_router.get(
    "/diagnostics",
    response_model=DiagnosticsOut,
    dependencies=[Depends(require_staff())],
)
def diagnostics(db: Session = Depends(get_db)):
    """کدام محیط، کدام دیتابیس، کدام مهاجرت.

    این همان کاوشی است که استقرارِ اشتباهِ دمو لازم داشت: `/api/health` فقط
    «ok» می‌گوید، پس vhostی که به بک‌اندِ اشتباه پراکسی شده بود سالم به‌نظر می‌رسید.
    """
    settings = get_settings()
    return DiagnosticsOut(
        env=settings.env,
        database_name=db.execute(text("SELECT current_database()")).scalar() or "?",
        alembic_version=_alembic_version(db),
        tenant_count=db.query(func.count(Tenant.id)).scalar() or 0,
        staff_count=db.query(func.count(PlatformAdmin.id))
        .filter(PlatformAdmin.is_active.is_(True))
        .scalar()
        or 0,
        legacy_admin_allowlist=settings.legacy_admin_allowlist,
    )
