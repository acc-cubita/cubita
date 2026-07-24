"""سقف اعتبار مشتری

Revision ID: 0031
Revises: 0030

یک ستونِ افزودنی: `credit_limit` روی `contacts`. سقفِ مجازِ مانده‌ی مطالبات از یک
مشتری (به ریال). صفر یعنی «بدون سقف» — یعنی هیچ هشداری داده نمی‌شود، رفتارِ فعلیِ
سیستم. به همین دلیل مشتری‌های موجود با پیش‌فرضِ صفر بدونِ تغییر رفتار باقی می‌مانند.

این ستون فقط پایه‌ی یک هشدارِ زنده هنگام صدور فاکتور است و روی حسابداری، مالیات یا
مطالبات هیچ اثری ندارد.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0031"
down_revision: Union[str, None] = "0030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "contacts",
        sa.Column("credit_limit", sa.Numeric(18, 0), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("contacts", "credit_limit")
