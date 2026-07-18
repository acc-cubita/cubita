import uuid
from datetime import date as date_

from sqlalchemy import Date, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin


class FiscalPeriodClose(UUIDPKMixin, TimestampMixin, Base):
    """بستن رسمی دوره مالی: از closing_date به قبل هیچ سند حسابداری جدیدی قابل ثبت نیست.
    سند بستن، حساب‌های درآمد/هزینه‌ی همان بازه را صفر و سود/زیان خالص را به سود انباشته منتقل می‌کند."""

    __tablename__ = "fiscal_period_closes"

    closing_date: Mapped[date_] = mapped_column(Date, unique=True)
    net_profit: Mapped[float] = mapped_column(Numeric(18, 0))
    notes: Mapped[str] = mapped_column(Text, default="")

    journal_entry_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("journal_entries.id"))
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
