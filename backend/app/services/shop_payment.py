"""پرداختِ آنلاینِ خریدارِ سایت با درگاهِ **خودِ مستأجر** (زرین‌پال، v4).

جریان: سایت `POST /orders/{id}/pay` می‌زند → این‌جا از زرین‌پالِ مستأجر authority
می‌گیریم و لینکِ StartPay را برمی‌گردانیم → خریدار پرداخت می‌کند → زرین‌پال به
`/api/shop/pay/callback?shop=<slug>` برمی‌گردد → verify → سفارش به فاکتورِ فروش تبدیل
می‌شود (`confirm_payment`).

منطقِ request/verify از فروشگاهِ نمونه (`D:\\Sample`) برداشته و پرمستأجر شده است.
"""
import logging

import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.storefront_native import PaymentGateway, Storefront, StorefrontOrder
from app.models.tenant import Membership
from app.models.user import User
from app.services.storefront_manage import confirm_payment

log = logging.getLogger("cubita.shop_payment")

_API_PROD = "https://payment.zarinpal.com/pg/v4/payment"
_API_SANDBOX = "https://sandbox.zarinpal.com/pg/v4/payment"
_STARTPAY_PROD = "https://payment.zarinpal.com/pg/StartPay"
_STARTPAY_SANDBOX = "https://sandbox.zarinpal.com/pg/StartPay"


def active_zarinpal(db: Session) -> PaymentGateway | None:
    return (
        db.query(PaymentGateway)
        .filter(
            PaymentGateway.provider == "zarinpal",
            PaymentGateway.is_active.is_(True),
            PaymentGateway.merchant_id != "",
        )
        .first()
    )


def has_online_payment(db: Session) -> bool:
    return active_zarinpal(db) is not None


def _sandbox(gateway: PaymentGateway) -> bool:
    return bool((gateway.config or {}).get("sandbox", False))


def _rial_amount(order: StorefrontOrder, storefront: Storefront) -> int:
    """مبلغِ ریالیِ موردِنیازِ درگاه. واحدِ ذخیره‌شده از تنظیماتِ فروشگاه می‌آید
    (theme_config.currency: «toman» پیش‌فرض → ×۱۰، یا «rial» → بدونِ تبدیل).
    این تصمیمِ پولِ واقعی است؛ پیش‌فرض با نمایشِ سایت (تومان) هم‌خوان است."""
    currency = (storefront.theme_config or {}).get("currency", "toman")
    total = int(order.total or 0)
    return total if currency == "rial" else total * 10


def _zp_call(base: str, path: str, payload: dict) -> dict:
    with httpx.Client(timeout=20.0) as client:
        res = client.post(f"{base}/{path}.json", json=payload, headers={"Accept": "application/json"})
        res.raise_for_status()
        return res.json()


def start_payment(db: Session, order: StorefrontOrder, storefront: Storefront, gateway: PaymentGateway, callback_url: str) -> str:
    base = _API_SANDBOX if _sandbox(gateway) else _API_PROD
    try:
        res = _zp_call(
            base,
            "request",
            {
                "merchant_id": gateway.merchant_id,
                "amount": _rial_amount(order, storefront),
                "callback_url": callback_url,
                "description": f"سفارش {order.tracking_code}",
                "metadata": {"mobile": order.customer_phone or "", "email": order.customer_email or ""},
            },
        )
    except httpx.HTTPError as err:
        log.warning("zarinpal request failed: %s", err)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "خطا در اتصال به درگاه پرداخت")

    authority = (res.get("data") or {}).get("authority")
    if not authority:
        msg = (res.get("errors") or {}).get("message", "خطا در ایجاد تراکنشِ پرداخت")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, msg)

    order.payment_authority = authority
    order.payment_provider = "zarinpal"
    db.flush()
    startpay = _STARTPAY_SANDBOX if _sandbox(gateway) else _STARTPAY_PROD
    return f"{startpay}/{authority}"


def verify_and_finalize(db: Session, order: StorefrontOrder, storefront: Storefront, gateway: PaymentGateway, authority: str, actor: User) -> bool:
    """پرداخت را verify و در صورتِ موفقیت سفارش را نهایی (فاکتور + کسرِ موجودی) می‌کند."""
    base = _API_SANDBOX if _sandbox(gateway) else _API_PROD
    try:
        res = _zp_call(base, "verify", {"merchant_id": gateway.merchant_id, "amount": _rial_amount(order, storefront), "authority": authority})
    except httpx.HTTPError as err:
        log.warning("zarinpal verify failed: %s", err)
        return False

    data = res.get("data") or {}
    if data.get("code") not in (100, 101):
        return False

    ref = str(data.get("ref_id", authority))
    try:
        confirm_payment(db, order.id, actor, provider="zarinpal", ref=ref)
    except HTTPException as err:
        # پرداخت موفق بوده ولی ثبتِ فاکتور نشد (مثلاً موجودی در این فاصله تمام شد).
        # پول را از دست نمی‌دهیم: سفارش «پرداخت‌شده» می‌شود ولی نیاز به بررسیِ دستی دارد.
        log.warning("paid but invoice failed for order %s: %s", order.id, err.detail)
        order.payment_status = "paid"
        order.payment_provider = "zarinpal"
        order.payment_ref = ref
        order.note = (order.note + " | ").lstrip(" |") + "پرداخت موفق ولی ثبتِ فاکتور ناموفق؛ بررسیِ دستی لازم است."
        db.flush()
    return True


def tenant_actor(db: Session, tenant_id) -> User | None:
    """کاربری که به‌عنوانِ ثبت‌کننده‌ی فاکتورِ خودکارِ سفارش عمل می‌کند (مالکِ کسب‌وکار).
    Membership سراسری است، پس بدونِ زمینه‌ی RLS هم قابلِ خواندن است."""
    m = (
        db.query(Membership)
        .filter(Membership.tenant_id == tenant_id, Membership.status == "active")
        .order_by(Membership.created_at.asc())
        .first()
    )
    return m.user if m else None
