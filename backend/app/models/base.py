import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from app.database import Base


class UUIDPKMixin:
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class VoidableMixin:
    """سندی که می‌تواند باطل شود — بدون اینکه پاک شود.

    حذف سند مالی در حسابداری قابل قبول نیست: دفتر باید نشان دهد چه اتفاقی افتاد و
    بعد چطور اصلاح شد، نه اینکه وانمود کند هرگز نیفتاده. پس ابطال یعنی این سه ستون
    پر می‌شوند و یک سند معکوس ثبت می‌شود؛ خودِ ردیف دست‌نخورده می‌ماند.

    `voided_at` تنها منبع حقیقت برای «آیا این سند باطل است» است. هر گزارشی که
    اسناد باطل را حساب کند، عدد غلط می‌دهد — ولی دفتر روزنامه عمداً هر دو سند
    (اصلی و معکوس) را نشان می‌دهد، چون جمعشان صفر است و همین ردِ حسابرسی است.
    """

    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    void_reason: Mapped[str] = mapped_column(Text, default="")

    @declared_attr
    def voided_by_id(cls) -> Mapped[uuid.UUID | None]:  # noqa: N805
        return mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    @property
    def is_voided(self) -> bool:
        return self.voided_at is not None
