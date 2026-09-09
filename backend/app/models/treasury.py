import uuid
from datetime import date as date_, datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, Text, text
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
        # یکتاییِ RRNِ کارتخوان در سطحِ مستأجر (فقط ردیف‌های دارای RRN) — پشتیبانِ
        # DBِ idempotency؛ کنترلِ نرمِ اصلی در سرویس با «اگر بود، همان را برگردان».
        Index(
            "uq_treasury_tenant_reference",
            "tenant_id",
            "reference_no",
            unique=True,
            postgresql_where=text("reference_no IS NOT NULL"),
        ),
    )

    type: Mapped[str] = mapped_column(String(20))  # receipt = دریافت از مشتری | payment = پرداخت به تأمین‌کننده
    transaction_date: Mapped[date_] = mapped_column(Date, default=date_.today)
    contact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("contacts.id"))
    amount: Mapped[float] = mapped_column(Numeric(18, 0))
    method: Mapped[str] = mapped_column(String(10), default="cash")
    bank_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bank_accounts.id"), nullable=True
    )
    #: کدام صندوق. `NULL` = صندوقِ پیش‌فرض — همان معنایی که تراکنش‌های پیش از
    #: مهاجرتِ ۰۱۰۵ دارند، پس داده‌ی مستقر بدونِ backfill درست می‌ماند.
    cashbox_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cashboxes.id"), nullable=True
    )
    description: Mapped[str] = mapped_column(Text, default="")

    # ── متادیتای پرداختِ کارتی (کارتخوان/POS) — برای مغایرت‌گیری با صورت‌حسابِ بانک ──
    #: کانالِ پرداخت: NULL/"" = ثبتِ دستی، "pos_terminal" = از دستگاهِ کارتخوان.
    paid_via: Mapped[str | None] = mapped_column(String(20), nullable=True)
    #: شماره‌ی مرجع/پیگیریِ تراکنش (RRN). یکتا در سطحِ مستأجر → کلیدِ idempotency.
    reference_no: Mapped[str | None] = mapped_column(String(40), nullable=True)
    #: شماره‌ی رسید/سریِ تراکنش (trace/STAN) که دستگاه برمی‌گرداند.
    trace_no: Mapped[str | None] = mapped_column(String(40), nullable=True)
    #: شماره‌ی کارتِ ماسک‌شده (۶۰۳۷****۱۲۳۴).
    card_mask: Mapped[str | None] = mapped_column(String(30), nullable=True)
    #: شماره‌ی پایانه‌ی کارتخوان.
    terminal_no: Mapped[str | None] = mapped_column(String(30), nullable=True)
    #: شرکتِ پرداخت (مثلاً behpardakht|sep|sadad|simulator).
    psp: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # ── تسویه‌ی کارتخوان ──
    #: فروشِ کارتی همان‌روز به حساب نمی‌نشیند؛ PSP چند روز بعد یک‌جا (منهای کارمزد)
    #: واریز می‌کند. تا این دو پر نشوند، تراکنش «تسویه‌نشده» است.
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    settlement_txn_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bank_transactions.id", ondelete="SET NULL"), nullable=True
    )

    journal_entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), index=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    contact: Mapped["Contact"] = relationship()
