"""مدیریتِ فروشگاهِ بومی از داخلِ برنامه — تنظیمات، کلید، انتشار، فهرستِ کالا، درگاه.

همه‌ی خواندن/نوشتن‌ها زیرِ RLSِ مستأجرِ جاری‌اند (سرویس زمینه را از get_principal
به ارث می‌برد). این لایه فقط منطقِ کسب‌وکار است؛ مجوز/گیتِ پلن در روتر اعمال می‌شود.
"""
import re
import secrets
from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.inventory import Item, Warehouse
from app.models.storefront_native import (
    PAYMENT_PROVIDERS,
    STOREFRONT_FULFILLMENT_STATUSES,
    ItemStorefront,
    PaymentGateway,
    Storefront,
    StorefrontOrder,
)
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.invoices import SalesInvoiceIn, SalesInvoiceLineIn
from app.schemas.storefront_native import (
    GatewayOut,
    ItemListingOut,
    OrderLineOut,
    OrderOut,
    StorefrontSettingsOut,
)
from app.services.inventory import post_sales_invoice
from app.tenant_context import require_session_tenant

ONLINE_WAREHOUSE_CODE = "ONLINE"


def _new_key() -> str:
    """کلیدِ publishable با آنتروپیِ بالا (~۳۲ کاراکترِ url-safe، جا در String(64))."""
    return secrets.token_urlsafe(24)


def _slugify(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", s or "").strip("-").lower()


def get_or_create_storefront(db: Session) -> Storefront:
    sf = db.query(Storefront).first()
    if sf is None:
        sf = Storefront(publishable_key=_new_key())
        db.add(sf)
        db.flush()
    elif not sf.publishable_key:
        sf.publishable_key = _new_key()
        db.flush()
    return sf


def _tenant_slug(db: Session) -> str:
    tenant = db.get(Tenant, require_session_tenant(db))
    return tenant.slug if tenant else ""


def to_settings_out(db: Session, sf: Storefront) -> StorefrontSettingsOut:
    return StorefrontSettingsOut(
        slug=_tenant_slug(db),
        theme_id=sf.theme_id,
        theme_config=sf.theme_config or {},
        seo_title=sf.seo_title,
        seo_description=sf.seo_description,
        contact_block=sf.contact_block or {},
        allowed_origin=sf.allowed_origin,
        publishable_key=sf.publishable_key,
        status=sf.status,
        last_built_at=sf.last_built_at,
    )


def update_settings(db: Session, data) -> Storefront:
    sf = get_or_create_storefront(db)
    sf.theme_id = (data.theme_id or "general").strip()
    sf.theme_config = data.theme_config or {}
    sf.seo_title = data.seo_title
    sf.seo_description = data.seo_description
    sf.contact_block = data.contact_block or {}
    sf.allowed_origin = (data.allowed_origin or "").strip()
    db.flush()
    return sf


def rotate_key(db: Session) -> Storefront:
    sf = get_or_create_storefront(db)
    sf.publishable_key = _new_key()
    db.flush()
    return sf


def set_published(db: Session, published: bool) -> Storefront:
    sf = get_or_create_storefront(db)
    if published and not sf.publishable_key:
        # نباید ممکن باشد (get_or_create کلید می‌سازد)، ولی انتشارِ بدونِ کلید یعنی
        # سایتی که هیچ‌وقت نمی‌تواند به API وصل شود.
        sf.publishable_key = _new_key()
    sf.status = "published" if published else "draft"
    db.flush()
    return sf


# ── فهرست‌کردنِ کالا روی سایت ─────────────────────────────────────────────────────


def list_item_listings(db: Session) -> list[ItemListingOut]:
    """همه‌ی کالاها (نه خدمت) با وضعیتِ نمایششان روی سایت — تا پنل بتواند تیک بزند."""
    rows = (
        db.query(Item, ItemStorefront)
        .outerjoin(ItemStorefront, ItemStorefront.item_id == Item.id)
        .filter(Item.is_service.is_(False), Item.is_active.is_(True))
        .order_by(Item.name)
        .all()
    )
    out: list[ItemListingOut] = []
    for item, isf in rows:
        out.append(
            ItemListingOut(
                item_id=str(item.id),
                name=item.name,
                sku=item.sku,
                sales_price=int(item.sales_price or 0),
                is_listed=bool(isf.is_listed) if isf else False,
                images=list(isf.images) if isf and isf.images else [],
                long_description=isf.long_description if isf else "",
                slug=isf.slug if isf else "",
                sort=isf.sort if isf else 0,
                badge=isf.badge if isf else "",
            )
        )
    return out


def upsert_item_listing(db: Session, item_id, data) -> tuple[ItemStorefront, Item]:
    item = db.query(Item).filter(Item.id == item_id).first()
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "کالا یافت نشد")
    if item.is_service:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "خدمت روی فروشگاه قابلِ نمایش نیست")

    slug = _slugify(data.slug) or _slugify(item.sku) or str(item.id)
    # یکتاییِ slug در همین مستأجر (به‌جز خودِ همین کالا)
    clash = (
        db.query(ItemStorefront)
        .filter(ItemStorefront.slug == slug, ItemStorefront.item_id != item.id)
        .first()
    )
    if clash is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"نشانیِ «{slug}» قبلاً برای کالای دیگری استفاده شده است")

    isf = db.query(ItemStorefront).filter(ItemStorefront.item_id == item.id).first()
    if isf is None:
        isf = ItemStorefront(item_id=item.id)
        db.add(isf)
    isf.is_listed = data.is_listed
    isf.images = data.images or []
    isf.long_description = data.long_description
    isf.slug = slug
    isf.sort = data.sort
    isf.badge = data.badge
    db.flush()
    return isf, item


# ── درگاهِ پرداختِ خودِ مستأجر ─────────────────────────────────────────────────────


def list_gateways(db: Session) -> list[GatewayOut]:
    """هر سه درگاهِ شناخته‌شده را برمی‌گرداند (موجود یا پیش‌فرض) تا پنل فهرستِ ثابت ببیند."""
    existing = {g.provider: g for g in db.query(PaymentGateway).all()}
    out: list[GatewayOut] = []
    for provider in PAYMENT_PROVIDERS:
        g = existing.get(provider)
        out.append(
            GatewayOut(
                provider=provider,
                has_merchant=bool(g and g.merchant_id),
                is_active=bool(g and g.is_active),
            )
        )
    return out


def upsert_gateway(db: Session, provider: str, data) -> PaymentGateway:
    if provider not in PAYMENT_PROVIDERS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "درگاهِ ناشناخته")
    g = db.query(PaymentGateway).filter(PaymentGateway.provider == provider).first()
    if g is None:
        g = PaymentGateway(provider=provider)
        db.add(g)
    if data.merchant_id:  # خالی یعنی مرچنتِ فعلی حفظ شود
        g.merchant_id = data.merchant_id.strip()
    g.is_active = data.is_active
    db.flush()
    return g


# ── فیدِ سفارش + تأییدِ پرداخت ────────────────────────────────────────────────────


def to_order_out(order: StorefrontOrder) -> OrderOut:
    return OrderOut(
        id=str(order.id),
        order_number=order.order_number,
        tracking_code=order.tracking_code,
        customer_name=order.customer_name,
        customer_phone=order.customer_phone,
        customer_email=order.customer_email,
        shipping_address=order.shipping_address,
        note=order.note,
        subtotal=int(order.subtotal or 0),
        total=int(order.total or 0),
        payment_status=order.payment_status,
        fulfillment_status=order.fulfillment_status,
        sales_invoice_id=str(order.sales_invoice_id) if order.sales_invoice_id else None,
        created_at=order.created_at,
        lines=[
            OrderLineOut(
                item_id=str(line.item_id),
                item_name=line.item_name,
                qty=float(line.qty),
                unit_price=int(line.unit_price or 0),
                line_total=int(line.line_total or 0),
            )
            for line in order.lines
        ],
    )


def list_orders(db: Session) -> list[OrderOut]:
    orders = db.query(StorefrontOrder).order_by(StorefrontOrder.order_number.desc()).all()
    return [to_order_out(o) for o in orders]


def get_order_or_404(db: Session, order_id) -> StorefrontOrder:
    order = db.query(StorefrontOrder).filter(StorefrontOrder.id == order_id).first()
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سفارش یافت نشد")
    return order


def confirm_payment(db: Session, order_id, user: User, *, provider: str = "manual", ref: str = "") -> StorefrontOrder:
    """پرداخت را تأیید و سفارش را به فاکتورِ فروش تبدیل می‌کند (کسرِ خودکارِ موجودی).

    idempotent: اگر سفارش قبلاً پرداخت‌شده باشد، دوباره فاکتور نمی‌سازد. این همان
    درزی است که بعداً callbackِ زرین‌پال روی آن می‌نشیند.
    """
    order = get_order_or_404(db, order_id)
    if order.payment_status == "paid":
        return order  # idempotent
    if order.payment_status == "cancelled":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "سفارشِ لغوشده قابلِ تأیید نیست")

    warehouse = db.query(Warehouse).filter(Warehouse.code == ONLINE_WAREHOUSE_CODE).first()
    if warehouse is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"انبار «{ONLINE_WAREHOUSE_CODE}» یافت نشد")

    lines = [
        SalesInvoiceLineIn(item_id=line.item_id, qty=Decimal(str(line.qty)), unit_price=Decimal(str(line.unit_price)))
        for line in order.lines
    ]
    if not lines:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "سفارش بدونِ ردیف است")

    invoice = post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=date.today(),
            warehouse_id=warehouse.id,
            contact_id=None,
            description=f"سفارشِ آنلاین #{order.order_number} (کد پیگیری {order.tracking_code})",
            lines=lines,
        ),
        user,
    )
    order.sales_invoice_id = invoice.id
    order.payment_status = "paid"
    order.payment_provider = provider
    order.payment_ref = ref
    if order.fulfillment_status == "new":
        order.fulfillment_status = "confirmed"
    db.flush()
    return order


def update_fulfillment(db: Session, order_id, new_status: str) -> StorefrontOrder:
    if new_status not in STOREFRONT_FULFILLMENT_STATUSES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "وضعیتِ ارسالِ نامعتبر")
    order = get_order_or_404(db, order_id)
    order.fulfillment_status = new_status
    db.flush()
    return order
