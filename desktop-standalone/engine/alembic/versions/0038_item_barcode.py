"""بارکدِ کالا برای صندوقِ فروشگاهی (POS)

Revision ID: 0038
Revises: 0037

یک ستونِ اختیاریِ بارکد روی `items` + ایندکس برای جست‌وجوی سریعِ اسکن. یکتایی در سطحِ
دیتابیس اجباری نمی‌شود (چند NULL و انعطافِ کاربر)، ولی رابط کاربری هنگام ثبت هشدارِ تکرار
می‌دهد. جدولِ `items` از قبل مستأجرمحور و زیرِ RLS است، پس افزودنِ ستون RLS تازه نمی‌خواهد.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0038"
down_revision: Union[str, None] = "0037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("items", sa.Column("barcode", sa.String(64), nullable=True))
    op.create_index("ix_items_barcode", "items", ["barcode"])


def downgrade() -> None:
    op.drop_index("ix_items_barcode", table_name="items")
    op.drop_column("items", "barcode")
