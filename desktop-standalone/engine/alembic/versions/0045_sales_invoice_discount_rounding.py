"""تخفیفِ کلِ فاکتور و گِرد کردنِ مبلغِ فاکتور فروش

Revision ID: 0045
Revises: 0044

دو ستونِ اختیاری روی `sales_invoices`:
  - `invoice_discount` — تخفیفِ کلِ فاکتور (که هنگام ثبت در ردیف‌ها تسهیم می‌شود؛ اینجا
     فقط برای نمایشِ شفاف جدا نگه داشته می‌شود).
  - `rounding` — تعدیلِ گِرد کردنِ مبلغِ نهایی (پس از مالیات)، علامت‌دار.

هر دو server_default='0' دارند تا فاکتورهای موجود بی‌تغییر بمانند. بدونِ جدول یا RLSِ تازه.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0045"
down_revision: Union[str, None] = "0044"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sales_invoices",
        sa.Column("invoice_discount", sa.Numeric(18, 0), nullable=False, server_default="0"),
    )
    op.add_column(
        "sales_invoices",
        sa.Column("rounding", sa.Numeric(18, 0), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("sales_invoices", "rounding")
    op.drop_column("sales_invoices", "invoice_discount")
