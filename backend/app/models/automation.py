"""نامه، ارجاع و سابقهٔ مکاتبات؛ هیچ‌کدام اثر مالی ندارند."""
import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, CheckConstraint, Date, DateTime, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin


class OfficeLetter(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "office_letters"
    __table_args__ = (
        UniqueConstraint("tenant_id", "kind", "number", name="uq_office_letter_number"),
        CheckConstraint("kind IN ('incoming','outgoing','internal')", name="ck_office_letter_kind"),
        CheckConstraint("status IN ('draft','registered','archived')", name="ck_office_letter_status"),
        CheckConstraint("priority IN ('normal','urgent')", name="ck_office_letter_priority"),
    )
    kind: Mapped[str] = mapped_column(String(16))
    number: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    subject: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text, default="")
    sender: Mapped[str] = mapped_column(String(200), default="")
    addressee: Mapped[str] = mapped_column(String(200), default="")
    external_number: Mapped[str] = mapped_column(String(100), default="")
    external_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    letter_date: Mapped[date] = mapped_column(Date, index=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    priority: Mapped[str] = mapped_column(String(16), default="normal")
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    registered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)


class OfficeReferral(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "office_referrals"
    letter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("office_letters.id"), index=True)
    from_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    to_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    instruction: Mapped[str] = mapped_column(Text, default="")
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    response: Mapped[str] = mapped_column(Text, default="")


class OfficeAttachment(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "office_attachments"
    letter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("office_letters.id"), index=True)
    filename: Mapped[str] = mapped_column(String(200))
    content_type: Mapped[str] = mapped_column(String(60))
    size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    # فایل در همان تراکنش و پشتیبان عمومی می‌ماند؛ مسیرِ عمومی/فایلِ یتیم نداریم.
    content: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))


class OfficeEvent(TenantMixin, UUIDPKMixin, Base):
    __tablename__ = "office_events"
    letter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("office_letters.id"), index=True)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
