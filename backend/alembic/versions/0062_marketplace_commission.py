"""بازار — کمیسیونِ پلتفرم (۲٪) روی سفارش‌های قطعی‌شده (جدولِ سراسری، بدونِ RLS)

Revision ID: 0062
Revises: 0061

یک رکورد به‌ازای هر سفارش (order_id یکتا)؛ ماهانه (period شمسی) توسطِ سوپرادمین با
واریزِ دستی تسویه می‌شود. مثلِ بقیه‌ی جدول‌های بازار میان‌مستأجری و بدونِ RLS است.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0062"
down_revision: Union[str, None] = "0061"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "marketplace_commissions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "order_id",
            UUID,
            sa.ForeignKey("marketplace_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "distributor_tenant_id",
            UUID,
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("period", sa.String(7), nullable=False),
        sa.Column("base_amount", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("rate", sa.Numeric(6, 4), nullable=False, server_default="0.02"),
        sa.Column("amount", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("settle_note", sa.String(300), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("order_id", name="uq_mp_commission_order"),
    )
    op.create_index("ix_mp_commission_order", "marketplace_commissions", ["order_id"])
    op.create_index(
        "ix_mp_commission_distributor", "marketplace_commissions", ["distributor_tenant_id"]
    )
    op.create_index("ix_mp_commission_period", "marketplace_commissions", ["period"])


def downgrade() -> None:
    op.drop_index("ix_mp_commission_period", table_name="marketplace_commissions")
    op.drop_index("ix_mp_commission_distributor", table_name="marketplace_commissions")
    op.drop_index("ix_mp_commission_order", table_name="marketplace_commissions")
    op.drop_table("marketplace_commissions")
