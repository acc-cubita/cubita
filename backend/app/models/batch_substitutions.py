"""جایگزینیِ بار — ردِ ممیزیِ §۱۳.

اگر بارِ اصلی قابلِ تحویل نبود (شکسته، گم‌شده، ته‌انبار نبود)، انباردارِ مجاز
بارِ دیگری برمی‌دارد. §۱۳ صریح است: «این تغییر نباید بدون Audit Trail انجام
شود».

## چرا از دفترِ انبار مشتق نمی‌شود

حرکتِ دفتر می‌گوید از کدام بار چه‌قدر رفت، پس «چه شد» را می‌دانیم. ولی
نمی‌گوید **چرا** بارِ اول کنار گذاشته شد — و همین چیزی است که ماهِ بعد کسی
دنبالش می‌گردد. دلیل از هیچ داده‌ی موجودی درنمی‌آید، پس ستونِ خودش را دارد و
اجباری است.
"""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin


class BatchSubstitution(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """«بارِ الف را برداشتم و به‌جایش ب دادم، این‌قدر، به این دلیل»."""

    __tablename__ = "batch_substitutions"

    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_batch_substitutions_qty"),
        #: جایگزینی با خودش معنا ندارد و فقط نویز در گزارش می‌سازد.
        CheckConstraint("original_batch_id <> new_batch_id", name="ck_batch_substitutions_distinct"),
    )

    original_batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stock_batches.id", ondelete="RESTRICT"), index=True
    )
    new_batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stock_batches.id", ondelete="RESTRICT"), index=True
    )
    qty: Mapped[float] = mapped_column(Numeric(18, 3))
    #: سندی که جایگزینی در آن رخ داد — چندریختی، مثلِ `source_id`ِ دفتر.
    source_type: Mapped[str] = mapped_column(String(50), default="", server_default="")
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    #: **اجباری.** جایگزینیِ بی‌دلیل، همان گزارشی را که §۱۳ می‌خواهد بی‌معنا می‌کند.
    reason: Mapped[str] = mapped_column(Text)
    changed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
