"""پرداختِ آنلاینِ خریدارِ سایت با درگاهِ **خودِ مستأجر** (زرین‌پال/زیبال/آی‌دی‌پی).

جریان: سایت `POST /orders/{id}/pay` می‌زند → این‌جا از درگاهِ فعالِ مستأجر تراکنش
می‌گیریم و لینکِ پرداخت را برمی‌گردانیم → خریدار پرداخت می‌کند → درگاه به
`/api/shop/pay/callback?shop=<slug>&provider=<provider>` برمی‌گردد → verify → سفارش
به فاکتورِ فروش تبدیل می‌شود (`confirm_payment`).

این ماژول از کدامِ درگاه خبر ندارد؛ آداپتورها در `payment_providers.py` هستند.
"""
import logging

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.storefront_native import PaymentGateway, Storefront, StorefrontOrder
from app.models.tenant import Membership
from app.models.user import User
from app.services.payment_providers import ProviderError, get_provider
from app.services.storefront_manage import confirm_payment

log = logging.getLogger("cubita.shop_payment")


def _gateway_query(db: Session):
    return db.query(PaymentGateway).filter(
        PaymentGateway.is_active.is_(True),
        PaymentGateway.merchant_id != "",
    )


def active_gateway(db: Session) -> PaymentGateway | None:
    """درگاهِ فعالِ مستأجر با کمترین `sort` (اولویتِ نمایش/پرداخت)."""
    return (
        _gateway_query(db)
        .order_by(PaymentGateway.sort.asc(), PaymentGateway.created_at.asc())
        .first()
    )


def gateway_for(db: Session, provider: str) -> PaymentGateway | None:
    """درگاهِ فعالِ یک provider مشخص — برای verifyِ callback با همان درگاهی که سفارش با آن شروع شد."""
    return _gateway_query(db).filter(PaymentGateway.provider == provider).first()


def has_online_payment(db: Session) -> bool:
    return active_gateway(db) is not None


def _sandbox(gateway: PaymentGateway) -> bool:
    return bool((gateway.config or {}).get("sandbox", False))


def _rial_amount(order: StorefrontOrder, storefront: Storefront) -> int:
    """مبلغِ ریالیِ موردِنیازِ درگاه. واحدِ ذخیره‌شده از تنظیماتِ فروشگاه می‌آید
    (theme_config.currency: «toman» پیش‌فرض → ×۱۰، یا «rial» → بدونِ تبدیل).
    این تصمیمِ پولِ واقعی است؛ پیش‌فرض با نمایشِ سایت (تومان) هم‌خوان است."""
    currency = (storefront.theme_config or {}).get("currency", "toman")
    total = int(order.total or 0)
    return total if currency == "rial" else total * 10


def start_payment(
    db: Session, order: StorefrontOrder, storefront: Storefront,
    gateway: PaymentGateway, callback_url: str,
) -> str:
    provider = get_provider(gateway.provider)
    if provider is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "درگاهِ ناشناخته")
    try:
        result = provider.start(
            merchant_id=gateway.merchant_id,
            amount_rial=_rial_amount(order, storefront),
            callback_url=callback_url,
            description=f"سفارش {order.tracking_code}",
            mobile=order.customer_phone or "",
            email=order.customer_email or "",
            order_ref=order.tracking_code,
            sandbox=_sandbox(gateway),
        )
    except ProviderError as err:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(err))
    except Exception as err:  # httpx و غیره
        log.warning("%s request failed: %s", gateway.provider, err)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "خطا در اتصال به درگاه پرداخت")

    order.payment_authority = result.authority
    order.payment_provider = gateway.provider
    db.flush()
    return result.redirect_url


def verify_and_finalize(
    db: Session, order: StorefrontOrder, storefront: Storefront,
    gateway: PaymentGateway, authority: str, actor: User,
) -> bool:
    """پرداخت را verify و در صورتِ موفقیت سفارش را نهایی (فاکتور + کسرِ موجودی) می‌کند."""
    provider = get_provider(gateway.provider)
    if provider is None:
        return False
    try:
        ok, ref = provider.verify(
            merchant_id=gateway.merchant_id,
            amount_rial=_rial_amount(order, storefront),
            authority=authority,
            order_ref=order.tracking_code,
            sandbox=_sandbox(gateway),
        )
    except Exception as err:
        log.warning("%s verify failed: %s", gateway.provider, err)
        return False
    if not ok:
        return False

    try:
        confirm_payment(db, order.id, actor, provider=gateway.provider, ref=ref)
    except HTTPException as err:
        # پرداخت موفق بوده ولی ثبتِ فاکتور نشد (مثلاً موجودی در این فاصله تمام شد).
        # پول را از دست نمی‌دهیم: سفارش «پرداخت‌شده» می‌شود ولی نیاز به بررسیِ دستی دارد.
        log.warning("paid but invoice failed for order %s: %s", order.id, err.detail)
        order.payment_status = "paid"
        order.payment_provider = gateway.provider
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
