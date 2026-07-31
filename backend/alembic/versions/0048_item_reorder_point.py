"""نقطه‌ی سفارشِ مجدد کالا

Revision ID: 0048
Revises: 0047

ستونِ `reorder_point` روی `items` — حداقلِ موجودی برای هشدارِ «نیازمندِ سفارش».
server_default='0' تا کالاهای موجود بی‌تغییر (بدونِ هشدار) بمانند. بدونِ جدول یا RLSِ
تازه (items مستأجرمحورِ موجود است).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0048"
down_revision: Union[str, None] = "0047"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "items",
        sa.Column("reorder_point", sa.Numeric(18, 3), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("items", "reorder_point")
