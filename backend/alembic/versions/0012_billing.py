"""billing: plans + purchases (سایت تجاری cubita.ir)

Revision ID: 0012
Revises: 0011
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("key", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("price_toman", sa.Numeric(18, 0), nullable=False),
        sa.Column("billing_period", sa.String(20), nullable=False, server_default="yearly"),
        sa.Column("max_users", sa.Integer, nullable=True),
        sa.Column("features", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("highlighted", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_plans_key", "plans", ["key"])

    op.create_table(
        "purchases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("plans.id"), nullable=False),
        sa.Column("customer_name", sa.String(150), nullable=False),
        sa.Column("customer_email", sa.String(150), nullable=False),
        sa.Column("customer_phone", sa.String(20), nullable=False, server_default=""),
        sa.Column("business_name", sa.String(150), nullable=False, server_default=""),
        sa.Column("amount_toman", sa.Numeric(18, 0), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending_payment"),
        sa.Column("zarinpal_authority", sa.String(100), nullable=True),
        sa.Column("zarinpal_ref_id", sa.String(100), nullable=True),
        sa.Column("fulfilled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("admin_notes", sa.Text, nullable=False, server_default=""),
        sa.CheckConstraint(
            "status IN ('pending_payment', 'paid', 'cancelled', 'fulfilled')", name="ck_purchases_status"
        ),
    )
    op.create_index("ix_purchases_zarinpal_authority", "purchases", ["zarinpal_authority"])


def downgrade() -> None:
    op.drop_table("purchases")
    op.drop_table("plans")
