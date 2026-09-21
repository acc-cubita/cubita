"""شخصی‌سازیِ پنل — روشن/خاموش‌کردنِ ماژول‌ها توسطِ مالکِ کسب‌وکار.

سطحِ شرکت (per-tenant): تنظیم روی خودِ tenant می‌نشیند، پس همه‌ی کاربرانِ آن کسب‌وکار
همان مجموعه را می‌بینند (فیلترِ نقش جداست). فقط `owner` می‌تواند تغییر دهد.

«حقِ دسترسی»ِ ماژول‌های محدود این‌جا تغییر نمی‌کند — آن فقط دستِ سوپرادمین است
(روترِ admin_accounts). این‌جا مالک صرفاً از میانِ ماژول‌های *مجاز* نمایش را می‌چیند.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import Principal, get_principal
from app.models.tenant import Tenant
from app.schemas.modules import ModulesStateOut, SetModulesIn, SetTradeIn
from app.services import assurance_access
from app.services import modules as svc

router = APIRouter(prefix="/api/modules", tags=["modules"])


def require_owner(principal: Principal = Depends(get_principal)) -> Principal:
    """شخصی‌سازیِ پنل کلِ کسب‌وکار را تغییر می‌دهد، پس فقط مالک — مثلِ backup."""
    if principal.role.key != "owner":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "فقط مالکِ کسب‌وکار می‌تواند ماژول‌های پنل را تغییر دهد"
        )
    return principal


def _state(db: Session, tenant: Tenant) -> ModulesStateOut:
    #: ماژولِ مشتق را هم باید ببیند، وگرنه صفحه‌ی «شخصی‌سازیِ پنل» و `/me` دو
    #: جوابِ متفاوت می‌دادند و مالک فکر می‌کرد ماژولی که می‌بیند خاموش است.
    derived = assurance_access.derived_modules(db, tenant.id)
    return ModulesStateOut(
        industry=tenant.industry,
        trade=tenant.trade,
        enabled=svc.enabled_modules(tenant, derived=derived),
        allowed=sorted(svc.allowed_modules(tenant, derived=derived)),
        core=list(svc.CORE_MODULES),
        optional=list(svc.OPTIONAL_MODULES),
        restricted=list(svc.RESTRICTED_MODULES),
        industries=list(svc.INDUSTRY_TEMPLATES.keys()),
    )


@router.get("", response_model=ModulesStateOut)
def get_modules(
    principal: Principal = Depends(get_principal), db: Session = Depends(get_db)
):
    """وضعیتِ فعلیِ ماژول‌ها + رجیستریِ سرور — برای صفحه‌ی شخصی‌سازی. هر عضو می‌بیند."""
    return _state(db, principal.membership.tenant)


@router.put("", response_model=ModulesStateOut)
def set_modules(
    data: SetModulesIn,
    principal: Principal = Depends(require_owner),
    db: Session = Depends(get_db),
):
    """ترجیحِ نمایشِ مالک را ذخیره می‌کند (فقط اختیاری‌های مجاز)."""
    svc.set_enabled(principal.membership.tenant, data.enabled)
    db.flush()
    return _state(db, principal.membership.tenant)


@router.put("/trade", response_model=ModulesStateOut)
def set_trade(
    data: SetTradeIn,
    principal: Principal = Depends(require_owner),
    db: Session = Depends(get_db),
):
    """صنفِ کسب‌وکار را اعلام/عوض می‌کند.

    **چرا این‌جا و نه فقط در ثبت‌نام.** صنف تا امروز وجود نداشت، پس همه‌ی
    کسب‌وکارهای موجود `NULL` اند. بدونِ راهی برای اعلامش، هدف‌گیریِ پخش‌کننده برای
    هیچ‌کدامشان هرگز کار نمی‌کرد و فقط حساب‌های تازه از این قابلیت بهره می‌بردند.

    مثلِ ماژول‌ها فقط مالک — این تنظیمِ کلِ کسب‌وکار است، نه ترجیحِ یک کاربر. و
    برخلافِ `industry` (که فقط سوپرادمین عوضش می‌کند) این چیزی را قفل یا باز
    نمی‌کند، پس دستِ خودِ مالک است.
    """
    principal.membership.tenant.trade = data.trade
    db.flush()
    return _state(db, principal.membership.tenant)
