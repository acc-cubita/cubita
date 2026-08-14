"""اشتراک کسب‌وکار — چه کسی تا کِی حق استفاده دارد.

**مسئله‌ای که حل می‌کند:** پلن‌ها `billing_period: "yearly"` دارند و ۴.۸ تا ۲۴
میلیون تومان **در سال** فروخته می‌شوند، ولی تا امروز هیچ فیلد انقضایی در هیچ مدلی
نبود. یعنی مشتری یک بار پرداخت می‌کرد و برای همیشه نرم‌افزار را داشت. این SaaS
نیست، یک خرید یک‌باره با مراحل اضافه است.

**چرا جدول جدا و نه چند ستون روی Tenant:** کسب‌وکاری که سه سال تمدید کرده سه ردیف
دارد، و همان تاریخچه است که «این مشتری از کِی با ماست» و «چند بار تمدید کرده» را
جواب می‌دهد. ستون روی Tenant فقط آخرین وضعیت را نگه می‌دارد و گذشته را پاک می‌کند.

**چرا سراسری و بدون RLS:** این داده‌ی صفحه‌ی کنترل پلتفرم است (قیف فروش خودِ
کوبیتا)، نه دفتر مشتری. همان تفکیک control-plane از data-plane که در deps.py
برای مجوزها انجام شد.

**وضعیت ذخیره نمی‌شود، محاسبه می‌شود.** یک ستون `status` که باید با گذر زمان
عوض شود، فقط تا وقتی درست است که یک cron به‌موقع اجرا شده باشد — و روزی که اجرا
نشود، سیستم با اطمینان عدد غلط می‌دهد. تاریخ‌ها منبع حقیقت‌اند و وضعیت از آن‌ها
مشتق می‌شود، پس همیشه درست است.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin


class Subscription(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "subscriptions"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plans.id"), nullable=True
    )

    #: خریدی که این دوره را ساخت. برای تمدید دستی یا هدیه خالی است.
    purchase_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchases.id"), nullable=True
    )

    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    #: لغو صریح توسط مشتری یا ما. با انقضا فرق دارد: لغوشده تمدید نمی‌شود.
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    #: چرا این دوره ساخته شد — «خرید»، «تمدید»، «هدیه»، «انتقال از سیستم قدیم».
    note: Mapped[str] = mapped_column(Text, default="")

    #: manual | zarinpal — از کجا آمد
    source: Mapped[str] = mapped_column(String(30), default="manual")

    plan = relationship("Plan")
