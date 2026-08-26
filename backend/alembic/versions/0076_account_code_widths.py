"""قاعده‌ی کدینگِ چارت — رقمِ افزوده در هر سطح

Revision ID: 0076
Revises: 0075

ستونِ `account_code_widths` روی `tenants`: فهرستِ چهارتایی (گروه، کل، معین، تفصیلی).
NULL یعنی «پیش‌فرضِ سرویس» — پس هیچ کسب‌وکاری با ارتقا قاعده‌ی تازه‌ای نمی‌گیرد و
هیچ کدِ موجودی نامعتبر نمی‌شود؛ پیش‌فرض عمداً همان ساختارِ چارتِ فعلی است.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0076"
down_revision: Union[str, None] = "0075"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("account_code_widths", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "account_code_widths")
