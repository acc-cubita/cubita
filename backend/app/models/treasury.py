import uuid
from datetime import date as date_
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin

if TYPE_CHECKING:
    from app.models.inventory import Contact

TREASURY_TYPES = ("receipt", "payment")
TREASURY_METHODS = ("cash", "bank")


class TreasuryTransaction(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """دریافت از مشتری یا پرداخت به تأمین‌کننده — تسویه‌ی حساب‌های دریافتنی/پرداختنی با سند خودکار."""

    __tablename__ = "treasury_transactions"
    __table_args__ = (
        CheckConstraint(f"type IN {TREASURY_TYPES}", name="ck_treasury_transactions_type"),
        CheckConstraint(f"method IN {TREASURY_METHODS}", name="ck_treasury_transactions_method"),
        CheckConstraint("amount > 0", name="ck_treasury_transactions_amount_positive"),
    )

    type: Mapped[str] = mapped_column(String(20))  # receipt = دریافت از مشتری | payment = پرداخت به تأمین‌کننده
    transaction_date: Mapped[date_] = mapped_column(Date, default=date_.today)
    contact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("contacts.id"))
    amount: Mapped[float] = mapped_column(Numeric(18, 0))
    method: Mapped[str] = mapped_column(String(10), default="cash")
    bank_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bank_accounts.id"), nullable=True
    )
    description: Mapped[str] = mapped_column(Text, default="")

    journal_entry_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("journal_entries.id"))
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    contact: Mapped["Contact"] = relationship()
