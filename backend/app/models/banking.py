import uuid
from datetime import date as date_
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin

if TYPE_CHECKING:
    from app.models.inventory import Contact

CHECK_TYPES = ("receivable", "payable")
CHECK_STATUSES = ("in_hand", "deposited", "cleared", "bounced", "endorsed", "issued")
PETTY_CASH_TYPES = ("charge", "expense")


class BankAccount(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "bank_accounts"

    name: Mapped[str] = mapped_column(String(200))
    bank_name: Mapped[str] = mapped_column(String(100), default="")
    account_number: Mapped[str] = mapped_column(String(50), default="")
    iban: Mapped[str] = mapped_column(String(34), default="")
    # حساب دفتر کل متناظر (پیش‌فرض «۱۱۰۲ بانک»)؛ امکان تفکیک حساب معین جداگانه در آینده باقی می‌ماند
    gl_account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Check(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """چک دریافتنی/پرداختنی. چرخه‌ی وضعیت در app/services/banking.py مدیریت و سند حسابداری متناظر می‌سازد."""

    __tablename__ = "checks"
    __table_args__ = (
        CheckConstraint(f"type IN {CHECK_TYPES}", name="ck_checks_type"),
        CheckConstraint(f"status IN {CHECK_STATUSES}", name="ck_checks_status"),
    )

    type: Mapped[str] = mapped_column(String(20))
    number: Mapped[str] = mapped_column(String(50))
    bank_name: Mapped[str] = mapped_column(String(100), default="")
    amount: Mapped[float] = mapped_column(Numeric(18, 0))
    issue_date: Mapped[date_] = mapped_column(Date)
    due_date: Mapped[date_] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(Text, default="")

    contact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=True)
    bank_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bank_accounts.id"), nullable=True
    )

    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    contact: Mapped["Contact | None"] = relationship("Contact")
    bank_account: Mapped["BankAccount | None"] = relationship("BankAccount")


class BankTransaction(TenantMixin, UUIDPKMixin, Base):
    """واریز(+)/برداشت(-) در یک حساب بانکی؛ برای تطبیق بانکی، is_reconciled بعداً علامت زده می‌شود."""

    __tablename__ = "bank_transactions"

    bank_account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("bank_accounts.id"))
    transaction_date: Mapped[date_] = mapped_column(Date, default=date_.today)
    amount: Mapped[float] = mapped_column(Numeric(18, 0))  # مثبت = واریز، منفی = برداشت
    description: Mapped[str] = mapped_column(Text, default="")
    is_reconciled: Mapped[bool] = mapped_column(Boolean, default=False)

    source_type: Mapped[str] = mapped_column(String(50), default="manual")  # manual | check_clear
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))


class BankStatementLine(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """یک ردیف واردشده از صورت‌حساب رسمی بانک؛ برای تطبیق با BankTransaction ثبت‌شده در سیستم."""

    __tablename__ = "bank_statement_lines"

    bank_account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("bank_accounts.id"))
    line_date: Mapped[date_] = mapped_column(Date)
    amount: Mapped[float] = mapped_column(Numeric(18, 0))  # مثبت = واریز، منفی = برداشت (مطابق صورت‌حساب بانک)
    description: Mapped[str] = mapped_column(Text, default="")

    # وقتی با یک BankTransaction سیستم تطبیق داده شود، اینجا و is_reconciled آن تراکنش هر دو ست می‌شوند
    matched_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bank_transactions.id"), nullable=True
    )


class PettyCashTransaction(TenantMixin, UUIDPKMixin, Base):
    """شارژ/هزینه‌کرد تنخواه‌گردان (یک صندوق تنخواه واحد در فاز ۳؛ چندصندوقی می‌تواند فاز بعد باشد)."""

    __tablename__ = "petty_cash_transactions"
    __table_args__ = (CheckConstraint(f"type IN {PETTY_CASH_TYPES}", name="ck_petty_cash_type"),)

    type: Mapped[str] = mapped_column(String(20))
    transaction_date: Mapped[date_] = mapped_column(Date, default=date_.today)
    amount: Mapped[float] = mapped_column(Numeric(18, 0))
    description: Mapped[str] = mapped_column(Text, default="")

    # برای شارژ: از کجا تأمین شد (صندوق/بانک). برای هزینه: بابت کدام حساب هزینه.
    counter_account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id"))

    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
