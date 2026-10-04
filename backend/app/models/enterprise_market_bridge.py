"""Minimal bridge records for an enterprise installation joining the cloud market.

The cloud never receives local item, warehouse, contact, invoice, or ledger IDs.
Only an explicitly published listing snapshot and a posting outcome cross the
boundary.  Local mappings and financial-event inboxes remain under tenant RLS.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin


class EnterpriseMarketLink(UUIDPKMixin, TimestampMixin, Base):
    """Cloud-side identity and credential, one active installation per cloud account."""

    __tablename__ = "enterprise_market_links"
    __table_args__ = (
        Index("uq_em_link_live_cloud_tenant", "cloud_tenant_id", unique=True, postgresql_where=text("status != 'revoked'")),
        Index("uq_em_link_live_install", "install_id", unique=True, postgresql_where=text("status != 'revoked'")),
        CheckConstraint("status IN ('pending','active','revoked')", name="ck_em_link_status"),
    )

    cloud_tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True)
    license_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("enterprise_licenses.id"), nullable=False)
    install_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", server_default="pending")
    original_kind: Mapped[str | None] = mapped_column(String(20), nullable=True)
    original_market_settings: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    credential_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    credential_delivery_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    pairing_code_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pairing_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cloud_owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    linked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    active_generation: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    pending_generation: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    pending_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: Until the local owner verifies every old catalog mapping, old cloud listings
    #: remain unpublished.  No automatic migration of historical orders is allowed.
    catalog_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class EnterpriseMarketCatalog(UUIDPKMixin, TimestampMixin, Base):
    """Cloud-visible, allowlisted publication; never a serialized local Item."""

    __tablename__ = "enterprise_market_catalog"
    __table_args__ = (
        UniqueConstraint("market_listing_ref", name="uq_em_catalog_ref"),
        CheckConstraint("available_qty >= 0", name="ck_em_catalog_available"),
    )

    link_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("enterprise_market_links.id", ondelete="CASCADE"), nullable=False, index=True)
    market_listing_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    cloud_listing_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("marketplace_listings.id"), nullable=True)
    #: Schema validated by MarketListingSnapshot at ingress and egress.  Its keys
    #: are deliberately allowlisted rather than derived from local ORM models.
    public_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    available_qty: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    sync_generation: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    staged_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    staged_available_qty: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EnterpriseMarketEvent(UUIDPKMixin, TimestampMixin, Base):
    """Cloud-side financial dispatch with one idempotency key per side/operation."""

    __tablename__ = "enterprise_market_events"
    __table_args__ = (
        UniqueConstraint("operation_ref", "side", name="uq_em_event_operation_side"),
        CheckConstraint("side IN ('buyer','seller')", name="ck_em_event_side"),
        CheckConstraint("status IN ('pending','posted','retryable_error','blocked')", name="ck_em_event_status"),
    )

    link_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("enterprise_market_links.id", ondelete="CASCADE"), nullable=False, index=True)
    operation_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("marketplace_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # order | return
    #: Order lines, settlement mode, and counterpart's public name only.
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    error_code: Mapped[str] = mapped_column(String(60), nullable=False, default="", server_default="")
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EnterpriseMarketCommand(UUIDPKMixin, TimestampMixin, Base):
    """Cloud-side exactly-once command receipt, committed with the market mutation."""

    __tablename__ = "enterprise_market_commands"
    __table_args__ = (UniqueConstraint("link_id", "request_id", name="uq_em_command_request"),)

    link_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("enterprise_market_links.id", ondelete="CASCADE"), nullable=False, index=True)
    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    operation: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_name: Mapped[str] = mapped_column(String(200), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class EnterpriseMarketCloudItemMap(UUIDPKMixin, TimestampMixin, Base):
    """Cloud shadow Item contains public catalog facts only, never local IDs."""

    __tablename__ = "enterprise_market_cloud_item_maps"
    __table_args__ = (
        UniqueConstraint("link_id", "market_item_ref", name="uq_em_cloud_item_ref"),
        UniqueConstraint("cloud_item_id", name="uq_em_cloud_item_id"),
    )

    link_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("enterprise_market_links.id", ondelete="CASCADE"), nullable=False)
    market_item_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    cloud_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"), nullable=False)


class EnterpriseMarketLocalState(UUIDPKMixin, TenantMixin, TimestampMixin, Base):
    """On-premise connection state; credential is encrypted with SECRETS_KEY."""

    __tablename__ = "enterprise_market_local_state"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_em_local_state_tenant"),
        CheckConstraint("status IN ('pending','active','revoked')", name="ck_em_local_status"),
    )

    cloud_tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    link_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    credential_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", server_default="pending")
    catalog_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    pending_generation: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    pending_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[str] = mapped_column(String(60), nullable=False, default="", server_default="")
    # Cloud market facts are cached locally for read-only use during outages.
    # This never contains the on-prem accounting database.
    market_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    market_snapshot_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    message_threads: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class EnterpriseMarketItemMap(UUIDPKMixin, TenantMixin, TimestampMixin, Base):
    """Private mapping from market item reference to local inventory Item."""

    __tablename__ = "enterprise_market_item_maps"
    __table_args__ = (
        UniqueConstraint("tenant_id", "market_item_ref", name="uq_em_item_map_ref"),
        UniqueConstraint("tenant_id", "local_item_id", name="uq_em_item_map_local"),
    )

    market_item_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    local_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"), nullable=False)
    approved_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EnterpriseMarketListingMap(UUIDPKMixin, TenantMixin, TimestampMixin, Base):
    """Private mapping from selected local listing to cloud-visible reference."""

    __tablename__ = "enterprise_market_listing_maps"
    __table_args__ = (
        UniqueConstraint("tenant_id", "market_listing_ref", name="uq_em_listing_map_ref"),
        UniqueConstraint("tenant_id", "local_listing_id", name="uq_em_listing_map_local"),
    )

    market_listing_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    local_listing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("marketplace_listings.id"), nullable=False)
    approved_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EnterpriseMarketCounterpartyMap(UUIDPKMixin, TenantMixin, TimestampMixin, Base):
    """Cloud market identity to a local receivable/payable contact."""

    __tablename__ = "enterprise_market_counterparty_maps"
    __table_args__ = (UniqueConstraint("tenant_id", "cloud_tenant_id", name="uq_em_counterparty"),)

    cloud_tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    local_contact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=False)


class EnterpriseMarketLocalPosting(UUIDPKMixin, TenantMixin, TimestampMixin, Base):
    """Durable local inbox/receipt: unique event means an invoice cannot be replayed."""

    __tablename__ = "enterprise_market_local_postings"
    __table_args__ = (
        UniqueConstraint("tenant_id", "event_id", name="uq_em_local_posting_event"),
        CheckConstraint("side IN ('buyer','seller')", name="ck_em_local_posting_side"),
        CheckConstraint("status IN ('pending','posted','retryable_error','blocked')", name="ck_em_local_posting_status"),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    quantity_inputs: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    error_code: Mapped[str] = mapped_column(String(60), nullable=False, default="", server_default="")
    #: Local only. Never included in MarketPostingReceipt or sent to the VPS.
    error_detail: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    local_document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
