"""کلید یکتاسازی درخواست — محافظت در برابر ثبت دوباره‌ی یک سند مالی.

**مسئله‌ای که حل می‌کند:** امروز هیچ دفاعی در برابر ارسال تکراری وجود ندارد. کاربری
که روی «ثبت فاکتور» دوبار کلیک کند، یا مرورگری که درخواست را retry کند، یا شبکه‌ای
که پاسخ را گم کند و کلاینت دوباره بفرستد — هر سه **دو سند مالی، دو سند حسابداری و
دو حرکت انبار** می‌سازند. برای نرم‌افزار حسابداری این از هر باگ دیگری بدتر است، چون
خطا نمی‌دهد و فقط دفتر را غلط می‌کند.

**چرا فقط شناسه‌ی منبع ذخیره می‌شود و نه بدنه‌ی پاسخ:** برای ذخیره‌ی پاسخ باید
سریال‌سازی FastAPI را دستی تکرار کنیم، که یعنی دو مسیر سریال‌سازی که می‌توانند از هم
جدا بیفتند. نگه داشتن شناسه و واکشی دوباره‌ی همان سند، هم کوچک‌تر است و هم همیشه با
آنچه اندپوینت واقعاً برمی‌گرداند یکی می‌ماند.

**چرا hash درخواست هم ذخیره می‌شود:** اگر کلاینت همان کلید را با محتوای متفاوت
بفرستد، برگرداندن بی‌صدای نتیجه‌ی قبلی یعنی فاکتور دومش خاموش گم می‌شود. آن حالت
خطاست، نه تکرار.
"""
import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin


class IdempotencyKey(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "idempotency_keys"

    __table_args__ = (
        # یکتایی مرکب با مستأجر: دو کسب‌وکار می‌توانند اتفاقی یک کلید تولید کنند و
        # نباید روی هم اثر بگذارند. این قید همچنین همان چیزی است که درخواست‌های
        # هم‌زمان را سریالیزه می‌کند — توضیح در services/idempotency.py
        UniqueConstraint("tenant_id", "key", name="uq_idempotency_tenant_key"),
    )

    key: Mapped[str] = mapped_column(String(200), index=True)

    #: کدام اندپوینت. همان کلید روی دو عملیات متفاوت نباید نتیجه‌ی یکی را به دیگری بدهد.
    operation: Mapped[str] = mapped_column(String(80))

    #: SHA-256 بدنه‌ی درخواست، برای تشخیص «همان کلید، محتوای متفاوت».
    request_hash: Mapped[str] = mapped_column(String(64))

    #: شناسه‌ی سندی که ساخته شد. تا وقتی عملیات تمام نشده NULL است.
    resource_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
