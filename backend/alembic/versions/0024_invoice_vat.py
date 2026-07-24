"""مالیات بر ارزش افزوده روی فاکتور فروش و خرید

Revision ID: 0024
Revises: 0023

فقط دو ستونِ «نرخ» و «مبلغ» مالیات به فاکتورها اضافه می‌شود؛ برای ردیف‌های قبلی
صفر (server_default). حساب‌های مالیاتِ چارت (۲۱۰۵ پرداختنی، ۱۱۰۷ اعتبار مالیاتی)
به‌صورت خودکار هنگام اولین فاکتورِ مالیات‌دار ساخته می‌شوند
(`app/services/common.get_or_create_account`)، پس اینجا نیازی به backfillِ
تنانت‌محور و درگیرشدن با RLS نیست.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: Union[str, None] = "0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ("sales_invoices", "purchase_invoices")


def upgrade() -> None:
    for table in TABLES:
        op.add_column(table, sa.Column("tax_rate", sa.Numeric(5, 2), nullable=False, server_default="0"))
        op.add_column(table, sa.Column("tax_amount", sa.Numeric(18, 0), nullable=False, server_default="0"))


def downgrade() -> None:
    for table in TABLES:
        op.drop_column(table, "tax_amount")
        op.drop_column(table, "tax_rate")
