"""sales & purchase returns (برگشت از فروش/خرید) against a specific original invoice

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE sales_return_number_seq START 1")
    op.execute("CREATE SEQUENCE purchase_return_number_seq START 1")

    op.create_table(
        "sales_returns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("number", sa.Integer, nullable=True, unique=True),
        sa.Column("return_date", sa.Date, nullable=False),
        sa.Column("sales_invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sales_invoices.id"), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("total_amount", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("total_cost", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("journal_entries.id"), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_index("ix_sales_returns_number", "sales_returns", ["number"])

    op.create_table(
        "sales_return_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("return_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sales_returns.id"), nullable=False),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("qty", sa.Numeric(18, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 0), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 0), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
    )

    op.create_table(
        "purchase_returns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("number", sa.Integer, nullable=True, unique=True),
        sa.Column("return_date", sa.Date, nullable=False),
        sa.Column(
            "purchase_invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("purchase_invoices.id"), nullable=False
        ),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("total_amount", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("journal_entries.id"), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_index("ix_purchase_returns_number", "purchase_returns", ["number"])

    op.create_table(
        "purchase_return_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("return_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("purchase_returns.id"), nullable=False),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("qty", sa.Numeric(18, 3), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 0), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_table("purchase_return_lines")
    op.drop_index("ix_purchase_returns_number", "purchase_returns")
    op.drop_table("purchase_returns")
    op.drop_table("sales_return_lines")
    op.drop_index("ix_sales_returns_number", "sales_returns")
    op.drop_table("sales_returns")
    op.execute("DROP SEQUENCE purchase_return_number_seq")
    op.execute("DROP SEQUENCE sales_return_number_seq")
