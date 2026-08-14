"""بازار — محدودیتِ سفارش‌گذاریِ لیستینگ + سهمِ نقدِ سفارش (تسویه‌ی نقد/اعتباری)

Revision ID: 0063
Revises: 0062

- روی marketplace_listings سه ستونِ محدودیت (کف/سقفِ تعداد و سقفِ دفعاتِ روزانه؛ ۰ = بی‌حد).
- روی marketplace_orders ستونِ cash_amount = سهمِ نقدِ تسویه‌شده هنگام تأیید.
همه با server_default تا ردیف‌های موجود مقدارِ ۰ بگیرند. جدول‌ها سراسری‌اند (بدونِ RLS).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0063"
down_revision: Union[str, None] = "0062"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "marketplace_listings",
        sa.Column("min_order_qty", sa.Numeric(18, 3), nullable=False, server_default="0"),
    )
    op.add_column(
        "marketplace_listings",
        sa.Column("max_order_qty", sa.Numeric(18, 3), nullable=False, server_default="0"),
    )
    op.add_column(
        "marketplace_listings",
        sa.Column("daily_order_limit", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "marketplace_orders",
        sa.Column("cash_amount", sa.Numeric(18, 0), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("marketplace_orders", "cash_amount")
    op.drop_column("marketplace_listings", "daily_order_limit")
    op.drop_column("marketplace_listings", "max_order_qty")
    op.drop_column("marketplace_listings", "min_order_qty")
