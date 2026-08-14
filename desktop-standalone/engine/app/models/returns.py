import uuid
from datetime import date as date_

from sqlalchemy import Date, ForeignKey, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin


class SalesReturn(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
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
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    lines: Mapped[list["SalesReturnLine"]] = relationship(
        back_populates="return_", cascade="all, delete-orphan", order_by="SalesReturnLine.id"
    )


class SalesReturnLine(TenantMixin, UUIDPKMixin, Base):
    __tablename__ = "sales_return_lines"

    return_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sales_returns.id"))
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"))
    qty: Mapped[float] = mapped_column(Numeric(18, 3))
    unit_price: Mapped[float] = mapped_column(Numeric(18, 0))
    unit_cost: Mapped[float] = mapped_column(Numeric(18, 0))
    description: Mapped[str] = mapped_column(Text, default="")

    return_: Mapped["SalesReturn"] = relationship(back_populates="lines")
    item: Mapped["Item"] = relationship()


class PurchaseReturn(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
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
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    lines: Mapped[list["PurchaseReturnLine"]] = relationship(
        back_populates="return_", cascade="all, delete-orphan", order_by="PurchaseReturnLine.id"
    )


class PurchaseReturnLine(TenantMixin, UUIDPKMixin, Base):
    __tablename__ = "purchase_return_lines"

    return_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("purchase_returns.id"))
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"))
    qty: Mapped[float] = mapped_column(Numeric(18, 3))
    unit_cost: Mapped[float] = mapped_column(Numeric(18, 0))
    description: Mapped[str] = mapped_column(Text, default="")

    return_: Mapped["PurchaseReturn"] = relationship(back_populates="lines")
    item: Mapped["Item"] = relationship()
