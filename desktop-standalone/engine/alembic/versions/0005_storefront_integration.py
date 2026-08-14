"""storefront integration: source_order_id on sales_invoices (idempotent order import)

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sales_invoices", sa.Column("source_order_id", sa.Integer(), nullable=True))
    op.create_unique_constraint("uq_sales_invoices_source_order_id", "sales_invoices", ["source_order_id"])
    op.create_index("ix_sales_invoices_source_order_id", "sales_invoices", ["source_order_id"])


def downgrade() -> None:
    op.drop_index("ix_sales_invoices_source_order_id", table_name="sales_invoices")
    op.drop_constraint("uq_sales_invoices_source_order_id", "sales_invoices", type_="unique")
    op.drop_column("sales_invoices", "source_order_id")
