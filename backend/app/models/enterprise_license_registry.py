"""دفترِ مجوزهای «کوبیتا سازمانی» — سمتِ ابر (ستادِ `admin.cubita.ir`).

با `models/enterprise_license.py` اشتباه نشود: آن یک ردیف روی **سرورِ مشتری** است
(مجوزِ نصب‌شده). این‌جا فهرستِ **فروخته‌شده‌ها** در ابرِ ماست: هر ردیف یک مجوز، با کدِ
فعال‌سازیِ هش‌شده، سقف‌ها، و دستگاهی که به آن گره خورده.

**کدِ فعال‌سازی فقط هش ذخیره می‌شود** — همان منطقِ رمزِ عبور. ستاد کد را یک‌بار موقعِ
ساخت می‌بیند؛ اگر گم شد کدِ تازه می‌سازد (کدِ قبلی باطل می‌شود). `code_hint` (چهار
نویسه‌ی آخر) فقط برای این است که پشتیبانی بفهمد مشتری از کدام کد حرف می‌زند.

**ابطال فقط جلوی صدورِ تازه را می‌گیرد.** توکنِ امضاشده‌ای که روی سرورِ آفلاینِ مشتری
نشسته خودکفاست و از ابر خبری نمی‌گیرد؛ ابطالِ واقعی با انقضای مجوز رخ می‌دهد. این
محدودیتِ ذاتیِ فعال‌سازیِ آفلاین است و پنل هم همین را صریح می‌گوید.

**سراسری و بدونِ RLS** — دفترِ کنترل‌پنل است، نه دفترِ یک مشتری (مثلِ `subscriptions`).
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin


class EnterpriseLicenseRecord(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "enterprise_licenses"

    #: شناسه‌ی کوتاهِ عمومی — در توکن (`lic`) و روی صفحه‌ی مجوزِ مشتری دیده می‌شود.
    lic_id: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    org_name: Mapped[str] = mapped_column(String(200), nullable=False)
    #: تلفن/ایمیلِ خریدار — برای پشتیبانی.
    contact: Mapped[str | None] = mapped_column(String(200), nullable=True)
    seats: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: None = همه‌ی ماژول‌ها / همه‌ی قابلیت‌های پولی.
    mods: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    feat: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    #: None = دائمی.
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    grace_days: Mapped[int] = mapped_column(Integer, nullable=False, default=14, server_default="14")

    code_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    code_hint: Mapped[str] = mapped_column(String(8), nullable=False)

    #: active | revoked
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", server_default="active")
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    #: دستگاهِ گره‌خورده — خالی یعنی هنوز فعال نشده یا منتقل شده و منتظرِ دستگاهِ تازه است.
    install_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fp: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    bound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    issue_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_email: Mapped[str | None] = mapped_column(String(255), nullable=True)


class EnterpriseLicenseEvent(Base):
    """تاریخچه‌ی یک مجوز: ساخت، فعال‌سازی، صدورِ آفلاین، انتقال، ابطال، ردِ فعال‌سازی.

    کنش‌های ستاد در `staff_audit_log` هم ثبت می‌شوند؛ این جدول جایی است که
    **فعال‌سازی‌های آنلاینِ خودِ مشتری** (که کارمندی پشتشان نیست) هم دیده شوند —
    «این کد از کدام دستگاه و کی استفاده شد» سؤالِ اولِ هر تماسِ پشتیبانی است.
    """

    __tablename__ = "enterprise_license_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    license_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("enterprise_licenses.id", ondelete="CASCADE"), index=True
    )
    #: create | update | activate | issue | refuse | transfer | revoke | code
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    #: ایمیلِ کارمند، یا `online` برای فعال‌سازیِ خودِ مشتری.
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
