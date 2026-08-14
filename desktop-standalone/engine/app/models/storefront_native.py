"""فروشگاهِ بومیِ کوبیتا — مدل‌های داده.

برخلافِ `storefront.py` (اتصال به سایتِ بیرونی، با sync/mapping)، این‌جا فروشگاه یک
سطحِ بومیِ خودِ برنامه است: کاتالوگ = همان `items`، سفارشِ سایت مستقیماً به فاکتورِ
فروش تبدیل می‌شود، و موجودی یک منبعِ حقیقت دارد (`stock_ledger`).

جزئیات و تصمیم‌های معماری در `D:\\hesabdari\\STOREFRONT_PLAN.md`.

نکته‌ی امنیتی: `publishable_key` داخلِ سایتِ استاتیکِ دانلودشده بیک می‌شود و در مرورگرِ
خریدار دیده می‌شود، پس فقط عملیاتِ عمومی را مجاز می‌کند (خواندنِ کاتالوگ + ثبتِ سفارش +
شروعِ پرداخت). چون `storefronts` هم RLS دارد، کلید داخلِ زمینه‌ی مستأجر اعتبارسنجی
می‌شود: اول مستأجر از `tenants.slug` (سراسری) پیدا می‌شود، بعد کلید سنجیده می‌شود.
`payment_gateways.merchant_id` هم راز است (الگوی مؤدیان: فقط `has_merchant` برمی‌گردد).
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin

STOREFRONT_STATUSES = ("draft", "published")
STOREFRONT_PAYMENT_STATUSES = ("pending", "paid", "failed", "cancelled")
STOREFRONT_FULFILLMENT_STATUSES = ("new", "confirmed", "shipped", "done", "cancelled")
PAYMENT_PROVIDERS = ("zarinpal", "zibal", "idpay")


class Storefront(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """فروشگاهِ بومیِ یک کسب‌وکار — یک ردیف به‌ازای مستأجر (MVP: یک فروشگاه)."""

    __tablename__ = "storefronts"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_storefronts_tenant"),)

    #: کلیدِ قالبِ انتخاب‌شده (به `storefront_themes.key` نگاشت می‌شود؛ فعلاً «general»).
    theme_id: Mapped[str] = mapped_column(String(50), default="general", server_default="general")
    #: پیکربندیِ ظاهر: رنگ/لوگو/بنر/هیرو/محصولِ ویژه.
    theme_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    seo_title: Mapped[str] = mapped_column(String(200), default="")
    seo_description: Mapped[str] = mapped_column(Text, default="")
    #: تلفن/آدرس/شبکه‌های اجتماعیِ فوترِ سایت.
    contact_block: Mapped[dict] = mapped_column(JSONB, default=dict)

    #: کلیدِ publishable که در سایتِ استاتیک بیک می‌شود. دیده‌شدنش بی‌خطر است؛ فقط
    #: عملیاتِ عمومی. قابلِ ابطال/بازتولید.
    publishable_key: Mapped[str] = mapped_column(String(64), default="", index=True)
    #: دامنه‌ی هاستِ مستأجر — برای بازتابِ CORS در API عمومی. خالی = هنوز تنظیم نشده.
    allowed_origin: Mapped[str] = mapped_column(String(300), default="")

    status: Mapped[str] = mapped_column(String(20), default="draft", server_default="draft")
    #: آخرین باری که سایت build/دانلود شد — برای نشانِ «نسخه‌ی جدید در دسترس است».
    last_built_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ItemStorefront(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """نمایشِ یک کالا روی فروشگاه. بدونِ این ردیف، کالا روی سایت دیده نمی‌شود
    (نمایش کاملاً اختیاری است تا `items` لاغر بماند)."""

    __tablename__ = "item_storefront"
    __table_args__ = (UniqueConstraint("tenant_id", "item_id", name="uq_item_storefront_item"),)

    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), index=True
    )
    is_listed: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    #: فهرستِ مسیر/URLِ عکس‌ها (اولی = عکسِ اصلی).
    images: Mapped[list] = mapped_column(JSONB, default=list)
    long_description: Mapped[str] = mapped_column(Text, default="")
    slug: Mapped[str] = mapped_column(String(200), default="", index=True)
    sort: Mapped[int] = mapped_column(Integer, default=0)
    badge: Mapped[str] = mapped_column(String(30), default="")

    item: Mapped["Item"] = relationship()  # noqa: F821


class StorefrontCategory(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """منوی دسته‌بندیِ سایت. `items.category` رشته‌ی تخت است؛ این برای نمایشِ
    مرتب/درختی و URLِ تمیز است."""

    __tablename__ = "storefront_categories"
    __table_args__ = (UniqueConstraint("tenant_id", "slug", name="uq_storefront_categories_slug"),)

    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(120), index=True)
    sort: Mapped[int] = mapped_column(Integer, default=0)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("storefront_categories.id"), nullable=True
    )


class StorefrontCustomer(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """خریدارِ سایت (ورودِ OTPِ پیامکی در فازِ بعد). اختیاری به `contacts` لینک
    می‌شود تا کارت‌حساب/باشگاهِ مشتریان کار کند."""

    __tablename__ = "storefront_customers"
    __table_args__ = (UniqueConstraint("tenant_id", "phone", name="uq_storefront_customers_phone"),)

    name: Mapped[str] = mapped_column(String(150), default="")
    phone: Mapped[str] = mapped_column(String(20), index=True)
    email: Mapped[str] = mapped_column(String(150), default="")
    address: Mapped[str] = mapped_column(Text, default="")
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=True
    )


class StorefrontOrder(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """انبارکِ سفارشِ سایت — تا تأییدِ پرداخت هیچ سندِ حسابداری نمی‌خورد. پس از
    پرداخت → `post_sales_invoice` و لینک در `sales_invoice_id`."""

    __tablename__ = "storefront_orders"
    __table_args__ = (
        CheckConstraint(
            f"payment_status IN {STOREFRONT_PAYMENT_STATUSES}", name="ck_storefront_orders_payment"
        ),
        CheckConstraint(
            f"fulfillment_status IN {STOREFRONT_FULFILLMENT_STATUSES}",
            name="ck_storefront_orders_fulfillment",
        ),
    )

    #: شماره‌ی نمایشیِ سفارش (به‌ازای هر مستأجر).
    order_number: Mapped[int] = mapped_column(Integer, default=0)
    tracking_code: Mapped[str] = mapped_column(String(40), default="", index=True)

    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("storefront_customers.id"), nullable=True
    )
    customer_name: Mapped[str] = mapped_column(String(150), default="")
    customer_phone: Mapped[str] = mapped_column(String(20), default="")
    customer_email: Mapped[str] = mapped_column(String(150), default="")
    shipping_address: Mapped[str] = mapped_column(Text, default="")
    note: Mapped[str] = mapped_column(Text, default="")

    subtotal: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    discount: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    shipping_fee: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    tax: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    total: Mapped[float] = mapped_column(Numeric(18, 0), default=0)

    payment_status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    payment_provider: Mapped[str] = mapped_column(String(20), default="")
    payment_ref: Mapped[str] = mapped_column(String(100), default="")
    payment_authority: Mapped[str] = mapped_column(String(100), default="", index=True)

    fulfillment_status: Mapped[str] = mapped_column(String(20), default="new", server_default="new")

    sales_invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales_invoices.id"), nullable=True
    )

    lines: Mapped[list["StorefrontOrderLine"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class StorefrontOrderLine(TenantMixin, UUIDPKMixin, Base):
    """ردیفِ سفارش. tenant_id روی خودش هست چون RLS per-table است."""

    __tablename__ = "storefront_order_lines"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("storefront_orders.id", ondelete="CASCADE"), index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"), index=True)
    #: نامِ کالا در لحظه‌ی سفارش (snapshot) — اگر بعداً نامِ کالا عوض شد، سفارش دست‌نخورده بماند.
    item_name: Mapped[str] = mapped_column(String(300), default="")
    qty: Mapped[float] = mapped_column(Numeric(18, 3), default=0)
    unit_price: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    line_total: Mapped[float] = mapped_column(Numeric(18, 0), default=0)

    order: Mapped["StorefrontOrder"] = relationship(back_populates="lines")


class PaymentGateway(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """درگاهِ پرداختِ خودِ مستأجر برای پولِ خریداران (نه پرداختِ کاربر به کوبیتا).
    `merchant_id` راز است و هرگز در پاسخ API برنمی‌گردد (فقط `has_merchant`)."""

    __tablename__ = "payment_gateways"
    __table_args__ = (
        UniqueConstraint("tenant_id", "provider", name="uq_payment_gateways_provider"),
        CheckConstraint(f"provider IN {PAYMENT_PROVIDERS}", name="ck_payment_gateways_provider"),
    )

    provider: Mapped[str] = mapped_column(String(20))  # zarinpal | zibal | idpay
    merchant_id: Mapped[str] = mapped_column(Text, default="")  # راز
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    sort: Mapped[int] = mapped_column(Integer, default=0)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
