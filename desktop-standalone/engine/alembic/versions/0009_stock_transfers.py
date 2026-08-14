"""inter-warehouse stock transfers (حواله بین‌انباری) — no accounting impact, quantity movement only

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE stock_transfer_number_seq START 1")

    op.create_table(
        "stock_transfers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("number", sa.Integer, nullable=True, unique=True),
        sa.Column("transfer_date", sa.Date, nullable=False),
        sa.Column("from_warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("to_warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.CheckConstraint("from_warehouse_id <> to_warehouse_id", name="ck_stock_transfers_diff_warehouse"),
    )
    op.create_index("ix_stock_transfers_number", "stock_transfers", ["number"])

    op.create_table(
        "stock_transfer_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("transfer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stock_transfers.id"), nullable=False),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("qty", sa.Numeric(18, 3), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("stock_transfer_lines")
    op.drop_index("ix_stock_transfers_number", "stock_transfers")
    op.drop_table("stock_transfers")
    op.execute("DROP SEQUENCE stock_transfer_number_seq")
