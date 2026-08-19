"""رفرش‌توکنِ نشستِ بلندمدت (اپ موبایل) — «همیشه‌واردمانده».

**چرا سراسری و بدونِ RLS** (مثلِ auth_tokens): رفرش قبل از هر زمینه‌ی مستأجری اجرا
می‌شود؛ کلاینت فقط یک رازِ ۲۵۶بیتی می‌فرستد و انتظار دارد یک accessِ تازه بگیرد. اگر
این جدول زیر RLS می‌رفت، کوئریِ رفرش با زمینه‌ی خالی صفر ردیف می‌داد و هر نشستِ
معتبری «نامعتبر» به‌نظر می‌رسید. هویتِ کاربر هم سراسری است (یک نفر عضوِ چند کسب‌وکار).

مرزِ محافظت خودِ راز است: فقط SHA-256ِ توکن ذخیره می‌شود، پس خواندنِ کلِ جدول هم
چیزی به مهاجم نمی‌دهد. علاوه بر آن به `user.token_version` گره خورده تا تغییرِ رمز
همه‌ی رفرش‌ها را هم — مثلِ اکسس‌ها — یک‌جا باطل کند.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin


class RefreshToken(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "refresh_tokens"

    #: SHA-256ِ خودِ رفرش‌توکن. مقدار خام هرگز ذخیره نمی‌شود.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    #: کسب‌وکاری که نشست به آن گره خورده؛ accessِ تازه برای همین مستأجر صادر می‌شود.
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )

    #: عکسِ نسلِ توکنِ کاربر در لحظه‌ی صدور. اگر با `user.token_version` نخواند (رمز عوض
    #: شده)، رفرش رد می‌شود — همان مکانیزمی که اکسس‌ها را باطل می‌کند.
    token_version: Mapped[int] = mapped_column(Integer, nullable=False)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    #: لحظه‌ی ابطال (چرخشِ رفرش یا خروج). ناتهی یعنی این توکن دیگر مصرف‌شدنی نیست.
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(foreign_keys=[user_id])  # noqa: F821
