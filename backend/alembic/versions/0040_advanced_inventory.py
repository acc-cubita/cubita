"""انبار پیشرفته — لیستِ قیمت و بچ/تاریخِ انقضا

Revision ID: 0040
Revises: 0039

سه جدولِ مستأجرمحور که مثلِ بقیه زیرِ RLS می‌روند.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.tenancy import policy_name

revision: str = "0040"
down_revision: Union[str, None] = "0039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ("price_lists", "price_list_items", "stock_batches")


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
        "price_lists",
        *_tenant_cols(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("notes", sa.Text, nullable=False, server_default=""),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_index("ix_price_lists_tenant_id", "price_lists", ["tenant_id"])

    op.create_table(
        "price_list_items",
        *_tenant_cols(),
        sa.Column("price_list_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("price_lists.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("price", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.UniqueConstraint("tenant_id", "price_list_id", "item_id", name="uq_price_list_items_list_item"),
    )
    op.create_index("ix_price_list_items_tenant_id", "price_list_items", ["tenant_id"])
    op.create_index("ix_price_list_items_price_list_id", "price_list_items", ["price_list_id"])
    op.create_index("ix_price_list_items_item_id", "price_list_items", ["item_id"])

    op.create_table(
        "stock_batches",
        *_tenant_cols(),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("batch_number", sa.String(80), nullable=False),
        sa.Column("expiry_date", sa.Date, nullable=True),
        sa.Column("qty", sa.Numeric(18, 3), nullable=False, server_default="0"),
        sa.Column("received_date", sa.Date, nullable=False),
        sa.Column("notes", sa.Text, nullable=False, server_default=""),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_index("ix_stock_batches_tenant_id", "stock_batches", ["tenant_id"])
    op.create_index("ix_stock_batches_item_id", "stock_batches", ["item_id"])
    op.create_index("ix_stock_batches_expiry_date", "stock_batches", ["expiry_date"])

    conn = op.get_bind()
    for t in TABLES:
        _enable_rls(conn, t)


def downgrade() -> None:
    op.drop_table("stock_batches")
    op.drop_table("price_list_items")
    op.drop_table("price_lists")
