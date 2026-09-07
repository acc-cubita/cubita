"""گزارشِ کرشِ کلاینت‌ها (فعلاً اپِ موبایل).

**چرا جدولِ سراسری و نه مستأجرمحور:** کرش ممکن است *پیش از ورود* بیفتد — موقعِ
راه‌اندازی، در صفحه‌ی ورود، یا وقتی رفرش‌توکن باطل شده. آن لحظه هیچ زمینه‌ی مستأجری
وجود ندارد. اگر جدول RLS داشت، دقیقاً گزارش‌هایی که بیشترین ارزش را دارند (خطای
راه‌اندازی و احراز) هرگز نوشته نمی‌شدند.

`tenant_id` و `user_id` اختیاری‌اند و فقط وقتی پر می‌شوند که گزارش با توکنِ معتبر
آمده باشد — برای پیگیری مفیدند، ولی شرطِ ثبت نیستند.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ClientError(Base):
    __tablename__ = "client_errors"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    #: شناسه‌ی ساخته‌شده روی خودِ دستگاه. یکتاست تا ارسالِ دوباره‌ی یک صف (که کاملاً
    #: عادی است: اگر پاسخِ سرور به دستگاه نرسد، دفعه‌ی بعد دوباره می‌فرستد) رکوردِ
    #: تکراری نسازد.
    client_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    fatal: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    name: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    stack: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: کجای اپ بود. برای دسته‌بندیِ گزارش‌ها مهم‌ترین فیلد بعد از پیام است.
    screen: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    app_version: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    platform: Mapped[str | None] = mapped_column(String(20), nullable=True)
    os_version: Mapped[str | None] = mapped_column(String(30), nullable=True)
    device: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # هر دو اختیاری: گزارشِ پیش از ورود هیچ‌کدام را ندارد. ondelete=SET NULL چون
    # حذفِ یک کاربر نباید سابقه‌ی خطاها را پاک کند.
    user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    tenant_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True
    )
