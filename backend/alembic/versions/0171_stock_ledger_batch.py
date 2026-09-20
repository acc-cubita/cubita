"""مقدارِ بچ از دفترِ انبار مشتق می‌شود

Revision ID: 0171
Revises: 0169

## چه چیزی اضافه می‌شود

دو ستون روی `stock_ledger`:

* `batch_id` — کدام بارِ ورودی این حرکت را ساخت یا مصرف کرد.
* `source_line_id` — کدام **ردیفِ** سند. `source_id` فقط به سند اشاره می‌کند.

## چرا لازم شد

`stock_batches.qty` ادعا می‌کرد «مانده‌ی سالمِ این بار» است، ولی هیچ فروشی، هیچ
خروجی و هیچ انتقالی کمش نمی‌کرد — فقط تعدیلِ دستی، برگشت از خرید و ابطال. یعنی
بارِ ۱۰۰۰تایی که تمامش فروخته شده بود هنوز ۱۰۰۰ نشان می‌داد.

راهِ درست ساختنِ یک دفترِ حرکتِ دوم نبود؛ `stock_ledger` **خودش** دفترِ حرکت است.
یک ستونِ هویت کافی است تا مانده‌ی بار همان‌طور مشتق شود که موجودیِ کالا از روزِ
اول مشتق می‌شده: `SUM(qty)`.

## `batch_id` فقط هویت است

هیچ‌وقت بهای بچ در `unit_cost`ِ ردیفِ خروج نمی‌نشیند. میانگینِ موزون **سراسریِ
کالا**ست و `app/services/valuation.py` بچ نمی‌شناسد؛ نوشتنِ بهای بار در این ستون
بازپخشِ ارزش‌گذاری را بی‌صدا خراب می‌کند. به همین دلیل `batch_id` عمداً در
`_COLUMNS`ِ آن ماژول نیست و یک تست همین را قفل می‌کند.

## چرا `source_line_id` از همین اول

ردیفِ ۱۰تاییِ یک خروج که بینِ دو بار تقسیم می‌شود دو ردیفِ دفتر می‌شود. سندی که
دو ردیفِ یک کالا در یک انبار دارد، بی این ستون **برگشت‌ناپذیر مبهم** می‌شود:
معلوم نیست کدام ردیف از کدام بار خورد. الان هزینه‌اش یک ستون است؛ بعداً یک
`ALTER` روی پرترددترین جدولِ سیستم.

## چرا `rls_disabled` این‌جا لازم است

دو دلیلِ جدا، و هر دو مستند در `app/migration_utils.py`:

۱. `batch_id` کلیدِ خارجی دارد و `stock_ledger` **پر از ردیف** است. اسکنِ
   اعتبارسنجیِ Postgres مشمولِ سیاستِ RLS است و روی PG14 (همان که تولید دارد)
   با `invalid input syntax for type uuid: ""` می‌ترکد.
۲. پرکردنِ داده‌ی پایین ردیف می‌خواند و می‌نویسد؛ بی این، بی‌صدا صفر ردیف را
   عوض می‌کرد و مهاجرت موفق گزارش می‌داد.

## چرا پرکردن این‌قدر محتاط است

فقط جایی برچسب می‌خورد که **ابهام صفر** باشد: ردیفِ ورودیِ خریدی یا رسیدی که
برای آن `(source_id, item_id)` دقیقاً یک ردیفِ دفتر و دقیقاً یک بار وجود دارد.

فاکتوری با دو ردیفِ یک کالا کنار گذاشته می‌شود. بازسازیِ ترتیبِ `P{n}-{idx}` از
روی `seq` وسوسه‌انگیز است و **ممنوع**: امروز حلقه‌ی ساختِ بچ و حلقه‌ی ساختِ حرکت
اتفاقی هم‌ترتیب‌اند، ولی این یک تصادفِ پیاده‌سازی است. مهاجرتی که به آن تکیه کند
غلط است به شکلی که بعداً هیچ‌کس نمی‌تواند تشخیصش دهد.

خروجی‌ها اصلاً برچسب نمی‌خورند — هیچ‌وقت بچ نداشته‌اند و حدس‌زدنشان یعنی جعلِ
تاریخچه. باری که ردیفِ برچسب‌خورده ندارد در API با `qty_source='legacy'` و
عددِ قدیمی‌اش نشان داده می‌شود، نه با صفرِ مشتق‌شده. «گزارش، نه گارد».
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.migration_utils import rls_disabled

revision: str = "0171"
down_revision: Union[str, None] = "0169"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


#: سندهایی که بارِ ورودی می‌سازند — تنها جایی که برچسبِ خودکار بی‌ابهام است.
INBOUND_SOURCES = ("purchase_invoice", "warehouse_receipt")

#: هر حرکتِ ورودیِ بی‌ابهام به بارِ هم‌سندش وصل می‌شود. `HAVING count(*) = 1` در هر
#: دو طرف یعنی اگر کوچک‌ترین ابهامی باشد، آن ردیف دست‌نخورده `NULL` می‌ماند.
#: `count(*) OVER (PARTITION BY …)` و نه `GROUP BY … HAVING`: شناسه UUID است و
#: Postgres برای UUID تابعِ `MIN` ندارد. به‌علاوه این شکل نیت را مستقیم‌تر
#: می‌گوید — «ردیفی که در گروهِ خودش تنهاست» — به‌جای «کمینه‌ی گروهِ تک‌عضوی».
BACKFILL = f"""
WITH moves AS (
    SELECT id AS move_id, tenant_id, source_id, item_id FROM (
        SELECT id, tenant_id, source_id, item_id,
               count(*) OVER (PARTITION BY tenant_id, source_id, item_id) AS peers
        FROM stock_ledger
        WHERE source_type IN {INBOUND_SOURCES}
          AND source_id IS NOT NULL
          AND qty > 0
          AND batch_id IS NULL
    ) t WHERE peers = 1
), batches AS (
    SELECT id AS batch_id, tenant_id, source_id, item_id FROM (
        SELECT id, tenant_id, source_id, item_id,
               count(*) OVER (PARTITION BY tenant_id, source_id, item_id) AS peers
        FROM stock_batches
        WHERE source_type IN {INBOUND_SOURCES}
          AND source_id IS NOT NULL
    ) t WHERE peers = 1
)
UPDATE stock_ledger sl
SET batch_id = b.batch_id
FROM moves m
JOIN batches b
  ON  b.tenant_id = m.tenant_id
  AND b.source_id = m.source_id
  AND b.item_id   = m.item_id
WHERE sl.id = m.move_id
"""


def upgrade() -> None:
    conn = op.get_bind()

    with rls_disabled(conn, ["stock_ledger", "stock_batches"]):
        op.add_column(
            "stock_ledger",
            sa.Column(
                "batch_id",
                UUID(as_uuid=True),
                #: RESTRICT و نه CASCADE: حذفِ باری که در دفتر گردش دارد یعنی
                #: پاک‌کردنِ تاریخچه‌ی حرکتِ انبار. روتر پیش از رسیدن به این‌جا
                #: پیامِ فارسی می‌دهد؛ این آخرین خطِ دفاع است.
                sa.ForeignKey("stock_batches.id", ondelete="RESTRICT"),
                nullable=True,
            ),
        )
        #: بی FK و عمداً: به ردیفِ سندهای مختلف اشاره می‌کند (فاکتور، حواله،
        #: رسید، ...) — دقیقاً مثلِ `source_id` که همین حالا چندریختی است.
        op.add_column(
            "stock_ledger",
            sa.Column("source_line_id", UUID(as_uuid=True), nullable=True),
        )
        conn.execute(sa.text(BACKFILL))

    #: ایندکسِ **جزئی**: اکثریتِ قاطعِ ردیف‌ها `batch_id` ندارند و نباید جا بگیرند.
    #: پرسشِ همیشگی «مانده‌ی این بار چند است؟» دقیقاً همین شکل را می‌خواهد.
    op.create_index(
        "ix_stock_ledger_batch",
        "stock_ledger",
        ["tenant_id", "batch_id"],
        postgresql_where=sa.text("batch_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_stock_ledger_batch", table_name="stock_ledger")
    op.drop_column("stock_ledger", "source_line_id")
    op.drop_column("stock_ledger", "batch_id")
