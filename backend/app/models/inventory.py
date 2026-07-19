import uuid
from datetime import date as date_

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Numeric,
    Sequence,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin

CONTACT_TYPES = ("customer", "supplier", "both")


class Warehouse(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "warehouses"

    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_warehouses_tenant_code"),
    )

    code: Mapped[str] = mapped_column(String(20), index=True)
    name: Mapped[str] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Contact(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """طرف حساب: مشتری، تأمین‌کننده یا هر دو."""

    __tablename__ = "contacts"
    __table_args__ = (CheckConstraint(f"type IN {CONTACT_TYPES}", name="ck_contacts_type"),)

    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(20), default="customer")
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    address: Mapped[str] = mapped_column(Text, default="")
    tax_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Item(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """کالا یا خدمت. average_cost فقط برای کالا به‌روزرسانی می‌شود (روش میانگین موزون)."""

    __tablename__ = "items"

    __table_args__ = (
        UniqueConstraint("tenant_id", "sku", name="uq_items_tenant_sku"),
    )

    sku: Mapped[str] = mapped_column(String(50), index=True)
    name: Mapped[str] = mapped_column(String(300))
    category: Mapped[str] = mapped_column(String(100), default="")
    unit: Mapped[str] = mapped_column(String(20), default="عدد")
    is_service: Mapped[bool] = mapped_column(Boolean, default=False)
    sales_price: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    average_cost: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # نگاشت به کالای متناظر روی سایت فروشگاهی (ipnetcity.ir) برای فاز Integration
    storefront_product_id: Mapped[int | None] = mapped_column(nullable=True)


class StockLedger(TenantMixin, UUIDPKMixin, Base):
    """دفتر موجودی: هر رکورد یک حرکت ورود(+)/خروج(-) است. موجودی فعلی = SUM(qty) به تفکیک کالا/انبار."""

    __tablename__ = "stock_ledger"

    #: ترتیب قطعیِ ثبت. کلید اصلی UUID تصادفی است و مرتب کردن بر اساسش بی‌معناست،
    #: و `entry_date` فقط روز را دارد — پس چند حرکت در یک روز هیچ ترتیب مشخصی
    #: ندارند. برای موجودی (که جمع ساده است) مهم نیست، ولی بهای تمام‌شده‌ی میانگین
    #: موزون به ترتیب وابسته است: خرید-فروش-خرید عدد متفاوتی از خرید-خرید-فروش
    #: می‌دهد. بدون این ستون، بازمحاسبه هر بار می‌توانست عدد دیگری بدهد.
    #:
    #: ایندکس عمداً یکتا نیست: خودِ SEQUENCE تضمین می‌کند مقدار تکراری صادر نشود، و
    #: یکتای سراسری روی جدول مستأجرمحور دقیقاً همان الگویی است که تست انحراف
    #: (به‌درستی) رد می‌کند.
    seq: Mapped[int] = mapped_column(
        BigInteger, Sequence("stock_ledger_seq"), nullable=False, index=True
    )

    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"), index=True)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id"), index=True)
    qty: Mapped[float] = mapped_column(Numeric(18, 3))
    unit_cost: Mapped[float] = mapped_column(Numeric(18, 0))
    entry_date: Mapped[date_] = mapped_column(Date, default=date_.today)

    source_type: Mapped[str] = mapped_column(String(50))  # sales_invoice | purchase_invoice | adjustment
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    item: Mapped["Item"] = relationship()
    warehouse: Mapped["Warehouse"] = relationship()


class StockAdjustment(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """انبارگردانی/تعدیل موجودی دستی (کسری یا اضافی) با سند حسابداری خودکار متناظر."""

    __tablename__ = "stock_adjustments"

    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"))
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id"))
    qty_diff: Mapped[float] = mapped_column(Numeric(18, 3))  # مثبت = اضافه‌شدن به موجودی، منفی = کسری
    unit_cost: Mapped[float] = mapped_column(Numeric(18, 0))  # از average_cost کالا در لحظه‌ی ثبت snapshot می‌شود
    reason: Mapped[str] = mapped_column(Text, default="")
    adjustment_date: Mapped[date_] = mapped_column(Date, default=date_.today)

    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    item: Mapped["Item"] = relationship()
    warehouse: Mapped["Warehouse"] = relationship()
