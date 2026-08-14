import uuid
from datetime import date as date_

from sqlalchemy import Date, ForeignKey, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin


class BudgetLine(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """بودجه‌ی یک حساب برای یک دوره‌ی ماهانه — مبلغِ برنامه‌ریزی‌شده.

    مبلغ همیشه در جهتِ طبیعیِ حساب است (هزینه و درآمد مثبت)، تا در گزارشِ «بودجه در
    برابر عملکرد» بی‌واسطه با ماندهٔ واقعیِ همان حساب مقایسه شود.

    قیدِ یکتای (حساب، دوره) عمدی است: برای هر ماه فقط یک ردیفِ بودجه معنا دارد؛
    ثبتِ دوباره‌ی همان حساب/ماه به‌جای ساختِ ردیفِ دوم، ردیفِ موجود را به‌روزرسانی
    می‌کند (منطقِ upsert در سرویس). بدون این قید، دو بودجه‌ی متناقض برای یک ماه
    بی‌سر‌و‌صدا در گزارش دوبار جمع می‌شد.
    """

    __tablename__ = "budget_lines"
    __table_args__ = (
        UniqueConstraint("tenant_id", "account_id", "period_date", name="uq_budget_account_period"),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id"))
    #: روزِ نماینده‌ی دوره (اولِ ماه). ذخیره‌ی میلادی؛ تبدیل شمسی فقط در UI.
    period_date: Mapped[date_] = mapped_column(Date, index=True)
    amount: Mapped[float] = mapped_column(Numeric(18, 0))
    notes: Mapped[str] = mapped_column(Text, default="")
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    account: Mapped["Account"] = relationship()  # noqa: F821
