"""قیفِ فروشِ خودِ کوبیتا — **فقط مسیرهای عمومی**.

دو اندپوینتِ ستادیِ `/api/admin/purchases*` به `app/routers/admin_billing.py`
منتقل شدند. اینجا ماندنشان یعنی یک فایل هم مسیرِ بی‌احراز‌هویتِ cubita.ir را
داشت و هم قدرتِ دیدنِ داده‌ی هویتیِ همه‌ی مشتریان را — و تفکیکشان در بازبینی
به چشم نمی‌آمد.
"""
from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.billing import Plan
from app.schemas.billing import PlanOut, PurchaseRequestIn, PurchaseRequestOut
from app.services import billing as billing_service

router = APIRouter(tags=["billing"])


@router.get("/api/plans", response_model=list[PlanOut])
def list_plans(db: Session = Depends(get_db)):
    """عمومی — برای نمایش در صفحه‌ی قیمت‌گذاری سایت تجاری، بدون نیاز به احراز هویت."""
    return db.query(Plan).filter(Plan.is_active.is_(True)).order_by(Plan.sort_order).all()


@router.post("/api/purchases", response_model=PurchaseRequestOut, status_code=201)
def request_purchase(data: PurchaseRequestIn, db: Session = Depends(get_db)):
    """عمومی — شروع فرآیند خرید یک پلن؛ کاربر به درگاه زرین‌پال هدایت می‌شود."""
    purchase, payment_url = billing_service.create_purchase_request(db, data)
    return PurchaseRequestOut(purchase_id=purchase.id, payment_url=payment_url)


@router.get("/api/purchases/callback")
def purchase_callback(Authority: str, Status: str, db: Session = Depends(get_db)):
    """عمومی — بازگشت از درگاه زرین‌پال؛ نتیجه را verify و کاربر را به سایت تجاری ریدایرکت می‌کند."""
    purchase = billing_service.verify_purchase_callback(db, Authority, Status == "OK")
    site = get_settings().marketing_site_url.rstrip("/")
    if purchase is None:
        return RedirectResponse(f"{site}/checkout-result?status=failed")
    if purchase.status == "paid":
        # شناسه‌ی خرید عمداً در URL نمی‌آید: صفحه‌ی نتیجه به آن نیازی ندارد و هر
        # شناسه‌ای در URL در تاریخچه‌ی مرورگر/هدر Referer می‌نشیند. فقط وضعیت کافی است.
        return RedirectResponse(f"{site}/checkout-result?status=success")
    return RedirectResponse(f"{site}/checkout-result?status=failed")

