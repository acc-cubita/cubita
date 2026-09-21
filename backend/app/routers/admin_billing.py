"""خریدهای سایتِ تجاری — کارتابلِ ستاد.

از `app/routers/billing.py` جدا شد. آنجا کنارِ سه مسیرِ کاملاً عمومیِ cubita.ir
نشسته بود، و یک فایل که هم درِ بی‌احراز‌هویت دارد و هم داده‌ی هویتیِ همه‌ی
مشتریانِ پولی را، اشتباهی است که در بازبینی دیده نمی‌شود.

ضمناً گاردش ارتقا یافت: تا دیروز `require_platform_admin` بود — لایه‌ی ضعیف‌تر و
یک allowlistِ **جدا** از سوپرادمین. حالا مثلِ بقیه‌ی `/api/admin/*` پشتِ هویتِ
ستاد است و با نقشِ `finance` هم کار می‌کند.
"""
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import StaffPrincipal, require_staff
from app.models.billing import Purchase
from app.rate_limit import limit_admin_write
from app.schemas.billing import PurchaseFulfillIn, PurchaseOut
from app.services import billing as billing_service
from app.services import staff_audit

router = APIRouter(prefix="/api/admin/purchases", tags=["admin-billing"])


@router.get("", response_model=list[PurchaseOut])
def list_purchases(
    db: Session = Depends(get_db),
    _: StaffPrincipal = Depends(require_staff("billing", "view")),
):
    """همه‌ی خریدها با داده‌ی هویتیِ مشتری."""
    return billing_service.list_purchases(db)


@router.post("/{purchase_id}/fulfill", response_model=PurchaseOut, dependencies=[Depends(limit_admin_write)])
def fulfill_purchase(
    purchase_id: UUID,
    data: PurchaseFulfillIn,
    db: Session = Depends(get_db),
    staff: StaffPrincipal = Depends(require_staff("billing", "fulfill")),
):
    """تحویلِ خرید: ساخت/ارتقای کسب‌وکار و ارسالِ لینکِ راه‌اندازی."""
    out = billing_service.fulfill_purchase(db, purchase_id, data.admin_notes)
    purchase = db.get(Purchase, purchase_id)
    staff_audit.record(
        db,
        staff,
        "purchase_fulfill",
        summary=f"تحویلِ خریدِ «{purchase.business_name}» ({purchase.customer_email})",
        target_type="purchase",
        target_id=purchase_id,
        target_label=purchase.business_name,
        details={"notes": data.admin_notes},
    )
    return out
