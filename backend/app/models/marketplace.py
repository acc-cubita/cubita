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
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
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
ORDER_STATUSES = ("placed", "confirmed", "delivered", "rejected", "shipped", "received", "cancelled")
SETTLEMENT_MODES = ("credit", "online")
ORDER_PAYMENT_STATUSES = ("unpaid", "paid", "refunded")
COMMISSION_STATUSES = ("pending", "settled")
MESSAGE_SENDER_ROLES = ("distributor", "retailer")
RETURN_STATUSES = ("requested", "approved", "rejected")


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
    #: گردشِ کارِ «تحویل با مامور حمل»: اگر روشن باشد، تأییدِ سفارشِ اعتباری فقط آن را
    #: می‌پذیرد (بدونِ سند)؛ ورودِ کالا به انبارِ فروشگاه و تسویه‌ی نقدی هنگامِ ثبتِ تحویل
    #: توسطِ «مامور حمل/انتقال» انجام می‌شود. خاموش = رفتارِ قبلی (تأیید = سند + ورودِ انبار).
    require_delivery: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    #: شماره‌ی سفارشِ بعدی (شمارنده‌ی نمایشیِ per-distributor).
    next_order_number: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    #: متنِ سیاستِ مرجوعی که به فروشگاه نشان داده می‌شود (شرایط، استثناها، ...).
    return_policy: Mapped[str] = mapped_column(Text, default="", server_default="")
    #: مهلتِ مرجوعی به روز از تاریخِ تأییدِ سفارش. ۰ = بدونِ محدودیتِ زمانی. سیستم این را
    #: هنگامِ درخواستِ مرجوعیِ فروشگاه اعمال می‌کند (بعد از این مهلت، درخواست رد می‌شود).
    return_window_days: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    #: شماره‌ی مرجوعیِ بعدی (شمارنده‌ی نمایشیِ per-distributor).
    next_return_number: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    #: اصنافی که این پخش‌کننده به آن‌ها جنس می‌دهد — کلیدهای `app/services/trades.py`.
    #:
    #: **فهرستِ خالی = بدونِ محدودیت** (همه‌ی فروشگاه‌ها می‌بینندش). پیش‌فرض همین
    #: است تا هیچ پخش‌کننده‌ی موجودی با این ارتقا از بازار غیب نشود؛ تبِ تنظیمات
    #: به‌جایش هشدار می‌دهد که قابلیت را ندیده نگیرد.
    target_trades: Mapped[list] = mapped_column(
        JSONB, default=list, server_default="[]", nullable=False
    )


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
    #: قیمتِ عمده (ریال) — برای single قیمتِ هر واحد، برای pack قیمتِ کلِ پک. «قیمتِ خرید»ِ فروشگاه.
    wholesale_price: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    #: قیمتِ مصرف‌کننده‌ی پیشنهادی (فروش) که پخش‌کننده اعلام می‌کند — روی کاتالوگ حاشیه‌ی سود
    #: (فروش − خرید) به فروشگاه نشان داده می‌شود و هنگامِ تأییدِ سفارش روی بچِ فروشگاه می‌نشیند. ۰ = اعلام‌نشده.
    consumer_price: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    currency_code: Mapped[str] = mapped_column(String(10), default="", server_default="")
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    images: Mapped[list] = mapped_column(JSONB, default=list)
    category: Mapped[str] = mapped_column(String(100), default="", server_default="")
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    #: اصنافی که این قلم **علاوه بر** اصنافِ کلیِ پخش‌کننده
    #: (`MarketplaceSettings.target_trades`) به آن‌ها هم نشان داده می‌شود.
    #:
    #: موردِ کاربردش: تولیدیِ پوشاک که هدفش پوشاک‌فروشی‌هاست، ولی «لباس کار» را به
    #: یدکی‌فروشی و ابزارفروشی هم می‌دهد — بدونِ اینکه کلِ کاتالوگِ پیراهن و مانتو
    #: برای آن‌ها باز شود.
    #:
    #: **اضافه می‌کند، جایگزین نمی‌کند.** پس تغییرِ بعدیِ اصنافِ کلی خودکار روی همه‌ی
    #: اقلام اثر می‌گذارد و لیستینگ‌ها از آن عقب نمی‌مانند. نتیجه‌اش این است که
    #: پخش‌کننده‌ی بدونِ صنفِ کلی (= همه می‌بینند) نمی‌تواند یک قلم را محدود کند؛
    #: این ذاتیِ همین انتخاب است و در فرم صریح گفته می‌شود.
    extra_trades: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]", nullable=False)

    #: محدودیت‌های سفارش‌گذاری که پخش‌کننده روی همین لیستینگ می‌گذارد (۰ = بدونِ محدودیت):
    #:   min/max_order_qty = کف/سقفِ تعداد در هر سفارش
    #:   daily_order_limit = حداکثر دفعاتِ سفارشِ این کالا در یک روز، به‌ازای هر فروشگاه
    #: **اشانتیون (§۲۵):** «۱۰ کارتن بخر، ۱ کارتن رایگان». صفر = بدونِ
    #: اشانتیون، یعنی رفتارِ امروزِ هر لیستینگی که چیزی اعلام نکرده.
    bonus_threshold_qty: Mapped[float] = mapped_column(Numeric(18, 3), default=0, server_default="0")
    bonus_qty: Mapped[float] = mapped_column(Numeric(18, 3), default=0, server_default="0")

    min_order_qty: Mapped[float] = mapped_column(Numeric(18, 3), default=0, server_default="0")
    max_order_qty: Mapped[float] = mapped_column(Numeric(18, 3), default=0, server_default="0")
    daily_order_limit: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

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
    #: زونِ ارسال که پخش‌کننده این فروشگاه را در آن گذاشته (برای مدیریتِ سریع‌ترِ ارسال).
    #: فقط پخش‌کننده تعیین می‌کند؛ NULL = بدونِ زون. FKِ سراسری به marketplace_zones.
    zone_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_zones.id", ondelete="SET NULL"), nullable=True, index=True
    )

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

    #: زمانِ آخرین‌باری که هر سمت رشته‌ی گفتگوی این اتصال را خواند — مبنای شمارشِ پیامِ
    #: خوانده‌نشده (خوانده‌نشده‌ی هر سمت = پیام‌های بعد از این زمان که فرستنده‌شان سمتِ مقابل است).
    distributor_last_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retailer_last_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


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
    #: سهمِ نقدِ تسویه‌شده هنگام تأیید (ریال). بقیه (total − cash_amount) اعتباری/طلب می‌ماند.
    #: پخش‌کننده این درصد را موقعِ تأییدِ سفارش تعیین می‌کند؛ سندِ خزانه‌ی هر دو طرف با آن می‌خورد.
    cash_amount: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")

    #: زمانِ آخرین خواندنِ رشته‌ی گفتگوی این سفارش توسطِ هر سمت — مبنای شمارشِ خوانده‌نشده
    #: (جدا از رشته‌ی کلیِ اتصال؛ هر سفارش گفتگوی خودش را دارد).
    distributor_last_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retailer_last_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    #: تحویلِ بار (گردشِ کارِ «مامور حمل»). هنگامِ ثبتِ تحویل پر می‌شوند: زمان و نامِ
    #: ثبت‌کننده‌ی تحویل (اسنپ‌شات، برای پاسخ‌گویی). تا وقتی تحویل ثبت نشده NULL/خالی‌اند.
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_by_name: Mapped[str] = mapped_column(String(200), default="", server_default="")

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


class MarketplaceCommission(UUIDPKMixin, TimestampMixin, Base):
    """کمیسیونِ پلتفرم (۲٪) روی هر سفارشِ قطعی‌شده‌ی بازار — لایه‌ی سراسری (بدونِ RLS).

    یک رکورد به‌ازای هر سفارش (`order_id` یکتا) هنگامِ قطعی‌شدن ثبت می‌شود؛ ماهانه
    (به‌تفکیکِ ماهِ شمسی در `period`) توسطِ سوپرادمین با واریزِ دستی تسویه می‌شود.
    `rate`/`base_amount`/`amount` اسنپ‌شات‌اند تا تغییرِ نرخ روی سابقه اثر نگذارد.
    عمداً هیچ سندی در دفترِ خودِ پخش‌کننده نمی‌خورد — فقط همین دفترِ پلتفرمی.
    """

    __tablename__ = "marketplace_commissions"
    __table_args__ = (UniqueConstraint("order_id", name="uq_mp_commission_order"),)

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_orders.id", ondelete="CASCADE"), index=True
    )
    distributor_tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    # ماهِ شمسی به شکلِ ASCIIِ مرتب‌شونده: "1405-05" — گروه‌بندی/سورت پایدار می‌ماند.
    period: Mapped[str] = mapped_column(String(7), index=True)
    base_amount: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    rate: Mapped[float] = mapped_column(Numeric(6, 4), default=0.02)
    amount: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    settle_note: Mapped[str] = mapped_column(String(300), default="", server_default="")


class MarketplaceMessage(UUIDPKMixin, TimestampMixin, Base):
    """پیامِ گفتگوی یک اتصالِ بازار (فروشگاه↔پخش‌کننده) — لایه‌ی سراسری (بدونِ RLS).

    یک رشته‌ی گفتگوی دائم به‌ازای هر `MarketplaceConnection`. `sender_role` تعیین می‌کند
    پیام از کدام سمت است. جداسازی در کدِ روتر با بررسیِ عضویتِ فراخوان در همان اتصال انجام
    می‌شود، نه RLS. `sender_user_id` فقط برای نمایش/رد است (نه FK، چون میان‌مستأجری است).
    ایندکسِ مرکبِ (connection_id, created_at) هم لیستِ رشته و هم کوئریِ `after` را می‌پوشاند.
    """

    __tablename__ = "marketplace_messages"
    __table_args__ = (
        Index("ix_mp_messages_connection_created", "connection_id", "created_at"),
        Index("ix_mp_messages_order_created", "order_id", "created_at"),
        # هر پیام دقیقاً به یک رشته تعلق دارد: یا رشته‌ی کلیِ اتصال (connection_id) یا
        # رشته‌ی یک سفارش (order_id) — نه هر دو، نه هیچ‌کدام.
        CheckConstraint("num_nonnulls(connection_id, order_id) = 1", name="ck_mp_messages_one_thread"),
    )

    #: رشته‌ی کلیِ اتصال (فروشگاه↔پخش‌کننده). برای پیامِ سطحِ سفارش تهی است.
    connection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_connections.id", ondelete="CASCADE"), nullable=True
    )
    #: رشته‌ی گفتگوی یک سفارشِ مشخص. برای پیامِ رشته‌ی کلیِ اتصال تهی است.
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_orders.id", ondelete="CASCADE"), nullable=True
    )
    sender_tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    sender_role: Mapped[str] = mapped_column(String(20))  # distributor | retailer
    sender_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    body: Mapped[str] = mapped_column(Text)


class MarketplaceZone(UUIDPKMixin, TimestampMixin, Base):
    """زونِ ارسال که یک پخش‌کننده برای تقسیم‌بندیِ فروشگاه‌هایش تعریف می‌کند — لایه‌ی سراسری.

    نه نقشه و نه جغرافیا؛ فقط یک تقسیم‌بندیِ نام‌گذاری‌شده‌ی خودِ پخش‌کننده (مثلاً «منطقه‌ی
    شرق»). هر فروشگاهِ متصل با تصمیمِ پخش‌کننده در یک زون می‌نشیند تا ارسالِ بار سریع‌تر
    مدیریت شود. `zone_id` روی `MarketplaceConnection` به این اشاره می‌کند.
    """

    __tablename__ = "marketplace_zones"
    __table_args__ = (
        UniqueConstraint("distributor_tenant_id", "name", name="uq_mp_zone_distributor_name"),
    )

    distributor_tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")


class MarketplaceReturn(UUIDPKMixin, TimestampMixin, Base):
    """درخواستِ مرجوعیِ یک سفارشِ بازار — لایه‌ی سراسری.

    فروشگاه روی یک سفارشِ تأییدشده درخواستِ مرجوعی (کامل یا پارشال، به‌ازای ردیف) می‌دهد؛
    پخش‌کننده تأیید یا رد می‌کند. با تأیید، در دو دفتر برگشتِ فروش (سمتِ پخش‌کننده) و برگشتِ
    خرید (سمتِ فروشگاه) ثبت و لینک می‌شود.
    """

    __tablename__ = "marketplace_returns"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_orders.id", ondelete="CASCADE"), index=True
    )
    distributor_tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    retailer_tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    return_number: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="requested")  # requested|approved|rejected
    reason: Mapped[str] = mapped_column(Text, default="", server_default="")
    #: پاسخِ پخش‌کننده هنگامِ رد (یا یادداشتِ تأیید).
    response_note: Mapped[str] = mapped_column(Text, default="", server_default="")
    total: Mapped[float] = mapped_column(Numeric(18, 0), default=0)

    #: برگشت‌های متناظر پس از تأیید — هرکدام در دفترِ مستأجرِ خودش (FKِ سراسری→جدولِ مستأجری).
    distributor_sales_return_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales_returns.id", ondelete="SET NULL"), nullable=True
    )
    retailer_purchase_return_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_returns.id", ondelete="SET NULL"), nullable=True
    )

    lines: Mapped[list["MarketplaceReturnLine"]] = relationship(
        back_populates="return_", cascade="all, delete-orphan"
    )


class MarketplaceReturnLine(UUIDPKMixin, Base):
    """ردیفِ مرجوعی — به ردیفِ سفارش اشاره می‌کند و مقدارِ مرجوع‌شده را نگه می‌دارد."""

    __tablename__ = "marketplace_return_lines"

    return_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_returns.id", ondelete="CASCADE"), index=True
    )
    order_line_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_order_lines.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(300), default="")  # snapshot
    unit_price: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    qty: Mapped[float] = mapped_column(Numeric(18, 3), default=0)
    line_total: Mapped[float] = mapped_column(Numeric(18, 0), default=0)

    return_: Mapped["MarketplaceReturn"] = relationship(back_populates="lines")
