"""دستگاه مشتری امانت است؛ هیچ رابطه‌ای با موجودی شرکت ندارد."""
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Integer, Index, text, LargeBinary, Numeric, String, Text, UniqueConstraint
from decimal import Decimal
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin


class RepairBranch(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "repair_branches"
    __table_args__ = (UniqueConstraint("tenant_id", "id"), UniqueConstraint("tenant_id", "name"))
    name: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    diagnostic_fee: Mapped[Decimal] = mapped_column(Numeric(18, 0), default=0)
    cancellation_fee: Mapped[Decimal] = mapped_column(Numeric(18, 0), default=0)
    discount_ceiling: Mapped[Decimal] = mapped_column(Numeric(18, 0), default=0)


class RepairBranchAccess(TenantMixin, UUIDPKMixin, Base):
    __tablename__ = "repair_branch_access"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "branch_id"], ["repair_branches.tenant_id", "repair_branches.id"]),
        UniqueConstraint("tenant_id", "branch_id", "user_id"),
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))


class RepairDeviceType(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "repair_device_types"
    __table_args__ = (UniqueConstraint("tenant_id", "id"), UniqueConstraint("tenant_id", "name"))
    name: Mapped[str] = mapped_column(String(120))
    fields: Mapped[list] = mapped_column(JSONB, default=list)
    checklist: Mapped[list] = mapped_column(JSONB, default=list)
    diagnostic_checklist: Mapped[list] = mapped_column(JSONB, default=list)
    quality_checklist: Mapped[list] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class RepairDevice(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "repair_devices"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(["tenant_id", "type_id"], ["repair_device_types.tenant_id", "repair_device_types.id"]),
    )
    type_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    brand: Mapped[str] = mapped_column(String(120), default="")
    model: Mapped[str] = mapped_column(String(120))
    serial: Mapped[str] = mapped_column(String(120), default="", index=True)
    imei: Mapped[str] = mapped_column(String(30), default="", index=True)
    attributes: Mapped[dict] = mapped_column(JSONB, default=dict)


class RepairCase(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "repair_cases"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"), UniqueConstraint("tenant_id", "number"),
        ForeignKeyConstraint(["tenant_id", "device_id"], ["repair_devices.tenant_id", "repair_devices.id"]),
        ForeignKeyConstraint(["tenant_id", "branch_id"], ["repair_branches.tenant_id", "repair_branches.id"]),
        CheckConstraint("priority IN ('normal','high','urgent')", name="ck_repair_priority"),
        ForeignKeyConstraint(["tenant_id", "contact_id"], ["contacts.tenant_id", "contacts.id"]),
        CheckConstraint("version > 0", name="ck_repair_version"),
    )
    number: Mapped[int] = mapped_column(Integer)
    device_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    contact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    owner_snapshot: Mapped[dict] = mapped_column(JSONB)
    device_snapshot: Mapped[dict] = mapped_column(JSONB)
    delivering_name: Mapped[str] = mapped_column(String(200), default="")
    delivering_phone: Mapped[str] = mapped_column(String(30), default="")
    reported_issue: Mapped[str] = mapped_column(Text)
    appearance: Mapped[str] = mapped_column(Text, default="")
    accessories: Mapped[str] = mapped_column(Text, default="")
    intake_checklist: Mapped[dict] = mapped_column(JSONB, default=dict)
    priority: Mapped[str] = mapped_column(String(10), default="normal")
    admission_date: Mapped[date] = mapped_column(Date, index=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    storage_location: Mapped[str] = mapped_column(String(200))
    terms: Mapped[str] = mapped_column(Text)
    approval_method: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(25), default="accepted")
    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    pause_reason: Mapped[str] = mapped_column(Text, default="")
    initial_diagnosis: Mapped[str] = mapped_column(Text, default="")
    final_diagnosis: Mapped[str] = mapped_column(Text, default="")
    diagnosis_checklist: Mapped[dict] = mapped_column(JSONB, default=dict)
    fault_ids: Mapped[list] = mapped_column(JSONB, default=list)
    work_version: Mapped[int] = mapped_column(Integer, default=1)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))


class RepairEvent(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "repair_events"
    __table_args__ = (ForeignKeyConstraint(["tenant_id", "case_id"], ["repair_cases.tenant_id", "repair_cases.id"]),)
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(40))
    detail: Mapped[dict] = mapped_column(JSONB, default=dict)


class RepairAttachment(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "repair_attachments"
    __table_args__ = (ForeignKeyConstraint(["tenant_id", "case_id"], ["repair_cases.tenant_id", "repair_cases.id"]),
                      UniqueConstraint("tenant_id", "case_id", "sha256"),
                      ForeignKeyConstraint(['tenant_id','case_id','portal_token_id'],['repair_portal_tokens.tenant_id','repair_portal_tokens.case_id','repair_portal_tokens.id']))
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    filename: Mapped[str] = mapped_column(String(200))
    content_type: Mapped[str] = mapped_column(String(80))
    sha256: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer)
    content: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"),nullable=True)
    customer_visible: Mapped[bool] = mapped_column(Boolean,default=False)
    portal_token_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True),nullable=True)


class RepairTask(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "repair_tasks"
    __table_args__ = (ForeignKeyConstraint(["tenant_id", "case_id"], ["repair_cases.tenant_id", "repair_cases.id"]),
                     CheckConstraint("status IN ('pending','working','done')", name="ck_repair_task_status"))
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    title: Mapped[str] = mapped_column(String(200))
    internal_note: Mapped[str] = mapped_column(Text, default="")
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))


class RepairFault(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "repair_faults"
    __table_args__ = (ForeignKeyConstraint(["tenant_id", "type_id"], ["repair_device_types.tenant_id", "repair_device_types.id"]),
                     UniqueConstraint("tenant_id", "name"))
    name: Mapped[str] = mapped_column(String(200))
    type_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class RepairEstimate(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "repair_estimates"
    __table_args__ = (ForeignKeyConstraint(["tenant_id", "case_id"], ["repair_cases.tenant_id", "repair_cases.id"]),
                     UniqueConstraint("tenant_id", "case_id", "version"), UniqueConstraint("tenant_id", "id"), UniqueConstraint("tenant_id", "case_id", "id"),
                     CheckConstraint("version > 0 AND (customer_ceiling IS NULL OR customer_ceiling >= 0)", name="ck_repair_estimate_amount"))
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    version: Mapped[int] = mapped_column(Integer)
    options: Mapped[list] = mapped_column(JSONB)
    valid_until: Mapped[date] = mapped_column(Date)
    duration_days: Mapped[int] = mapped_column(Integer)
    customer_ceiling: Mapped[Decimal | None] = mapped_column(Numeric(18, 0), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="IRR")
    diagnosis_snapshot: Mapped[str] = mapped_column(Text)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))


class RepairEstimateDecision(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "repair_estimate_decisions"
    __table_args__ = (ForeignKeyConstraint(["tenant_id", "case_id"], ["repair_cases.tenant_id", "repair_cases.id"]),
                     ForeignKeyConstraint(["tenant_id", "case_id", "estimate_id"], ["repair_estimates.tenant_id", "repair_estimates.case_id", "repair_estimates.id"]),
                     UniqueConstraint("tenant_id", "estimate_id"),
                     ForeignKeyConstraint(['tenant_id','case_id','portal_token_id'],['repair_portal_tokens.tenant_id','repair_portal_tokens.case_id','repair_portal_tokens.id']),
                     CheckConstraint("decision IN ('approved','rejected')", name="ck_repair_decision"))
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    estimate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    decision: Mapped[str] = mapped_column(String(15))
    option_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    method: Mapped[str] = mapped_column(String(20))
    customer_name: Mapped[str] = mapped_column(String(200))
    reason: Mapped[str] = mapped_column(Text, default="")
    authorized_ceiling: Mapped[Decimal | None] = mapped_column(Numeric(18, 0), nullable=True)
    recorded_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"),nullable=True)
    portal_token_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True),nullable=True)


class RepairPart(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "repair_parts"
    __table_args__ = (ForeignKeyConstraint(["tenant_id", "case_id"], ["repair_cases.tenant_id", "repair_cases.id"]),
        ForeignKeyConstraint(["tenant_id", "item_id"], ["items.tenant_id", "items.id"]), UniqueConstraint("tenant_id", "id"),
        CheckConstraint("owner IN ('company','customer') AND qty > 0 AND unit_price >= 0", name="ck_repair_part_values"))
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    owner: Mapped[str] = mapped_column(String(10))
    item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    qty: Mapped[Decimal] = mapped_column(Numeric(24,8))
    unit_snapshot: Mapped[dict] = mapped_column(JSONB)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18,0), default=0)
    charge_to_customer: Mapped[bool] = mapped_column(Boolean, default=True)
    source_warehouse_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("warehouses.id"), nullable=True)
    work_warehouse_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("warehouses.id"), nullable=True)
    batch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("stock_batches.id"), nullable=True)
    work_batch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("stock_batches.id"), nullable=True)
    substitute_for_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("repair_parts.id"), nullable=True)
    compatibility_reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="requested")
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))


class RepairPartMovement(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "repair_part_movements"
    __table_args__ = (ForeignKeyConstraint(["tenant_id", "part_id"], ["repair_parts.tenant_id", "repair_parts.id"]),)
    part_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    action: Mapped[str] = mapped_column(String(25))
    qty: Mapped[Decimal] = mapped_column(Numeric(24,8))
    document_type: Mapped[str] = mapped_column(String(30), default="")
    document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    document_line_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    serials: Mapped[list] = mapped_column(JSONB, default=list)
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))


class RepairWork(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "repair_work"
    __table_args__ = (ForeignKeyConstraint(["tenant_id", "case_id"], ["repair_cases.tenant_id", "repair_cases.id"]),
                     ForeignKeyConstraint(["tenant_id", "service_id"], ["items.tenant_id", "items.id"]))
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    technician_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    collaborators: Mapped[list] = mapped_column(JSONB, default=list)
    service_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    description: Mapped[str] = mapped_column(Text)
    internal_result: Mapped[str] = mapped_column(Text, default="")
    customer_result: Mapped[str] = mapped_column(Text, default="")
    work_minutes: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    charge_amount: Mapped[Decimal] = mapped_column(Numeric(18,0), default=0)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))


class RepairOutsource(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "repair_outsources"
    __table_args__ = (ForeignKeyConstraint(["tenant_id", "case_id"], ["repair_cases.tenant_id", "repair_cases.id"]),
                     ForeignKeyConstraint(["tenant_id", "vendor_id"], ["contacts.tenant_id", "contacts.id"]), UniqueConstraint("tenant_id", "purchase_invoice_id"))
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    vendor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    description: Mapped[str] = mapped_column(Text)
    expected_cost: Mapped[Decimal] = mapped_column(Numeric(18,0))
    due_date: Mapped[date] = mapped_column(Date)
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    return_result: Mapped[str] = mapped_column(Text, default="")
    purchase_invoice_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("purchase_invoices.id"), nullable=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))


class RepairQualityCheck(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "repair_quality_checks"
    __table_args__ = (ForeignKeyConstraint(["tenant_id", "case_id"], ["repair_cases.tenant_id", "repair_cases.id"]),)
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    work_version: Mapped[int] = mapped_column(Integer)
    passed: Mapped[bool] = mapped_column(Boolean)
    checklist: Mapped[dict] = mapped_column(JSONB)
    result: Mapped[str] = mapped_column(Text)
    checked_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))


class RepairRemovedPart(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "repair_removed_parts"
    __table_args__ = (ForeignKeyConstraint(["tenant_id", "case_id"], ["repair_cases.tenant_id", "repair_cases.id"]),)
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    title: Mapped[str] = mapped_column(String(200))
    disposition: Mapped[str] = mapped_column(String(25))
    authorization_method: Mapped[str] = mapped_column(String(20))
    customer_name: Mapped[str] = mapped_column(String(200))
    reason: Mapped[str] = mapped_column(Text)
    recorded_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))


class RepairDeviceSecret(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "repair_device_secrets"
    __table_args__ = (ForeignKeyConstraint(["tenant_id", "case_id"], ["repair_cases.tenant_id", "repair_cases.id"]), UniqueConstraint("tenant_id", "case_id"))
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    ciphertext: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))


class RepairPurchaseRequest(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "repair_purchase_requests"
    __table_args__ = (ForeignKeyConstraint(["tenant_id", "part_id"], ["repair_parts.tenant_id", "repair_parts.id"]), UniqueConstraint("tenant_id", "part_id"))
    part_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    due_date: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    purchase_invoice_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("purchase_invoices.id"), nullable=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))


class RepairDocument(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """فقط پیوند به سند موجود؛ هیچ مبلغ یا ماندهٔ موازی ذخیره نمی‌شود."""
    __tablename__ = 'repair_documents'
    __table_args__ = (ForeignKeyConstraint(['tenant_id','case_id'],['repair_cases.tenant_id','repair_cases.id']),
                     UniqueConstraint('tenant_id','document_type','document_id'),
                     CheckConstraint("document_type IN ('sales_invoice','receipt','payment','sales_return','settlement')",name='ck_repair_document_type'))
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),index=True)
    document_type: Mapped[str] = mapped_column(String(25))
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    work_version: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict] = mapped_column(JSONB,default=dict)
    linked_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))


class RepairDelivery(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = 'repair_deliveries'
    __table_args__ = (ForeignKeyConstraint(['tenant_id','case_id'],['repair_cases.tenant_id','repair_cases.id']),UniqueConstraint('tenant_id','case_id'))
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    delivered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    receiver_name: Mapped[str] = mapped_column(String(200))
    receiver_phone: Mapped[str] = mapped_column(String(30))
    authorization: Mapped[str] = mapped_column(Text)
    accessories: Mapped[str] = mapped_column(Text)
    care_instructions: Mapped[str] = mapped_column(Text)
    credit_reason: Mapped[str] = mapped_column(Text,default='')
    outstanding_snapshot: Mapped[Decimal] = mapped_column(Numeric(18,0))
    approval_method: Mapped[str] = mapped_column(String(20))
    checklist: Mapped[dict] = mapped_column(JSONB,default=dict)
    handed_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))


class RepairMessageTemplate(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """نسخه‌ها تغییرناپذیرند؛ متن پیام در لحظهٔ صف‌شدن تثبیت می‌شود."""
    __tablename__ = 'repair_message_templates'
    __table_args__ = (ForeignKeyConstraint(['tenant_id','branch_id'],['repair_branches.tenant_id','repair_branches.id']),
                     UniqueConstraint('tenant_id','scope','kind','version'),UniqueConstraint('tenant_id','id'),
                     CheckConstraint("kind IN ('admission','approval','due','ready') AND version > 0",name='ck_repair_message_template'))
    branch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    scope: Mapped[str] = mapped_column(String(36))
    kind: Mapped[str] = mapped_column(String(25))
    version: Mapped[int] = mapped_column(Integer)
    body: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))


class RepairNotification(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = 'repair_notifications'
    __table_args__ = (ForeignKeyConstraint(['tenant_id','case_id'],['repair_cases.tenant_id','repair_cases.id']),
                     UniqueConstraint('tenant_id','id'), UniqueConstraint('tenant_id','dedupe_key'),
                     ForeignKeyConstraint(['tenant_id','template_id'],['repair_message_templates.tenant_id','repair_message_templates.id']),
                     CheckConstraint("status IN ('queued','sending','accepted','uncertain','unavailable','cancelled')",name='ck_repair_notification_status'))
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),index=True)
    kind: Mapped[str] = mapped_column(String(25))
    dedupe_key: Mapped[str] = mapped_column(String(150))
    template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    recipient: Mapped[str] = mapped_column(String(30))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20),default='queued',index=True)
    attempt_count: Mapped[int] = mapped_column(Integer,default=0)
    last_result: Mapped[str] = mapped_column(String(300),default='')
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),nullable=True)


class RepairNotificationAttempt(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = 'repair_notification_attempts'
    __table_args__ = (ForeignKeyConstraint(['tenant_id','notification_id'],['repair_notifications.tenant_id','repair_notifications.id']),
                     UniqueConstraint('tenant_id','notification_id','number'))
    notification_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),index=True)
    number: Mapped[int] = mapped_column(Integer)
    outcome: Mapped[str] = mapped_column(String(25))
    result: Mapped[str] = mapped_column(String(300))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),nullable=True)


class RepairPortalToken(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__='repair_portal_tokens'
    __table_args__=(ForeignKeyConstraint(['tenant_id','case_id'],['repair_cases.tenant_id','repair_cases.id']),
                   UniqueConstraint('tenant_id','id'),UniqueConstraint('tenant_id','case_id','id'),UniqueConstraint('tenant_id','token_hash'))
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),index=True)
    token_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),nullable=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))


class RepairPortalSubmission(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__='repair_portal_submissions'
    __table_args__=(ForeignKeyConstraint(['tenant_id','case_id'],['repair_cases.tenant_id','repair_cases.id']),
                   ForeignKeyConstraint(['tenant_id','case_id','token_id'],['repair_portal_tokens.tenant_id','repair_portal_tokens.case_id','repair_portal_tokens.id']),
                   UniqueConstraint('tenant_id','token_id','operation','request_key'))
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    token_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    operation: Mapped[str] = mapped_column(String(30))
    request_key: Mapped[str] = mapped_column(String(128))
    payload_hash: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))


class RepairCustomerMessage(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__='repair_customer_messages'
    __table_args__=(ForeignKeyConstraint(['tenant_id','case_id'],['repair_cases.tenant_id','repair_cases.id']),
                   ForeignKeyConstraint(['tenant_id','case_id','token_id'],['repair_portal_tokens.tenant_id','repair_portal_tokens.case_id','repair_portal_tokens.id']),
                   CheckConstraint("kind IN ('comment','complaint','survey') AND (rating IS NULL OR rating BETWEEN 1 AND 5)",name='ck_repair_customer_message'))
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),index=True)
    token_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    kind: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    rating: Mapped[int | None] = mapped_column(Integer,nullable=True)


class RepairOnlineSettings(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__='repair_online_settings'
    __table_args__=(ForeignKeyConstraint(['tenant_id','branch_id'],['repair_branches.tenant_id','repair_branches.id']),UniqueConstraint('tenant_id','branch_id'))
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    gateway_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('payment_gateways.id'))
    pos_terminal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('pos_terminals.id'))
    enabled: Mapped[bool] = mapped_column(Boolean,default=False)
    configured_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))


class RepairPaymentIntent(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """درخواست حامل و اثبات verify؛ رسید و مانده فقط در خزانهٔ موجود ثبت می‌شوند."""
    __tablename__='repair_payment_intents'
    __table_args__=(ForeignKeyConstraint(['tenant_id','case_id'],['repair_cases.tenant_id','repair_cases.id']),
                   ForeignKeyConstraint(['tenant_id','case_id','token_id'],['repair_portal_tokens.tenant_id','repair_portal_tokens.case_id','repair_portal_tokens.id']),
                   UniqueConstraint('tenant_id','provider','authority'),
                   CheckConstraint("amount_rial > 0 AND status IN ('pending','verification_failed','accounting_pending','posted')",name='ck_repair_payment_intent'))
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),index=True)
    token_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    provider: Mapped[str] = mapped_column(String(20))
    merchant_ciphertext: Mapped[str] = mapped_column(Text)
    sandbox: Mapped[bool] = mapped_column(Boolean)
    amount_rial: Mapped[Decimal] = mapped_column(Numeric(18,0))
    authority: Mapped[str] = mapped_column(String(200))
    redirect_url: Mapped[str] = mapped_column(Text)
    pos_terminal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('pos_terminals.id'))
    posting_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))
    status: Mapped[str] = mapped_column(String(25),default='pending')
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),nullable=True)
    payment_ref: Mapped[str] = mapped_column(String(200),default='')
    receipt_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('receipts.id'),nullable=True)
    last_result: Mapped[str] = mapped_column(String(300),default='')


class RepairWarranty(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = 'repair_warranties'
    __table_args__ = (ForeignKeyConstraint(['tenant_id','case_id'], ['repair_cases.tenant_id','repair_cases.id']),
        UniqueConstraint('tenant_id','id'), UniqueConstraint('tenant_id','case_id','id'),
        CheckConstraint("scope IN ('service','part') AND valid_until >= valid_from", name='ck_repair_warranty'))
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    scope: Mapped[str] = mapped_column(String(20))
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    title: Mapped[str] = mapped_column(String(200))
    valid_from: Mapped[date] = mapped_column(Date)
    valid_until: Mapped[date] = mapped_column(Date)
    terms: Mapped[str] = mapped_column(Text)
    exclusions: Mapped[str] = mapped_column(Text, default='')
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))


class RepairWarrantyClaim(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = 'repair_warranty_claims'
    __table_args__ = (ForeignKeyConstraint(['tenant_id','original_case_id','warranty_id'], ['repair_warranties.tenant_id','repair_warranties.case_id','repair_warranties.id']),
        ForeignKeyConstraint(['tenant_id','revisit_case_id'], ['repair_cases.tenant_id','repair_cases.id']),
        UniqueConstraint('tenant_id','revisit_case_id'),
        CheckConstraint("classification IN ('repeat_fault','new_fault') AND responsibility IN ('company','technician','vendor','customer') AND cost_policy IN ('covered','customer','responsible')", name='ck_repair_warranty_claim'))
    original_case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    warranty_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    revisit_case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    classification: Mapped[str] = mapped_column(String(20))
    responsibility: Mapped[str] = mapped_column(String(20))
    cost_policy: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(Text)
    recorded_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))


class RepairFeeRule(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__='repair_fee_rules'
    __table_args__=(UniqueConstraint('tenant_id','id'),UniqueConstraint('tenant_id','technician_id','version'),
        ForeignKeyConstraint(['tenant_id','payee_id'],['contacts.tenant_id','contacts.id']),
        ForeignKeyConstraint(['tenant_id','service_id'],['items.tenant_id','items.id']),
        CheckConstraint("mode IN ('fixed_case','percent_labor','per_operation') AND value >= 0 AND version > 0",name='ck_repair_fee_rule'))
    technician_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))
    version: Mapped[int] = mapped_column(Integer)
    mode: Mapped[str] = mapped_column(String(25))
    value: Mapped[Decimal] = mapped_column(Numeric(18,4))
    payee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    service_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    enabled: Mapped[bool] = mapped_column(Boolean)
    reason: Mapped[str] = mapped_column(Text)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))


class RepairTechnicianFee(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__='repair_technician_fees'
    __table_args__=(ForeignKeyConstraint(['tenant_id','case_id'],['repair_cases.tenant_id','repair_cases.id']),
        ForeignKeyConstraint(['tenant_id','rule_id'],['repair_fee_rules.tenant_id','repair_fee_rules.id']),
        UniqueConstraint('tenant_id','case_id','rule_id','work_version'),UniqueConstraint('tenant_id','purchase_invoice_id'),
        CheckConstraint('amount_rial > 0',name='ck_repair_technician_fee_amount'))
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),index=True)
    rule_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    technician_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))
    work_version: Mapped[int] = mapped_column(Integer)
    amount_rial: Mapped[Decimal] = mapped_column(Numeric(18,0))
    calculation: Mapped[dict] = mapped_column(JSONB)
    purchase_invoice_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('purchase_invoices.id'),nullable=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('users.id'),nullable=True)


class RepairServiceRequest(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__='repair_service_requests'
    __table_args__=(UniqueConstraint('tenant_id','id'),
        ForeignKeyConstraint(['tenant_id','branch_id'],['repair_branches.tenant_id','repair_branches.id']),
        ForeignKeyConstraint(['tenant_id','contact_id'],['contacts.tenant_id','contacts.id']),
        ForeignKeyConstraint(['tenant_id','type_id'],['repair_device_types.tenant_id','repair_device_types.id']),
        ForeignKeyConstraint(['tenant_id','case_id'],['repair_cases.tenant_id','repair_cases.id']),UniqueConstraint('tenant_id','case_id'))
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),index=True)
    contact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    type_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    case_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True),nullable=True)
    device_description: Mapped[str] = mapped_column(String(500))
    reported_issue: Mapped[str] = mapped_column(Text)
    address: Mapped[str] = mapped_column(Text)
    coordinator_name: Mapped[str] = mapped_column(String(200))
    coordinator_phone: Mapped[str] = mapped_column(String(30))
    version: Mapped[int] = mapped_column(Integer,default=1)
    status: Mapped[str] = mapped_column(String(20),default='open')
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))


class RepairTechnicianSkill(TenantMixin, UUIDPKMixin, Base):
    __tablename__='repair_technician_skills'
    __table_args__=(UniqueConstraint('tenant_id','technician_id','type_id'),
        ForeignKeyConstraint(['tenant_id','type_id'],['repair_device_types.tenant_id','repair_device_types.id']))
    technician_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))
    type_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))


class RepairAppointment(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__='repair_appointments'
    __table_args__=(UniqueConstraint('tenant_id','id'),
        ForeignKeyConstraint(['tenant_id','request_id'],['repair_service_requests.tenant_id','repair_service_requests.id']),
        CheckConstraint("ends_at > starts_at AND status IN ('scheduled','dispatched','onsite','completed','cancelled')",name='ck_repair_appointment'))
    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),index=True)
    technician_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'),index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20),default='scheduled')
    result: Mapped[str] = mapped_column(Text,default='')
    arrived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),nullable=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))


class RepairFieldEvent(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__='repair_field_events'
    __table_args__=(ForeignKeyConstraint(['tenant_id','request_id'],['repair_service_requests.tenant_id','repair_service_requests.id']),)
    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),index=True)
    action: Mapped[str] = mapped_column(String(40))
    detail: Mapped[dict] = mapped_column(JSONB)
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))


class RepairCustodyTransfer(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__='repair_custody_transfers'
    __table_args__=(ForeignKeyConstraint(['tenant_id','case_id'],['repair_cases.tenant_id','repair_cases.id']),
        ForeignKeyConstraint(['tenant_id','from_branch_id'],['repair_branches.tenant_id','repair_branches.id']),
        ForeignKeyConstraint(['tenant_id','to_branch_id'],['repair_branches.tenant_id','repair_branches.id']),
        UniqueConstraint('tenant_id','id'),
        Index('uq_repair_active_custody','tenant_id','case_id',unique=True,postgresql_where=text("status='in_transit'")),
        CheckConstraint("status IN ('in_transit','received','returned')",name='ck_repair_custody_status'))
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),index=True)
    from_branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    to_branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    from_location: Mapped[str] = mapped_column(String(200))
    destination_location: Mapped[str] = mapped_column(String(200))
    carrier_name: Mapped[str] = mapped_column(String(200))
    carrier_phone: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20),default='in_transit')
    dispatched_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))
    received_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('users.id'),nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),nullable=True)
    receiver_name: Mapped[str] = mapped_column(String(200),default='')
    receipt_confirmation: Mapped[str] = mapped_column(Text,default='')


class RepairCustodyLeg(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__='repair_custody_legs'
    __table_args__=(ForeignKeyConstraint(['tenant_id','transfer_id'],['repair_custody_transfers.tenant_id','repair_custody_transfers.id']),)
    transfer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    from_carrier: Mapped[str] = mapped_column(String(200))
    to_carrier: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str] = mapped_column(String(30))
    location: Mapped[str] = mapped_column(String(200))
    confirmation: Mapped[str] = mapped_column(Text)
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))


class RepairLoan(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__='repair_loans'
    __table_args__=(ForeignKeyConstraint(['tenant_id','case_id'],['repair_cases.tenant_id','repair_cases.id']),
        ForeignKeyConstraint(['tenant_id','return_custodian_id'],['contacts.tenant_id','contacts.id']),
        Index('uq_repair_active_loan_asset','tenant_id','asset_id',unique=True,postgresql_where=text('returned_at IS NULL')))
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),index=True)
    asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('fixed_assets.id'))
    asset_snapshot: Mapped[dict] = mapped_column(JSONB)
    serial: Mapped[str] = mapped_column(String(120),default='')
    receiver_name: Mapped[str] = mapped_column(String(200))
    authorization: Mapped[str] = mapped_column(Text)
    accessories: Mapped[str] = mapped_column(Text)
    condition_out: Mapped[str] = mapped_column(Text)
    due_date: Mapped[date] = mapped_column(Date)
    return_custodian_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    return_location: Mapped[str] = mapped_column(String(200))
    checkout_assignment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('asset_assignments.id'))
    return_assignment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('asset_assignments.id'),nullable=True)
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),nullable=True)
    condition_in: Mapped[str] = mapped_column(Text,default='')
    return_confirmation: Mapped[str] = mapped_column(Text,default='')
    checked_out_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))
    checked_in_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('users.id'),nullable=True)


class RepairMaintenanceContract(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__='repair_maintenance_contracts'
    __table_args__=(UniqueConstraint('tenant_id','id'),UniqueConstraint('tenant_id','code','version'),
        ForeignKeyConstraint(['tenant_id','contact_id'],['contacts.tenant_id','contacts.id']),
        CheckConstraint('valid_until >= valid_from AND version > 0',name='ck_repair_contract_dates'))
    code: Mapped[str] = mapped_column(String(120))
    version: Mapped[int] = mapped_column(Integer)
    contact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    title: Mapped[str] = mapped_column(String(200))
    valid_from: Mapped[date] = mapped_column(Date)
    valid_until: Mapped[date] = mapped_column(Date)
    terms: Mapped[str] = mapped_column(Text)
    address: Mapped[str] = mapped_column(Text)
    coordinator_name: Mapped[str] = mapped_column(String(200))
    coordinator_phone: Mapped[str] = mapped_column(String(30))
    covers_labor: Mapped[bool] = mapped_column(Boolean)
    covers_parts: Mapped[bool] = mapped_column(Boolean)
    visit_quota: Mapped[int | None] = mapped_column(Integer,nullable=True)
    minute_quota: Mapped[int | None] = mapped_column(Integer,nullable=True)
    value_quota_rial: Mapped[Decimal | None] = mapped_column(Numeric(18,0),nullable=True)
    response_hours: Mapped[int] = mapped_column(Integer)
    completion_hours: Mapped[int] = mapped_column(Integer)
    enabled: Mapped[bool] = mapped_column(Boolean)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))


class RepairContractDevice(TenantMixin, UUIDPKMixin, Base):
    __tablename__='repair_contract_devices'
    __table_args__=(ForeignKeyConstraint(['tenant_id','contract_id'],['repair_maintenance_contracts.tenant_id','repair_maintenance_contracts.id']),
        ForeignKeyConstraint(['tenant_id','device_id'],['repair_devices.tenant_id','repair_devices.id']),UniqueConstraint('tenant_id','contract_id','device_id'))
    contract_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    device_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))


class RepairContractCase(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__='repair_contract_cases'
    __table_args__=(ForeignKeyConstraint(['tenant_id','contract_id'],['repair_maintenance_contracts.tenant_id','repair_maintenance_contracts.id']),
        ForeignKeyConstraint(['tenant_id','case_id'],['repair_cases.tenant_id','repair_cases.id']),
        ForeignKeyConstraint(['tenant_id','case_id','outside_estimate_id'],['repair_estimates.tenant_id','repair_estimates.case_id','repair_estimates.id']),UniqueConstraint('tenant_id','case_id'))
    contract_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    service_date: Mapped[date] = mapped_column(Date)
    allocated_minutes: Mapped[int] = mapped_column(Integer)
    consumed_minutes: Mapped[int | None] = mapped_column(Integer,nullable=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),nullable=True)
    release_reason: Mapped[str] = mapped_column(Text,default='')
    covered_value_rial: Mapped[Decimal] = mapped_column(Numeric(18,0))
    snapshot: Mapped[dict] = mapped_column(JSONB)
    outside_estimate_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True),nullable=True)
    response_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completion_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recorded_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))


class RepairMaintenancePlan(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__='repair_maintenance_plans'
    __table_args__=(UniqueConstraint('tenant_id','id'),
        ForeignKeyConstraint(['tenant_id','contract_id'],['repair_maintenance_contracts.tenant_id','repair_maintenance_contracts.id']),
        ForeignKeyConstraint(['tenant_id','device_id'],['repair_devices.tenant_id','repair_devices.id']),
        ForeignKeyConstraint(['tenant_id','branch_id'],['repair_branches.tenant_id','repair_branches.id']),CheckConstraint('interval_days > 0',name='ck_repair_maintenance_interval'))
    contract_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    device_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    title: Mapped[str] = mapped_column(String(200))
    interval_days: Mapped[int] = mapped_column(Integer)
    next_due: Mapped[date] = mapped_column(Date,index=True)
    allocated_minutes: Mapped[int] = mapped_column(Integer)
    covered_value_rial: Mapped[Decimal] = mapped_column(Numeric(18,0))
    enabled: Mapped[bool] = mapped_column(Boolean,default=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))


class RepairMaintenanceVisit(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__='repair_maintenance_visits'
    __table_args__=(ForeignKeyConstraint(['tenant_id','plan_id'],['repair_maintenance_plans.tenant_id','repair_maintenance_plans.id']),
        ForeignKeyConstraint(['tenant_id','request_id'],['repair_service_requests.tenant_id','repair_service_requests.id']),
        UniqueConstraint('tenant_id','plan_id','due_date'),UniqueConstraint('tenant_id','request_id'))
    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    due_date: Mapped[date] = mapped_column(Date)
    performed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),nullable=True)
    result: Mapped[str] = mapped_column(Text,default='')
    recorded_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))


class RepairConsolidatedBill(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__='repair_consolidated_bills'
    __table_args__=(UniqueConstraint('tenant_id','id'),ForeignKeyConstraint(['tenant_id','contact_id'],['contacts.tenant_id','contacts.id']))
    contact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    title: Mapped[str] = mapped_column(String(200))
    issued_date: Mapped[date] = mapped_column(Date)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id'))


class RepairConsolidatedBillMember(TenantMixin, UUIDPKMixin, Base):
    __tablename__='repair_consolidated_bill_members'
    __table_args__=(ForeignKeyConstraint(['tenant_id','bill_id'],['repair_consolidated_bills.tenant_id','repair_consolidated_bills.id']),
        ForeignKeyConstraint(['tenant_id','case_id'],['repair_cases.tenant_id','repair_cases.id']),UniqueConstraint('tenant_id','bill_id','case_id'))
    bill_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    sales_invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('sales_invoices.id'))
    invoice_snapshot: Mapped[dict] = mapped_column(JSONB)
