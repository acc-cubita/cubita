"""ایندکسِ `journal_entry_id` — تا «این سند از کدام عملیات آمد؟» seq scan نباشد

Revision ID: 0101
Revises: 0100

## چه چیزی این را لازم کرد

جهتِ **عملیات ← سند** از قبل کار می‌کرد: شانزده مدل ستونِ `journal_entry_id`
دارند. جهتِ معکوس — «سندِ ۸۵۰ از کدام فاکتور آمد؟» — نبود.

`JournalEntry.source_id` برای همین ساخته شده بود و هیچ‌وقت پر نشد. به‌جای پرکردنش
(که همان رابطه را در دو ستون ذخیره می‌کرد و می‌توانست دریفت کند)، جواب از خودِ
داده مشتق می‌شود: `source_type` می‌گوید سراغِ کدام جدول برویم و آن‌جا
`WHERE journal_entry_id = ?` جواب را دارد.

## چرا ایندکس

**کلیدِ خارجی در PostgreSQL خودبه‌خود ایندکس نمی‌گیرد** — فقط ستونِ *ارجاع‌شده*
(کلیدِ اصلی) ایندکس دارد، نه ستونِ ارجاع‌دهنده. بدونِ این مهاجرت، هر بار که فهرستِ
اسناد باز شود روی `sales_invoices` و بقیه seq scan می‌خورد؛ برای کسب‌وکاری با صد
هزار فاکتور یعنی صفحه‌ای که باز نمی‌شود.

همین ایندکس‌ها کارِ دومی هم می‌کنند: حذفِ یک سند حسابداری باید همه‌ی ارجاع‌های
FK را بسنجد و آن هم امروز seq scan است.

## ایمنی

**فقط `CREATE INDEX` است — هیچ `INSERT`/`UPDATE`ی ندارد.** پس قاعده‌ی پروژه
(«هرگز داخلِ مهاجرت روی جدولِ RLS ردیف ننویس») اصلاً موضوعیت پیدا نمی‌کند و
ایندکس هم به سیاست‌های RLS کاری ندارد.

`CONCURRENTLY` عمداً نیست: مهاجرت در یک تراکنش اجرا می‌شود و
`CREATE INDEX CONCURRENTLY` بیرونِ تراکنش لازم دارد. قفلِ `SHARE` روی این
جدول‌ها کوتاه است و استقرار هم پشتِ توقفِ سرویس انجام می‌شود.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0101"
down_revision: Union[str, None] = "0100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: هر جدولی که ستونِ `journal_entry_id` دارد. `payroll_settlements` هم هست: ستونش
#: امروز همیشه NULL است (تسویه‌حساب سند نمی‌زند)، ولی ایندکسِ جزئی‌نشده روی ستونِ
#: خالی تقریباً رایگان است و اگر روزی سند بزند، آماده است.
TABLES = (
    "sales_invoices",
    "purchase_invoices",
    "sales_returns",
    "purchase_returns",
    "treasury_transactions",
    "bank_transactions",
    "petty_cash_transactions",
    "payslips",
    "benefit_runs",
    "payroll_settlements",
    "depreciation_entries",
    "production_orders",
    "stock_adjustments",
    "stock_count_sessions",
    "credit_debit_notes",
    "fiscal_period_closes",
)


def upgrade() -> None:
    for table in TABLES:
        op.create_index(f"ix_{table}_journal_entry_id", table, ["journal_entry_id"])


def downgrade() -> None:
    for table in TABLES:
        op.drop_index(f"ix_{table}_journal_entry_id", table_name=table)
