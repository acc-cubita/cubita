"""ویژگی‌های حساب — شش پرچمِ فرمِ ویرایشِ حساب، و پیگیریِ ردیفِ سند

Revision ID: 0088
Revises: 0087

شش ستونِ بولی روی `accounts` و دو ستونِ اختیاری روی `journal_lines`.

**هیچ‌کدام backfill ندارند.** پیش‌فرضِ DDL روی ستونِ تازه در PostgreSQL ۱۱ به بعد در
کاتالوگ می‌نشیند و جدول را بازنویسی نمی‌کند، پس هیچ `UPDATE`ی روی جدولِ RLS‌دار
اجرا نمی‌شود — همان دامی که `CLAUDE.md` درباره‌اش هشدار می‌دهد.

پیش‌فرض‌ها طوری انتخاب شده‌اند که **رفتارِ امروز عوض نشود**:

* `in_management_reports` پیش‌فرض *true* است تا هیچ حسابی از گزارش‌ها نیفتد؛ این
  پرچم فقط وقتی اثر دارد که کاربر خودش خاموشش کند.
* بقیه پیش‌فرض *false*اند و هیچ‌کدام مسیرِ موجودی را نمی‌بندند:
  - `nature_control` فقط صافیِ اختیاریِ گزارشِ خلافِ ماهیت است.
  - `is_fx` و `fx_revaluable` سندِ تسعیر را محدود *نمی‌کنند* مگر کاربر حسابی را
    صریحاً «ارزی ولی غیرقابلِ تسعیر» علامت بزند — یعنی انصراف، نه انتخاب. بدونِ
    این طراحی، پیش‌فرضِ false صفحه‌ی تسعیرِ موجود را یک‌شبه خالی می‌کرد.
  - `accepts_tafsili` فقط ساختِ زیرحسابِ *تازه* زیرِ حسابِ غیرِسرفصل را مشروط
    می‌کند؛ حسابی که از قبل زیرمجموعه دارد در روتر تفصیلی‌پذیر شمرده می‌شود، پس
    چارت‌های موجود دست‌نخورده می‌مانند و این مهاجرت لازم نیست چیزی را پر کند.
  - `has_tracking` فقط دو فیلدِ تازه‌ی ردیفِ سند را باز می‌کند.

`tracking_no`/`tracking_date` عمداً روی *ردیف* نشسته‌اند نه سند: پیگیری مالِ آن
حسابِ خاص است (شماره‌ی حواله، شماره‌ی نامه، ارجاعِ پرونده) و یک سند می‌تواند چند
ردیف با پیگیری‌های متفاوت داشته باشد. این جدولِ `checks` نیست و جایش را نمی‌گیرد:
چک موجودیتِ مستقلی با سررسید و وضعیت و گردش است؛ پیگیری فقط یک ارجاعِ متنی است.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0088"
down_revision: Union[str, None] = "0087"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: (نام، پیش‌فرض) — پیش‌فرضِ `in_management_reports` عمداً با بقیه فرق دارد.
_FLAGS = (
    ("nature_control", "false"),
    ("is_fx", "false"),
    ("fx_revaluable", "false"),
    ("accepts_tafsili", "false"),
    ("has_tracking", "false"),
    ("in_management_reports", "true"),
)


def upgrade() -> None:
    for name, default in _FLAGS:
        op.add_column(
            "accounts",
            sa.Column(name, sa.Boolean(), nullable=False, server_default=sa.text(default)),
        )
    # «تسعیر پذیر» بدونِ «ارزی» بی‌معناست — در فرمِ سپیدار هم تا ارزی تیک نخورد
    # خاکستری است. قید این را در پایگاه‌داده هم می‌بندد تا از راهِ API هم نشود.
    op.create_check_constraint(
        "ck_accounts_fx_revaluable",
        "accounts",
        "NOT fx_revaluable OR is_fx",
    )

    op.add_column("journal_lines", sa.Column("tracking_no", sa.String(length=50), nullable=True))
    op.add_column("journal_lines", sa.Column("tracking_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("journal_lines", "tracking_date")
    op.drop_column("journal_lines", "tracking_no")
    op.drop_constraint("ck_accounts_fx_revaluable", "accounts", type_="check")
    for name, _ in reversed(_FLAGS):
        op.drop_column("accounts", name)
