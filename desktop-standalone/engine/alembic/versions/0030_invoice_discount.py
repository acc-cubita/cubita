"""تخفیف روی فاکتور فروش و خرید

Revision ID: 0030
Revises: 0029

چهار ستونِ افزودنی: `discount` روی ردیف‌های فاکتور و `total_discount` روی سرِ فاکتور.

**قرارداد معنایی (مهم):** `total_amount` همچنان «خالص» است، ولی از این پس یعنی
**خالصِ پس از تخفیف**. به همین دلیل سند حسابداری، محاسبه‌ی مالیات بر ارزش افزوده،
گزارش‌ها و مطالبات هیچ‌کدام تغییر نمی‌کنند و همچنان درست‌اند: درآمد به مبلغِ پس از
تخفیف ثبت می‌شود و مالیات روی همان پایه حساب می‌شود — که رفتارِ درستِ «تخفیف تجاری»
است. تخفیف جدا ذخیره می‌شود تا صورتحساب مؤدیان و نمای چاپی رقمِ واقعی را نشان دهند.

همه‌ی ستون‌ها با پیش‌فرضِ صفر اضافه می‌شوند، پس فاکتورهای موجود بدون تغییرِ معنا
باقی می‌مانند (تخفیفِ صفر = همان مبلغِ قبلی).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0030"
down_revision: Union[str, None] = "0029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sales_invoice_lines",
        sa.Column("discount", sa.Numeric(18, 0), nullable=False, server_default="0"),
    )
    op.add_column(
        "purchase_invoice_lines",
        sa.Column("discount", sa.Numeric(18, 0), nullable=False, server_default="0"),
    )
    op.add_column(
        "sales_invoices",
        sa.Column("total_discount", sa.Numeric(18, 0), nullable=False, server_default="0"),
    )
    op.add_column(
        "purchase_invoices",
        sa.Column("total_discount", sa.Numeric(18, 0), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("purchase_invoices", "total_discount")
    op.drop_column("sales_invoices", "total_discount")
    op.drop_column("purchase_invoice_lines", "discount")
    op.drop_column("sales_invoice_lines", "discount")
