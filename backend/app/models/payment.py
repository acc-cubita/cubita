"""اعلامیه‌ی پرداخت: سربرگِ عملیاتی روی ابزارهای واقعی خزانه‌داری."""

import uuid
from datetime import date as date_, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin, VoidableMixin
from app.models.tenant import TenantMixin

if TYPE_CHECKING:
    from app.models.inventory import Contact


PAYMENT_TYPES = ("supplier", "customer", "other")


class Payment(TenantMixin, VoidableMixin, UUIDPKMixin, TimestampMixin, Base):
    """یک پرداخت با چند ابزار و یک سند حسابداری متوازن."""

    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_payments_tenant_number"),
        CheckConstraint("payment_amount > 0", name="ck_payments_amount_positive"),
        CheckConstraint("discount_amount >= 0 AND bank_fee_amount >= 0", name="ck_payments_nonnegative"),
        CheckConstraint("exchange_rate > 0", name="ck_payments_exchange_rate_positive"),
    )

    number: Mapped[int] = mapped_column(Numeric(18, 0))
    payment_type: Mapped[str] = mapped_column(String(20), default="supplier")
    contact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("contacts.id"))
    payment_date: Mapped[date_] = mapped_column(Date, default=date_.today)

    # حساب‌ها از نقش سیستمی resolve می‌شوند، ولی شناسه‌ی واقعیِ استفاده‌شده برای
    # توضیح‌پذیری و حسابرسی روی سند می‌ماند.
    counterparty_account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id"))
    bank_fee_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=True
    )
    discount_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=True
    )

    currency_code: Mapped[str] = mapped_column(String(3), default="IRR", server_default="IRR")
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=1)
    # سه مفهوم مستقل: خروج واقعیِ اصل پرداخت، تخفیفِ غیرنقدی، و جمعِ تسویه.
    payment_amount: Mapped[Decimal] = mapped_column(Numeric(18, 0))
    base_currency_amount: Mapped[Decimal] = mapped_column(Numeric(18, 0))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(18, 0), default=0)
    settlement_total: Mapped[Decimal] = mapped_column(Numeric(18, 0))
    bank_fee_amount: Mapped[Decimal] = mapped_column(Numeric(18, 0), default=0)

    description: Mapped[str] = mapped_column(Text, default="")
    description2: Mapped[str] = mapped_column(String(200), default="")
    establishment: Mapped[str] = mapped_column(String(120), default="")

    journal_entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), index=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    contact: Mapped["Contact"] = relationship()


class PaymentChequeTransfer(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """رخدادِ خرج‌کردنِ همان چک دریافتنی؛ خودِ چک تکثیر نمی‌شود."""

    __tablename__ = "payment_cheque_transfers"
    __table_args__ = (UniqueConstraint("tenant_id", "payment_id", "check_id", name="uq_payment_cheque_transfer"),)

    payment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("payments.id"), index=True)
    check_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("checks.id"), index=True)
    previous_status: Mapped[str] = mapped_column(String(20), default="in_hand")
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))


class PaymentRelatedDocument(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """پیوندِ قابل‌ردگیری؛ تخصیص و تسویه‌ی نهایی در موتور Settlement می‌ماند."""

    __tablename__ = "payment_related_documents"
    __table_args__ = (
        UniqueConstraint("tenant_id", "payment_id", "document_type", "document_id", name="uq_payment_related_document"),
        CheckConstraint("allocated_amount >= 0", name="ck_payment_related_allocated_nonnegative"),
    )

    payment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("payments.id"), index=True)
    document_type: Mapped[str] = mapped_column(String(40))
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    allocated_amount: Mapped[Decimal] = mapped_column(Numeric(18, 0), default=0)
