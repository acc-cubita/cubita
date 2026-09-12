import uuid
from datetime import date as date_, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin

QUOTATION_STATUSES = ("draft", "sent", "accepted", "rejected", "converted")


class SalesQuotation(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """پیش‌فاکتور فروش: پیشنهاد قیمت به مشتری، بدون اثر مالی یا انبار تا زمانی که به فاکتور تبدیل شود."""

    __tablename__ = "sales_quotations"
    __table_args__ = (
        CheckConstraint(f"status IN {QUOTATION_STATUSES}", name="ck_sales_quotations_status"),
        UniqueConstraint("tenant_id", "number", name="uq_sales_quotations_tenant_number"),
    )

    number: Mapped[int | None] = mapped_column(nullable=True, index=True)
    quotation_date: Mapped[date_] = mapped_column(Date, default=date_.today)
    valid_until: Mapped[date_ | None] = mapped_column(Date, nullable=True)
    contact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=True)
    #: نامِ مشتریِ دستی — وقتی مشتری از فهرستِ اشخاص انتخاب نشده و آزادانه تایپ شده.
    #: نمایش/چاپِ پیش‌فاکتور = نامِ طرف‌حساب (اگر contact_id باشد) وگرنه همین.
    customer_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    warehouse_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id"), nullable=True)
    customer_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    customer_name2: Mapped[str] = mapped_column(String(200), default="", server_default="")
    delivery_location: Mapped[str] = mapped_column(Text, default="", server_default="")
    sale_type_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sale_types.id", ondelete="SET NULL"), nullable=True)
    currency_code: Mapped[str | None] = mapped_column(String(3), nullable=True)
    exchange_rate: Mapped[float] = mapped_column(Numeric(18, 4), default=1, server_default="1")
    terminated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    terminated_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="draft")

    total_amount: Mapped[float] = mapped_column(Numeric(18, 0), default=0)

    # وقتی به فاکتور قطعی تبدیل شود، پیوند به همان فاکتور نگه داشته می‌شود (برای جلوگیری از تبدیل دوباره)
    converted_invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales_invoices.id"), nullable=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    lines: Mapped[list["SalesQuotationLine"]] = relationship(
        back_populates="quotation", cascade="all, delete-orphan", order_by="SalesQuotationLine.id"
    )


class SalesQuotationLine(TenantMixin, UUIDPKMixin, Base):
    __tablename__ = "sales_quotation_lines"

    quotation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sales_quotations.id"))
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"))
    qty: Mapped[float] = mapped_column(Numeric(18, 3))
    unit_price: Mapped[float] = mapped_column(Numeric(18, 0))
    description: Mapped[str] = mapped_column(Text, default="")
    item_code_snapshot: Mapped[str] = mapped_column(String(50), default="", server_default="")
    item_name_snapshot: Mapped[str] = mapped_column(String(300), default="", server_default="")
    unit_snapshot: Mapped[str] = mapped_column(String(20), default="", server_default="")

    quotation: Mapped["SalesQuotation"] = relationship(back_populates="lines")
    item: Mapped["Item"] = relationship()
