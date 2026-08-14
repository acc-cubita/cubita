"""آخرین ورودِ کاربر

Revision ID: 0047
Revises: 0046

ستونِ اختیاریِ `last_login_at` روی `users` — مهرِ زمانِ آخرین ورودِ موفق، برای
پنلِ «مدیریت اکانت‌ها» (آخرین فعالیتِ هر اکانت). nullable است تا کاربرانِ موجود
(که هنوز واردی ثبت نشده) بی‌تغییر بمانند؛ با نخستین ورود پر می‌شود. بدونِ RLS تازه
(جدولِ users سراسری است).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0047"
down_revision: Union[str, None] = "0046"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "last_login_at")
