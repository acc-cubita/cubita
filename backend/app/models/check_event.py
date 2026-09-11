"""تاریخچه‌ی عملیاتِ چک — «وضعیتِ فعلی» به‌تنهایی کافی نیست.

## چه چیزی نبود

`checks.status` می‌گفت چک **الان** کجاست، و همین. نمی‌شد پرسید:

* این چک کِی به بانک واگذار شد و به کدام بانک؟
* چه کسی واخواستش را ثبت کرد؟
* پیش از آنکه دستِ ما برگردد، به چه کسی خرج شده بود؟

و بدترش: `Check` **در رجیستریِ `audit.audited_models()` هم نبود**، پس حتی ردِ
حسابرسیِ عمومی هم برایش نوشته نمی‌شد. موجودیتی با غنی‌ترین چرخه‌ی عمرِ خزانه،
تنها موجودیتی بود که هیچ ردی از خودش نمی‌گذاشت.

## چرا جدولِ جدا و نه `audit_log`

`audit_log` می‌گوید «چه فیلدی از چه مقداری به چه مقداری رفت» — عمومی، و برای
حسابرسیِ تغییر ساخته شده. این جدول رویدادِ *کسب‌وکاری* را نگه می‌دارد: کدام
عملیات، با کدام بانک/صندوق/طرف‌حساب، با کدام سند. این دو نمای یک داده نیستند؛
دومی ستون‌های تایپ‌دار می‌خواهد تا بشود رویش گزارش گرفت و پیوند زد.

`Check` جداگانه به رجیستریِ حسابرسی هم اضافه شد — آن یکی جای دیگری را می‌پوشاند.

## دو نما روی یک داده (§۴۱)

«فهرستِ چک‌ها» می‌گوید الان چه داریم؛ «فهرستِ عملیاتِ چک» می‌گوید چه اتفاقی
افتاده. هر دو از همین جدول و `checks` می‌آیند — نه از دو منبعِ موازی.

## فقط‌افزودنی (§۴۷)

تریگرِ `check_events_no_update_delete` در سطحِ پایگاه‌داده جلوی UPDATE/DELETE را
می‌گیرد. تاریخچه‌ی واخواست پاک نمی‌شود تا وضعیتِ فعلی تمیزتر به‌نظر برسد؛ اصلاح
یعنی **افزودنِ** رویدادِ تازه. تنها دریچه‌ی عبور `app.audit_purge` است که فقط در
حذفِ مستأجر و بازیابیِ پشتیبان باز می‌شود — همان گاردی که `audit_log` دارد.
"""
import uuid
from datetime import date as date_, datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import UUIDPKMixin
from app.models.tenant import TenantMixin

if TYPE_CHECKING:
    from app.models.banking import Check

#: نامِ عملیات — مستقل از `to_status` است و باید باشد.
#:
#: `deposited → in_hand` و `endorsed → in_hand` هر دو به یک وضعیت می‌رسند ولی دو
#: رویدادِ کاملاً متفاوت‌اند: یکی «بانک برگ را پس داد» و دیگری «چکی که خرج کرده
#: بودیم برگشت». اگر عملیات را از وضعیتِ مقصد استنتاج کنیم، این دو در تاریخچه یک
#: چیز می‌شوند — همان اشتباهی که §۳۴ درباره‌ی سه «برگشت» هشدار می‌دهد.
CHECK_OPERATIONS = (
    "receive",  # دریافت از طرف‌حساب (ثبتِ اولیه‌ی چکِ دریافتنی)
    "issue",  # صدور چکِ پرداختنی
    "deposit",  # واگذاری به بانک
    "undeposit",  # بازگشت از بانک بدونِ واخواست
    "collect",  # وصول
    "dishonor",  # واخواست
    "cash",  # نقد کردن به صندوق
    "endorse",  # خرج کردن
    "return_endorsed",  # برگشت از خرج
    "refund",  # استرداد به طرفِ مقابل
)


class CheckEvent(TenantMixin, UUIDPKMixin, Base):
    """یک گذرِ وضعیتِ چک، با همه‌ی چیزی که برای توضیحش لازم است."""

    __tablename__ = "check_events"
    __table_args__ = (
        #: کوئریِ غالب: تایم‌لاینِ یک چک، به ترتیبِ زمان.
        Index("ix_check_events_check_at", "check_id", "at"),
        #: کوئریِ دومِ غالب: فهرستِ عملیات، تازه‌ترین اول.
        Index("ix_check_events_tenant_at", "tenant_id", "at"),
    )

    check_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("checks.id", ondelete="CASCADE"), index=True
    )

    operation: Mapped[str] = mapped_column(String(30))
    #: `NULL` فقط برای رویدادِ اولِ چک (دریافت/صدور) که وضعیتِ قبلی ندارد.
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str] = mapped_column(String(20))

    #: تاریخِ کسب‌وکاریِ عملیات — همان که سند با آن می‌خورد.
    event_date: Mapped[date_] = mapped_column(Date)
    #: لحظه‌ی ثبت. با بالایی یکی نیست و نباید بشود: واگذاریِ دیروز را می‌شود
    #: امروز ثبت کرد، و ترتیبِ تایم‌لاین باید ترتیبِ *ثبت* باشد.
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    #: شماره‌ی عملیات (§۱۱) — با شماره‌ی چک و شماره‌ی سند یکی نیست. عملیاتِ گروهی
    #: یک شماره می‌گیرد و همه‌ی ردیف‌هایش همان را دارند.
    operation_no: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    #: چند چک که با یک عملیات رفته‌اند (§۴۴). تکِ‌چک هم شناسه می‌گیرد تا فهرستِ
    #: عملیات یک‌جور خوانده شود.
    batch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)

    bank_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bank_accounts.id", ondelete="SET NULL"), nullable=True
    )
    cashbox_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cashboxes.id", ondelete="SET NULL"), nullable=True
    )
    #: طرفِ مقابلِ همین عملیات — که لزوماً صاحبِ چک نیست. چکی که به تأمین‌کننده خرج
    #: می‌شود، `contact_id`ِ خودش هنوز مشتری است؛ گیرنده اینجا می‌نشیند.
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True
    )
    #: `NULL` یعنی این گذر سندی نزده — مثلِ بازگشت از بانک، که واگذاریِ خودش هم
    #: سندِ قرینه دارد و سندِ سومی لازم نیست.
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id", ondelete="SET NULL"), nullable=True
    )

    note: Mapped[str] = mapped_column(Text, default="", server_default="")
    #: کاربر ممکن است بعداً حذف شود؛ رویداد باید بماند.
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    check: Mapped["Check"] = relationship("Check")
