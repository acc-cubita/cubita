"""هویتِ مالیاتیِ طرف حساب — برای گزارشِ معاملاتِ فصلی (ماده ۱۶۹ ق.م.م)

Revision ID: 0042
Revises: 0041

چهار ستونِ اختیاری روی `contacts`:
  - entity_type: نوعِ شخص (real=حقیقی / legal=حقوقی)، پیش‌فرض حقیقی
  - national_id: کد ملی (حقیقی) یا شناسه‌ی ملی (حقوقی)
  - economic_code: کد اقتصادی
  - postal_code: کد پستی

هیچ جدول یا سیاستِ RLS تازه‌ای نیست؛ فقط ستون روی جدولِ موجود.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0042"
down_revision: Union[str, None] = "0041"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "contacts",
        sa.Column("entity_type", sa.String(10), nullable=False, server_default="real"),
    )
    op.add_column("contacts", sa.Column("national_id", sa.String(20), nullable=True))
    op.add_column("contacts", sa.Column("economic_code", sa.String(20), nullable=True))
    op.add_column("contacts", sa.Column("postal_code", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("contacts", "postal_code")
    op.drop_column("contacts", "economic_code")
    op.drop_column("contacts", "national_id")
    op.drop_column("contacts", "entity_type")
