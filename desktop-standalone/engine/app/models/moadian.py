import uuid
from datetime import date as date_, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin

SUBMISSION_STATUSES = ("pending", "sent", "confirmed", "rejected", "failed")


class MoadianSettings(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """اعتبارنامه و تنظیماتِ سامانه‌ی مؤدیانِ هر کسب‌وکار — یک ردیف برای هر مستأجر.

    **کلید خصوصی راز است.** اینجا ذخیره می‌شود چون امضای صورتحساب سمتِ سرور انجام
    می‌شود، ولی هرگز در پاسخِ API برنمی‌گردد (اسکیمای خروجی فقط `has_private_key` را
    می‌دهد) و در لاگ نمی‌آید. جداسازیِ بین مستأجرها با همان RLSِ بقیه‌ی جدول‌هاست.
    """

    __tablename__ = "moadian_settings"
    __table_args__ = (
        # هر کسب‌وکار فقط یک پیکربندی دارد؛ بدون این قید دو ردیفِ متناقض ممکن بود
        # و انتخابِ «کدام اعتبارنامه» بی‌قاعده می‌شد.
        UniqueConstraint("tenant_id", name="uq_moadian_settings_tenant"),
    )

    #: شناسه یکتای حافظه مالیاتی — ۶ کاراکتر، از کارپوشه گرفته می‌شود.
    memory_id: Mapped[str] = mapped_column(String(6), default="")
    #: شماره اقتصادی مؤدی
    economic_code: Mapped[str] = mapped_column(String(20), default="")
    #: شناسه ملی/کد ملی مؤدی (فیلد tins در بسته‌ی صورتحساب)
    national_id: Mapped[str] = mapped_column(String(20), default="")
    #: کلید خصوصیِ PEM برای امضای بسته — راز؛ هرگز در پاسخ API برنمی‌گردد.
    private_key_pem: Mapped[str] = mapped_column(Text, default="")
    #: گواهیِ امضای X.509 (PEM) که در هدرِ `x5c` بسته‌های JWS/توکن قرار می‌گیرد.
    #: پروتکل v2 هم کلید خصوصی و هم گواهیِ متناظر را لازم دارد.
    certificate_pem: Mapped[str] = mapped_column(Text, default="", server_default="")
    #: محیطِ ارسال. پیش‌فرض سندباکس است تا ارسالِ ناخواسته به سامانه‌ی واقعی رخ ندهد.
    is_sandbox: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    #: تا وقتی فعال نشده، هیچ ارسالی انجام نمی‌شود.
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    #: در صورت نیاز، آدرسِ پایه را دستی بازنویسی کن (خالی = پیش‌فرضِ محیط).
    base_url_override: Mapped[str] = mapped_column(String(300), default="")
    #: شمارنده‌ی سریالِ داخلیِ صورتحساب — ورودیِ تولیدِ شناسه مالیاتی.
    last_serial: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class MoadianSubmission(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """یک تلاشِ ارسالِ صورتحساب به سامانه‌ی مؤدیان، با ردِ کاملِ درخواست و پاسخ.

    شناسه مالیاتی روی خودِ رکورد می‌ماند (نه محاسبه‌ی دوباره) چون بخشی از سندِ
    قانونی است: اگر بعداً الگوریتم یا سریال عوض شود، شناسه‌ی ارسال‌شده نباید تغییر کند.
    """

    __tablename__ = "moadian_submissions"
    __table_args__ = (
        CheckConstraint(f"status IN {SUBMISSION_STATUSES}", name="ck_moadian_submissions_status"),
        UniqueConstraint("tenant_id", "tax_id", name="uq_moadian_submissions_tax_id"),
    )

    sales_invoice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sales_invoices.id"), index=True)
    #: شناسه یکتای مالیاتی ۲۲ کاراکتری
    tax_id: Mapped[str] = mapped_column(String(22), index=True)
    serial: Mapped[int] = mapped_column(Integer)
    invoice_date: Mapped[date_] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    #: شماره مرجعِ دریافتی از سامانه (برای استعلامِ بعدی)
    reference_number: Mapped[str] = mapped_column(String(100), default="")
    error_message: Mapped[str] = mapped_column(Text, default="")
    request_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    response_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
