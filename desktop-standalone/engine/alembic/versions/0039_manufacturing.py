"""تولید و بهای تمام‌شده — BOM و سفارشِ تولید

Revision ID: 0039
Revises: 0038

چهار جدولِ مستأجرمحور که مثلِ بقیه زیرِ RLS می‌روند.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.migration_utils import rls_disabled
from app.tenancy import policy_name

revision: str = "0039"
down_revision: Union[str, None] = "0038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ("boms", "bom_lines", "production_orders", "production_order_lines")


def _enable_rls(conn, table: str) -> None:
    conn.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"DROP POLICY IF EXISTS {policy_name(table)} ON {table}"))
    conn.execute(
        sa.text(
            f"CREATE POLICY {policy_name(table)} ON {table} "
            "USING (tenant_id = current_setting('app.tenant_id', true)::uuid) "
            "WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)"
        )
    )


def _tenant_cols() -> list[sa.Column]:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    ]


def upgrade() -> None:
    op.create_table(
        "boms",
        *_tenant_cols(),
        sa.Column("finished_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False, server_default=""),
        sa.Column("yield_qty", sa.Numeric(18, 3), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("notes", sa.Text, nullable=False, server_default=""),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_index("ix_boms_tenant_id", "boms", ["tenant_id"])
    op.create_index("ix_boms_finished_item_id", "boms", ["finished_item_id"])

    op.create_table(
        "bom_lines",
        *_tenant_cols(),
        sa.Column("bom_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("boms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("component_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("qty", sa.Numeric(18, 3), nullable=False),
    )
    op.create_index("ix_bom_lines_tenant_id", "bom_lines", ["tenant_id"])
    op.create_index("ix_bom_lines_bom_id", "bom_lines", ["bom_id"])

    op.create_table(
        "production_orders",
        *_tenant_cols(),
        sa.Column("number", sa.Integer, nullable=True),
        sa.Column("bom_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("boms.id"), nullable=False),
        sa.Column("finished_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("production_date", sa.Date, nullable=False),
        sa.Column("qty_produced", sa.Numeric(18, 3), nullable=False),
        sa.Column("component_cost", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("overhead_cost", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("unit_cost", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("journal_entries.id"), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_index("ix_production_orders_tenant_id", "production_orders", ["tenant_id"])
    op.create_index("ix_production_orders_number", "production_orders", ["number"])
    op.create_index("ix_production_orders_finished_item_id", "production_orders", ["finished_item_id"])

    op.create_table(
        "production_order_lines",
        *_tenant_cols(),
        sa.Column("production_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("production_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("component_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("qty", sa.Numeric(18, 3), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 0), nullable=False, server_default="0"),
    )
    op.create_index("ix_production_order_lines_tenant_id", "production_order_lines", ["tenant_id"])
    op.create_index("ix_production_order_lines_production_order_id", "production_order_lines", ["production_order_id"])

    conn = op.get_bind()
    for t in TABLES:
        _enable_rls(conn, t)

    # شمارنده‌ی «سفارشِ تولید» را برای مستأجرهای موجود بک‌فیل کن؛ provisioningِ تازه خودش
    # می‌سازد ولی مستأجرهای قدیمی این ردیف را ندارند و next_document_number بدونِ آن ۵۰۰ می‌دهد.
    with rls_disabled(conn, ["document_counters"]):
        conn.execute(
            sa.text(
                "INSERT INTO document_counters (id, tenant_id, doc_type, last_number, created_at, updated_at) "
                "SELECT gen_random_uuid(), t.id, 'production_order', 0, now(), now() FROM tenants t "
                "WHERE NOT EXISTS ("
                "  SELECT 1 FROM document_counters dc WHERE dc.tenant_id = t.id AND dc.doc_type = 'production_order'"
                ")"
            )
        )


def downgrade() -> None:
    op.drop_table("production_order_lines")
    op.drop_table("production_orders")
    op.drop_table("bom_lines")
    op.drop_table("boms")
