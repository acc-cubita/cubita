"""توکنِ دستگاه برای اعلانِ Push (FCM) — اپ موبایل.

**چرا سراسری و بدونِ RLS:** دستگاه به یک *کاربر* تعلق دارد (که سراسری است)، نه به یک
مستأجر. `tenant_id` فقط ثبت می‌کند اپ هنگامِ ثبتِ دستگاه در کدام کسب‌وکار بود — داده‌ی
کمکی برای هدف‌گیریِ اعلان، نه مرزِ امنیتی. ارسالِ اعلان همیشه با فیلترِ صریحِ `user_id`
انجام می‌شود.

`fcm_token` یکتاست: یک دستگاهِ فیزیکی یک توکن دارد. اگر همان دستگاه با کاربرِ دیگری
دوباره وارد شود، ردیف به کاربرِ تازه منتقل می‌شود (upsert بر پایه‌ی توکن) تا اعلانِ
کاربرِ قبلی به دستگاهی که دیگر دستِ او نیست نرود.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin


class DeviceToken(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "device_tokens"

    #: توکنِ ثبتِ FCM — طولانی و یکتا به‌ازای هر دستگاه.
    fcm_token: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    #: کسب‌وکارِ فعالِ اپ هنگامِ ثبت (کمکی؛ نه مرزِ امنیتی).
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )

    platform: Mapped[str] = mapped_column(String(20), default="android", server_default="android")
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(foreign_keys=[user_id])  # noqa: F821
