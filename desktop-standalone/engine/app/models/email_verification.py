"""کدِ تأییدِ ایمیل برای ثبت‌نام — پیش از ساختِ حساب.

**چرا جدولِ جداگانه و نه `auth_tokens`:** آن جدول `user_id` اجباری دارد (بازیابیِ رمز و
دعوت هر دو کاربرِ موجود دارند). ولی تأییدِ ایمیل *قبل از* وجودِ کاربر رخ می‌دهد — هنوز
هیچ ردیفی در users نیست — پس کلید اینجا **خودِ ایمیل** است، نه یک شناسه‌ی کاربر.

**چرا سراسری و بدونِ RLS:** مثلِ `auth_tokens`، این جریان پیش از احراز هویت و بی‌زمینه‌ی
مستأجر اجرا می‌شود؛ RLS با زمینه‌ی خالی صفر ردیف می‌داد و کل جریان «نامعتبر» می‌شد.
مرزِ محافظت خودِ کد است: فقط hashِ نمک‌خورده (با ایمیل) ذخیره می‌شود، سقفِ تلاش دارد و
زماندار است.
"""
from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin


class EmailVerificationCode(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "email_verification_codes"

    #: ایمیلِ در حالِ تأیید (نرمال‌شده: trim + lowercase). کلیدِ جست‌وجو.
    email: Mapped[str] = mapped_column(String(320), index=True)

    #: SHA-256ِ `email:purpose:code`. خامِ کد هرگز ذخیره نمی‌شود؛ نمکِ ایمیل تصادمِ
    #: کدهای ۶رقمیِ یکسانِ دو ایمیل را جدا می‌کند.
    code_hash: Mapped[str] = mapped_column(String(64), index=True)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    #: تلاش‌های ناموفق. کدِ ۶رقمی فقط یک‌میلیون حالت دارد؛ بعد از سقف قفل می‌شود.
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
