import uuid
from decimal import Decimal
from datetime import date as date_
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
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
from app.models.base import TimestampMixin, UUIDPKMixin, VoidableMixin
from app.models.tenant import TenantMixin


class SalesInvoice(TenantMixin, VoidableMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "sales_invoices"

    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_sales_invoices_tenant_number"),
        UniqueConstraint("tenant_id", "source_order_id", name="uq_sales_invoices_tenant_source_order_id"),
        CheckConstraint("broker_commission >= 0", name="ck_sales_invoices_broker_commission"),
        CheckConstraint(
            "settlement_terms IN ('cash', 'credit', 'mixed')",
            name="ck_sales_invoices_settlement_terms",
        ),
    )

    number: Mapped[int | None] = mapped_column(nullable=True, index=True)
    invoice_date: Mapped[date_] = mapped_column(Date, default=date_.today)
    contact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=True)
    # فقط زمینه/پیشنهاد تجاری؛ انبار قطعی روی WarehouseIssue است.
    warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.id"), nullable=True
    )
    customer_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    seller_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    customer_name2: Mapped[str] = mapped_column(String(200), default="", server_default="")
    delivery_location: Mapped[str] = mapped_column(Text, default="", server_default="")
    receivable_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=True
    )
    settlement_terms: Mapped[str] = mapped_column(String(10), default="credit", server_default="credit")
    statement_date: Mapped[date_ | None] = mapped_column(Date, nullable=True)
    #: مرکز هزینه/پروژه‌ی این فاکتور؛ به ردیف‌های سندش هم منتقل می‌شود. NULL = بدون مرکز.
    cost_center_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cost_centers.id"), nullable=True
    )
    description: Mapped[str] = mapped_column(Text, default="")

    #: خالصِ **پس از تخفیف** و بدون مالیات. پایه‌ی محاسبه‌ی مالیات؛ در سند، درآمد
    #: ناخالص و تخفیف فروش جداگانه ثبت می‌شوند.
    total_amount: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    #: جمع تخفیفِ ردیف‌ها (شاملِ سهمِ تسهیم‌شده‌ی تخفیفِ کلِ فاکتور). فقط برای
    #: نمایش/صورتحساب مؤدیان و ثبتِ بدهکارِ مستقلِ تخفیف فروش در سند حسابداری.
    total_discount: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    #: تخفیفِ کلِ فاکتور که کاربر روی سرِ فاکتور اعمال کرده. هنگام ثبت به‌نسبتِ خالصِ
    #: هر ردیف بینِ ردیف‌ها تسهیم می‌شود (پس در total_discount هم منظور شده)؛ اینجا
    #: فقط برای نمایشِ شفافِ «چه مقدار از تخفیف، تخفیفِ کل بوده» جدا نگه داشته می‌شود.
    invoice_discount: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    total_additions: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    total_duties: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    #: تعدیلِ گِرد کردنِ مبلغِ نهایی (پس از مالیات). علامت‌دار: منفی = رند به پایین
    #: (تخفیفِ نقدی)، مثبت = رند به بالا. مبلغِ قابل‌پرداخت = خالص + مالیات + rounding.
    rounding: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    total_cost: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    # مالیات بر ارزش افزوده: نرخ درصدی و مبلغِ محاسبه‌شده. مبلغِ قابل‌پرداختِ مشتری = total_amount + tax_amount
    tax_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=0, server_default="0")
    tax_amount: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")

    #: ارزِ فاکتور. NULL = پایه (ریال). مبالغِ بالا همیشه پایه‌اند؛ این‌ها فقط برای
    #: نمایشِ معادلِ ارزی و نرخ‌اند — دفتر پایه می‌ماند.
    currency_code: Mapped[str | None] = mapped_column(String(3), nullable=True)
    exchange_rate: Mapped[float] = mapped_column(Numeric(18, 4), default=1, server_default="1")

    # شناسه‌ی سفارش روی سایت فروشگاهی؛ برای idempotent بودن sync (جلوگیری از وارد کردن دوباره‌ی همان سفارش)
    source_order_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    source_quotation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "sales_quotations.id",
            name="fk_sales_invoices_source_quotation",
            use_alter=True,
        ),
        nullable=True,
        index=True,
    )

    #: **بستنِ فاکتور** — قفل از ویرایش و ابطال. همان معنایی که «دائم» برای سند
    #: دارد: فاکتورِ بسته امضاشده است. یک‌طرفه؛ راهِ بازکردن عمداً نیست.
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    closed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    #: فروشنده‌ی این فاکتور — مبنای پورسانت. NULL = بی‌فروشنده (فروشِ مستقیم).
    salesperson_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    #: نوعِ فروش (نقدی، اعتباری، صادراتی…). NULL = تعیین‌نشده.
    sale_type_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sale_types.id", ondelete="SET NULL"), nullable=True
    )

    #: واسطه‌ی این معامله — طرف‌حسابی با نقشِ `is_broker`. NULL = بی‌واسطه.
    #: با `salesperson_id` اشتباه نشود: آن کاربرِ داخلیِ ماست، این طرفِ بیرونی.
    broker_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    #: کارمزدِ واسطه، **قفل‌شده در لحظه‌ی ثبت**. مشتق نیست چون
    #: `contacts.commission_rate` نرخِ امروز است و عوض می‌شود؛ این مبلغ بدهیِ همان
    #: فروش است. همان دلیلی که `tax_amount` هم کنارِ `tax_rate` ذخیره می‌شود.
    broker_commission: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")

    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True, index=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    lines: Mapped[list["SalesInvoiceLine"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan", order_by="SalesInvoiceLine.id"
    )


class SalesInvoiceLine(TenantMixin, UUIDPKMixin, Base):
    __tablename__ = "sales_invoice_lines"

    invoice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sales_invoices.id"))
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"))
    qty: Mapped[float] = mapped_column(Numeric(18, 3))
    unit_price: Mapped[float] = mapped_column(Numeric(18, 0))
    #: تخفیفِ این ردیف به مبلغ (نه درصد). خالصِ ردیف = qty×unit_price − discount.
    discount: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    # فقط snapshot کمکی؛ بهای قطعی و COGS روی ردیف خروج انبار قفل می‌شود.
    unit_cost: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    description: Mapped[str] = mapped_column(Text, default="")
    addition: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    duty_amount: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    item_code_snapshot: Mapped[str] = mapped_column(String(50), default="", server_default="")
    item_name_snapshot: Mapped[str] = mapped_column(String(300), default="", server_default="")
    unit_snapshot: Mapped[str] = mapped_column(String(20), default="", server_default="")
    tax_rate_snapshot: Mapped[float] = mapped_column(Numeric(5, 2), default=0, server_default="0")
    tax_amount_snapshot: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    source_quotation_line_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales_quotation_lines.id"), nullable=True, index=True
    )

    #: وضعیتِ مالیاتیِ کالا **در لحظه‌ی فروش** — از `Item.vat_status` کپی می‌شود.
    #:
    #: **چرا کپی و نه خواندنِ کالا:** قانون عوض می‌شود، تاریخ نه. کالایی که امسال
    #: معاف شده، اگر گزارش از وضعیتِ *امروزش* بخواند، فروشِ پارسال را هم معاف نشان
    #: می‌دهد — در حالی که آن فروش واقعاً مشمول بوده. همان استثنای «مقداری که در یک
    #: لحظه قطعی شده» که `tax_amount` هم به همان دلیل کنارِ `tax_rate` ذخیره می‌شود.
    vat_status: Mapped[str] = mapped_column(String(10), default="taxable", server_default="taxable")

    #: نرخ و مبلغِ مالیاتِ **همین ردیف**، قفل‌شده در لحظه‌ی فروش — قرینه‌ی همان دو
    #: ستونی که ردیفِ فاکتورِ خرید از قبل داشت.
    #:
    #: **چرا لازم شد:** مالیات روی جمعِ فاکتور حساب می‌شد، پس ردیفِ معاف هم
    #: مالیات می‌خورد و هیچ‌جا ثبت نمی‌شد که کدام ردیف چقدر مالیات داشته.
    #: بسته‌ی مؤدیان هم نرخِ سرِ فاکتور را روی *هر* ردیف می‌زد — یعنی قلمِ معاف
    #: با مالیات به سازمان اظهار می‌شد.
    tax_rate_snapshot: Mapped[float] = mapped_column(Numeric(5, 2), default=0, server_default="0")
    tax_amount_snapshot: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")

    #: **ردِ قیمت (§۹ §۵۹ §۹۱): این ردیف چرا این نرخ را دارد؟**
    #:
    #: `declared_unit_price` نرخی است که اعلامیه‌ی قیمت *در لحظه‌ی ثبت* داد، و
    #: `price_rule_id` می‌گوید کدام قاعده آن را داد. هر دو snapshotاند — به همان
    #: دلیلِ `tax_rate_snapshot` بالا: بازخواندنِ اعلامیه‌ی **امروز** برای توضیحِ
    #: فاکتورِ پارسال یعنی پیکربندیِ جاری تاریخ را بازنویسی کند (§۹۳).
    #:
    #: و §۶۱ (دست‌کاریِ دستی ≠ قیمت‌گذاریِ دوباره ≠ نگه‌داشتنِ قیمت) با همین دو
    #: ستون **مشتق** می‌شود، نه با یک پرچمِ `price_changed`ِ مبهم:
    #: `unit_price != declared_unit_price` یعنی کاربر عدد را عوض کرده.
    #:
    #: `NULL` یعنی «ردِ نامعلوم» — ردیف‌های پیش از مهاجرتِ ۰۱۲۲، و هر ردیفی که
    #: هیچ قاعده‌ی قیمتی با زمینه‌اش نخوانده باشد.
    declared_unit_price: Mapped[float | None] = mapped_column(Numeric(18, 0), nullable=True)
    price_rule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("price_list_items.id", ondelete="SET NULL"), nullable=True
    )

    invoice: Mapped["SalesInvoice"] = relationship(back_populates="lines")
    item: Mapped["Item"] = relationship()


#: انواعِ رسیدِ انبار (§۲).
#:
#: **یک موتور، چند منشأ (§۳).** پنج جدول و پنج موتورِ انبار نمی‌سازیم؛ یک دامنه
#: با رفتارِ وابسته به نوع.
#:
#: فصل فقط **خریدِ داخلی** را کامل باز می‌کند. برای بقیه از روی *اسمشان*
#: workflow اختراع نمی‌کنیم: نوع ثبت می‌شود و رفتارِ اختصاصی‌اش وقتی می‌آید که
#: فصلِ خودش بیاید.
RECEIPT_TYPES = (
    "purchase_domestic",
    "purchase_import",
    "production",
    "other",
    "opening",
)
RECEIPT_TYPE_LABELS = {
    "purchase_domestic": "خرید (داخلی)",
    "purchase_import": "خرید (وارداتی)",
    "production": "تولید",
    "other": "سایر",
    "opening": "موجودی اول دوره",
}

class WarehouseIssue(TenantMixin, VoidableMixin, UUIDPKMixin, TimestampMixin, Base):
    """خروج فیزیکی مستقل فروش؛ مالک کاهش موجودی و COGS."""

    __tablename__ = "warehouse_issues"
    __table_args__ = (UniqueConstraint("tenant_id", "number", name="uq_warehouse_issues_tenant_number"),)

    number: Mapped[int] = mapped_column(nullable=False, index=True)
    issue_date: Mapped[date_] = mapped_column(Date, default=date_.today)
    sales_invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales_invoices.id"), index=True
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id"))
    status: Mapped[str] = mapped_column(String(20), default="posted", server_default="posted")
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True, index=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    lines: Mapped[list["WarehouseIssueLine"]] = relationship(
        back_populates="issue", cascade="all, delete-orphan", order_by="WarehouseIssueLine.id"
    )


class WarehouseIssueLine(TenantMixin, UUIDPKMixin, Base):
    __tablename__ = "warehouse_issue_lines"
    __table_args__ = (CheckConstraint("qty > 0", name="ck_warehouse_issue_lines_qty_positive"),)

    issue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouse_issues.id", ondelete="CASCADE"), index=True
    )
    sales_invoice_line_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales_invoice_lines.id"), index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"), index=True)
    qty: Mapped[float] = mapped_column(Numeric(18, 3))
    unit_cost: Mapped[float] = mapped_column(Numeric(18, 0))
    item_code_snapshot: Mapped[str] = mapped_column(String(50), default="", server_default="")
    item_name_snapshot: Mapped[str] = mapped_column(String(300), default="", server_default="")
    unit_snapshot: Mapped[str] = mapped_column(String(20), default="", server_default="")
    description: Mapped[str] = mapped_column(Text, default="", server_default="")

    issue: Mapped["WarehouseIssue"] = relationship(back_populates="lines")
    item: Mapped["Item"] = relationship()


class WarehouseReceipt(TenantMixin, VoidableMixin, UUIDPKMixin, TimestampMixin, Base):
    """ورودِ واقعیِ کالا به یک انبار — و در گردشِ خرید، سندِ عملیاتیِ همان ورود.

    **دو مسیرِ معتبر (§۹).** رسید می‌تواند به فاکتورِ خرید گره بخورد، یا مستقیم
    و بدونِ فاکتور ثبت شود. تا امروز فقط مسیرِ اول ممکن بود چون
    `purchase_invoice_id` اجباری بود — یعنی خریدی که فاکتورش بعداً می‌آید (یا
    اصلاً نمی‌آید) هیچ راهی برای ورودِ کالا نداشت.

    **نقطه‌ی ثبتِ حسابداری صریح است (§۳۷).** بدهیِ تأمین‌کننده را *یک* سند
    می‌سازد، نه دو تا:

    * رسیدِ گره‌خورده به فاکتور → فقط حرکتِ فیزیکی. فاکتور بدهی را از قبل
      شناخته و ثبتِ دوباره یعنی حسابِ تأمین‌کننده دو برابر شود.
    * رسیدِ مستقیم → خودش منشأِ مالی است، چون هیچ سندِ دیگری این خرید را
      نمی‌شناسد. نزدنِ سند یعنی کالا بی‌هیچ اثرِ حسابداری وارد انبار شود و
      دفتر با گزارشِ انبار برای همیشه واگرا بماند.
    """

    __tablename__ = "warehouse_receipts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_warehouse_receipts_tenant_number"),
        CheckConstraint(f"receipt_type IN {RECEIPT_TYPES}", name="ck_warehouse_receipts_type"),
        CheckConstraint(
            "freight_basis IN ('equal')", name="ck_warehouse_receipts_freight_basis"
        ),
    )

    number: Mapped[int] = mapped_column(nullable=False, index=True)
    receipt_date: Mapped[date_] = mapped_column(Date, default=date_.today)
    #: §۸ §۹ — **اختیاری.** ارجاع است، نه پیش‌نیاز.
    purchase_invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_invoices.id"), nullable=True, index=True
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id"))
    receipt_type: Mapped[str] = mapped_column(
        String(20), default="purchase_domestic", server_default="purchase_domestic"
    )

    #: **سه نقشِ جدا (§۶ §۷).**
    #:
    #: تحویل‌دهنده طرفِ معامله است (در خریدِ داخلی همان تأمین‌کننده)، حمل‌کننده
    #: کسی است که کالا را آورده، و واسطِ حمل زمینه‌ی مالیِ حمل است. فصل صریح
    #: می‌گوید این سه را در یک فیلدِ `supplier` قاطی نکنیم.
    #:
    #: معنای دقیقِ «واسطِ حمل» را فصل تثبیت نمی‌کند («با قسمت‌های بعدی تثبیت
    #: شود»)، پس این‌جا فقط *ارجاع* نگه داشته می‌شود و هیچ رفتارِ مالی‌ای از
    #: رویش ساخته نمی‌شود.
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=True, index=True
    )
    carrier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=True
    )
    freight_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=True
    )

    #: §۱۳ — ارز و نرخ از موتورِ ارزِ موجود. مبالغِ ردیف‌ها همیشه پایه‌اند؛
    #: این‌ها فقط برای نمایشِ معادل و نرخ‌اند — همان قراردادی که فاکتور دارد.
    currency_code: Mapped[str | None] = mapped_column(String(3), nullable=True)
    exchange_rate: Mapped[float] = mapped_column(Numeric(18, 4), default=1, server_default="1")

    #: **بلوکِ حمل (§۲۱).** «Freight فقط یک Description نیست؛ یک جزء مالیِ
    #: واقعیِ Receipt است.»
    #:
    #: سه مبلغِ جدا، چون سه مقصدِ جدا دارند (§۲۵ §۲۶):
    #:
    #: * `freight_amount` و `freight_duty` → بهای تمام‌شده‌ی ورودِ کالا
    #: * `freight_tax` → اعتبارِ مالیاتی، **نه** بهای کالا
    #:
    #: فصل صریح هشدار می‌دهد: «ایجنت نباید فرض کند Inventory Cost = Price +
    #: Freight + VAT در تمام شرایط.» پس هیچ‌کدام در دیگری حل نمی‌شود و
    #: «جمعِ مبلغِ حمل» از همین سه مشتق می‌شود، نه ذخیره.
    freight_amount: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    freight_tax: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    freight_duty: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    #: §۲۳ — مبنای تسهیم. الگوریتمش در `services/freight.py` است، نه در فرم.
    freight_basis: Mapped[str] = mapped_column(String(20), default="equal", server_default="equal")

    #: §۲۵ — نرخِ مالیاتِ **کالا**های این رسید. فقط در رسیدِ مستقیم ثبت می‌شود؛
    #: رسیدِ گره‌خورده به فاکتور مالیاتش را از فاکتور دارد و ثبتِ دوباره یعنی
    #: اعتبارِ مالیاتی دو برابر شود (§۳۷).
    tax_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=0, server_default="0")

    #: سندِ حسابداریِ این رسید. `NULL` یعنی رسید اثرِ مالی نداشته — یعنی گره
    #: خورده به فاکتوری که خودش بدهی را شناخته است (§۳۷).
    #:
    #: §۴۴: «اثرِ انباری» و «اثرِ حسابداری» دو چیزند و یک بولینِ مبهم نباید
    #: نماینده‌ی هر دو باشد. این ستون دومی را می‌گوید و `status` اولی را.
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True, index=True
    )

    status: Mapped[str] = mapped_column(String(20), default="posted", server_default="posted")
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    description2: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    #: `(seq, id)` و نه `id`: کلید اصلی UUIDِ تصادفی است و مرتب‌کردن بر اساسش
    #: یعنی ردیف‌ها به ترتیبِ ورودِ اپراتور برنگردند — و چاپِ رسید (§۴۱ §۴۲) هر
    #: بار ترتیبِ دیگری بدهد.
    lines: Mapped[list["WarehouseReceiptLine"]] = relationship(
        back_populates="receipt",
        cascade="all, delete-orphan",
        order_by="(WarehouseReceiptLine.seq, WarehouseReceiptLine.id)",
    )

    # ── §۲۵ §۲۷ — اجزای خالص، مشتق و نه ذخیره ────────────────────────────
    #
    # فصل: «کاربر اگر عددِ ۱٬۴۹۵٬۰۰۰ را دید، کوبیتا بتواند نشان دهد
    # ۱٬۴۰۰٬۰۰۰ کالا + ۵۰٬۰۰۰ حمل + ۴۵٬۰۰۰ مالیات — نه اینکه این عدد
    # جداگانه و دستی نگهداری شود.»
    #
    # هیچ‌کدام ستون نیستند. §۴۲ هم همین را می‌خواهد: چاپ مدلِ مالیِ دیگری
    # نیست، از همین اجزا می‌خواند.

    @property
    def goods_amount(self) -> Decimal:
        """«کل» — جمعِ مبلغِ کالاها، پیش از حمل و مالیات."""
        return sum((line.goods_amount for line in self.lines), Decimal(0))

    @property
    def freight_total(self) -> Decimal:
        """«جمع مبلغ حمل» (§۲۱) — جمعِ خودِ پنجره‌ی حمل.

        **این یک جزءِ خالص نیست.** اجزایش جداگانه در «حمل»، «مالیات» و
        «عوارض» شمرده شده‌اند؛ افزودنش به خالص یعنی دوباره‌شماری.
        """
        return Decimal(self.freight_amount) + Decimal(self.freight_tax) + Decimal(self.freight_duty)

    @property
    def tax_amount(self) -> Decimal:
        """«مالیات» — مالیاتِ کالاها به‌علاوه‌ی مالیاتِ حمل.

        §۲۶: این عدد از بهای تمام‌شده‌ی کالا **بیرون** است و عمداً بیرون است.
        """
        return (
            sum((Decimal(line.tax_amount_snapshot) for line in self.lines), Decimal(0))
            + Decimal(self.freight_tax)
        )

    @property
    def duty_amount(self) -> Decimal:
        """«عوارض» — جدا از مالیات، چون مقصدِ حسابداری‌اش فرق دارد (§۲۵)."""
        return Decimal(self.freight_duty)

    @property
    def net_amount(self) -> Decimal:
        """«خالص» (§۲۷) = کالا + حمل + عوارض + مالیات."""
        return (
            self.goods_amount + Decimal(self.freight_amount) + self.duty_amount + self.tax_amount
        )


class WarehouseReceiptLine(TenantMixin, UUIDPKMixin, Base):
    __tablename__ = "warehouse_receipt_lines"

    receipt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouse_receipts.id", ondelete="CASCADE"), index=True
    )
    #: §۹ — در رسیدِ مستقیم ردیفِ مبدأیی وجود ندارد، پس اختیاری است.
    purchase_invoice_line_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_invoice_lines.id"), nullable=True, index=True
    )
    #: شماره‌ی ردیف در همین رسید (از ۱). صفر یعنی «ردیفِ پیش از مهاجرتِ ۰۱۲۸»،
    #: که ترتیبش بازیابی‌شدنی نبود.
    seq: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"), index=True)
    qty: Mapped[float] = mapped_column(Numeric(18, 3))
    #: §۲۰ — **«فی»**، نه «فی تمام‌شده». بهای خریدِ واحد، پیش از حمل.
    unit_cost: Mapped[float] = mapped_column(Numeric(18, 0))

    #: §۲۲ — سهمِ این ردیف از هزینه‌ی حمل، خروجیِ `services/freight.allocate`.
    #:
    #: **چرا ذخیره و نه مشتق:** نتیجه‌ی یک تقسیمِ گِردشده است که ته‌مانده‌اش به
    #: ردیفِ آخر رفته. بازمحاسبه از روی مبلغِ حمل لزوماً همان عدد را نمی‌دهد، و
    #: همین سهم است که در بهای موجودی نشسته — یعنی Snapshot است، نه مشتق.
    freight_share: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")

    #: §۲۵ — مالیاتِ همین ردیف، مستقل و قابلِ ردیابی.
    #:
    #: **در رسیدِ گره‌خورده به فاکتور فقط برای چاپ است.** آن مالیات را فاکتور
    #: شناخته؛ ثبتِ دوباره یعنی اعتبارِ مالیاتی دو برابر شود (§۳۷). این‌جا
    #: می‌نشیند تا «خالص»ِ رسید از اجزای خودش توضیح‌پذیر باشد (§۲۷).
    tax_rate_snapshot: Mapped[float] = mapped_column(Numeric(5, 2), default=0, server_default="0")
    tax_amount_snapshot: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")

    item_code_snapshot: Mapped[str] = mapped_column(String(50), default="", server_default="")
    item_name_snapshot: Mapped[str] = mapped_column(String(300), default="", server_default="")
    unit_snapshot: Mapped[str] = mapped_column(String(20), default="", server_default="")
    description: Mapped[str] = mapped_column(Text, default="", server_default="")

    receipt: Mapped["WarehouseReceipt"] = relationship(back_populates="lines")
    item: Mapped["Item"] = relationship()

    @property
    def goods_amount(self) -> Decimal:
        """مبلغِ کالا — §۱۹: مقدار × فی."""
        return Decimal(self.qty) * Decimal(self.unit_cost)

    @property
    def landed_amount(self) -> Decimal:
        """بهای تمام‌شده‌ی ورود = مبلغِ کالا + سهمِ حمل (§۲۴).

        مالیات این‌جا نیست و عمداً نیست (§۲۶).
        """
        return self.goods_amount + Decimal(self.freight_share)

    @property
    def landed_unit_cost(self) -> Decimal:
        """**«فی تمام‌شده» (§۲۰)** — و این با «فی» یکی نیست.

        نمونه‌ی فصل: فیِ ۵٬۰۰۰ پس از تسهیمِ حمل، فیِ تمام‌شده‌ی ۵٬۲۵۰ می‌شود.

        ذخیره نمی‌شود چون از `unit_cost` و `freight_share` مشتق است — همان
        قاعده‌ی §۲۷ («مشتق بهتر از ذخیره»). عددی که در دفترِ موجودی نشسته
        Snapshotِ خودِ `stock_ledger` است.
        """
        qty = Decimal(self.qty)
        return (self.landed_amount / qty) if qty else Decimal(0)


class PurchaseInvoice(TenantMixin, VoidableMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "purchase_invoices"

    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_purchase_invoices_tenant_number"),
    )

    number: Mapped[int | None] = mapped_column(nullable=True, index=True)
    invoice_date: Mapped[date_] = mapped_column(Date, default=date_.today)
    contact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=True)
    # فقط برای سازگاری فاکتورهای قدیمی؛ ورود فیزیکی از WarehouseReceipt می‌آید.
    warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.id"), nullable=True
    )
    supplier_invoice_number: Mapped[str] = mapped_column(String(80), default="", server_default="")
    #: هویت طرفین در لحظه‌ی ثبت. چاپ سند قطعی نباید با تغییر بعدی Contact یا
    #: تنظیمات مؤدی بازنویسی شود؛ JSONB شکلِ داده را بدون ستون‌های همیشه‌خالی حفظ می‌کند.
    supplier_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    buyer_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    #: مرکز هزینه/پروژه‌ی این فاکتور؛ به ردیف‌های سندش هم منتقل می‌شود. NULL = بدون مرکز.
    cost_center_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cost_centers.id"), nullable=True
    )
    description: Mapped[str] = mapped_column(Text, default="")
    description2: Mapped[str] = mapped_column(String(200), default="", server_default="")

    #: خالصِ **پس از تخفیف** و بدون مالیات.
    total_amount: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    #: جمع تخفیفِ ردیف‌ها (شاملِ سهمِ تسهیم‌شده‌ی تخفیفِ کلِ فاکتور؛ بهای موجودی از
    #: همان اول پس از تخفیف است).
    total_discount: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    #: تخفیفِ کلِ فاکتور که تأمین‌کننده روی سرِ فاکتور داده. هنگام ثبت بینِ ردیف‌ها
    #: تسهیم می‌شود (پس ارزش‌گذاریِ موجودی و اعتبارِ مالیاتی هم پس از آن‌اند)؛ اینجا
    #: فقط برای نمایشِ شفاف جدا نگه داشته می‌شود.
    invoice_discount: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    total_additions: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    total_duties: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    # مالیات بر ارزش افزوده: نرخ درصدی و مبلغِ محاسبه‌شده. مبلغِ پرداختنی به تأمین‌کننده = total_amount + tax_amount
    tax_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=0, server_default="0")
    tax_amount: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")

    #: ارزِ فاکتور. NULL = پایه (ریال). مبالغِ بالا همیشه پایه‌اند؛ این‌ها فقط برای
    #: نمایشِ معادلِ ارزی و نرخ‌اند — دفتر پایه می‌ماند.
    currency_code: Mapped[str | None] = mapped_column(String(3), nullable=True)
    exchange_rate: Mapped[float] = mapped_column(Numeric(18, 4), default=1, server_default="1")

    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True, index=True
    )

    #: **این فاکتور کالا را در «کالای در راه» گذاشته یا مستقیم در انبار؟**
    #:
    #: پرچمِ *سیاستِ ثبت* است، نه وضعیتِ امروز: می‌گوید این سند وقتی زده شد چه
    #: کرد. رسیدِ انبار به آن نگاه می‌کند تا بداند باید طبقه‌بندیِ دوباره بزند
    #: یا نه.
    #:
    #: **چرا ذخیره و نه مشتق:** فاکتورهای پیش از این تغییر مستقیماً «موجودی
    #: کالا» را بدهکار کرده‌اند. اگر رسیدشان حالا دوباره موجودی را بدهکار کند،
    #: موجودیِ دفتری **دو برابر** می‌شود. `False` روی ردیف‌های موجود یعنی
    #: «رسیدت سند نزند» — همان رفتاری که تا امروز داشته‌اند.
    goods_in_transit: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )

    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    lines: Mapped[list["PurchaseInvoiceLine"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan", order_by="PurchaseInvoiceLine.id"
    )


class PurchaseInvoiceLine(TenantMixin, UUIDPKMixin, Base):
    __tablename__ = "purchase_invoice_lines"

    invoice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("purchase_invoices.id"))
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"))
    qty: Mapped[float] = mapped_column(Numeric(18, 3))
    unit_cost: Mapped[float] = mapped_column(Numeric(18, 0))
    #: تخفیفِ این ردیف به مبلغ. خالصِ ردیف = qty×unit_cost − discount.
    discount: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    description: Mapped[str] = mapped_column(Text, default="")

    #: وضعیتِ مالیاتیِ کالا **در لحظه‌ی خرید** — دلیلش همان `SalesInvoiceLine`.
    vat_status: Mapped[str] = mapped_column(String(10), default="taxable", server_default="taxable")

    # snapshot تاریخی؛ تغییر بعدی شناسنامه/واحد کالا فاکتور قدیمی را عوض نمی‌کند.
    item_code_snapshot: Mapped[str] = mapped_column(String(50), default="", server_default="")
    item_name_snapshot: Mapped[str] = mapped_column(String(300), default="", server_default="")
    unit_snapshot: Mapped[str] = mapped_column(String(20), default="", server_default="")
    addition: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    duty_amount: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    tax_rate_snapshot: Mapped[float] = mapped_column(Numeric(5, 2), default=0, server_default="0")
    tax_amount_snapshot: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")

    invoice: Mapped["PurchaseInvoice"] = relationship(back_populates="lines")
    item: Mapped["Item"] = relationship()
