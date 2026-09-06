"""کدِ مرکز هزینه یکتا شود

Revision ID: 0098
Revises: 0097

## چه چیزی را می‌بندد

`cost_centers.code` هیچ قیدی نداشت، پس دو مرکز با کدِ `1001` ممکن بود. کدی که
تکرار می‌شود چیزی را شناسایی نمی‌کند — همان کاری که قرار بود بکند.

## چرا **جزئی** است و نه یکتاییِ ساده

کد در کوبیتا **اختیاری** است و این عمدی می‌ماند: مرکزهای کوچک (یک واحد سازمانی،
یک قرارداد) اغلب کد ندارند و اجباری‌کردنش کاربر را به ساختنِ کدِ الکی وامی‌دارد.
ولی اگر قید ساده بود، دومین مرکزِ بی‌کد به اولی گیر می‌کرد چون `''` هم یک مقدار
است. پس شرطِ `code <> ''` روی ایندکس می‌نشیند: بی‌کدها آزادند، کددارها یکتا.

## چرا `tenant_id` در کلید هست

مستأجرها کدینگِ مستقل دارند؛ یکتاییِ سراسری یعنی کدِ یک شرکت جلوی شرکتِ دیگر را
بگیرد. همان الگوی `uq_sales_invoices_tenant_number`.

## چرا backfill/dedup نیست

هر دو پایگاه‌داده پیش از این مهاجرت بررسی شدند — محلی و production هر دو **صفر**
ردیفِ `cost_centers` دارند، پس چیزی برای نرمال‌کردن نیست. و اگر بود هم داخلِ
مهاجرت انجام نمی‌شد: `cost_centers` جدولِ RLSدار است و `UPDATE`ِ داخلِ مهاجرت یا
صفر ردیف می‌گیرد یا به مستأجرِ اشتباه می‌رود. در آن حالت راهِ درست این است که
مهاجرت شکست بخورد و آدم تصمیم بگیرد، نه اینکه کدِ کسی بی‌صدا عوض شود.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0098"
down_revision: Union[str, None] = "0097"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "uq_cost_centers_tenant_code",
        "cost_centers",
        ["tenant_id", "code"],
        unique=True,
        postgresql_where=sa.text("code <> ''"),
    )


def downgrade() -> None:
    op.drop_index("uq_cost_centers_tenant_code", table_name="cost_centers")
