"""صنفِ کسب‌وکار، و اصنافی که هر پخش‌کننده به آن‌ها جنس می‌دهد

Revision ID: 0168
Revises: 0167

## چه چیزی اضافه می‌شود

دو ستون، برای وصل‌کردنِ دو سرِ بازارِ پخش:

* `tenants.trade` — «این کسب‌وکار چه می‌فروشد» (بستنی‌فروشی، لوازم یدکی خودرو، …).
  فهرستِ ثابتش در `app/services/trades.py` است.
* `marketplace_settings.target_trades` — اصنافی که این پخش‌کننده هدف گرفته.

## چرا `trade` مقدارِ پیش‌فرض ندارد

`NULL` یعنی «هنوز اعلام نکرده»، و این با «هیچ‌کدام» فرق دارد. همه‌ی حساب‌های
موجود بعد از این مهاجرت `NULL` می‌مانند، و `list_distributors_for_retailer`
برایشان **هیچ چیزی را فیلتر نمی‌کند** — یعنی بازارشان دقیقاً مثلِ دیروز است.
اگر این‌جا از `industry` حدس می‌زدیم («خرده‌فروشی» → کدام صنف؟) یا پیش‌فرضی
می‌گذاشتیم، آن دو حالت یکی می‌شدند و فروشگاهی که هرگز صنفش را نگفته، بی‌صدا
نیمی از پخش‌کننده‌ها را از دست می‌داد.

به همان دلیل `target_trades` پیش‌فرضِ `[]` می‌گیرد که یعنی «بدونِ محدودیت»: هیچ
پخش‌کننده‌ی فعالی با این ارتقا از بازار غیب نمی‌شود.

## چرا `rls_disabled` این‌جا لازم نیست

`tenants` زیرِ FORCE RLS است، ولی این مهاجرت هیچ ردیفی نمی‌خواند و نمی‌نویسد —
فقط `ALTER TABLE ... ADD COLUMN` است و DDL از سیاستِ RLS رد می‌شود. گارد جایی
لازم است که `SELECT`/`INSERT`/`UPDATE` روی جدولِ RLS‌دار باشد (مثلِ ۰۱۶۷).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0168"
down_revision: Union[str, None] = "0167"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("trade", sa.String(40), nullable=True))
    op.add_column(
        "marketplace_settings",
        sa.Column("target_trades", postgresql.JSONB(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("marketplace_settings", "target_trades")
    op.drop_column("tenants", "trade")
