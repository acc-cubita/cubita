import uuid
from datetime import date as date_

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin

PLAN_STATUSES = ("active", "completed", "cancelled")


class InstallmentPlan(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """قراردادِ فروشِ اقساطی: مبلغِ کل، پیش‌پرداخت و زمان‌بندیِ اقساطِ یک مشتری.

    قرارداد فقط **زمان‌بندیِ وصول** است؛ خودِ بدهی از فاکتورِ نسیه (حساب‌های دریافتنی)
    می‌آید و هر پرداختِ قسط یک دریافتِ خزانه‌ی واقعی می‌سازد که مانده‌ی دریافتنی را کم
    می‌کند. پس حسابداری هرگز دوباره‌کاری نمی‌شود.
    """

    __tablename__ = "installment_plans"

    number: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    contact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("contacts.id"), index=True)
    #: فاکتورِ فروشِ نسیه‌ی مرتبط (اختیاری) — منبعِ بدهی.
    sales_invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales_invoices.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(200), default="")
    total_amount: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    down_payment: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    num_installments: Mapped[int] = mapped_column(Integer, default=1)
    interval_months: Mapped[int] = mapped_column(Integer, default=1)
    start_date: Mapped[date_] = mapped_column(Date, default=date_.today)
    status: Mapped[str] = mapped_column(String(20), default="active")
    notes: Mapped[str] = mapped_column(Text, default="")

    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    contact: Mapped["Contact"] = relationship()  # noqa: F821
    installments: Mapped[list["Installment"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", order_by="Installment.seq"
    )


class Installment(TenantMixin, UUIDPKMixin, Base):
    """یک قسط از یک قرارداد. وضعیت (پرداخت‌شده/جزئی/معوق/در انتظار) از روی
    `paid_amount`/`due_date` مشتق می‌شود، ذخیره نمی‌شود — پس بدونِ زمان‌بندِ پس‌زمینه
    همیشه درست است."""

    __tablename__ = "installments"

    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("installment_plans.id", ondelete="CASCADE"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer)
    due_date: Mapped[date_] = mapped_column(Date)
    amount: Mapped[float] = mapped_column(Numeric(18, 0))
    paid_amount: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    paid_date: Mapped[date_ | None] = mapped_column(Date, nullable=True)

    plan: Mapped["InstallmentPlan"] = relationship(back_populates="installments")
