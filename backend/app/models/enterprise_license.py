"""مجوزِ «کوبیتا سازمانی» روی سرورِ خودِ شرکت — یک ردیف، همیشه `id = 1`.

**چرا در دیتابیس و هم در فایل.** این ردیف و فایلِ `license.lic` کنارِ هم نگه داشته
می‌شوند (`app/licensing/state.py`): پاک‌کردنِ فایل دوره‌ی آزمایشی را ریست نمی‌کند، و
بازگرداندنِ یک پشتیبانِ قدیمیِ دیتابیس فعال‌سازی را نمی‌بَرد. هرکدام گم شود از
دیگری ساخته می‌شود و زودترین `installed_at` برنده است.

**سراسری و بدونِ RLS.** مالِ نصب است نه مالِ یک کسب‌وکار، و پیش از هر زمینه‌ی
مستأجری (در مسیرِ ورود و راه‌اندازی) خوانده می‌شود. در نسخه‌ی ابری خالی می‌ماند.
"""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EnterpriseLicense(Base):
    __tablename__ = "enterprise_license"
    __table_args__ = (CheckConstraint("id = 1", name="ck_enterprise_license_singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    #: شناسه‌ی این نصب — در «کدِ درخواست» می‌رود تا ستاد نصب‌ها را از هم تشخیص دهد.
    install_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False)
    #: شروعِ دوره‌ی آزمایشیِ ۳۰روزه.
    installed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    #: توکنِ امضاشده‌ی `CUB1.…`؛ خالی = هنوز فعال نشده (آزمایشی).
    token: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: دیرترین زمانی که سرور دیده — فقط جلو می‌رود. ساعتی که از این عقب‌تر باشد
    #: یعنی کسی ساعت را برای دور زدنِ انقضا عقب برده.
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
