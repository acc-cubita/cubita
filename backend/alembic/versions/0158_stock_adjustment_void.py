"""تعدیلِ انبار ابطال‌پذیر شد — و حرکتش بالاخره به خودش گره خورد.

تعدیلِ انبار سندی است که **کارش اصلاحِ خطاست** و تا امروز تنها سندِ انباری بود که
خودش اصلاح نمی‌شد. تنها راهِ موجود، ثبتِ یک تعدیلِ معکوسِ دوم بود؛ عدد درست
درمی‌آمد ولی کاردکسِ کالا دو تعدیلِ *ظاهراً واقعی* نشان می‌داد و هیچ‌جا نمی‌گفت
دومی اشتباهِ اولی را می‌پوشاند.

## دو کار، نه یکی

**۱) سه ستونِ `VoidableMixin`** روی `stock_adjustments` — همان سه ستونی که هر سندِ
ابطال‌پذیرِ دیگری دارد.

**۲) پُرکردنِ `stock_ledger.source_id`** برای حرکاتِ `source_type='adjustment'`.
این نقصِ دومی است که هنگامِ ساختِ ابطال پیدا شد: `post_stock_adjustment` هیچ‌وقت
`source_id` نمی‌نوشت — **تنها سندِ انباری که این کار را نمی‌کرد** (انبارگردانی،
انتقال، رسید و خروج همه می‌نویسند). بی آن، ابطال حتی نمی‌توانست حرکتِ خودش را
پیدا کند، و `valuation._VOIDABLE` هم که سندِ باطل را از بازپخشِ میانگین کنار
می‌گذارد، به هیچ ردیفی نمی‌خورد.

## چرا `rls_disabled` این‌جا اجباری است

هر دو کار روی جدول‌های `FORCE ROW LEVEL SECURITY` است و مهاجرت هیچ `app.tenant_id`
ی ست نکرده:

* `UPDATE`/`SELECT`ِ backfill **بی‌صدا صفر ردیف** می‌دید و مهاجرت موفق گزارش می‌شد.
* `ADD COLUMN … REFERENCES users(id)` روی جدولی که **ردیف دارد** اعتبارسنجیِ کلیدِ
  خارجی می‌کند و روی PG 14 با `invalid input syntax for type uuid: ""` می‌افتد —
  همان چیزی که مهاجرتِ ۰۱۵۷ درست پیش از استقرار گرفتارش شد. دو طرفِ کلید هر دو باید
  باز باشند.

## تطبیقِ backfill — و چرا قطعی است

کلید: (مستأجر، کالا، انبار، تاریخ، مقدار). روی دادهٔ تولید هر ۱۱ ردیف در هر دو طرف
**یکتا**ست (بررسی شد: صفر گروهِ تکراری). ولی برای اینکه در هر دادهٔ دیگری هم قطعی
بماند، دو طرف با `row_number()` روی همان کلید جفت می‌شوند: دو تعدیلِ کاملاً یکسانِ
هم‌روز هم به ترتیبِ ثبت به دو حرکتِ هم‌ترتیب می‌خورند، نه اینکه هر دو به یکی بروند.

ردیفی که جفت پیدا نکند `NULL` می‌ماند و مهاجرت **نمی‌افتد** — ولی شمارشش چاپ
می‌شود. سرویسِ ابطال چنین تعدیلی را ۴۰۹ می‌کند، چون ابطالِ بی‌حرکت یعنی دفترِ
انبار و حسابداری از هم جدا شوند.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.migration_utils import rls_disabled

revision: str = "0158"
down_revision: Union[str, None] = "0157"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_BACKFILL = """
WITH led AS (
    SELECT id,
           row_number() OVER (
               PARTITION BY tenant_id, item_id, warehouse_id, entry_date, qty
               ORDER BY seq
           ) AS rn,
           tenant_id, item_id, warehouse_id, entry_date, qty
    FROM stock_ledger
    WHERE source_type = 'adjustment' AND source_id IS NULL
),
adj AS (
    SELECT id,
           row_number() OVER (
               PARTITION BY tenant_id, item_id, warehouse_id, adjustment_date, qty_diff
               ORDER BY created_at, id
           ) AS rn,
           tenant_id, item_id, warehouse_id, adjustment_date, qty_diff
    FROM stock_adjustments
)
UPDATE stock_ledger sl
SET source_id = adj.id
FROM led JOIN adj
      ON adj.tenant_id = led.tenant_id
     AND adj.item_id = led.item_id
     AND adj.warehouse_id = led.warehouse_id
     AND adj.adjustment_date = led.entry_date
     AND adj.qty_diff = led.qty
     AND adj.rn = led.rn
WHERE sl.id = led.id
"""

_LEFTOVER = """
SELECT count(*) FROM stock_ledger
WHERE source_type = 'adjustment' AND source_id IS NULL
"""


def upgrade() -> None:
    conn = op.get_bind()

    #: `users` هم باز می‌شود — سمتِ دیگرِ کلیدِ خارجی هم اعتبارسنجی می‌شود.
    with rls_disabled(conn, ["stock_adjustments", "stock_ledger", "users"]):
        op.add_column(
            "stock_adjustments",
            sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index(
            "ix_stock_adjustments_voided_at", "stock_adjustments", ["voided_at"]
        )
        op.add_column(
            "stock_adjustments",
            sa.Column("void_reason", sa.Text(), server_default="", nullable=False),
        )
        op.add_column(
            "stock_adjustments",
            sa.Column(
                "voided_by_id",
                UUID(as_uuid=True),
                sa.ForeignKey("users.id"),
                nullable=True,
            ),
        )

        matched = conn.execute(sa.text(_BACKFILL)).rowcount
        leftover = conn.execute(sa.text(_LEFTOVER)).scalar_one()

    print(f"[0158] حرکتِ تعدیل که به سندش گره خورد: {matched}")
    if leftover:
        print(f"[0158] *** {leftover} حرکتِ تعدیل جفت پیدا نکرد — این‌ها ابطال‌پذیر نیستند ***")


def downgrade() -> None:
    conn = op.get_bind()
    with rls_disabled(conn, ["stock_adjustments", "stock_ledger", "users"]):
        #: `source_id` عمداً برنمی‌گردد: پُرکردنش داده‌ی درست است، نه بدهیِ اسکیما.
        #: پاک‌کردنش فقط همان اطلاعاتِ بازیافته را دور می‌ریخت.
        op.drop_column("stock_adjustments", "voided_by_id")
        op.drop_column("stock_adjustments", "void_reason")
        op.drop_index("ix_stock_adjustments_voided_at", table_name="stock_adjustments")
        op.drop_column("stock_adjustments", "voided_at")
