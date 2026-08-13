"""بازار — فیلدهای پرداختِ آنلاین روی سفارش (تسویه‌ی online)

Revision ID: 0061
Revises: 0060

authority/provider/ref برای جریانِ پرداختِ آنلاین با درگاهِ خودِ پخش‌کننده.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0061"
down_revision: Union[str, None] = "0060"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("marketplace_orders", sa.Column("payment_authority", sa.String(120), nullable=True))
    op.add_column(
        "marketplace_orders",
        sa.Column("payment_provider", sa.String(20), nullable=False, server_default=""),
    )
    op.add_column(
        "marketplace_orders",
        sa.Column("payment_ref", sa.String(120), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("marketplace_orders", "payment_ref")
    op.drop_column("marketplace_orders", "payment_provider")
    op.drop_column("marketplace_orders", "payment_authority")
