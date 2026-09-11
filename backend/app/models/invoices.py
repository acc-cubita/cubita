import uuid
from datetime import date as date_
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
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
    )

    number: Mapped[int | None] = mapped_column(nullable=True, index=True)
    invoice_date: Mapped[date_] = mapped_column(Date, default=date_.today)
    contact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=True)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id"))
    #: مرکز هزینه/پروژه‌ی این فاکتور؛ به ردیف‌های سندش هم منتقل می‌شود. NULL = بدون مرکز.
    cost_center_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cost_centers.id"), nullable=True
    )
    description: Mapped[str] = mapped_column(Text, default="")

    #: خالصِ **پس از تخفیف** و بدون مالیات. پایه‌ی ثبتِ درآمد و محاسبه‌ی مالیات.
    total_amount: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    #: جمع تخفیفِ ردیف‌ها (شاملِ سهمِ تسهیم‌شده‌ی تخفیفِ کلِ فاکتور). فقط برای
    #: نمایش/صورتحساب مؤدیان؛ در سند حسابداری نمی‌آید چون درآمد از همان اول به مبلغِ
    #: پس از تخفیف ثبت می‌شود (تخفیف تجاری).
    total_discount: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    #: تخفیفِ کلِ فاکتور که کاربر روی سرِ فاکتور اعمال کرده. هنگام ثبت به‌نسبتِ خالصِ
    #: هر ردیف بینِ ردیف‌ها تسهیم می‌شود (پس در total_discount هم منظور شده)؛ اینجا
    #: فقط برای نمایشِ شفافِ «چه مقدار از تخفیف، تخفیفِ کل بوده» جدا نگه داشته می‌شود.
    invoice_discount: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
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
    unit_cost: Mapped[float] = mapped_column(Numeric(18, 0))  # بهای تمام‌شده در لحظه‌ی فروش (برای COGS)
    description: Mapped[str] = mapped_column(Text, default="")

    #: وضعیتِ مالیاتیِ کالا **در لحظه‌ی فروش** — از `Item.vat_status` کپی می‌شود.
    #:
    #: **چرا کپی و نه خواندنِ کالا:** قانون عوض می‌شود، تاریخ نه. کالایی که امسال
    #: معاف شده، اگر گزارش از وضعیتِ *امروزش* بخواند، فروشِ پارسال را هم معاف نشان
    #: می‌دهد — در حالی که آن فروش واقعاً مشمول بوده. همان استثنای «مقداری که در یک
    #: لحظه قطعی شده» که `tax_amount` هم به همان دلیل کنارِ `tax_rate` ذخیره می‌شود.
    vat_status: Mapped[str] = mapped_column(String(10), default="taxable", server_default="taxable")

    invoice: Mapped["SalesInvoice"] = relationship(back_populates="lines")
    item: Mapped["Item"] = relationship()


class WarehouseReceipt(TenantMixin, VoidableMixin, UUIDPKMixin, TimestampMixin, Base):
    """رسید مستقل ورود فیزیکی؛ یک فاکتور می‌تواند چند رسید جزئی داشته باشد."""

    __tablename__ = "warehouse_receipts"
    __table_args__ = (UniqueConstraint("tenant_id", "number", name="uq_warehouse_receipts_tenant_number"),)

    number: Mapped[int] = mapped_column(nullable=False, index=True)
    receipt_date: Mapped[date_] = mapped_column(Date, default=date_.today)
    purchase_invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_invoices.id"), index=True
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id"))
    status: Mapped[str] = mapped_column(String(20), default="posted", server_default="posted")
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    lines: Mapped[list["WarehouseReceiptLine"]] = relationship(
        back_populates="receipt", cascade="all, delete-orphan", order_by="WarehouseReceiptLine.id"
    )


class WarehouseReceiptLine(TenantMixin, UUIDPKMixin, Base):
    __tablename__ = "warehouse_receipt_lines"

    receipt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouse_receipts.id", ondelete="CASCADE"), index=True
    )
    purchase_invoice_line_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_invoice_lines.id"), index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"), index=True)
    qty: Mapped[float] = mapped_column(Numeric(18, 3))
    unit_cost: Mapped[float] = mapped_column(Numeric(18, 0))
    item_code_snapshot: Mapped[str] = mapped_column(String(50), default="", server_default="")
    item_name_snapshot: Mapped[str] = mapped_column(String(300), default="", server_default="")
    unit_snapshot: Mapped[str] = mapped_column(String(20), default="", server_default="")
    description: Mapped[str] = mapped_column(Text, default="", server_default="")

    receipt: Mapped["WarehouseReceipt"] = relationship(back_populates="lines")
    item: Mapped["Item"] = relationship()


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
