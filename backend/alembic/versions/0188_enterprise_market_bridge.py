"""Enterprise market bridge: cloud-visible catalog and private local mappings.

This migration copies no company data.  All bridge tables are empty and the
feature flag remains off. Five on-premise tables have FORCE RLS; the cloud
broker tables are global because both market counterparties use them.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.tenancy import rls_statements

revision = "0188"
down_revision = "0187"
branch_labels = None
depends_on = None

LOCAL_TABLES = (
    "enterprise_market_local_state",
    "enterprise_market_item_maps",
    "enterprise_market_listing_maps",
    "enterprise_market_counterparty_maps",
    "enterprise_market_local_postings",
)


def uuid_pk():
    return sa.Column("id", UUID(as_uuid=True), primary_key=True)


def timestamps():
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def tenant():
    return sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)


def upgrade():
    op.add_column("marketplace_order_lines", sa.Column("fulfillment_snapshot", JSONB(), nullable=True))
    op.add_column("marketplace_messages", sa.Column("sender_name", sa.String(200), nullable=False, server_default=""))
    op.create_table(
        "enterprise_market_links",
        uuid_pk(), *timestamps(),
        sa.Column("cloud_tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True),
        sa.Column("license_id", UUID(as_uuid=True), sa.ForeignKey("enterprise_licenses.id"), nullable=False),
        sa.Column("install_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("original_kind", sa.String(20), nullable=True),
        sa.Column("original_market_settings", JSONB(), nullable=True),
        sa.Column("credential_hash", sa.String(64), nullable=True),
        sa.Column("credential_delivery_encrypted", sa.Text(), nullable=True),
        sa.Column("pairing_code_hash", sa.String(64), nullable=True),
        sa.Column("pairing_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cloud_owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active_generation", UUID(as_uuid=True), nullable=True),
        sa.Column("pending_generation", UUID(as_uuid=True), nullable=True),
        sa.Column("pending_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("catalog_approved", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.CheckConstraint("status IN ('pending','active','revoked')", name="ck_em_link_status"),
    )
    op.create_index("uq_em_link_live_cloud_tenant", "enterprise_market_links", ["cloud_tenant_id"], unique=True, postgresql_where=sa.text("status != 'revoked'"))
    op.create_index("uq_em_link_live_install", "enterprise_market_links", ["install_id"], unique=True, postgresql_where=sa.text("status != 'revoked'"))
    op.create_table(
        "enterprise_market_catalog",
        uuid_pk(), *timestamps(),
        sa.Column("link_id", UUID(as_uuid=True), sa.ForeignKey("enterprise_market_links.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("market_listing_ref", UUID(as_uuid=True), nullable=False),
        sa.Column("cloud_listing_id", UUID(as_uuid=True), sa.ForeignKey("marketplace_listings.id"), nullable=True),
        sa.Column("public_snapshot", JSONB(), nullable=False),
        sa.Column("available_qty", sa.Numeric(18, 3), nullable=False),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("sync_generation", UUID(as_uuid=True), nullable=True),
        sa.Column("staged_snapshot", JSONB(), nullable=True),
        sa.Column("staged_available_qty", sa.Numeric(18, 3), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("market_listing_ref", name="uq_em_catalog_ref"),
        sa.CheckConstraint("available_qty >= 0", name="ck_em_catalog_available"),
    )
    op.create_table(
        "enterprise_market_cloud_item_maps",
        uuid_pk(), *timestamps(),
        sa.Column("link_id", UUID(as_uuid=True), sa.ForeignKey("enterprise_market_links.id", ondelete="CASCADE"), nullable=False),
        sa.Column("market_item_ref", UUID(as_uuid=True), nullable=False),
        sa.Column("cloud_item_id", UUID(as_uuid=True), sa.ForeignKey("items.id"), nullable=False),
        sa.UniqueConstraint("link_id", "market_item_ref", name="uq_em_cloud_item_ref"),
        sa.UniqueConstraint("cloud_item_id", name="uq_em_cloud_item_id"),
    )
    op.create_table(
        "enterprise_market_events",
        uuid_pk(), *timestamps(),
        sa.Column("link_id", UUID(as_uuid=True), sa.ForeignKey("enterprise_market_links.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("operation_ref", UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("marketplace_orders.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(60), nullable=False, server_default=""),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("operation_ref", "side", name="uq_em_event_operation_side"),
        sa.CheckConstraint("side IN ('buyer','seller')", name="ck_em_event_side"),
        sa.CheckConstraint("status IN ('pending','posted','retryable_error','blocked')", name="ck_em_event_status"),
    )
    op.create_table(
        "enterprise_market_commands",
        uuid_pk(), *timestamps(),
        sa.Column("link_id", UUID(as_uuid=True), sa.ForeignKey("enterprise_market_links.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("request_id", UUID(as_uuid=True), nullable=False),
        sa.Column("operation", sa.String(40), nullable=False),
        sa.Column("actor_name", sa.String(200), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("result", JSONB(), nullable=True),
        sa.UniqueConstraint("link_id", "request_id", name="uq_em_command_request"),
    )
    op.create_table(
        "enterprise_market_local_state",
        uuid_pk(), tenant(), *timestamps(),
        sa.Column("cloud_tenant_id", UUID(as_uuid=True), nullable=True),
        sa.Column("link_id", UUID(as_uuid=True), nullable=False),
        sa.Column("credential_encrypted", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("catalog_approved", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("pending_generation", UUID(as_uuid=True), nullable=True),
        sa.Column("pending_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(60), nullable=False, server_default=""),
        sa.Column("market_snapshot", JSONB(), nullable=True),
        sa.Column("market_snapshot_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("message_threads", JSONB(), nullable=True),
        sa.UniqueConstraint("tenant_id", name="uq_em_local_state_tenant"),
        sa.CheckConstraint("status IN ('pending','active','revoked')", name="ck_em_local_status"),
    )
    op.create_table(
        "enterprise_market_item_maps",
        uuid_pk(), tenant(), *timestamps(),
        sa.Column("market_item_ref", UUID(as_uuid=True), nullable=False),
        sa.Column("local_item_id", UUID(as_uuid=True), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("approved_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "market_item_ref", name="uq_em_item_map_ref"),
        sa.UniqueConstraint("tenant_id", "local_item_id", name="uq_em_item_map_local"),
    )
    op.create_table(
        "enterprise_market_listing_maps",
        uuid_pk(), tenant(), *timestamps(),
        sa.Column("market_listing_ref", UUID(as_uuid=True), nullable=False),
        sa.Column("local_listing_id", UUID(as_uuid=True), sa.ForeignKey("marketplace_listings.id"), nullable=False),
        sa.Column("approved_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "market_listing_ref", name="uq_em_listing_map_ref"),
        sa.UniqueConstraint("tenant_id", "local_listing_id", name="uq_em_listing_map_local"),
    )
    op.create_table(
        "enterprise_market_counterparty_maps",
        uuid_pk(), tenant(), *timestamps(),
        sa.Column("cloud_tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("local_contact_id", UUID(as_uuid=True), sa.ForeignKey("contacts.id"), nullable=False),
        sa.UniqueConstraint("tenant_id", "cloud_tenant_id", name="uq_em_counterparty"),
    )
    op.create_table(
        "enterprise_market_local_postings",
        uuid_pk(), tenant(), *timestamps(),
        sa.Column("event_id", UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", UUID(as_uuid=True), nullable=False),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(60), nullable=False, server_default=""),
        sa.Column("error_detail", sa.Text(), nullable=False, server_default=""),
        sa.Column("local_document_id", UUID(as_uuid=True), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "event_id", name="uq_em_local_posting_event"),
        sa.CheckConstraint("side IN ('buyer','seller')", name="ck_em_local_posting_side"),
        sa.CheckConstraint("status IN ('pending','posted','retryable_error','blocked')", name="ck_em_local_posting_status"),
    )
    for statement in rls_statements(LOCAL_TABLES):
        op.execute(sa.text(statement))


def downgrade():
    for table in reversed(LOCAL_TABLES):
        op.drop_table(table)
    for table in ("enterprise_market_commands", "enterprise_market_events", "enterprise_market_cloud_item_maps", "enterprise_market_catalog", "enterprise_market_links"):
        op.drop_table(table)
    op.drop_column("marketplace_order_lines", "fulfillment_snapshot")
    op.drop_column("marketplace_messages", "sender_name")
