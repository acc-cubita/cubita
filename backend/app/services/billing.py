import logging
from datetime import datetime, timezone
from uuid import UUID

import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.models.billing import Plan, Purchase
from app.schemas.billing import PurchaseRequestIn
from app.services.notifications import send_purchase_paid_notification

ZARINPAL_API_BASE = {
    True: "https://sandbox.zarinpal.com/pg/v4/payment",
    False: "https://payment.zarinpal.com/pg/v4/payment",
}
ZARINPAL_STARTPAY_BASE = {
    True: "https://sandbox.zarinpal.com/pg/StartPay",
    False: "https://payment.zarinpal.com/pg/StartPay",
}


def _zarinpal_call(path: str, payload: dict) -> dict:
    settings = get_settings()
    api_base = ZARINPAL_API_BASE[settings.zarinpal_sandbox]
    try:
        resp = httpx.post(f"{api_base}/{path}.json", json=payload, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as e:
        logging.warning(f"Zarinpal {path} call failed: {e}")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "خطا در ارتباط با درگاه پرداخت")


def create_purchase_request(db: Session, data: PurchaseRequestIn) -> tuple[Purchase, str]:
    plan = db.query(Plan).filter(Plan.key == data.plan_key, Plan.is_active.is_(True)).first()
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "پلن یافت نشد")

    purchase = Purchase(
        plan_id=plan.id,
        customer_name=data.customer_name,
        customer_email=data.customer_email,
        customer_phone=data.customer_phone,
        business_name=data.business_name,
        amount_toman=plan.price_toman,
        status="pending_payment",
    )
    db.add(purchase)
    db.flush()

    settings = get_settings()
    callback_url = f"{settings.backend_url.rstrip('/')}/api/purchases/callback"
    result = _zarinpal_call(
        "request",
        {
            "merchant_id": settings.zarinpal_merchant_id,
            "amount": int(plan.price_toman) * 10,  # مبلغ به ریال (تومان × ۱۰)
            "callback_url": callback_url,
            "description": f"خرید پلن {plan.name} - Cubita",
            "metadata": {"email": data.customer_email, "mobile": data.customer_phone},
        },
    )
    authority = (result.get("data") or {}).get("authority")
    if not authority:
        # rollback صریح لازم نیست: مرز تراکنش در get_db با بالا رفتن استثنا خودش برمی‌گرداند.
        message = (result.get("errors") or {}).get("message", "خطا در ایجاد تراکنش زرین‌پال")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, message)

    purchase.zarinpal_authority = authority
    db.flush()
    db.refresh(purchase)

    payment_url = f"{ZARINPAL_STARTPAY_BASE[settings.zarinpal_sandbox]}/{authority}"
    return purchase, payment_url


def verify_purchase_callback(db: Session, authority: str, ok: bool) -> Purchase | None:
    """اگر Authority در دیتابیس پیدا نشود None برمی‌گرداند (نشست منقضی‌شده یا پارامتر دستکاری‌شده)؛
    مسیرِ فراخواننده باید این را هم مثل شکست پرداخت، به‌جای خطای خام، به صفحه‌ی نتیجه ریدایرکت کند."""
    purchase = db.query(Purchase).filter(Purchase.zarinpal_authority == authority).first()
    if purchase is None:
        return None

    if not ok:
        purchase.status = "cancelled"
        db.flush()
        return purchase

    settings = get_settings()
    result = _zarinpal_call(
        "verify",
        {
            "merchant_id": settings.zarinpal_merchant_id,
            "amount": int(purchase.amount_toman) * 10,
            "authority": authority,
        },
    )
    data = result.get("data") or {}
    if data.get("code") in (100, 101):
        purchase.status = "paid"
        purchase.zarinpal_ref_id = str(data.get("ref_id", authority))
    else:
        purchase.status = "cancelled"
    db.flush()
    db.refresh(purchase)

    if purchase.status == "paid":
        _deliver(db, purchase)

    return purchase


def _deliver(db: Session, purchase: Purchase) -> None:
    """تحویل خودکار پلن خریداری‌شده.

    قبلاً فقط ایمیل اعلان به مدیر می‌رفت و ساخت کسب‌وکار دستی انجام می‌شد. حالا
    کسب‌وکار همین‌جا ساخته می‌شود.

    شکست تحویل نباید پرداخت را باطل کند: پول از حساب مشتری رفته و وضعیت «paid»
    حقیقت دارد. اگر provisioning بشکند، خرید پرداخت‌شده باقی می‌ماند و ادمین از
    اعلان باخبر می‌شود تا دستی رسیدگی کند — که دقیقاً همان رفتار قبلی است، فقط
    حالا به‌عنوان مسیر پشتیبان نه مسیر اصلی.
    """
    from app.services.provisioning import provision_for_purchase

    credentials = None
    try:
        with db.begin_nested():
            credentials = provision_for_purchase(db, purchase)
    except Exception as err:  # noqa: BLE001 - تحویل ناموفق نباید پرداخت را برگرداند
        logging.exception(f"provisioning failed for purchase {purchase.id}: {err}")

    send_purchase_paid_notification(purchase, credentials=credentials)


def list_purchases(db: Session) -> list[Purchase]:
    return (
        db.query(Purchase)
        .options(selectinload(Purchase.plan))
        .order_by(Purchase.created_at.desc())
        .all()
    )


def fulfill_purchase(db: Session, purchase_id: UUID, admin_notes: str) -> Purchase:
    purchase = db.get(Purchase, purchase_id)
    if purchase is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "خرید یافت نشد")
    if purchase.status != "paid":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "فقط خریدهای پرداخت‌شده قابل تحویل‌اند")

    purchase.status = "fulfilled"
    purchase.fulfilled_at = datetime.now(timezone.utc)
    purchase.admin_notes = admin_notes
    db.flush()
    db.refresh(purchase)
    return purchase
