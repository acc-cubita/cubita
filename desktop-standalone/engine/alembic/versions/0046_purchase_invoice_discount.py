"""تخفیفِ کلِ فاکتور خرید

Revision ID: 0046
Revises: 0045

ستونِ اختیاریِ `invoice_discount` روی `purchase_invoices` — تخفیفِ کلِ فاکتور که هنگام
ثبت در ردیف‌ها تسهیم می‌شود (اینجا فقط برای نمایشِ شفاف جدا نگه داشته می‌شود).
server_default='0' تا فاکتورهای موجود بی‌تغییر بمانند. بدونِ جدول یا RLSِ تازه.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0046"
down_revision: Union[str, None] = "0045"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "purchase_invoices",
        sa.Column("invoice_discount", sa.Numeric(18, 0), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("purchase_invoices", "invoice_discount")
