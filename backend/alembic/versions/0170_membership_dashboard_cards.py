"""کارت‌های داشبوردِ هر کاربر

Revision ID: 0170
Revises: 0169

## چه چیزی اضافه می‌شود

`memberships.dashboard_cards` — فهرستِ شناسه‌ی کارت‌هایی که کاربر برای باکسِ
«شروعِ کارِ تازه»ی داشبورد انتخاب کرده، به همان ترتیبِ نمایش. هر شناسه یا کلیدِ
صفحه است (`salesinvoice`) یا کلیدِ صفحه و تب (`inventory/products`).

## چرا روی `memberships` و نه `users`

کارت‌ها به ماژول‌های **یک کسب‌وکارِ مشخص** اشاره می‌کنند. حسابداری که در دو شرکت
عضو است، در شرکتی که ماژولِ انبار ندارد نباید کارتِ «رسید انبار» ببیند. همان
استدلالی که `permissions` را هم روی عضویت نشاند، نه روی کاربر.

## چرا nullable و بدونِ `server_default`

`NULL` یعنی «کاربر هنوز چیزی انتخاب نکرده» و همان شش کارتِ پیش‌فرض نشان داده
می‌شود؛ `[]` یعنی «کاربر همه را برداشته» و باکس خالی است. اگر پیش‌فرضِ ستون `[]`
بود، این دو حالت یکی می‌شدند و هیچ‌کس نمی‌توانست باکس را خالی نگه دارد — با هر بار
باز شدنِ داشبورد پیش‌فرض‌ها برمی‌گشتند.

## چرا `rls_disabled` این‌جا لازم نیست

این مهاجرت فقط `ALTER TABLE ... ADD COLUMN` است: هیچ ردیفی نمی‌خواند و نمی‌نویسد،
پس سیاستِ RLS نمی‌تواند بی‌صدا صفر ردیف نشانش بدهد. (`memberships` هم در
`GLOBAL_TABLES`ِ `app/tenancy.py` است و اصلاً سیاستِ RLS ندارد.)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0170"
down_revision: Union[str, None] = "0169"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "memberships",
        sa.Column("dashboard_cards", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("memberships", "dashboard_cards")
