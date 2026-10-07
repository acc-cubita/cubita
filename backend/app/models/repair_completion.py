"""افزونه‌های تعمیرگاه؛ اسناد و snapshotهای نسخهٔ منتشرشده تغییر نمی‌کنند."""
import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, ForeignKeyConstraint, Integer, String, Text, UniqueConstraint, Index, CheckConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin


class RepairBranchSettings(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = 'repair_branch_settings'
    __table_args__ = (ForeignKeyConstraint(['tenant_id','branch_id'],['repair_branches.tenant_id','repair_branches.id']), UniqueConstraint('tenant_id','branch_id'))
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    version: Mapped[int] = mapped_column(Integer, default=1)
    default_location: Mapped[str] = mapped_column(String(200))
    terms: Mapped[str] = mapped_column(Text)
    code: Mapped[str] = mapped_column(String(40))
    number_format: Mapped[str] = mapped_column(String(120), default='{branch}-{year}-{number:06d}')


class RepairIntakeBatch(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = 'repair_intake_batches'
    __table_args__ = (UniqueConstraint('tenant_id','id'),)
    contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('contacts.id'))
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))


class RepairCaseDetails(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = 'repair_case_details'
    __table_args__ = (ForeignKeyConstraint(['tenant_id','case_id'],['repair_cases.tenant_id','repair_cases.id']), ForeignKeyConstraint(['tenant_id','batch_id'],['repair_intake_batches.tenant_id','repair_intake_batches.id']), ForeignKeyConstraint(['tenant_id','representative_contact_id'],['contacts.tenant_id','contacts.id']), ForeignKeyConstraint(['tenant_id','organization_unit_contact_id'],['contacts.tenant_id','contacts.id']), UniqueConstraint('tenant_id','case_id'))
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    batch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    display_number: Mapped[str] = mapped_column(String(220), default='')
    organization_unit: Mapped[str] = mapped_column(String(200), default='')
    representative: Mapped[str] = mapped_column(String(200), default='')
    representative_contact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    organization_unit_contact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    organization_order: Mapped[str] = mapped_column(String(120), default='')
    settings_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict)
    receipt_revision: Mapped[int] = mapped_column(Integer, default=1)


class RepairTechnicianCapacity(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = 'repair_technician_capacity'
    __table_args__ = (UniqueConstraint('tenant_id','technician_id'),)
    technician_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))
    max_active_cases: Mapped[int | None] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer, default=1)


class RepairAcknowledgment(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = 'repair_acknowledgments'
    __table_args__ = (ForeignKeyConstraint(['tenant_id','case_id'],['repair_cases.tenant_id','repair_cases.id']), UniqueConstraint('tenant_id','case_id','kind','document_revision'))
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    kind: Mapped[str] = mapped_column(String(20))
    document_revision: Mapped[int] = mapped_column(Integer)
    signer_name: Mapped[str] = mapped_column(String(200))
    signer_relation: Mapped[str] = mapped_column(String(200))
    strokes: Mapped[list] = mapped_column(JSONB)
    document_snapshot: Mapped[dict] = mapped_column(JSONB)
    document_hash: Mapped[str] = mapped_column(String(64))
    confirmed_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))


class RepairBulkOperation(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = 'repair_bulk_operations'
    action: Mapped[str] = mapped_column(String(20))
    results: Mapped[list] = mapped_column(JSONB, default=list)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))


class RepairTimeSession(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = 'repair_time_sessions'
    __table_args__ = (
        ForeignKeyConstraint(['tenant_id','case_id'],['repair_cases.tenant_id','repair_cases.id']),
        UniqueConstraint('tenant_id','id'),
        Index('uq_repair_active_timer','tenant_id','technician_id',unique=True,postgresql_where=text('stopped_at IS NULL')),
        CheckConstraint('confirmed_seconds IS NULL OR confirmed_seconds >= 0'),
    )
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    technician_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))
    version: Mapped[int] = mapped_column(Integer,default=1)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_seconds: Mapped[int | None] = mapped_column(Integer)


class RepairTimeCorrection(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = 'repair_time_corrections'
    __table_args__ = (ForeignKeyConstraint(['tenant_id','session_id'],['repair_time_sessions.tenant_id','repair_time_sessions.id']),UniqueConstraint('tenant_id','session_id','session_version'))
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    session_version: Mapped[int] = mapped_column(Integer)
    old_seconds: Mapped[int | None] = mapped_column(Integer)
    new_seconds: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text)
    recorded_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))
