import uuid
from datetime import date as date_

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin

#: تناوب‌های پشتیبانی‌شده. فاصله (interval) روی هرکدام ضرب می‌شود: مثلاً monthly×۲ = هر دو ماه.
RECURRING_FREQUENCIES = ("weekly", "monthly", "yearly")


class RecurringJournalEntry(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """قالبِ یک سندِ حسابداریِ دوره‌ای.

    `next_run_date` سررسیدِ بعدی است و تنها منبعِ حقیقت برای «چه چیزی هنوز ساخته
    نشده». تولید بر اساس تقاضاست: با هر اجرا همه‌ی سررسیدهای گذشته تا امروز ساخته
    می‌شوند و این تاریخ جلو می‌رود؛ چون ذخیره می‌شود، اجرای دوباره سندِ تکراری
    نمی‌سازد. سررسیدی که در دوره‌ی مالیِ بسته بیفتد ساخته نمی‌شود ولی تاریخ باز هم
    جلو می‌رود تا قالب گیر نکند.
    """

    __tablename__ = "recurring_journal_entries"

    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    frequency: Mapped[str] = mapped_column(String(20))
    interval: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    start_date: Mapped[date_] = mapped_column(Date)
    end_date: Mapped[date_ | None] = mapped_column(Date, nullable=True)
    next_run_date: Mapped[date_] = mapped_column(Date)
    last_run_date: Mapped[date_ | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    cost_center_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cost_centers.id"), nullable=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    lines: Mapped[list["RecurringJournalLine"]] = relationship(
        "RecurringJournalLine", back_populates="recurring", cascade="all, delete-orphan"
    )


class RecurringJournalLine(TenantMixin, UUIDPKMixin, Base):
    """یک ردیفِ ثابت از قالبِ سندِ دوره‌ای — حساب و مبلغِ بدهکار/بستانکار."""

    __tablename__ = "recurring_journal_lines"

    recurring_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recurring_journal_entries.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id"))
    debit: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    credit: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    description: Mapped[str] = mapped_column(Text, default="", server_default="")

    recurring: Mapped["RecurringJournalEntry"] = relationship("RecurringJournalEntry", back_populates="lines")
    account: Mapped["object"] = relationship("Account")
