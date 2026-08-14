"""نامِ مشتریِ دستی روی پیش‌فاکتور

Revision ID: 0044
Revises: 0043

ستونِ اختیاریِ `customer_name` روی `sales_quotations` — برای وقتی مشتری از فهرستِ
اشخاص انتخاب نشده و نامش دستی وارد می‌شود. بدونِ جدول یا RLSِ تازه.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0044"
down_revision: Union[str, None] = "0043"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("sales_quotations", sa.Column("customer_name", sa.String(200), nullable=True))


def downgrade() -> None:
    op.drop_column("sales_quotations", "customer_name")
