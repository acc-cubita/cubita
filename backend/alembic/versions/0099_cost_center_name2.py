"""عنوانِ دومِ مرکز هزینه

Revision ID: 0099
Revises: 0098

## چه چیزی را می‌بندد

فرمِ «مرکز هزینه»ی سپیدار «عنوان انگلیسی» دارد و کوبیتا نداشت — با اینکه سه
موجودیتِ هم‌رده‌اش از قبل دارند: `accounts.name2`، `analytic_accounts.name2` و
`contacts.name2`. مرکز هزینه تنها یکی بود که جا مانده بود، و برای کسب‌وکارِ
صادراتی که گزارشِ دوزبانه می‌خواهد همان کمبود است.

## چیزی که از همان فرم عمداً **نیامد**: «کد تفصیلی»

فرمِ سپیدار مرکز هزینه را به یک تفصیلی پیوند می‌زند. آن فیلد **محصولِ معماریِ
سپیدار است، نه یک قابلیت**: سپیدار بُعدِ جدایی برای مرکز هزینه ندارد و با سطحِ
تفصیلی شبیه‌سازی‌اش می‌کند.

کوبیتا همان چیز را درجه‌یک دارد — `journal_lines` هر دو ستون را جدا نگه می‌دارد
(`cost_center_id` و `analytic_id`)، و docstringِ `AnalyticAccount` این تفکیک را
صریح ثبت کرده: «لحظه‌ای که چیزی ساختار بگیرد، جایش مرکز هزینه است نه اینجا».

پس پیوند دادنِ مرکز هزینه به یک تفصیلی یعنی یک چیز روی یک ردیفِ سند در دو بُعد
بنشیند — همان «دو نمای یک داده» که قیدِ ۶ `CLAUDE.md` منع می‌کند، و دو عددِ
متناقض در گزارش می‌سازد.

(`contacts.analytic_id` نقضِ این نیست: طرف‌حساب **ذاتاً** یک تفصیلی است، چون
دریافتنی به نامش ثبت می‌شود — نه یک بُعدِ ساختاریِ موازی.)

## چرا backfill نیست

مرکزهای موجود عنوانِ دوم نداشتند، پس `''` مقدارِ درستشان است نه حدس. و
`cost_centers` جدولِ RLSدار است: `UPDATE`ِ داخلِ مهاجرت یا صفر ردیف می‌بیند یا به
مستأجرِ اشتباه می‌رود.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0099"
down_revision: Union[str, None] = "0098"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "cost_centers",
        sa.Column("name2", sa.String(200), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("cost_centers", "name2")
