import uuid
from datetime import date as date_

from sqlalchemy import Date, ForeignKey, Index, Numeric, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin


class BudgetLine(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """بودجه‌ی یک حساب برای یک دوره‌ی ماهانه — مبلغِ برنامه‌ریزی‌شده.

    مبلغ همیشه در جهتِ طبیعیِ حساب است (هزینه و درآمد مثبت)، تا در گزارشِ «بودجه در
    برابر عملکرد» بی‌واسطه با ماندهٔ واقعیِ همان حساب مقایسه شود.

    قیدِ یکتای (حساب، دوره، مرکز) عمدی است: برای هر ماه فقط یک ردیفِ بودجه معنا
    دارد؛ ثبتِ دوباره‌ی همان ترکیب به‌جای ساختِ ردیفِ دوم، ردیفِ موجود را به‌روزرسانی
    می‌کند (منطقِ upsert در سرویس). بدون این قید، دو بودجه‌ی متناقض برای یک ماه
    بی‌سر‌و‌صدا در گزارش دوبار جمع می‌شد.

    بودجه می‌تواند سراسری باشد (`cost_center_id` خالی) یا مالِ یک مرکز. هر دو در یک
    جدول می‌نشینند چون یک مفهوم‌اند و دو جدول یعنی دو منبعِ حقیقت برای «برنامه».
    """

    __tablename__ = "budget_lines"
    __table_args__ = (
        # دو ایندکسِ *جزئی* به‌جای یک قیدِ یکتا: در پستگرس NULL با NULL برابر نیست،
        # پس یک قیدِ ساده روی ستونِ nullable جلوی دو ردیفِ سراسریِ تکراری را نمی‌گرفت.
        Index(
            "uq_budget_account_period_global",
            "tenant_id",
            "account_id",
            "period_date",
            unique=True,
            postgresql_where=text("cost_center_id IS NULL"),
        ),
        Index(
            "uq_budget_account_period_center",
            "tenant_id",
            "account_id",
            "period_date",
            "cost_center_id",
            unique=True,
            postgresql_where=text("cost_center_id IS NOT NULL"),
        ),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id"))
    #: بُعدِ اختیاریِ مرکز هزینه. NULL یعنی بودجه‌ی کلِ کسب‌وکار — همان معنایی که
    #: ردیف‌های پیش از این ستون داشتند، پس رفتارِ قبلی دست‌نخورده می‌ماند.
    cost_center_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cost_centers.id", ondelete="CASCADE"), nullable=True, index=True
    )
    #: روزِ نماینده‌ی دوره (اولِ ماه). ذخیره‌ی میلادی؛ تبدیل شمسی فقط در UI.
    period_date: Mapped[date_] = mapped_column(Date, index=True)
    amount: Mapped[float] = mapped_column(Numeric(18, 0))
    notes: Mapped[str] = mapped_column(Text, default="")
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    account: Mapped["Account"] = relationship()  # noqa: F821
    cost_center: Mapped["CostCenter | None"] = relationship()  # noqa: F821
