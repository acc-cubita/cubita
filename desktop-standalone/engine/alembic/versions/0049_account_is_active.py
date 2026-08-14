"""فعال/غیرفعالِ حساب در چارت

Revision ID: 0049
Revises: 0048

ستونِ `is_active` روی `accounts` — برای بایگانیِ حساب‌هایی که دیگر استفاده نمی‌شوند
ولی سند دارند و پاک نمی‌شوند. server_default='true' تا حساب‌های موجود فعال بمانند.
بدونِ جدول یا RLSِ تازه.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0049"
down_revision: Union[str, None] = "0048"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
    )


def downgrade() -> None:
    op.drop_column("accounts", "is_active")
