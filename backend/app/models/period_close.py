import uuid
from datetime import date as date_

from sqlalchemy import Date, ForeignKey, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin


class FiscalPeriodClose(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """بستن رسمی دوره مالی: از closing_date به قبل هیچ سند حسابداری جدیدی قابل ثبت نیست.
    سند بستن، حساب‌های درآمد/هزینه‌ی همان بازه را صفر و سود/زیان خالص را به سود انباشته منتقل می‌کند."""

    __tablename__ = "fiscal_period_closes"

    __table_args__ = (
        UniqueConstraint("tenant_id", "closing_date", name="uq_fiscal_period_closes_tenant_closing_date"),
    )

    closing_date: Mapped[date_] = mapped_column(Date)
    net_profit: Mapped[float] = mapped_column(Numeric(18, 0))
    notes: Mapped[str] = mapped_column(Text, default="")

    journal_entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), index=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
