"""دسترسیِ اختصاصیِ کاربر در هر کسب‌وکار

Revision ID: 0075
Revises: 0074

ستونِ `permissions` روی `memberships`: نقشه‌ی ماژول→اکشن‌ها که **جایگزینِ** مجوزِ
نقش می‌شود. NULL یعنی «همان مجوزِ نقش»، پس همه‌ی عضویت‌های موجود بی‌تغییر می‌مانند و
ارتقا دسترسیِ هیچ‌کس را کم‌وزیاد نمی‌کند.

`memberships` جدولِ سراسری است (در GLOBAL_TABLES)، پس RLS ندارد و این‌جا فقط یک
ستونِ ساده اضافه می‌شود.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0075"
down_revision: Union[str, None] = "0074"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("memberships", sa.Column("permissions", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("memberships", "permissions")
