"""«ثبت فاکتور» چه‌قدر کار انجام دهد — انتخابِ خودِ کسب‌وکار

Revision ID: 0126
Revises: 0125

مهاجرتِ `0125` فاکتور فروش را از خروجِ انبار جدا کرد: سندِ تجاری، سندِ حسابداری
و خروجِ فیزیکی سه حقیقتِ مستقل شدند. جداسازی درست است و برنمی‌گردد — کسب‌وکاری
که امروز فاکتور می‌دهد و هفته‌ی بعد کالا را می‌فرستد بدونش کار نمی‌کند.

ولی برای مغازه‌ای که فاکتور و تحویل یک لحظه‌اند، سه سند یعنی دو دکمه‌ی اضافه و
دو فراموشیِ ممکن: فاکتوری بی‌سند، و کالایی که از انبار کم نشده. پس این‌جا یک
پرچمِ سیاست می‌نشیند، نه یک بازگشتِ معماری.

**پیش‌فرض `immediate` است** — یعنی رفتاری که کاربران سال‌ها داشته‌اند. `NULL`
می‌ماند و سرویس تفسیرش می‌کند، پس هیچ ردیفی نوشته نمی‌شود و backfill لازم نیست.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0126"
down_revision: Union[str, None] = "0125"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    #: `NULL` = پیش‌فرضِ سرویس. `server_default` عمداً نیست: پیش‌فرض جای واحدش
    #: `sales_posting.DEFAULT_POSTING_MODE` است، و دو جا نوشتنش یعنی روزی که یکی
    #: عوض شود آن یکی بی‌صدا جا بماند.
    op.add_column("tenants", sa.Column("sales_invoice_posting", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "sales_invoice_posting")
