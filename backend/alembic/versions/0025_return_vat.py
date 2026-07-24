"""مالیات بر ارزش افزوده روی برگشت از فروش و برگشت از خرید

Revision ID: 0025
Revises: 0024

تا امروز فقط خودِ فاکتورها مالیات داشتند و برگشت‌ها بدون مالیات ثبت می‌شدند. یعنی
مالیاتی که هنگام فروش بستانکار (یا هنگام خرید بدهکار) شده بود، با برگشتِ کالا
برنمی‌گشت و ماندهٔ حساب‌های ۲۱۰۵/۱۱۰۷ برای همیشه از واقعیت جلو می‌افتاد — درست
همان عددی که مبنای اظهارنامه است.

دو ستون دقیقاً مثل خودِ فاکتورها (`0024`) اضافه می‌شود؛ برای ردیف‌های قبلی صفر، پس
برگشت‌های ثبت‌شده‌ی گذشته رفتارشان عوض نمی‌شود (مالیاتشان صفر بوده و صفر می‌ماند).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: Union[str, None] = "0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ("sales_returns", "purchase_returns")


def upgrade() -> None:
    for table in TABLES:
        op.add_column(table, sa.Column("tax_rate", sa.Numeric(5, 2), nullable=False, server_default="0"))
        op.add_column(table, sa.Column("tax_amount", sa.Numeric(18, 0), nullable=False, server_default="0"))


def downgrade() -> None:
    for table in TABLES:
        op.drop_column(table, "tax_amount")
        op.drop_column(table, "tax_rate")
