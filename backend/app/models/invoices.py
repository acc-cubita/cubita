import uuid
from datetime import date as date_

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin


class SalesInvoice(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "sales_invoices"

    number: Mapped[int | None] = mapped_column(nullable=True, unique=True, index=True)
    invoice_date: Mapped[date_] = mapped_column(Date, default=date_.today)
    contact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=True)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id"))
    description: Mapped[str] = mapped_column(Text, default="")

    total_amount: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    total_cost: Mapped[float] = mapped_column(Numeric(18, 0), default=0)

    # شناسه‌ی سفارش روی سایت فروشگاهی؛ برای idempotent بودن sync (جلوگیری از وارد کردن دوباره‌ی همان سفارش)
    source_order_id: Mapped[int | None] = mapped_column(unique=True, nullable=True, index=True)

    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    lines: Mapped[list["SalesInvoiceLine"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan", order_by="SalesInvoiceLine.id"
    )


class SalesInvoiceLine(UUIDPKMixin, Base):
    __tablename__ = "sales_invoice_lines"

    invoice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sales_invoices.id"))
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"))
    qty: Mapped[float] = mapped_column(Numeric(18, 3))
    unit_price: Mapped[float] = mapped_column(Numeric(18, 0))
    unit_cost: Mapped[float] = mapped_column(Numeric(18, 0))  # بهای تمام‌شده در لحظه‌ی فروش (برای COGS)
    description: Mapped[str] = mapped_column(Text, default="")

    invoice: Mapped["SalesInvoice"] = relationship(back_populates="lines")
    item: Mapped["Item"] = relationship()


class PurchaseInvoice(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "purchase_invoices"

    number: Mapped[int | None] = mapped_column(nullable=True, unique=True, index=True)
    invoice_date: Mapped[date_] = mapped_column(Date, default=date_.today)
    contact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=True)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id"))
    description: Mapped[str] = mapped_column(Text, default="")

    total_amount: Mapped[float] = mapped_column(Numeric(18, 0), default=0)

    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    lines: Mapped[list["PurchaseInvoiceLine"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan", order_by="PurchaseInvoiceLine.id"
    )


class PurchaseInvoiceLine(UUIDPKMixin, Base):
    __tablename__ = "purchase_invoice_lines"

    invoice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("purchase_invoices.id"))
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"))
    qty: Mapped[float] = mapped_column(Numeric(18, 3))
    unit_cost: Mapped[float] = mapped_column(Numeric(18, 0))
    description: Mapped[str] = mapped_column(Text, default="")

    invoice: Mapped["PurchaseInvoice"] = relationship(back_populates="lines")
    item: Mapped["Item"] = relationship()
