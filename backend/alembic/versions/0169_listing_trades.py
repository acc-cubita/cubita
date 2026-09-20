"""اصنافِ اضافه‌ی یک قلمِ کاتالوگ

Revision ID: 0169
Revises: 0168

## چه چیزی اضافه می‌شود

`marketplace_listings.extra_trades` — اصنافی که **این قلم** علاوه بر اصنافِ کلیِ
پخش‌کننده (`marketplace_settings.target_trades`، مهاجرتِ ۰۱۶۸) به آن‌ها هم نشان
داده می‌شود.

## چرا لازم شد

هدف‌گیریِ ۰۱۶۸ دانه‌ی کلِ کسب‌وکار را دارد: یا همه‌ی کاتالوگ برای یک صنف باز است یا
هیچ‌کدام. تولیدیِ پوشاکی که «لباس کار» هم می‌سازد، برای رساندنش به یدکی‌فروشی مجبور
بود یدکی را به اصنافِ کلی‌اش اضافه کند — و آن‌وقت یدکی‌فروش کلِ پیراهن و مانتو را هم
می‌دید.

## چرا پیش‌فرض `[]` است

`[]` یعنی «اضافه‌ای ندارد»، پس هیچ لیستینگِ موجودی رفتارش عوض نمی‌شود: مخاطبش دقیقاً
همان چیزی می‌ماند که اصنافِ کلیِ پخش‌کننده می‌گوید.

## چرا `rls_disabled` این‌جا لازم نیست

`marketplace_listings` جدولِ **سراسری** است (در `GLOBAL_TABLES`ِ `app/tenancy.py`) و
اصلاً سیاستِ RLS ندارد. به‌علاوه این مهاجرت فقط `ALTER TABLE ... ADD COLUMN` است و
هیچ ردیفی نمی‌خواند و نمی‌نویسد.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0169"
down_revision: Union[str, None] = "0168"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "marketplace_listings",
        sa.Column("extra_trades", postgresql.JSONB(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("marketplace_listings", "extra_trades")
