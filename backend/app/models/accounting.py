import uuid
from datetime import date as date_

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin

ACCOUNT_TYPES = ("asset", "liability", "equity", "income", "expense")


class Account(UUIDPKMixin, TimestampMixin, Base):
    """یک گره در چارت حساب‌ها. is_group=True یعنی سرفصل (فقط برای دسته‌بندی)، نه ثبت سند مستقیم روی آن."""

    __tablename__ = "accounts"
    __table_args__ = (CheckConstraint(f"type IN {ACCOUNT_TYPES}", name="ck_accounts_type"),)

    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(20))
    is_group: Mapped[bool] = mapped_column(default=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=True
    )

    parent: Mapped["Account | None"] = relationship(remote_side="Account.id", back_populates="children")
    children: Mapped[list["Account"]] = relationship(back_populates="parent")


class JournalEntry(UUIDPKMixin, TimestampMixin, Base):
    """سند حسابداری: واحد اتمی هر رویداد مالی. دفتر روزنامه/کل/تراز همه از JournalLine مشتق می‌شوند."""

    __tablename__ = "journal_entries"

    number: Mapped[int | None] = mapped_column(nullable=True, unique=True, index=True)  # شماره رسمی، فقط سرور اختصاص می‌دهد
    entry_date: Mapped[date_] = mapped_column(Date, default=date_.today)
    description: Mapped[str] = mapped_column(Text, default="")

    # منشأ سند: مثلاً "sales_invoice" / "manual" / "payroll" برای ردیابی این‌که کدام ماژول این سند را خودکار ساخته
    source_type: Mapped[str] = mapped_column(String(50), default="manual")
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    lines: Mapped[list["JournalLine"]] = relationship(
        back_populates="entry", cascade="all, delete-orphan", order_by="JournalLine.id"
    )


class JournalLine(UUIDPKMixin, Base):
    __tablename__ = "journal_lines"
    __table_args__ = (
        CheckConstraint("debit >= 0 AND credit >= 0", name="ck_journal_lines_nonnegative"),
        CheckConstraint("NOT (debit > 0 AND credit > 0)", name="ck_journal_lines_one_sided"),
    )

    entry_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("journal_entries.id"))
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id"))

    debit: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    credit: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    description: Mapped[str] = mapped_column(Text, default="")

    entry: Mapped["JournalEntry"] = relationship(back_populates="lines")
    account: Mapped["Account"] = relationship()
