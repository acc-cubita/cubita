import uuid

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin

PURCHASE_STATUSES = ("pending_payment", "paid", "cancelled", "fulfilled")


class Plan(UUIDPKMixin, TimestampMixin, Base):
    """پلن فروش نرم‌افزار (نمایش‌داده‌شده در سایت تجاری cubita.ir)."""

    __tablename__ = "plans"

    key: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")
    price_toman: Mapped[float] = mapped_column(Numeric(18, 0))
    billing_period: Mapped[str] = mapped_column(String(20), default="yearly")  # yearly | monthly
    max_users: Mapped[int | None] = mapped_column(Integer, nullable=True)
    features: Mapped[list] = mapped_column(JSONB, default=list)  # لیست ساده‌ای از رشته‌ها برای نمایش در صفحه‌ی قیمت‌گذاری
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    highlighted: Mapped[bool] = mapped_column(Boolean, default=False)  # پلن پیشنهادی/محبوب

    purchases: Mapped[list["Purchase"]] = relationship(back_populates="plan")


class Purchase(UUIDPKMixin, TimestampMixin, Base):
    """درخواست خرید یک پلن از سایت تجاری. فعلاً تحویل نسخه‌ی کامل به‌صورت دستی توسط ادمین انجام می‌شود
    (معماری چندمستأجری کامل هنوز پیاده نشده)؛ این رکورد فقط ثبت پرداخت و صف پیگیری برای تحویل دستی است."""

    __tablename__ = "purchases"
    __table_args__ = (CheckConstraint(f"status IN {PURCHASE_STATUSES}", name="ck_purchases_status"),)

    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("plans.id"))
    customer_name: Mapped[str] = mapped_column(String(150))
    customer_email: Mapped[str] = mapped_column(String(150))
    customer_phone: Mapped[str] = mapped_column(String(20), default="")
    business_name: Mapped[str] = mapped_column(String(150), default="")

    amount_toman: Mapped[float] = mapped_column(Numeric(18, 0))
    status: Mapped[str] = mapped_column(String(20), default="pending_payment")

    zarinpal_authority: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    zarinpal_ref_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # پر می‌شود وقتی ادمین دستی تحویل داد
    admin_notes: Mapped[str] = mapped_column(Text, default="")

    plan: Mapped["Plan"] = relationship(back_populates="purchases")

    @property
    def plan_name(self) -> str:
        return self.plan.name
