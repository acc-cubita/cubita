"""قیمتِ مصرف‌کننده و اشانتیون

Revision ID: 0175
Revises: 0174

## چه چیزی اضافه می‌شود

**روی `items` چهار ستون:**

* `has_consumer_price` — پیش‌فرض `false`. §۱۷ صریح است که این قابلیت برای همه‌ی
  کالاها وجود ندارد: پیچ و مهره قیمتِ مصرف‌کننده‌ی چاپی ندارد.
* `printed_consumer_price` / `suggested_retail_price` / `maximum_retail_price` —
  هر سه **تهی‌پذیر**، چون §۱۸ می‌خواهد از هم تفکیک شوند و §۲۸ می‌خواهد هیچ‌کدام
  اجباری نباشند.

**روی `stock_batches` دو ستون:** `printed_consumer_price` و
`maximum_retail_price`.

**روی `purchase_invoice_lines` یک ستون:** `bonus_qty`.

**روی `marketplace_listings` دو ستون:** `bonus_threshold_qty` و `bonus_qty`
(«۱۰ کارتن بخر، ۱ کارتن رایگان» — §۲۵).

## چرا `suggested_retail_price` روی بار اضافه **نشد**

چون از قبل هست. `stock_batches.consumer_price` در مهاجرتِ ۰۰۷۰ دقیقاً همین
تعریف را گرفته: «قیمتِ مصرف‌کننده (فروشِ پیشنهادی)». افزودنِ ستونی به همان
معنا یعنی دو نمای یک داده که روزی با هم اختلاف پیدا می‌کنند — همان چیزی که کلِ
این مجموعه مهاجرت برای رفعش نوشته شد.

پس نگاشت صریح است و در مدل هم مستند می‌شود:

    consumer_price            = قیمتِ پیشنهادی (از قبل)
    printed_consumer_price    = آن‌چه واقعاً روی بسته چاپ شده  ← تازه
    maximum_retail_price      = سقفِ مجازِ فروش                ← تازه

`items` هیچ‌کدام را نداشت، پس هر سه آن‌جا تازه‌اند.

## چرا اشانتیون ستونِ «قیمتِ صفر» نمی‌گیرد

وسوسه‌ی طبیعی این است که کارتنِ رایگان یک **ردیفِ جدا با قیمتِ صفر** شود. غلط
است: میانگینِ موزون از `stock_ledger` بازپخش می‌شود و ردیفِ صفرقیمت میانگین را
به‌سمتِ پایین می‌کشد، بی آنکه هیچ‌جا نوشته شده باشد چرا.

راهِ درست همان چیزی است که خودِ §۲۵ می‌خواهد: تعداد **۱۱** ثبت می‌شود با تخفیفی
برابرِ بهای **۱** واحد. آن‌وقت `post_purchase_invoice` بی هیچ تغییری
`total_paid / 11` را حساب می‌کند و `effective_unit_cost`ِ §۲۵ خودبه‌خود درست
درمی‌آید. `bonus_qty` فقط **یادداشتِ گزارشی** است: می‌گوید از آن ۱۱ تا، ۱ تا
رایگان بوده. هیچ محاسبه‌ای به آن وابسته نیست.

## چرا `rls_disabled` لازم نیست

هیچ‌کدام از این ستون‌ها کلیدِ خارجی ندارند، و `ALTER TABLE ... ADD COLUMN` از
سیاستِ RLS رد می‌شود. گارد فقط برای خواندن/نوشتنِ داده در مهاجرت لازم است —
شرحِ کامل در `app/migration_utils.py`.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0175"
down_revision: Union[str, None] = "0174"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: مبلغِ ریالِ صحیح — همان دقتی که هر قیمتِ دیگری در این مخزن دارد.
_MONEY = sa.Numeric(18, 0)
_QTY = sa.Numeric(18, 3)


def upgrade() -> None:
    op.add_column(
        "items", sa.Column("has_consumer_price", sa.Boolean(), server_default="false", nullable=False)
    )
    #: تهی‌پذیر و نه «صفر = نامشخص»: §۳۰ می‌گوید فیلدِ بی‌مقدار اصلاً نباید نمایش
    #: داده شود، و صفر یک مقدارِ معتبرِ دیگر است (کالای رایگان).
    for column in ("printed_consumer_price", "suggested_retail_price", "maximum_retail_price"):
        op.add_column("items", sa.Column(column, _MONEY, nullable=True))

    #: `suggested` روی بار از قبل هست (`consumer_price`، مهاجرتِ ۰۰۷۰).
    for column in ("printed_consumer_price", "maximum_retail_price"):
        op.add_column("stock_batches", sa.Column(column, _MONEY, nullable=True))

    #: یادداشتِ گزارشی، نه ورودیِ محاسبه — دلیلش در داک‌استرینگِ بالا.
    op.add_column(
        "purchase_invoice_lines",
        sa.Column("bonus_qty", _QTY, server_default="0", nullable=False),
    )

    #: پیشنهادِ اشانتیونِ پخش‌کننده (§۲۵). صفر = بدونِ اشانتیون، یعنی رفتارِ امروز.
    op.add_column(
        "marketplace_listings",
        sa.Column("bonus_threshold_qty", _QTY, server_default="0", nullable=False),
    )
    op.add_column(
        "marketplace_listings",
        sa.Column("bonus_qty", _QTY, server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("marketplace_listings", "bonus_qty")
    op.drop_column("marketplace_listings", "bonus_threshold_qty")
    op.drop_column("purchase_invoice_lines", "bonus_qty")
    for column in ("maximum_retail_price", "printed_consumer_price"):
        op.drop_column("stock_batches", column)
    for column in ("maximum_retail_price", "suggested_retail_price", "printed_consumer_price"):
        op.drop_column("items", column)
    op.drop_column("items", "has_consumer_price")
