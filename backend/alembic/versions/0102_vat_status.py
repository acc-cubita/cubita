"""وضعیتِ مالیات بر ارزش افزوده — «معاف» از «نرخِ صفر» جدا می‌شود

Revision ID: 0102
Revises: 0101

## چه چیزی این را لازم کرد

اولین سؤالِ هر گزارشِ ارزش افزوده — «چقدر فروشِ معاف داشته‌ایم؟» — در کوبیتا
جوابی نداشت. نه کالا وضعیتِ مالیاتی داشت، نه گزارش پایه را تفکیک می‌کرد؛ تنها
چیزی که بود `tax_rate` روی سربرگِ فاکتور.

و `tax_rate = 0` **مبهم** است: سالِ بعد کسی نمی‌تواند بگوید این کالا واقعاً معاف
بوده یا فقط آن فاکتور بی‌مالیات صادر شده.

## سه ستون، دو نقشِ متفاوت

* `items.vat_status` — **تنظیم**. جایی که کاربر تعیین می‌کند.
* `sales_invoice_lines.vat_status` و `purchase_invoice_lines.vat_status` —
  **واقعیتِ قفل‌شده در لحظه‌ی معامله**، کپی‌شده از کالا هنگام ثبتِ فاکتور.

جداییِ این دو عمدی است و همان الگوی `tax_rate` / `tax_amount` را دارد. اگر گزارش
از وضعیتِ *امروزِ* کالا می‌خواند، کالایی که امسال معاف شده فروشِ **پارسال** را هم
معاف نشان می‌داد — در حالی که آن فروش واقعاً مشمول بوده. قانون عوض می‌شود؛ تاریخ نه.

## پیش‌فرض چیزی را عوض نمی‌کند

همه‌ی ردیف‌های موجود `taxable` می‌شوند، که همان فرضِ ضمنیِ امروزِ گزارش است:
تا پیش از این، هر فروشی مشمول فرض می‌شد.

**هیچ `UPDATE`ی اجرا نمی‌شود.** پیش‌فرضِ DDL در PostgreSQL ۱۱+ در کاتالوگ می‌نشیند
و ردیف‌های موجود دست نمی‌خورند — پس قاعده‌ی پروژه («هرگز داخلِ مهاجرت روی جدولِ
RLS ردیف ننویس») اصلاً موضوعیت پیدا نمی‌کند.

قیدِ `CHECK` عمداً **نیست**: مقدارِ سومی مثل «نرخِ صفرِ قانونی» یا «خارج از شمول»
روزی ممکن است لازم شود، و قیدِ پایگاه‌داده آن روز یک مهاجرتِ اضافه می‌طلبد بی‌آنکه
امروز چیزی را ایمن‌تر کند — اعتبارسنجی در لایه‌ی schema انجام می‌شود.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0102"
down_revision: Union[str, None] = "0101"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ("items", "sales_invoice_lines", "purchase_invoice_lines")


def upgrade() -> None:
    for table in TABLES:
        op.add_column(
            table,
            sa.Column("vat_status", sa.String(10), nullable=False, server_default="taxable"),
        )


def downgrade() -> None:
    for table in TABLES:
        op.drop_column(table, "vat_status")
