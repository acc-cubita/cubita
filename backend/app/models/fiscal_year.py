"""سالِ مالی — دوره‌ی رسمیِ حسابداریِ کسب‌وکار.

تا پیش از این، سیستم فقط «بستنِ دوره» را می‌شناخت (`fiscal_period_closes`): یک قفلِ
تاریخی که جلوی ثبتِ سند در گذشته را می‌گیرد. ولی خودِ *دوره* هیچ‌جا تعریف نشده بود —
نه ابتدایی داشت، نه نامی، نه وضعیتی. این جدول همان تعریفِ گم‌شده است: هر ردیف یک سالِ
مالی با بازه‌ی مشخص، وضعیت (باز/بسته)، و پیوند به سندِ افتتاحیه و سندِ اختتامیه‌اش.

بازه‌ها **نباید هم‌پوشانی داشته باشند** و در هر لحظه فقط یک سال «جاری» است؛ هر دو در
سرویس تضمین می‌شوند (نه با قیدِ دیتابیس، چون هم‌پوشانی به مقایسه‌ی بازه‌ای نیاز دارد).
"""
import uuid
from datetime import date as date_, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin

#: وضعیت‌های ممکنِ یک سالِ مالی.
STATUS_OPEN = "open"
STATUS_CLOSED = "closed"


class FiscalYear(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "fiscal_years"

    __table_args__ = (
        UniqueConstraint("tenant_id", "title", name="uq_fiscal_years_tenant_title"),
    )

    title: Mapped[str] = mapped_column(String(60))
    start_date: Mapped[date_] = mapped_column(Date)
    end_date: Mapped[date_] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(10), default=STATUS_OPEN)
    #: سالِ «جاری» — پیش‌فرضِ تاریخِ فرم‌ها و مرجعِ گزارش‌های دوره‌ای. همیشه حداکثر یکی.
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str] = mapped_column(Text, default="")

    #: سندِ افتتاحیه — مانده‌های منتقل‌شده از سالِ قبل (اگر انتقال انجام شده باشد).
    opening_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True
    )
    #: سندِ اختتامیه — بستنِ حساب‌های موقت (اگر سال فعالیتی داشته باشد).
    closing_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
