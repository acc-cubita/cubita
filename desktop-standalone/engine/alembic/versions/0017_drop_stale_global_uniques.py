"""حذف ایندکس‌های یکتای سراسری که از مهاجرت 0015 جا مانده بودند

Revision ID: 0017
Revises: 0016

مهاجرت 0015 قیدهای یکتا را مرکب کرد ولی فقط CONSTRAINTها را حذف کرد. برای ستون‌هایی
که در مدل هم `unique=True` و هم `index=True` داشتند، Postgres علاوه بر constraint یک
ایندکس یکتای جداگانه به نام `ix_<جدول>_<ستون>` هم داشت که دست‌نخورده ماند.

نتیجه این بود که چند‌مستأجری در عمل کار نمی‌کرد: مستأجر دوم نمی‌توانست کد حساب
«1101» یا نقش «owner» یا فاکتور شماره ۱ داشته باشد، چون ایندکس یکتای سراسری هنوز
سر جایش بود. اولین ثبت‌نام واقعی روی دیتابیس مهاجرت‌شده با UniqueViolation شکست خورد.

چرا تست‌ها نگرفتند: schema تست با `Base.metadata.create_all()` از روی مدل‌های
امروز ساخته می‌شود، و در آن مدل‌ها `unique=True` قبلاً برداشته شده — پس ایندکس
اصلاً یکتا ساخته نمی‌شد. فقط دیتابیسی که واقعاً *مهاجرت* کرده بود این حالت را داشت.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (جدول، ستون) — ایندکس یکتای سراسری که باید غیریکتا شود
STALE = [
    ("accounts", "code"),
    ("employees", "national_id"),
    ("fiscal_period_closes", "closing_date"),
    ("items", "sku"),
    ("journal_entries", "number"),
    ("payroll_settings", "year"),
    ("payslips", "number"),
    ("purchase_invoices", "number"),
    ("purchase_returns", "number"),
    ("roles", "key"),
    ("sales_invoices", "number"),
    ("sales_invoices", "source_order_id"),
    ("sales_quotations", "number"),
    ("sales_returns", "number"),
    ("stock_transfers", "number"),
    ("warehouses", "code"),
]


def upgrade() -> None:
    conn = op.get_bind()

    for table, column in STALE:
        index = f"ix_{table}_{column}"
        is_unique = conn.execute(
            sa.text(
                "SELECT indexdef LIKE '%%UNIQUE%%' FROM pg_indexes "
                "WHERE schemaname = current_schema() AND indexname = :i"
            ),
            {"i": index},
        ).scalar()
        if not is_unique:
            continue  # روی دیتابیسی که از create_all ساخته شده کاری لازم نیست

        # ایندکس جست‌وجو حفظ می‌شود، فقط یکتایی‌اش برداشته می‌شود؛ یکتایی حالا
        # وظیفه‌ی قید مرکب (tenant_id, ستون) است که 0015 ساخت.
        conn.execute(sa.text(f"DROP INDEX {index}"))
        op.create_index(index, table, [column], unique=False)

    # گارد: بعد از این مهاجرت نباید هیچ ایندکس یکتای سراسری روی ستون‌های
    # مستأجرمحور باقی بماند، وگرنه مستأجر دوم بی‌صدا شکست می‌خورد.
    leftovers = conn.execute(
        sa.text(
            "SELECT indexname FROM pg_indexes "
            "WHERE schemaname = current_schema() AND indexdef LIKE '%UNIQUE%' "
            "  AND indexname LIKE 'ix_%' AND indexdef NOT LIKE '%tenant_id%'"
        )
    ).scalars().all()
    if leftovers:
        raise RuntimeError(f"ایندکس یکتای سراسری باقی مانده: {leftovers}")


def downgrade() -> None:
    conn = op.get_bind()
    for table, column in STALE:
        index = f"ix_{table}_{column}"
        conn.execute(sa.text(f"DROP INDEX IF EXISTS {index}"))
        op.create_index(index, table, [column], unique=True)
