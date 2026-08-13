"""بازارِ عمده‌فروشیِ درون‌پلتفرمی (پخش‌کننده ↔ فروشگاه) — لایه‌ی **سراسری** (بدونِ RLS).

این جدول‌ها عمداً میان‌مستأجری‌اند: یک شرکتِ پخش کاتالوگ منتشر می‌کند و یک فروشگاه که
مستأجرِ دیگری است آن را می‌بیند و سفارش می‌دهد. چون سیاستِ RLS هر نشست را به یک مستأجر
می‌بندد ([app/tenancy.py](app/tenancy.py))، این داده نمی‌تواند per-tenant باشد؛ مثلِ
`tenants`/`subscriptions` در `GLOBAL_TABLES` ثبت می‌شود و **جداسازی در کدِ روتر** با
فیلترِ صریحِ tenant + نقش + وضعیتِ اتصال انجام می‌شود، نه با RLS.

پس این مدل‌ها `TenantMixin` ندارند؛ ستون‌های `*_tenant_id`/`*_item_id` فقط FKِ ساده‌اند
(نه کلیدِ RLS). چون FKِ سراسری→`items`/`sales_invoices` بین مستأجرها می‌پرد، به این
اتکا می‌کنیم که بررسیِ کلیدِ خارجیِ Postgres از RLS عبور می‌کند (برای صحتِ ارجاعی).

نوشتنِ سند در دو دفتر (روی تأییدِ سفارش) با `tenant_scope` انجام می‌شود؛ اینجا فقط داده.
"""
import uuid

from sqlalchemy import (
    Boolean,
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

LISTING_KINDS = ("single", "pack")
CONNECTION_STATUSES = ("pending", "approved", "rejected", "blocked")
ORDER_STATUSES = ("placed", "confirmed", "rejected", "shipped", "received", "cancelled")
SETTLEMENT_MODES = ("credit", "online")
ORDER_PAYMENT_STATUSES = ("unpaid", "paid", "refunded")


class MarketplaceSettings(UUIDPKMixin, TimestampMixin, Base):
    """تنظیماتِ بازار برای هر پخش‌کننده (یک ردیف به‌ازای مستأجرِ پخش‌کننده)."""

    __tablename__ = "marketplace_settings"
    __table_args__ = (UniqueConstraint("distributor_tenant_id", name="uq_mp_settings_distributor"),)

    distributor_tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    #: نامِ نمایشیِ پخش‌کننده در بازار (خالی = نامِ کسب‌وکار).
    display_name: Mapped[str] = mapped_column(String(200), default="", server_default="")
    #: نحوه‌ی تسویه‌ی سفارش‌ها — انتخابِ پخش‌کننده: credit (اعتباری/آفلاین) | online (درگاه).
    settlement_mode: Mapped[str] = mapped_column(String(20), default="credit", server_default="credit")
    #: تا فعال نشود، پخش‌کننده در بازار دیده نمی‌شود و درخواستِ اتصال نمی‌گیرد.
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    #: شماره‌ی سفارشِ بعدی (شمارنده‌ی نمایشیِ per-distributor).
    next_order_number: Mapped[int] = mapped_column(Integer, default=1, server_default="1")


class MarketplaceListing(UUIDPKMixin, TimestampMixin, Base):
    """یک آیتمِ کاتالوگِ پخش‌کننده — کالای تکی یا پکِ چندمحصولی."""

    __tablename__ = "marketplace_listings"

    distributor_tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(10), default="single")  # single | pack
    title: Mapped[str] = mapped_column(String(300))
    code: Mapped[str] = mapped_column(String(60), default="", server_default="")
    unit: Mapped[str] = mapped_column(String(20), default="عدد", server_default="عدد")
    #: قیمتِ عمده (ریال) — برای single قیمتِ هر واحد، برای pack قیمتِ کلِ پک.
    wholesale_price: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    currency_code: Mapped[str] = mapped_column(String(10), default="", server_default="")
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    images: Mapped[list] = mapped_column(JSONB, default=list)
    category: Mapped[str] = mapped_column(String(100), default="", server_default="")
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    #: برای single: کالای متناظرِ خودِ پخش‌کننده (برای کسر از انبارش هنگامِ تأیید). برای
    #: pack تهی است (اجزا در components‌اند).
    distributor_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), nullable=True, index=True
    )

    components: Mapped[list["MarketplaceListingComponent"]] = relationship(
        back_populates="listing", cascade="all, delete-orphan"
    )


class MarketplaceListingComponent(UUIDPKMixin, Base):
    """اجزای یک لیستینگ. single = یک جزء؛ pack = چند جزء. تعداد در واحدِ کالای پخش‌کننده."""

    __tablename__ = "marketplace_listing_components"

    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_listings.id", ondelete="CASCADE"), index=True
    )
    distributor_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), index=True
    )
    item_name: Mapped[str] = mapped_column(String(300), default="")  # snapshot
    qty: Mapped[float] = mapped_column(Numeric(18, 3), default=1)

    listing: Mapped["MarketplaceListing"] = relationship(back_populates="components")


class MarketplaceConnection(UUIDPKMixin, TimestampMixin, Base):
    """رابطه‌ی پخش‌کننده↔فروشگاه. فروشگاه فقط کاتالوگِ پخش‌کننده‌های approved را می‌بیند."""

    __tablename__ = "marketplace_connections"
    __table_args__ = (
        UniqueConstraint("distributor_tenant_id", "retailer_tenant_id", name="uq_mp_connection_pair"),
    )

    distributor_tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    retailer_tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|approved|rejected|blocked
    #: چه کسی درخواست داد — retailer (فروشگاه) یا distributor (دعوت).
    requested_by: Mapped[str] = mapped_column(String(20), default="retailer")

    #: طرف‌حسابِ خودکارِ دو سمت، تا سفارش‌های پیاپیِ همین رابطه روی یک طرف‌حساب جمع شوند
    #: (نه یک طرف‌حسابِ تازه به‌ازای هر سفارش). هرکدام Contactِ tenantِ خودش است (نه FK،
    #: چون میان‌مستأجری است و در تأیید دوباره اعتبارسنجی می‌شود):
    #:   distributor_customer_contact_id → «مشتری» در دفترِ پخش‌کننده (همان فروشگاه)
    #:   retailer_supplier_contact_id    → «تأمین‌کننده» در دفترِ فروشگاه (همان پخش‌کننده)
    distributor_customer_contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    retailer_supplier_contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )


class MarketplaceOrder(UUIDPKMixin, TimestampMixin, Base):
    """سفارشِ فروشگاه از پخش‌کننده. روی تأیید، در دو دفتر فاکتور می‌خورد و لینک می‌شود."""

    __tablename__ = "marketplace_orders"

    distributor_tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    retailer_tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    order_number: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="placed")  # ORDER_STATUSES
    settlement_mode: Mapped[str] = mapped_column(String(20), default="credit")  # snapshot از تنظیماتِ پخش‌کننده
    payment_status: Mapped[str] = mapped_column(String(20), default="unpaid")  # unpaid|paid|refunded
    note: Mapped[str] = mapped_column(Text, default="", server_default="")

    #: پرداختِ آنلاین (تسویه‌ی online): با درگاهِ خودِ پخش‌کننده. authority شناسه‌ی تراکنشِ
    #: درگاه است که در callback با آن سفارش پیدا و verify می‌شود؛ ref شناسه‌ی پیگیریِ نهایی.
    payment_authority: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payment_provider: Mapped[str] = mapped_column(String(20), default="", server_default="")
    payment_ref: Mapped[str] = mapped_column(String(120), default="", server_default="")
    subtotal: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    total: Mapped[float] = mapped_column(Numeric(18, 0), default=0)

    #: فاکتورهای متناظر پس از تأیید — هرکدام در دفترِ مستأجرِ خودش (FKِ سراسری→جدولِ مستأجری).
    distributor_sales_invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales_invoices.id", ondelete="SET NULL"), nullable=True
    )
    retailer_purchase_invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_invoices.id", ondelete="SET NULL"), nullable=True
    )

    lines: Mapped[list["MarketplaceOrderLine"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class MarketplaceOrderLine(UUIDPKMixin, Base):
    """ردیفِ سفارش — به لیستینگ اشاره می‌کند و عنوان/قیمت را snapshot می‌کند."""

    __tablename__ = "marketplace_order_lines"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_orders.id", ondelete="CASCADE"), index=True
    )
    listing_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_listings.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(300), default="")  # snapshot
    unit_price: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    qty: Mapped[float] = mapped_column(Numeric(18, 3), default=1)
    line_total: Mapped[float] = mapped_column(Numeric(18, 0), default=0)

    order: Mapped["MarketplaceOrder"] = relationship(back_populates="lines")


class MarketplaceItemLink(UUIDPKMixin, TimestampMixin, Base):
    """نگاشتِ ضدِتکرارِ سمتِ فروشگاه: کالای پخش‌کننده → کالای متناظر در انبارِ فروشگاه.

    بارِ اولِ دریافتِ یک کالای پخش‌کننده، `Item` تازه در انبارِ فروشگاه ساخته و اینجا لینک
    می‌شود؛ دفعاتِ بعد همان کالا پیدا و فقط تعدادش اضافه می‌شود (نه کالای تکراری).
    """

    __tablename__ = "marketplace_item_links"
    __table_args__ = (
        UniqueConstraint("retailer_tenant_id", "distributor_item_id", name="uq_mp_item_link"),
    )

    retailer_tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    distributor_tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    distributor_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), index=True
    )
    retailer_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), index=True
    )
