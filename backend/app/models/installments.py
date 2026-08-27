import uuid
from datetime import date as date_, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func
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
    #: قیمتِ نقدیِ همان کالا/خدمت و سودِ فروشِ اقساطی. رابطه‌ی «نقدی + سود = کل» در
    #: سرویس تضمین می‌شود. این دو **توصیفی**اند: سند از فاکتورِ نسیه می‌آید، نه از اینجا.
    cash_price: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    profit_amount: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    #: درصدِ جریمه‌ی دیرکرد به‌ازای هر ماه تأخیر. مبلغش محاسبه می‌شود نه ذخیره — مثلِ
    #: وضعیتِ قسط — تا بدونِ زمان‌بندِ پس‌زمینه همیشه با تاریخِ امروز درست باشد.
    penalty_rate: Mapped[float] = mapped_column(Numeric(6, 3), default=0, server_default="0")
    down_payment: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    num_installments: Mapped[int] = mapped_column(Integer, default=1)
    interval_months: Mapped[int] = mapped_column(Integer, default=1)
    start_date: Mapped[date_] = mapped_column(Date, default=date_.today)
    status: Mapped[str] = mapped_column(String(20), default="active")
    #: ضامن — در فروشِ اقساطی بخشی از خودِ قرارداد است، نه یادداشت.
    guarantor_name: Mapped[str] = mapped_column(String(200), default="", server_default="")
    guarantor_phone: Mapped[str] = mapped_column(String(30), default="", server_default="")
    guarantor_national_id: Mapped[str] = mapped_column(String(20), default="", server_default="")
    notes: Mapped[str] = mapped_column(Text, default="")

    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    contact: Mapped["Contact"] = relationship()  # noqa: F821
    installments: Mapped[list["Installment"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", order_by="Installment.seq"
    )
    payments: Mapped[list["InstallmentPayment"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", order_by="InstallmentPayment.paid_on"
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


class InstallmentPayment(TenantMixin, UUIDPKMixin, Base):
    """یک وصولِ واقعی روی یک قسط — مبلغ، تاریخ، روش، و سندِ خزانه‌اش.

    `installments.paid_amount` جمعِ همین ردیف‌هاست. نگه‌داشتنِ جمع کنارِ جزئیات عمدی
    است: گزارش‌ها و وضعیتِ قسط به یک ستون نگاه می‌کنند و لازم نیست هر بار جمع بزنند،
    ولی «کِی و چطور وصول شد» هم دیگر گم نمی‌شود.
    """

    __tablename__ = "installment_payments"
    __table_args__ = (Index("ix_installment_payments_tenant_plan", "tenant_id", "plan_id"),)

    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("installment_plans.id", ondelete="CASCADE")
    )
    installment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("installments.id", ondelete="CASCADE")
    )
    amount: Mapped[float] = mapped_column(Numeric(18, 0))
    paid_on: Mapped[date_] = mapped_column(Date)
    method: Mapped[str] = mapped_column(String(20), default="cash", server_default="cash")
    treasury_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("treasury_transactions.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    plan: Mapped["InstallmentPlan"] = relationship(back_populates="payments")
