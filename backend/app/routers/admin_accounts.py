"""کنترل‌پنلِ «مدیریت اکانت‌ها» — فقط سوپرادمینِ سامانه (require_super_admin).

همه‌ی اندپوینت‌ها پشتِ SUPER_ADMIN_EMAILS‌اند، نه RBAC مستأجر و نه حتی platform_admin.
داده‌ی هویتیِ همه‌ی مشتریان و قدرتِ ساخت/حذفِ اکانت، فقط دستِ مالکِ سامانه.
"""
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import Principal, get_principal, require_super_admin
from app.models.user import User
from app.schemas.admin_accounts import (
    AccountRowOut,
    CreateAccountIn,
    ExtendIn,
    ResetPasswordIn,
    SetGrantsIn,
    SetIndustryIn,
    SetKindIn,
    StatusIn,
)
from app.services import admin_accounts

router = APIRouter(tags=["admin-accounts"], prefix="/api/admin/accounts")


@router.get("", response_model=list[AccountRowOut])
def list_accounts(
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    """همه‌ی اکانت‌ها با وضعیتِ اشتراک، تاریخِ انقضا و روزهای مانده."""
    return [AccountRowOut(**r) for r in admin_accounts.list_accounts(db)]


@router.post("", response_model=AccountRowOut, status_code=201)
def create_account(
    data: CreateAccountIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
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
    return AccountRowOut(**admin_accounts.account_row(db, tenant_id))


@router.post("/{tenant_id}/kind", response_model=AccountRowOut)
def set_kind(
    tenant_id: UUID,
    data: SetKindIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    """تغییرِ نوعِ حسابِ بازار (standard | distributor | retailer)."""
    admin_accounts.set_kind(db, tenant_id, kind=data.kind)
    return AccountRowOut(**admin_accounts.account_row(db, tenant_id))


@router.post("/{tenant_id}/industry", response_model=AccountRowOut)
def set_industry(
    tenant_id: UUID,
    data: SetIndustryIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    """تغییرِ صنف — ماژول‌ها را به قالبِ همان صنف بازنشانی و محدودهای قالب را گرنت می‌کند."""
    admin_accounts.set_industry(db, tenant_id, industry=data.industry)
    return AccountRowOut(**admin_accounts.account_row(db, tenant_id))


@router.post("/{tenant_id}/modules", response_model=AccountRowOut)
def set_grants(
    tenant_id: UUID,
    data: SetGrantsIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    """گرنتِ «حقِ دسترسی»ِ ماژول‌های محدود (مثلِ تولید) به اکانت."""
    admin_accounts.set_grants(db, tenant_id, granted=data.granted)
    return AccountRowOut(**admin_accounts.account_row(db, tenant_id))


@router.post("/{tenant_id}/extend", response_model=AccountRowOut)
def extend_account(
    tenant_id: UUID,
    data: ExtendIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    """تمدیدِ اشتراک (افزودنِ روز) یا تعیینِ تاریخِ انقضای مشخص."""
    admin_accounts.extend_account(db, tenant_id, days=data.days, expires_at=data.expires_at)
    return AccountRowOut(**admin_accounts.account_row(db, tenant_id))


@router.post("/{tenant_id}/status", response_model=AccountRowOut)
def set_status(
    tenant_id: UUID,
    data: StatusIn,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
    _: User = Depends(require_super_admin),
):
    """تعلیق یا فعال‌سازیِ اکانت."""
    admin_accounts.set_status(db, tenant_id, new_status=data.status, acting_tenant_id=principal.tenant_id)
    return AccountRowOut(**admin_accounts.account_row(db, tenant_id))


@router.post("/{tenant_id}/reset-password", response_model=AccountRowOut)
def reset_password(
    tenant_id: UUID,
    data: ResetPasswordIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    """تعیینِ رمزِ تازه برای مالکِ اکانت."""
    admin_accounts.reset_owner_password(db, tenant_id, password=data.password)
    return AccountRowOut(**admin_accounts.account_row(db, tenant_id))


@router.delete("/{tenant_id}")
def delete_account(
    tenant_id: UUID,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
    _: User = Depends(require_super_admin),
):
    """پاک‌سازیِ کاملِ اکانت (غیرقابل‌بازگشت)."""
    admin_accounts.delete_account(db, tenant_id, acting_tenant_id=principal.tenant_id)
    return {"deleted": True}
