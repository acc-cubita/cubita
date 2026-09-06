"""ماهیتِ حساب و عنوانِ دوم روی چارت

Revision ID: 0087
Revises: 0086

دو ستون روی `accounts`، هر دو اختیاری و هر دو بی‌اثر بر داده‌ی موجود.

**`nature` عمداً nullable است و backfill ندارد.** ماهیتِ هر حساب از `type` مشتق
می‌شود (دارایی و هزینه بدهکار؛ بدهی، سرمایه و درآمد بستانکار) و NULL یعنی «همان
مشتق». پس هیچ حسابِ موجودی معنایش عوض نمی‌شود، کسی مجبور نیست چارتش را دوباره پر
کند، و — مهم‌تر — این مهاجرت هیچ `UPDATE`ی روی جدولِ RLS‌دار نمی‌زند، پس در دامِ
«backfill موفق گزارش داد و صفر ردیف را عوض کرد» نمی‌افتد.

مقدارِ صریح فقط برای دو حالت لازم است: حسابی که خلافِ نوعش ماهیت دارد، و حسابی که
هر دو سمت برایش طبیعی است (`any` — حسابِ واسط، تسویه، طرفِ‌حسابی که هم می‌خرد هم
می‌فروشد).

**این ستون هیچ ثبتی را نمی‌شکند.** فقط مبنای گزارشِ «حساب‌های خلافِ ماهیت» است.
خلافِ ماهیت شدن گاهی واقعاً درست است (اضافه‌برداشتِ بانکی، پیش‌دریافتِ مشتری)، پس
مسدود کردنش یعنی جلوگیری از ثبتِ رویدادی که واقعاً اتفاق افتاده.

`name2` عنوانِ دومِ حساب است (معمولاً انگلیسی) برای گزارشِ دوزبانه؛ پیش‌فرض رشته‌ی
خالی، پس روی هیچ نمایشی اثر ندارد.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0087"
down_revision: Union[str, None] = "0086"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("accounts", sa.Column("nature", sa.String(length=10), nullable=True))
    op.add_column(
        "accounts",
        sa.Column("name2", sa.String(length=200), nullable=False, server_default=""),
    )
    op.create_check_constraint(
        "ck_accounts_nature",
        "accounts",
        "nature IS NULL OR nature IN ('debit', 'credit', 'any')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_accounts_nature", "accounts", type_="check")
    op.drop_column("accounts", "name2")
    op.drop_column("accounts", "nature")
