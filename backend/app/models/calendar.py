import uuid
from datetime import date as date_

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin

# دسته‌بندی رویداد — فقط برای رنگ/فیلتر است، نه منطق مالی. ثابت نگه‌داشتنش در یک
# tuple یعنی هم schema (اعتبارسنجی) و هم CheckConstraint (پایگاه‌داده) از یک منبع
# می‌خوانند و نمی‌توانند از هم جدا بیفتند.
EVENT_CATEGORIES = ("reminder", "meeting", "payment", "tax", "task", "other")


class CalendarEvent(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """رویداد یا یادآوریِ تقویمِ کسب‌وکار — مشترک بین همه‌ی کاربرانِ همان مستأجر.

    عمداً مستأجرمحور است و نه شخصی: یادآوریِ «چکِ سررسیدِ ۱۵م» یا «اظهارنامه‌ی
    مالیاتی» به کل کسب‌وکار مربوط است، نه به یک کاربر. `created_by_id` فقط نگه
    می‌دارد چه کسی ثبت کرده.
    """

    __tablename__ = "calendar_events"
    __table_args__ = (
        CheckConstraint(f"category IN {EVENT_CATEGORIES}", name="ck_calendar_events_category"),
    )

    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    #: روزِ رویداد. به‌صورت میلادی ذخیره می‌شود؛ تبدیل به شمسی فقط در UI انجام می‌شود
    #: تا تاریخِ داخل پایگاه‌داده استاندارد و قابل مقایسه/بازه‌گیری بماند.
    event_date: Mapped[date_] = mapped_column(Date, index=True)
    #: ساعت اختیاری به‌صورت "HH:MM". خالی یعنی «تمام‌روز».
    start_time: Mapped[str | None] = mapped_column(String(5), nullable=True)
    end_time: Mapped[str | None] = mapped_column(String(5), nullable=True)
    category: Mapped[str] = mapped_column(String(20), default="reminder")
    #: انجام‌شده/رسیدگی‌شده — برای تیک‌زدنِ یادآوری بدون حذفش.
    is_done: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
