"""کنترل‌پنلِ «مدیریت اکانت‌ها» — فقط کارمندِ ستاد (`require_staff`).

این مسیرها داده‌ی هویتیِ همه‌ی مشتریان و قدرتِ ساخت/حذفِ اکانت را دارند. تا پیش
از کوچ به `admin.cubita.ir` پشتِ یک allowlistِ ایمیل بودند و توکنشان **مستأجری**
بود؛ حالا پشتِ هویتِ ستادند و توکنشان هیچ مستأجری ندارد.

**هر تغییری اینجا یک ردِ ستادی می‌نویسد.** تا دیروز حذفِ برگشت‌ناپذیرِ یک مشتری
هیچ ردی نمی‌گذاشت: `audit_log` مستأجرمحور است و هیچ مدلِ پلتفرمی‌ای در
`audited_models()` نیست.
"""
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import StaffPrincipal, require_staff
from app.models.tenant import Tenant
from app.rate_limit import limit_admin_write
from app.schemas.admin_accounts import (
    AccountRowOut,
    CreateAccountIn,
    DeleteAccountIn,
    ExtendIn,
    ResetPasswordIn,
    SetGrantsIn,
    SetIndustryIn,
    SetKindIn,
    StatusIn,
)
from app.services import admin_accounts, staff_audit

router = APIRouter(tags=["admin-accounts"], prefix="/api/admin/accounts")

#: نوشتن‌های این پنل محدودِ نرخ می‌شوند. تا امروز حتی حذفِ اکانت هیچ سقفی نداشت.
_WRITE = [Depends(limit_admin_write)]


def _label(db: Session, tenant_id: UUID) -> str | None:
    """نامِ کسب‌وکار **در همان لحظه** — تنها چیزی که بعد از حذف باقی می‌ماند."""
    tenant = db.get(Tenant, tenant_id)
    return tenant.name if tenant is not None else None


@router.get("", response_model=list[AccountRowOut])
def list_accounts(
    db: Session = Depends(get_db),
    _: StaffPrincipal = Depends(require_staff("accounts", "view")),
):
    """همه‌ی اکانت‌ها با وضعیتِ اشتراک، تاریخِ انقضا و روزهای مانده."""
    return [AccountRowOut(**r) for r in admin_accounts.list_accounts(db)]


@router.post("", response_model=AccountRowOut, status_code=201, dependencies=_WRITE)
def create_account(
    data: CreateAccountIn,
    db: Session = Depends(get_db),
    staff: StaffPrincipal = Depends(require_staff("accounts", "create")),
):
    """ساختِ دستیِ اکانت (کسب‌وکار + کاربرِ مالک) با رمزِ اولیه و اشتراکِ اولیه."""
    tenant_id = admin_accounts.create_account(
        db,
        business_name=data.business_name,
        owner_name=data.owner_name,
        email=str(data.email),
        password=data.password,
        days=data.days,
        kind=data.kind,
    )
    staff_audit.record(
        db,
        staff,
        "account_create",
        summary=f"ساختِ اکانتِ «{data.business_name}» برای {data.email}",
        target_type="tenant",
        target_id=tenant_id,
        target_label=data.business_name,
        tenant_id=tenant_id,
        # رمزِ اولیه **ثبت نمی‌شود** — فقط واقعه و هدف، قاعده‌ی SECRET_FIELDS.
        details={"days": data.days, "kind": data.kind},
    )
    return AccountRowOut(**admin_accounts.account_row(db, tenant_id))


@router.get("/{tenant_id}", response_model=AccountRowOut)
def get_account(
    tenant_id: UUID,
    db: Session = Depends(get_db),
    _: StaffPrincipal = Depends(require_staff("accounts", "view")),
):
    """یک اکانت. تا امروز این ردیف فقط به‌عنوانِ اثرِ جانبیِ یک *تغییر* در دسترس بود."""
    return AccountRowOut(**admin_accounts.account_row(db, tenant_id))


@router.post("/{tenant_id}/kind", response_model=AccountRowOut, dependencies=_WRITE)
def set_kind(
    tenant_id: UUID,
    data: SetKindIn,
    db: Session = Depends(get_db),
    staff: StaffPrincipal = Depends(require_staff("accounts", "edit")),
):
    """تغییرِ نوعِ حسابِ بازار (standard | distributor | retailer)."""
    admin_accounts.set_kind(db, tenant_id, kind=data.kind)
    label = _label(db, tenant_id)
    staff_audit.record(
        db,
        staff,
        "account_kind",
        summary=f"نوعِ حسابِ بازارِ «{label}» شد {data.kind}",
        target_type="tenant",
        target_id=tenant_id,
        target_label=label,
        tenant_id=tenant_id,
        details={"kind": data.kind},
    )
    return AccountRowOut(**admin_accounts.account_row(db, tenant_id))


@router.post("/{tenant_id}/industry", response_model=AccountRowOut, dependencies=_WRITE)
def set_industry(
    tenant_id: UUID,
    data: SetIndustryIn,
    db: Session = Depends(get_db),
    staff: StaffPrincipal = Depends(require_staff("accounts", "edit")),
):
    """تغییرِ صنف — ماژول‌ها را به قالبِ همان صنف بازنشانی و محدودهای قالب را گرنت می‌کند."""
    admin_accounts.set_industry(db, tenant_id, industry=data.industry)
    label = _label(db, tenant_id)
    staff_audit.record(
        db,
        staff,
        "account_industry",
        summary=f"صنفِ «{label}» شد {data.industry} — ماژول‌ها به قالبِ صنف بازنشانی شد",
        target_type="tenant",
        target_id=tenant_id,
        target_label=label,
        tenant_id=tenant_id,
        details={"industry": data.industry},
    )
    return AccountRowOut(**admin_accounts.account_row(db, tenant_id))


@router.post("/{tenant_id}/modules", response_model=AccountRowOut, dependencies=_WRITE)
def set_grants(
    tenant_id: UUID,
    data: SetGrantsIn,
    db: Session = Depends(get_db),
    staff: StaffPrincipal = Depends(require_staff("accounts", "edit")),
):
    """گرنتِ «حقِ دسترسی»ِ ماژول‌های محدود (مثلِ تولید) به اکانت."""
    admin_accounts.set_grants(db, tenant_id, granted=data.granted)
    label = _label(db, tenant_id)
    granted = "، ".join(data.granted) if data.granted else "هیچ"
    staff_audit.record(
        db,
        staff,
        "account_modules",
        summary=f"ماژول‌های محدودِ «{label}»: {granted}",
        target_type="tenant",
        target_id=tenant_id,
        target_label=label,
        tenant_id=tenant_id,
        details={"granted": data.granted},
    )
    return AccountRowOut(**admin_accounts.account_row(db, tenant_id))


@router.post("/{tenant_id}/extend", response_model=AccountRowOut, dependencies=_WRITE)
def extend_account(
    tenant_id: UUID,
    data: ExtendIn,
    db: Session = Depends(get_db),
    staff: StaffPrincipal = Depends(require_staff("accounts", "extend")),
):
    """تمدیدِ اشتراک (افزودنِ روز) یا تعیینِ تاریخِ انقضای مشخص."""
    admin_accounts.extend_account(db, tenant_id, days=data.days, expires_at=data.expires_at)
    label = _label(db, tenant_id)
    detail = f"{data.days} روز" if data.days else f"تا {data.expires_at}"
    staff_audit.record(
        db,
        staff,
        "account_extend",
        summary=f"تمدیدِ اشتراکِ «{label}» — {detail}",
        target_type="tenant",
        target_id=tenant_id,
        target_label=label,
        tenant_id=tenant_id,
        details={
            "days": data.days,
            "expires_at": str(data.expires_at) if data.expires_at else None,
        },
    )
    return AccountRowOut(**admin_accounts.account_row(db, tenant_id))


@router.post("/{tenant_id}/status", response_model=AccountRowOut, dependencies=_WRITE)
def set_status(
    tenant_id: UUID,
    data: StatusIn,
    db: Session = Depends(get_db),
    staff: StaffPrincipal = Depends(require_staff("accounts", "status")),
):
    """تعلیق یا فعال‌سازیِ اکانت."""
    label = _label(db, tenant_id)
    admin_accounts.set_status(db, tenant_id, new_status=data.status)
    verb = "فعال‌سازیِ" if data.status == "active" else "تعلیقِ"
    staff_audit.record(
        db,
        staff,
        "account_status",
        summary=f"{verb} اکانتِ «{label}»",
        target_type="tenant",
        target_id=tenant_id,
        target_label=label,
        tenant_id=tenant_id,
        details={"status": data.status},
    )
    return AccountRowOut(**admin_accounts.account_row(db, tenant_id))


@router.post("/{tenant_id}/reset-password", response_model=AccountRowOut, dependencies=_WRITE)
def reset_password(
    tenant_id: UUID,
    data: ResetPasswordIn,
    db: Session = Depends(get_db),
    staff: StaffPrincipal = Depends(require_staff("accounts", "reset_password")),
):
    """تعیینِ رمزِ تازه برای مالکِ اکانت.

    خطرناک‌ترین قابلیتِ شبه‌خواندنیِ این پنل است: عملاً حسابِ مشتری را دستِ ما
    می‌دهد و مالکِ واقعی را هم بیرون می‌اندازد (نسلِ توکن جلو می‌رود). پس ردِ
    ستادی می‌گیرد — و **مقدارِ رمز هرگز ثبت نمی‌شود**، فقط اینکه بازنشانی شد.
    """
    label = _label(db, tenant_id)
    admin_accounts.reset_owner_password(db, tenant_id, password=data.password)
    staff_audit.record(
        db,
        staff,
        "account_reset_password",
        summary=f"بازنشانیِ رمزِ مالکِ «{label}» توسطِ پشتیبانی",
        target_type="tenant",
        target_id=tenant_id,
        target_label=label,
        tenant_id=tenant_id,
    )
    return AccountRowOut(**admin_accounts.account_row(db, tenant_id))


@router.delete("/{tenant_id}", dependencies=_WRITE)
def delete_account(
    tenant_id: UUID,
    data: DeleteAccountIn,
    db: Session = Depends(get_db),
    staff: StaffPrincipal = Depends(require_staff("accounts", "delete", role="owner")),
):
    """پاک‌سازیِ کاملِ اکانت (غیرقابل‌بازگشت).

    سه گارد: نقشِ `owner`، تایپ‌کردنِ شناسه‌ی کسب‌وکار، و دلیلِ اجباری.

    **ردِ ستادی پیش از حذف نوشته و flush می‌شود.** ترتیب عمدی است: ردیفِ ردْ FK
    به `tenants` ندارد، پس حذفِ مستأجر نمی‌بردش — و این تنها سندی است که می‌گوید
    چه کسی و چرا این مشتری را پاک کرد.
    """
    label = _label(db, tenant_id)
    staff_audit.record(
        db,
        staff,
        "account_delete",
        summary=f"حذفِ کاملِ اکانتِ «{label}» — {data.reason}",
        target_type="tenant",
        target_id=tenant_id,
        target_label=label,
        tenant_id=tenant_id,
        details={"reason": data.reason},
    )
    admin_accounts.delete_account(db, tenant_id, confirm_slug=data.confirm_slug)
    return {"deleted": True}
