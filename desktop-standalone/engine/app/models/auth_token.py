"""توکن‌های یک‌بارمصرف: بازیابی رمز و دعوت همکار.

**چرا این جدول سراسری است و RLS ندارد** — و چرا این استثنا امن است:

هر دو جریانی که از این جدول استفاده می‌کنند *قبل از* احراز هویت اجرا می‌شوند. کسی
که رمزش را فراموش کرده توکنی ندارد، و کسی که دعوت شده هنوز حساب فعالی ندارد؛ پس در
لحظه‌ی مصرف توکن هیچ زمینه‌ی مستأجری وجود ندارد. اگر این جدول زیر RLS می‌رفت، سیاست
با زمینه‌ی خالی صفر ردیف برمی‌گرداند و هر لینک بازیابی «نامعتبر» به‌نظر می‌رسید —
شکستی که مثل باگ منطقی دیده می‌شود نه مثل مشکل ایزوله‌سازی.

مرز محافظت اینجا خودِ راز است، نه RLS: توکن ۲۵۶ بیت آنتروپی دارد و فقط hash آن
ذخیره می‌شود، پس دسترسی خواندن به کل جدول هم چیزی به مهاجم نمی‌دهد.

**ولی یک خطر واقعی باقی می‌ماند:** `tenant_id` اینجا فقط داده است، نه مرز. هر
کوئریِ *فهرست‌کننده* روی این جدول باید صراحتاً بر اساس tenant_id فیلتر شود، وگرنه
دعوت‌های همه‌ی کسب‌وکارها را برمی‌گرداند. RLS این اشتباه را نمی‌گیرد، پس
`test_auth_tokens.py` می‌گیردش.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin

PURPOSE_PASSWORD_RESET = "password_reset"
PURPOSE_INVITE = "invite"
#: کدهای کوتاهِ عددیِ پیامکی (برخلافِ دو موردِ بالا که توکنِ ۲۵۶بیتیِ لینک‌اند).
PURPOSE_PHONE_VERIFY = "phone_verify"
PURPOSE_SMS_PASSWORD_RESET = "sms_password_reset"
PURPOSES = (PURPOSE_PASSWORD_RESET, PURPOSE_INVITE, PURPOSE_PHONE_VERIFY, PURPOSE_SMS_PASSWORD_RESET)


class AuthToken(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "auth_tokens"

    purpose: Mapped[str] = mapped_column(String(30), index=True)

    #: SHA-256 خودِ توکن. مقدار خام هرگز ذخیره و هرگز لاگ نمی‌شود — اگر ذخیره می‌شد،
    #: هر کسی با دسترسی خواندن به دیتابیس می‌توانست حساب هر کاربری را تصاحب کند.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)

    #: فقط برای دعوت پر می‌شود: مشخص می‌کند دعوت به کدام کسب‌وکار است.
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    #: تلاش‌های ناموفقِ راستی‌آزماییِ کدِ کوتاهِ عددی. کدِ ۶رقمی فقط یک‌میلیون حالت دارد،
    #: پس بدونِ سقفِ تلاش با چند صد درخواست حدس‌زدنی است؛ بعد از سقف، کد قفل می‌شود.
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)

    user: Mapped["User"] = relationship(foreign_keys=[user_id])  # noqa: F821
