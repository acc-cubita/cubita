"""حسابرسی — قرارداد، اجرا و یافته.

سه جدول با **دو ماهیتِ متفاوت**، و این تفاوت عمدی است:

* `assurance_engagements` **سراسری** است (بدونِ RLS). قرارداد، پیمانی بینِ
  *پلتفرم* و *مستأجر* است — ساختاراً همان `subscriptions`. کارتابلِ ستاد باید
  درخواست‌های همه‌ی کسب‌وکارها را کنارِ هم ببیند، و سیاستِ RLS هر نشست را به یک
  مستأجر می‌بندد. پس مثلِ `marketplace_*` جداسازی در **کدِ روتر** با فیلترِ صریح
  انجام می‌شود، نه در پایگاه‌داده — و تستِ نشتی برایش الزامی است.
* `assurance_runs` و `assurance_findings` **مستأجری**اند (با RLS). این‌ها دفترِ
  خودِ مشتری‌اند: عکسی از وضعیتِ دفترش در یک لحظه.

**چرا اصلاً ذخیره می‌شوند.** هر سطحِ «یافته»ی دیگری در کوبیتا (یکپارچگی، هشدارها،
نقضِ ماهیت) بی‌حالت است و هر بار از نو حساب می‌شود. حسابرسی نمی‌تواند این‌طور باشد:
گزارشِ حسابرس به وضعیتِ دفتر **در تاریخِ بررسی** استناد می‌کند. اگر مشتری فردا سند
را اصلاح کند، آن گزارش نباید بی‌صدا عوض شود. گذشته با حال تغییر نمی‌کند.
"""
import uuid
from datetime import date as date_
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin

#: چرخه‌ی زندگیِ قرارداد.
#:
#: گذارِ مجاز — `services/assurance.py` همین را می‌سنجد:
#:   requested → approved → active → closed
#:   requested → rejected            (پایانی)
#:   approved  → closed              (تأیید شد ولی هرگز شروع نشد)
#:
#: `rejected` و `closed` پایانی‌اند: درخواستِ تازه ردیفِ **تازه** می‌سازد، نه
#: بازگشت. تاریخچه‌ی «یک بار رد شدیم» باید بماند.
ENGAGEMENT_STATUSES: tuple[str, ...] = (
    "requested",
    "approved",
    "active",
    "rejected",
    "closed",
)

#: وضعیت‌هایی که «قراردادِ باز» شمرده می‌شوند — هم گیتِ ماژولِ مشتق با همین کار
#: می‌کند و هم ایندکسِ یکتای جزئی.
OPEN_ENGAGEMENT_STATUSES: tuple[str, ...] = ("requested", "approved", "active")

#: چه چیزی اجرا را راه انداخته. هیچ زمان‌بندی‌ای در کار نیست — این سه تا کلِ
#: نویسنده‌های `assurance_runs` هستند.
RUN_TRIGGERS: tuple[str, ...] = ("approval", "manual", "staff")

#: درجه‌ی کارنامه. برچسبِ فارسی‌اش در `services/assurance_score.py` است.
RUN_GRADES: tuple[str, ...] = ("healthy", "warning", "critical")


class AssuranceEngagement(UUIDPKMixin, TimestampMixin, Base):
    """قراردادِ حسابرسیِ یک کسب‌وکار — **جدولِ سراسری، بدونِ TenantMixin**."""

    __tablename__ = "assurance_engagements"
    __table_args__ = (
        CheckConstraint(
            f"status IN {ENGAGEMENT_STATUSES}", name="ck_assurance_engagements_status"
        ),
        Index("ix_assurance_engagements_status_requested", "status", "requested_at"),
        #: یک قراردادِ **باز** به‌ازای هر کسب‌وکار — کمربندِ پایگاه‌داده کنارِ ۴۰۹ِ
        #: سرویس. جزئی‌بودنش عمدی است: سالِ بعد پرونده‌ی خودش را با دوره و تیمِ
        #: خودش می‌گیرد، پس یکتاییِ کامل روی `tenant_id` فازهای بعدی را می‌شکست.
        #:
        #: روی *مدل* هم اعلام می‌شود نه فقط در مهاجرت، وگرنه `create_all`ِ تست‌ها
        #: آن را نمی‌ساخت و production قیدی می‌داشت که هیچ تستی نمی‌دیدش — همان
        #: چیزی که `test_migration_drift` می‌پاید.
        Index(
            "uq_assurance_open_per_tenant",
            "tenant_id",
            unique=True,
            postgresql_where=text(
                "status IN ('requested'::character varying, 'approved'::character varying, "
                "'active'::character varying)"
            ),
        ),
    )

    #: ستونِ مستأجر هست — برای فیلترِ صریحِ روتر و برای زمینه‌ی ردِ حسابرسی — ولی
    #: سیاستِ RLS نیست. به همین دلیل هر خواندنِ مستأجری باید از یک تابعِ واحد
    #: بگذرد (`_own_engagement`)؛ فیلترِ فراموش‌شده یعنی نشتی.
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default="requested", server_default="requested"
    )

    # ── درخواستِ مشتری ────────────────────────────────────────────────────
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    requested_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    #: دوره‌ی موردِ حسابرسی. اختیاری است چون مشتری همیشه نمی‌داند؛ حسابرس هنگامِ
    #: تأیید می‌تواند تعیینش کند و اجرای بررسی با همین بازه انجام می‌شود.
    period_from: Mapped[date_ | None] = mapped_column(Date, nullable=True)
    period_to: Mapped[date_ | None] = mapped_column(Date, nullable=True)
    contact_phone: Mapped[str] = mapped_column(String(30), default="", server_default="")
    request_note: Mapped[str] = mapped_column(Text, default="", server_default="")

    # ── تصمیمِ ما ─────────────────────────────────────────────────────────
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    decided_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    reject_reason: Mapped[str] = mapped_column(Text, default="", server_default="")

    # ── حسابرسِ گمارده ────────────────────────────────────────────────────
    auditor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    #: عضویتِ موقتی که برای حسابرس ساخته شده. `SET NULL` چون اگر مشتری خودش
    #: حسابرس را از فهرستِ کاربرانش بردارد (حقش است — دفتر مالِ اوست)، قرارداد
    #: نباید بشکند؛ فقط دیگر دسترسی ندارد.
    auditor_membership_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True
    )
    access_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── آینه‌ی آخرین اجرا ─────────────────────────────────────────────────
    #: **عمداً بدونِ FK.** `assurance_runs` زیرِ RLS است و کلیدِ خارجی از والدِ
    #: سراسری به فرزندِ RLS‌دار یعنی اسکنِ راستی‌آزماییِ پستگرس زیرِ سیاستی اجرا
    #: می‌شود که `current_setting('app.tenant_id')` می‌خواند — همان خطایی که
    #: `app/migration_utils.py` مستندش کرده. جهتِ برعکس امن است و
    #: `assurance_runs.engagement_id` کلیدِ خارجیِ واقعی دارد.
    #:
    #: این سه ستون غیرنرمال‌اند تا کارتابلِ ستاد بتواند نمره‌ی دویست کسب‌وکار را
    #: بدونِ دویست بار سوییچِ زمینه‌ی مستأجر نشان دهد.
    last_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    last_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── پایان ────────────────────────────────────────────────────────────
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    close_note: Mapped[str] = mapped_column(Text, default="", server_default="")


class AssuranceRun(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """یک بررسیِ اجراشده — عکسِ وضعیتِ دفتر در یک لحظه."""

    __tablename__ = "assurance_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_assurance_runs_tenant_number"),
        CheckConstraint(f"trigger IN {RUN_TRIGGERS}", name="ck_assurance_runs_trigger"),
        CheckConstraint(f"grade IN {RUN_GRADES}", name="ck_assurance_runs_grade"),
    )

    #: فرزندِ RLS‌دار → والدِ سراسری: این جهت امن است.
    engagement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assurance_engagements.id"), index=True
    )
    number: Mapped[int] = mapped_column(Integer)
    ran_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ran_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    trigger: Mapped[str] = mapped_column(String(20))

    date_from: Mapped[date_ | None] = mapped_column(Date, nullable=True)
    date_to: Mapped[date_ | None] = mapped_column(Date, nullable=True)

    score: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    grade: Mapped[str] = mapped_column(String(20), default="healthy")
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    warning_count: Mapped[int] = mapped_column(Integer, default=0)
    finding_count: Mapped[int] = mapped_column(Integer, default=0)
    total_debit: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    total_credit: Mapped[float] = mapped_column(Numeric(18, 0), default=0)

    #: سندِ خودِ نمره: یک ردیف به‌ازای هر بررسی — عنوان، شدت، شمارشِ **قطع‌نشده**،
    #: وزن و امتیازِ ازدست‌رفته. دو چیز را نگه می‌دارد که از ردیف‌های ذخیره‌شده
    #: قابلِ بازسازی نیستند: شمارشِ کامل (ردیف‌ها سقف دارند)، و وزنی که آن روز
    #: اعمال شده (تنظیمِ بعدیِ وزن‌ها نباید تاریخچه را بازنویسی کند).
    summary: Mapped[list] = mapped_column(JSONB, default=list)


class AssuranceFinding(TenantMixin, UUIDPKMixin, Base):
    """یک ردیفِ یافته درونِ یک اجرا.

    `TimestampMixin` ندارد — مثلِ `AuditLog`: زمانش زمانِ خودِ اجراست و ستونِ
    تکراری فقط جا می‌گیرد.
    """

    __tablename__ = "assurance_findings"
    __table_args__ = (
        CheckConstraint(
            "severity IN ('error', 'warning')", name="ck_assurance_findings_severity"
        ),
        Index("ix_assurance_findings_run_check", "run_id", "check_key"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assurance_runs.id", ondelete="CASCADE"), index=True
    )
    check_key: Mapped[str] = mapped_column(String(60), index=True)
    severity: Mapped[str] = mapped_column(String(10))
    seq: Mapped[int] = mapped_column(Integer, default=0)
    label: Mapped[str] = mapped_column(String(300), default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    debit: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    credit: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    difference: Mapped[float] = mapped_column(Numeric(18, 0), default=0)

    #: لنگرهای drill-down — **عمداً بدونِ کلیدِ خارجی**، به همان دلیلِ
    #: `AuditLog.entity_id`: این عکسِ گذشته است. اگر سندی بعداً باطل یا حذف شود،
    #: یافته نباید ناپدید شود یا درج را بشکند؛ رابط اگر سند را پیدا نکرد، همان را
    #: می‌گوید.
    entry_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    account_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
