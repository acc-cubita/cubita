"""باشگاه مشتریان / CRM — سرنخ‌ها، پیگیری‌ها و امتیازِ وفاداری.

سه جدول:
  - crm_leads: مشتریِ بالقوه در قیفِ فروش (new→contacted→qualified→won/lost).
  - crm_activities: پیگیری/فعالیت (تماس، جلسه، یادداشت، کار) روی سرنخ یا مشتری.
  - crm_loyalty_transactions: امتیازِ وفاداریِ مشتری (کسب/استفاده) — «باشگاه مشتریان».

هر سه مستأجرمحورند (TenantMixin) و مثلِ بقیه زیرِ RLS می‌روند؛ مانده‌ی امتیاز از
جمعِ تراکنش‌ها درمی‌آید، نه یک ستونِ قابلِ ناسازگاری روی خودِ مشتری.
"""
import uuid
from datetime import date as date_

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin

#: مراحلِ قیفِ فروش
LEAD_STATUSES = ("new", "contacted", "qualified", "won", "lost")
#: انواعِ فعالیت/پیگیری
ACTIVITY_KINDS = ("call", "meeting", "note", "task")


class Lead(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """سرنخ — مشتریِ بالقوه‌ای که هنوز به مشتریِ واقعی تبدیل نشده.

    وقتی وضعیت به «won» می‌رسد می‌توان سرنخ را به یک «شخص» (مشتری) تبدیل کرد؛ آن‌گاه
    `converted_contact_id` پر می‌شود و از تبدیلِ دوباره جلوگیری می‌شود.
    """

    __tablename__ = "crm_leads"

    name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str] = mapped_column(String(30), default="", server_default="")
    email: Mapped[str] = mapped_column(String(150), default="", server_default="")
    company: Mapped[str] = mapped_column(String(200), default="", server_default="")
    #: منبعِ سرنخ (اینستاگرام، معرفی، تماس، …) — برچسبِ آزادِ کاربر
    source: Mapped[str] = mapped_column(String(80), default="", server_default="")
    status: Mapped[str] = mapped_column(String(20), default="new", server_default="new")
    estimated_value: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")
    next_action_date: Mapped[date_ | None] = mapped_column(Date, nullable=True)
    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    #: بعد از تبدیل به مشتری، به همان شخص گره می‌خورد (تبدیلِ دوباره ممنوع)
    converted_contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))


class CrmActivity(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """پیگیری/فعالیت — تماس، جلسه، یادداشت یا کارِ مرتبط با یک سرنخ یا مشتری.

    فعالیتِ انجام‌نشده با تاریخِ آینده = یادآوریِ پیگیری. به سرنخ یا شخص وصل می‌شود
    (نه هر دو به‌طورِ هم‌زمانِ اجباری؛ حداقل یکی).
    """

    __tablename__ = "crm_activities"

    kind: Mapped[str] = mapped_column(String(20), default="call", server_default="call")
    subject: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="", server_default="")
    activity_date: Mapped[date_] = mapped_column(Date)
    done: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm_leads.id", ondelete="CASCADE"), nullable=True, index=True
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=True, index=True
    )
    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))


class LoyaltyTransaction(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """امتیازِ وفاداریِ مشتری — «باشگاه مشتریان».

    مثبت = کسبِ امتیاز (مثلاً بابتِ خرید)، منفی = استفاده/سوختِ امتیاز. مانده‌ی هر
    مشتری = جمعِ تراکنش‌هایش؛ عمداً روی خودِ مشتری ستونِ مانده نگذاشتیم تا هیچ‌گاه با
    تراکنش‌ها ناسازگار نشود.
    """

    __tablename__ = "crm_loyalty_transactions"

    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), index=True
    )
    points: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    reason: Mapped[str] = mapped_column(String(200), default="", server_default="")
    txn_date: Mapped[date_] = mapped_column(Date)
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))


class LoyaltySettings(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """تنظیماتِ کسبِ خودکارِ امتیازِ وفاداری — یک ردیف به‌ازای هر مستأجر.

    وقتی فعال باشد، هر فروش به یک مشتری خودکار امتیاز می‌دهد: امتیاز = مبلغِ فروش ÷
    `amount_per_point` (رو به پایین). پیش‌فرض غیرفعال است تا رفتارِ فعلیِ فروش تغییر نکند.
    """

    __tablename__ = "loyalty_settings"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_loyalty_settings_tenant"),)

    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    #: چند تومان خرید = ۱ امتیاز (مثلاً ۱۰۰۰۰ یعنی هر ۱۰هزار تومان یک امتیاز)
    amount_per_point: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
