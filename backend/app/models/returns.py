import uuid
from datetime import date as date_

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin, VoidableMixin
from app.models.tenant import TenantMixin


class SalesReturnReason(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """علتِ برگشتِ کالا — مِسترِ مستقل، نه متنِ آزاد.

    **چرا جدول و نه یک `String` روی ردیف:** «خرابی»، «خراب بود»، «کالا خراب» سه
    نوشته‌ی یک علت‌اند. با متنِ آزاد، گزارشِ «برگشت به تفکیکِ علت» هیچ‌وقت ساخته
    نمی‌شود چون هیچ دو ردیفی با هم جمع نمی‌شوند. با مِستر، همان گزارش بدونِ
    تغییرِ مدلِ تراکنش در می‌آید.

    `is_active` غیرفعال می‌کند ولی حذف نمی‌کند: علتِ غیرفعال در انتخابِ تازه
    نمی‌آید ولی روی برگشت‌های تاریخی همچنان دیده می‌شود — وگرنه سندِ پارسال با
    یک تصمیمِ امروز بی‌علت می‌شد.
    """

    __tablename__ = "sales_return_reasons"

    __table_args__ = (
        UniqueConstraint("tenant_id", "title", name="uq_sales_return_reasons_tenant_title"),
    )

    title: Mapped[str] = mapped_column(String(120))
    #: عنوانِ دوم (لاتین یا نامِ جایگزین) — همان الگویی که فرمِ مرجع نشان می‌دهد.
    title2: Mapped[str] = mapped_column(String(120), default="", server_default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class SalesReturn(TenantMixin, VoidableMixin, UUIDPKMixin, TimestampMixin, Base):
    """برگشت از فروش: بازگشت کالا از مشتری بابت یک فاکتور فروش مشخص. موجودی برمی‌گردد و درآمد/بهای تمام‌شده معکوس می‌شود."""

    __tablename__ = "sales_returns"

    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_sales_returns_tenant_number"),
    )

    number: Mapped[int | None] = mapped_column(nullable=True, index=True)
    return_date: Mapped[date_] = mapped_column(Date, default=date_.today)
    sales_invoice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sales_invoices.id"))
    description: Mapped[str] = mapped_column(Text, default="")

    total_amount: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    total_cost: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    # مالیاتِ برگشتی — با همان نرخِ فاکتورِ اصلی. مبلغِ بازگرداندنی به مشتری = total_amount + tax_amount
    tax_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=0, server_default="0")
    tax_amount: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")

    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True, index=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    lines: Mapped[list["SalesReturnLine"]] = relationship(
        back_populates="return_", cascade="all, delete-orphan", order_by="SalesReturnLine.id"
    )


class SalesReturnLine(TenantMixin, UUIDPKMixin, Base):
    __tablename__ = "sales_return_lines"

    return_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sales_returns.id"))
    #: **ردیفِ فاکتورِ مبدأ.** بدونِ این، برگشت فقط می‌دانست «کدام کالا» و نه «کدام
    #: ردیف» — پس فاکتوری با دو ردیفِ یک کالا به دو قیمت، میانگین می‌گرفت و
    #: مشتری چیزی پس می‌گرفت که هرگز نپرداخته بود.
    #:
    #: nullable است چون ردیف‌های پیش از مهاجرتِ ۰۱۲۱ آن را ندارند و مهاجرت روی
    #: جدولِ RLS‌دار `UPDATE` نمی‌زند. `NULL` یعنی «کالا-محورِ قدیمی»، و
    #: `_drain_legacy` در سرویس مقدارشان را از استخرِ همان کالا کم می‌کند.
    sales_invoice_line_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales_invoice_lines.id"), nullable=True, index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"))
    qty: Mapped[float] = mapped_column(Numeric(18, 3))
    unit_price: Mapped[float] = mapped_column(Numeric(18, 0))
    unit_cost: Mapped[float] = mapped_column(Numeric(18, 0))
    #: علتِ برگشت — **جدا از `description`**. یکی بُعدِ گزارش است و دیگری یادداشتِ
    #: آزادِ همین ردیف؛ یکی‌کردنشان هر دو را بی‌مصرف می‌کند.
    return_reason_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales_return_reasons.id"), nullable=True, index=True
    )
    description: Mapped[str] = mapped_column(Text, default="")

    return_: Mapped["SalesReturn"] = relationship(back_populates="lines")
    item: Mapped["Item"] = relationship()
    reason: Mapped["SalesReturnReason"] = relationship()


class PurchaseReturn(TenantMixin, VoidableMixin, UUIDPKMixin, TimestampMixin, Base):
    """برگشت از خرید: بازگشت کالا به تأمین‌کننده بابت یک فاکتور خرید مشخص."""

    __tablename__ = "purchase_returns"

    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_purchase_returns_tenant_number"),
    )

    number: Mapped[int | None] = mapped_column(nullable=True, index=True)
    return_date: Mapped[date_] = mapped_column(Date, default=date_.today)
    purchase_invoice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("purchase_invoices.id"))
    description: Mapped[str] = mapped_column(Text, default="")

    total_amount: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    # مالیاتِ برگشتی — با همان نرخِ فاکتورِ اصلی. مبلغِ بازپس‌گرفتنی از تأمین‌کننده = total_amount + tax_amount
    tax_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=0, server_default="0")
    tax_amount: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")

    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True, index=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    lines: Mapped[list["PurchaseReturnLine"]] = relationship(
        back_populates="return_", cascade="all, delete-orphan", order_by="PurchaseReturnLine.id"
    )


class PurchaseReturnLine(TenantMixin, UUIDPKMixin, Base):
    __tablename__ = "purchase_return_lines"

    return_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("purchase_returns.id"))
    #: قرینه‌ی `SalesReturnLine.sales_invoice_line_id` — همان دلیل، همان قاعده‌ی `NULL`.
    purchase_invoice_line_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_invoice_lines.id"), nullable=True, index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"))
    qty: Mapped[float] = mapped_column(Numeric(18, 3))
    unit_cost: Mapped[float] = mapped_column(Numeric(18, 0))
    description: Mapped[str] = mapped_column(Text, default="")

    return_: Mapped["PurchaseReturn"] = relationship(back_populates="lines")
    item: Mapped["Item"] = relationship()
