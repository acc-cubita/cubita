"""کمیسیونِ ۲٪ بازارِ عمده‌فروشی — کارتابلِ ستاد.

از `app/routers/marketplace.py` منتقل شد. آنجا مسیرش `/api/marketplace/admin/*`
بود — پیشوندی که هیچ‌کس هنگامِ شمردنِ «سطحِ ستاد» پیدایش نمی‌کرد. حالا کنارِ بقیه‌ی
`/api/admin/*` نشسته است.

جدولِ `marketplace_commissions` سراسری است و RLS ندارد، پس این کوئری‌ها به
`tenant_scope` نیازی ندارند — ولی به همین دلیل هر فیلترِ فراموش‌شده یک نشتِ
میان‌مشتری است. همه‌ی دسترسی‌ها از همان سه تابعِ سرویس می‌گذرند.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import StaffPrincipal, require_staff
from app.rate_limit import limit_admin_write
from app.schemas.marketplace import (
    CommissionOverviewOut,
    CommissionPeriodOut,
    CommissionSettleIn,
    CommissionSettleOut,
)
from app.services import marketplace as svc
from app.services import staff_audit

router = APIRouter(prefix="/api/admin/commissions", tags=["admin-commissions"])


@router.get("/overview", response_model=CommissionOverviewOut)
def overview(
    db: Session = Depends(get_db),
    _: StaffPrincipal = Depends(require_staff("commissions", "view")),
):
    """جمع‌های سرصفحه: کلِ کمیسیون، تسویه‌نشده، تسویه‌شده، تعدادِ پخش‌کننده و نرخ."""
    return CommissionOverviewOut(**svc.commission_overview(db))


@router.get("", response_model=list[CommissionPeriodOut])
def summary(
    db: Session = Depends(get_db),
    _: StaffPrincipal = Depends(require_staff("commissions", "view")),
):
    """صورتِ ماهانه‌ی هر پخش‌کننده."""
    return [CommissionPeriodOut(**r) for r in svc.commission_summary(db)]


@router.post("/settle", response_model=CommissionSettleOut, dependencies=[Depends(limit_admin_write)])
def settle(
    data: CommissionSettleIn,
    db: Session = Depends(get_db),
    staff: StaffPrincipal = Depends(require_staff("commissions", "settle")),
):
    """یک دوره‌ی یک پخش‌کننده را تسویه‌شده علامت می‌زند (انتقالِ بانکیِ دستی)."""
    out = svc.settle_commission_period(db, data.distributor_tenant_id, data.period, data.note)
    staff_audit.record(
        db,
        staff,
        "commission_settle",
        summary=f"تسویه‌ی کمیسیونِ دوره‌ی {data.period}",
        target_type="commission_period",
        tenant_id=data.distributor_tenant_id,
        details={"period": data.period, "note": data.note},
    )
    return CommissionSettleOut(**out)
