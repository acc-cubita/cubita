"""افزونه‌های تعمیرگاه؛ اسناد و snapshotهای نسخهٔ منتشرشده تغییر نمی‌کنند."""
import uuid
from datetime import datetime
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, ForeignKeyConstraint, Integer, Numeric, String, Text, UniqueConstraint, Index, CheckConstraint, text
from decimal import Decimal
from datetime import date
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


class RepairServiceProfile(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = 'repair_service_profiles'
    __table_args__ = (ForeignKeyConstraint(['tenant_id','branch_id'],['repair_branches.tenant_id','repair_branches.id']),ForeignKeyConstraint(['tenant_id','service_id'],['items.tenant_id','items.id']),UniqueConstraint('tenant_id','branch_id','service_id','revision'),CheckConstraint('suggested_charge >= 0 AND estimated_minutes >= 0'))
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    service_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    revision: Mapped[int] = mapped_column(Integer)
    suggested_charge: Mapped[Decimal] = mapped_column(Numeric(18,0))
    estimated_minutes: Mapped[int] = mapped_column(Integer)
    enabled: Mapped[bool] = mapped_column(Boolean,default=True)
    recorded_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))


class RepairTypeProtocol(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = 'repair_type_protocols'
    __table_args__ = (ForeignKeyConstraint(['tenant_id','branch_id'],['repair_branches.tenant_id','repair_branches.id']),ForeignKeyConstraint(['tenant_id','type_id'],['repair_device_types.tenant_id','repair_device_types.id']),UniqueConstraint('tenant_id','branch_id','type_id','revision'),UniqueConstraint('tenant_id','id'))
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    type_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    revision: Mapped[int] = mapped_column(Integer)
    metrics: Mapped[list] = mapped_column(JSONB)
    checklist: Mapped[list] = mapped_column(JSONB)
    requires_supervisor_review: Mapped[bool] = mapped_column(Boolean,default=False)
    recorded_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))


class RepairDiagnosticRecord(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = 'repair_diagnostic_records'
    __table_args__ = (ForeignKeyConstraint(['tenant_id','case_id'],['repair_cases.tenant_id','repair_cases.id']),ForeignKeyConstraint(['tenant_id','protocol_id'],['repair_type_protocols.tenant_id','repair_type_protocols.id']),UniqueConstraint('tenant_id','case_id','revision'),UniqueConstraint('tenant_id','id'))
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    protocol_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    revision: Mapped[int] = mapped_column(Integer)
    work_version: Mapped[int] = mapped_column(Integer)
    protocol_snapshot: Mapped[dict] = mapped_column(JSONB)
    measurements: Mapped[list] = mapped_column(JSONB)
    checklist: Mapped[dict] = mapped_column(JSONB)
    root_cause: Mapped[str] = mapped_column(Text)
    test_failure_reason: Mapped[str] = mapped_column(Text,default='')
    recorded_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))


class RepairSupervisorReview(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = 'repair_supervisor_reviews'
    __table_args__ = (ForeignKeyConstraint(['tenant_id','case_id'],['repair_cases.tenant_id','repair_cases.id']),ForeignKeyConstraint(['tenant_id','diagnostic_id'],['repair_diagnostic_records.tenant_id','repair_diagnostic_records.id']),UniqueConstraint('tenant_id','diagnostic_id'))
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    diagnostic_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    approved: Mapped[bool] = mapped_column(Boolean)
    reason: Mapped[str] = mapped_column(Text)
    reviewed_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))


class RepairWorkPause(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = 'repair_work_pauses'
    __table_args__ = (ForeignKeyConstraint(['tenant_id','case_id'],['repair_cases.tenant_id','repair_cases.id']),Index('uq_repair_active_pause','tenant_id','case_id',unique=True,postgresql_where=text('ended_at IS NULL')),CheckConstraint('ended_at IS NULL OR ended_at >= started_at'))
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    version: Mapped[int] = mapped_column(Integer,default=1)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(Text)
    end_reason: Mapped[str] = mapped_column(Text,default='')
    recorded_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))
    ended_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('users.id'))


class RepairDeadlineAgreement(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = 'repair_deadline_agreements'
    __table_args__ = (ForeignKeyConstraint(['tenant_id','case_id'],['repair_cases.tenant_id','repair_cases.id']),ForeignKeyConstraint(['tenant_id','case_id','estimate_id'],['repair_estimates.tenant_id','repair_estimates.case_id','repair_estimates.id']))
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    version: Mapped[int] = mapped_column(Integer,default=1)
    old_due_date: Mapped[date | None] = mapped_column(Date)
    new_due_date: Mapped[date] = mapped_column(Date)
    estimate_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    estimate_revision: Mapped[int | None] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20),default='pending')
    customer_name: Mapped[str] = mapped_column(String(200),default='')
    approval_method: Mapped[str] = mapped_column(String(20),default='')
    decision_reason: Mapped[str] = mapped_column(Text,default='')
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recorded_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))
    decided_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('users.id'))


class RepairKnowledgeArticle(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = 'repair_knowledge_articles'
    __table_args__ = (ForeignKeyConstraint(['tenant_id','branch_id'],['repair_branches.tenant_id','repair_branches.id']),ForeignKeyConstraint(['tenant_id','type_id'],['repair_device_types.tenant_id','repair_device_types.id']),UniqueConstraint('tenant_id','branch_id','family_id','revision'))
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    type_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    revision: Mapped[int] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer,default=1)
    title: Mapped[str] = mapped_column(String(200))
    symptoms: Mapped[str] = mapped_column(Text)
    root_cause: Mapped[str] = mapped_column(Text)
    solution: Mapped[str] = mapped_column(Text)
    recorded_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('users.id'))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RepairWorkTimeLink(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = 'repair_work_time_links'
    __table_args__ = (ForeignKeyConstraint(['tenant_id','case_id'],['repair_cases.tenant_id','repair_cases.id']),ForeignKeyConstraint(['tenant_id','session_id'],['repair_time_sessions.tenant_id','repair_time_sessions.id']),UniqueConstraint('tenant_id','work_id'),UniqueConstraint('tenant_id','session_id'))
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    work_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('repair_work.id'))
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    session_version: Mapped[int] = mapped_column(Integer)
    confirmed_seconds: Mapped[int] = mapped_column(Integer)


class RepairPartAssessment(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = 'repair_part_assessments'
    __table_args__ = (ForeignKeyConstraint(['tenant_id','case_id'],['repair_cases.tenant_id','repair_cases.id']),UniqueConstraint('tenant_id','part_id','revision'),UniqueConstraint('tenant_id','id'))
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    part_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('repair_parts.id'))
    revision: Mapped[int] = mapped_column(Integer)
    quality: Mapped[str] = mapped_column(String(20))
    compatibility: Mapped[str] = mapped_column(Text)
    test_result: Mapped[str] = mapped_column(Text)
    expected_supply_date: Mapped[date | None] = mapped_column(Date)
    purchase_invoice_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('purchase_invoices.id'))
    purchase_line_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('purchase_invoice_lines.id'))
    supplier_snapshot: Mapped[dict] = mapped_column(JSONB,default=dict)
    warranty_until: Mapped[date | None] = mapped_column(Date)
    warranty_terms: Mapped[str] = mapped_column(Text)
    recorded_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))


class RepairSupplierClaim(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = 'repair_supplier_claims'
    __table_args__ = (ForeignKeyConstraint(['tenant_id','case_id'],['repair_cases.tenant_id','repair_cases.id']),ForeignKeyConstraint(['tenant_id','assessment_id'],['repair_part_assessments.tenant_id','repair_part_assessments.id']))
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    assessment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    version: Mapped[int] = mapped_column(Integer,default=1)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20),default='submitted')
    response: Mapped[str] = mapped_column(Text,default='')
    purchase_return_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('purchase_returns.id'))
    replacement_part_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('repair_parts.id'))
    recorded_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))
    resolved_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('users.id'))


class RepairHarvest(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = 'repair_harvests'
    __table_args__ = (ForeignKeyConstraint(['tenant_id','branch_id'],['repair_branches.tenant_id','repair_branches.id']),ForeignKeyConstraint(['tenant_id','item_id'],['items.tenant_id','items.id']),CheckConstraint('waste_percent >= 0 AND waste_percent <= 100'))
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    version: Mapped[int] = mapped_column(Integer,default=1)
    status: Mapped[str] = mapped_column(String(20),default='draft')
    on: Mapped[date] = mapped_column(Date)
    source_warehouse_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('warehouses.id'))
    output_warehouse_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('warehouses.id'))
    device_input: Mapped[dict] = mapped_column(JSONB)
    outputs: Mapped[list] = mapped_column(JSONB)
    waste_percent: Mapped[Decimal] = mapped_column(Numeric(9,6))
    waste_account_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('accounts.id'))
    reason: Mapped[str] = mapped_column(Text)
    device_cost: Mapped[Decimal | None] = mapped_column(Numeric(18,0))
    waste_cost: Mapped[Decimal | None] = mapped_column(Numeric(18,0))
    issue_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('warehouse_issues.id'))
    receipt_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('warehouse_receipts.id'))
    waste_entry_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('journal_entries.id'))
    recorded_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('users.id'))
    voided_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('users.id'))
    void_reason: Mapped[str] = mapped_column(Text,default='')


class RepairParticipation(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = 'repair_participations'
    __table_args__ = (ForeignKeyConstraint(['tenant_id','case_id'],['repair_cases.tenant_id','repair_cases.id']),UniqueConstraint('tenant_id','work_id','revision'))
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    work_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('repair_work.id'))
    revision: Mapped[int] = mapped_column(Integer)
    shares: Mapped[list] = mapped_column(JSONB)
    reason: Mapped[str] = mapped_column(Text)
    approved_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))


class RepairCustomerFollowup(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = 'repair_customer_followups'
    __table_args__ = (ForeignKeyConstraint(['tenant_id','case_id'],['repair_cases.tenant_id','repair_cases.id']),)
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    message_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('repair_customer_messages.id'))
    previous_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('repair_customer_followups.id'))
    kind: Mapped[str] = mapped_column(String(20))
    body: Mapped[str] = mapped_column(Text)
    customer_name: Mapped[str] = mapped_column(String(200))
    direction: Mapped[str] = mapped_column(String(20))
    complaint_stage: Mapped[str] = mapped_column(String(20))
    responsible_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('users.id'))
    recorded_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))


class RepairNotificationPolicy(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = 'repair_notification_policies'
    __table_args__ = (ForeignKeyConstraint(['tenant_id','branch_id'],['repair_branches.tenant_id','repair_branches.id']),UniqueConstraint('tenant_id','branch_id','revision'))
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    revision: Mapped[int] = mapped_column(Integer)
    events: Mapped[list] = mapped_column(JSONB)
    overdue_days: Mapped[int] = mapped_column(Integer)
    uncollected_days: Mapped[int] = mapped_column(Integer)
    repeat_days: Mapped[int] = mapped_column(Integer)
    approved_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))


class RepairHistoryImport(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = 'repair_history_imports'
    __table_args__ = (ForeignKeyConstraint(['tenant_id','branch_id'],['repair_branches.tenant_id','repair_branches.id']),UniqueConstraint('tenant_id','branch_id','source_id','digest'))
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    source_id: Mapped[str] = mapped_column(String(120))
    digest: Mapped[str] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer,default=1)
    status: Mapped[str] = mapped_column(String(20),default='preview')
    rows: Mapped[list] = mapped_column(JSONB)
    recorded_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))


class RepairHistoricalRecord(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """Read-only imported history, deliberately without operational case/document links."""
    __tablename__ = 'repair_historical_records'
    __table_args__ = (ForeignKeyConstraint(['tenant_id','branch_id'],['repair_branches.tenant_id','repair_branches.id']),UniqueConstraint('tenant_id','branch_id','source_id','external_id'))
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    import_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('repair_history_imports.id'))
    source_id: Mapped[str] = mapped_column(String(120))
    external_id: Mapped[str] = mapped_column(String(120))
    data: Mapped[dict] = mapped_column(JSONB)


class RepairOnsiteAction(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__='repair_onsite_actions'
    __table_args__=(ForeignKeyConstraint(['tenant_id','request_id'],['repair_service_requests.tenant_id','repair_service_requests.id']),)
    request_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True))
    appointment_id: Mapped[uuid.UUID]=mapped_column(ForeignKey('repair_appointments.id'))
    version: Mapped[int]=mapped_column(Integer,default=1)
    description: Mapped[str]=mapped_column(Text)
    result: Mapped[str]=mapped_column(Text)
    recorded_by_id: Mapped[uuid.UUID]=mapped_column(ForeignKey('users.id'))


class RepairOnsiteApproval(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__='repair_onsite_approvals'
    __table_args__=(ForeignKeyConstraint(['tenant_id','request_id'],['repair_service_requests.tenant_id','repair_service_requests.id']),UniqueConstraint('tenant_id','action_id','action_version'))
    request_id: Mapped[uuid.UUID]=mapped_column(UUID(as_uuid=True))
    action_id: Mapped[uuid.UUID]=mapped_column(ForeignKey('repair_onsite_actions.id'))
    action_version: Mapped[int]=mapped_column(Integer)
    approver_name: Mapped[str]=mapped_column(String(200))
    signature: Mapped[list]=mapped_column(JSONB)
    snapshot: Mapped[dict]=mapped_column(JSONB)
    signature_hash: Mapped[str]=mapped_column(String(64))
    recorded_by_id: Mapped[uuid.UUID]=mapped_column(ForeignKey('users.id'))
