"""sales quotations (پیش‌فاکتور): quote before a firm sales invoice, convertible to one

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE sales_quotation_number_seq START 1")

    op.create_table(
        "sales_quotations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("number", sa.Integer, nullable=True, unique=True),
        sa.Column("quotation_date", sa.Date, nullable=False),
        sa.Column("valid_until", sa.Date, nullable=True),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contacts.id"), nullable=True),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("total_amount", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column(
            "converted_invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sales_invoices.id"), nullable=True
        ),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'sent', 'accepted', 'rejected', 'converted')", name="ck_sales_quotations_status"
        ),
    )
    op.create_index("ix_sales_quotations_number", "sales_quotations", ["number"])

    op.create_table(
        "sales_quotation_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "quotation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sales_quotations.id"), nullable=False
        ),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("qty", sa.Numeric(18, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 0), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_table("sales_quotation_lines")
    op.drop_index("ix_sales_quotations_number", "sales_quotations")
    op.drop_table("sales_quotations")
    op.execute("DROP SEQUENCE sales_quotation_number_seq")
