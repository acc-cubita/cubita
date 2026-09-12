"""هزینه‌ی حمل جایی برای نشستن نداشت، پس موجودی ارزان‌تر از واقع ثبت می‌شد

Revision ID: 0131
Revises: 0130

## نقصی که بسته می‌شود

رسیدِ انبار هیچ فیلدی برای حمل نداشت. کرایه‌ای که برای آوردنِ کالا داده می‌شود
یا اصلاً ثبت نمی‌شد، یا به‌عنوان هزینه‌ی دوره به سود و زیانِ همان ماه می‌رفت.
هر دو یک نتیجه دارند:

    خریدِ ۱۰۰ عدد × ۵٬۰۰۰ = ۵۰۰٬۰۰۰   +   حملِ ۵۰٬۰۰۰

    ارزشِ موجودی در دفتر  = ۵۰۰٬۰۰۰      (باید ۵۵۰٬۰۰۰ باشد)
    بهای هر واحد          =    ۵٬۰۰۰      (باید ۵٬۵۰۰ باشد)

یعنی موجودی ۵۰٬۰۰۰ کمتر از واقع ارزش‌گذاری می‌شود، و لحظه‌ی فروش بهای
تمام‌شده به همان اندازه کم و **سود به همان اندازه زیاد** گزارش می‌شود. عددی که
هیچ ترازی به‌هم نمی‌خورد تا خبرش را بدهد.

## §۲۰ — «فی» و «فی تمام‌شده» دو چیزند

فصل صریح می‌گوید این دو نباید یکی شوند:

    Purchase Unit Rate  ≠  Inventory Landed Unit Cost

`unit_cost` روی ردیفِ رسید همان «فی» می‌ماند و دست نمی‌خورد. «فی تمام‌شده»
**ذخیره نمی‌شود** — از `unit_cost` و `freight_share` مشتق می‌شود (§۲۷: «مشتق
بهتر از ذخیره»). فقط سهمِ حملِ هر ردیف ذخیره می‌شود، چون نتیجه‌ی یک تسهیمِ
گِردشده است و بازمحاسبه‌اش لزوماً همان عدد را نمی‌دهد.

## §۲۵ §۲۶ — کالا، حمل، مالیات و عوارض مستقل می‌مانند

فصل هشدار می‌دهد: «ایجنت نباید فرض کند Inventory Cost = Price + Freight + VAT
در تمام شرایط.» پس چهار جزء جدا ذخیره می‌شوند و هرکدام مقصدِ خودش را دارد:

| جزء | مقصد |
|---|---|
| مبلغ حمل | بهای تمام‌شده‌ی ورودِ کالا |
| عوارضِ حمل | بهای تمام‌شده‌ی ورودِ کالا |
| مالیاتِ حمل | اعتبارِ مالیاتی — **نه** بهای کالا |
| مالیاتِ کالا | اعتبارِ مالیاتی — **نه** بهای کالا |

## `tax_rate` روی رسید — فقط برای رسیدِ مستقیم

رسیدی که به فاکتور گره خورده، مالیاتش را فاکتور شناخته و ثبتِ دوباره یعنی
اعتبارِ مالیاتی دو برابر شود (§۳۷). پس `tax_amount_snapshot` روی آن ردیف‌ها
سهمِ تسهیم‌شده‌ی مالیاتِ فاکتور است — **فقط برای چاپ و توضیحِ خالص (§۲۷)**، و
هرگز ثبت نمی‌شود.

## و یک واگرایی که راستی‌آزماییِ زنده پیدایش کرد

روی داده‌ی واقعی، رسیدی با همان اعدادِ فصل این را داد:

    «موجودی کالا» در دفتر  = ۱٬۴۵۰٬۰۰۰
    ارزشِ گزارشِ انبار      = ۱٬۴۵۰٬۰۵۰

۵۰ ریال اختلاف. ریشه‌اش حمل نیست، **دقتِ ستون** است: بهای تمام‌شده‌ی ردیفِ دوم
۹۲۵٬۰۰۰ ÷ ۱۵۰ = ۶٬۱۶۶٫۶۶… بود و `items.average_cost` و `stock_ledger.unit_cost`
هر دو `Numeric(18, 0)` — یعنی ریالِ صحیح. عدد به ۶٬۱۶۷ گِرد می‌شد و گزارش
۱۵۰ × ۶٬۱۶۷ را جمع می‌زد، در حالی که دفتر مبلغِ واقعی را داشت.

**این نقص از پیش بود** و به حمل ربطی ندارد: هر فاکتورِ خریدی که خالصش بر تعداد
بخش‌پذیر نباشد همین را می‌سازد (و تولید و برگشت هم همین فرمول را دارند). ولی
تسهیمِ حمل کسرِ اعشاری را از استثنا به قاعده تبدیل می‌کند، پس همین‌جا بسته
می‌شود: هر سه ستونِ بهای تمام‌شده به `Numeric(18, 4)` می‌روند.

چهار رقم اعشار اختلاف را از ۵۰ ریال به کسری از ریال می‌برد. **صفر نمی‌کند** —
در روشِ میانگینِ موزون که یک *بهای واحد* ذخیره می‌کند، `مقدار × میانگین` وقتی
میانگین گویا نیست هرگز دقیقاً برابرِ مبلغِ واقعی نمی‌شود. عرض‌دادنِ ستون‌ها
تنها کارِ بی‌ریسکی است که این‌جا می‌شود کرد؛ برابریِ دقیق نیازمندِ ذخیره‌ی
*مبلغ* به‌جای *بهای واحد* است، که تغییرِ مدلِ ارزش‌گذاری است نه یک ستون.

## پیش‌فرض‌ها هیچ رسیدی را تکان نمی‌دهند

همه‌ی ستون‌ها صفر (و مبنا `equal`) پیش‌فرض دارند، پس رسیدهای موجود دقیقاً
همان‌اند که بودند: بی‌حمل، بی‌مالیات، و فی تمام‌شده برابرِ فی.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0131"
down_revision: Union[str, None] = "0130"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: §۲۳ — «انواع دیگر را فعلاً فرض نکنیم». ویدیو فقط «به نسبت مساوی» را نشان
#: می‌دهد، پس تنها همان ساخته می‌شود. قید این‌جاست تا مبنایی که سرویسی برایش
#: وجود ندارد از در پشتی وارد پایگاه داده نشود.
FREIGHT_BASES = ("equal",)

#: ستون‌هایی که *بهای تمام‌شده‌ی واحد* را نگه می‌دارند و زنجیره‌ی ارزش‌گذاری
#: می‌خوانَدشان. `sales_invoice_lines.unit_price` و امثالش عمداً این‌جا نیستند:
#: آن‌ها قیمتِ واردشده‌ی کاربرند، نه نتیجه‌ی یک تقسیم.
_COST_COLUMNS = (
    ("items", "average_cost"),
    ("stock_ledger", "unit_cost"),
    ("stock_batches", "unit_cost"),
)


def upgrade() -> None:
    op.add_column(
        "warehouse_receipts",
        sa.Column("freight_amount", sa.Numeric(18, 0), server_default="0", nullable=False),
    )
    op.add_column(
        "warehouse_receipts",
        sa.Column("freight_tax", sa.Numeric(18, 0), server_default="0", nullable=False),
    )
    op.add_column(
        "warehouse_receipts",
        sa.Column("freight_duty", sa.Numeric(18, 0), server_default="0", nullable=False),
    )
    op.add_column(
        "warehouse_receipts",
        sa.Column("freight_basis", sa.String(20), server_default="equal", nullable=False),
    )
    op.add_column(
        "warehouse_receipts",
        sa.Column("tax_rate", sa.Numeric(5, 2), server_default="0", nullable=False),
    )
    op.create_check_constraint(
        "ck_warehouse_receipts_freight_basis",
        "warehouse_receipts",
        "freight_basis IN ({})".format(", ".join(f"'{b}'" for b in FREIGHT_BASES)),
    )

    #: **ترتیبِ ردیف‌ها بازیابی‌شدنی نبود.**
    #:
    #: `WarehouseReceipt.lines` با `order_by=id` مرتب می‌شد و `id` یک UUIDِ
    #: **تصادفی** است — یعنی ردیف‌ها به ترتیبِ ورودِ اپراتور برنمی‌گشتند و چاپِ
    #: رسید (§۴۱ §۴۲) هر بار می‌توانست ترتیبِ دیگری بدهد. با تسهیمِ حمل بدتر
    #: هم می‌شود: ته‌ماندهٔ گِردکردن روی «ردیفِ آخر» می‌نشیند، و «آخر» باید
    #: معنای ثابتی داشته باشد.
    #:
    #: همان الگوی `journal_lines.seq` (مهاجرت ۰۱۰۰). صفر یعنی «ردیفِ پیش از
    #: این مهاجرت»؛ ترتیبِ آن‌ها بازیابی‌شدنی نیست، پس `(seq, id)` مرتبشان
    #: می‌کند و رفتارشان دقیقاً همان قبل می‌ماند.
    op.add_column(
        "warehouse_receipt_lines",
        sa.Column("seq", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "warehouse_receipt_lines",
        sa.Column("freight_share", sa.Numeric(18, 0), server_default="0", nullable=False),
    )
    op.add_column(
        "warehouse_receipt_lines",
        sa.Column("tax_rate_snapshot", sa.Numeric(5, 2), server_default="0", nullable=False),
    )
    op.add_column(
        "warehouse_receipt_lines",
        sa.Column("tax_amount_snapshot", sa.Numeric(18, 0), server_default="0", nullable=False),
    )


    #: عرض‌دادنِ ستون‌های بهای تمام‌شده — بی‌اتلاف، و هیچ عددِ موجودی را عوض
    #: نمی‌کند (عددِ صحیح در `Numeric(18, 4)` همان عددِ صحیح است).
    for table, column in _COST_COLUMNS:
        op.alter_column(
            table, column, type_=sa.Numeric(18, 4), existing_type=sa.Numeric(18, 0)
        )


def downgrade() -> None:
    for table, column in _COST_COLUMNS:
        op.alter_column(
            table, column, type_=sa.Numeric(18, 0), existing_type=sa.Numeric(18, 4)
        )
    op.drop_column("warehouse_receipt_lines", "tax_amount_snapshot")
    op.drop_column("warehouse_receipt_lines", "tax_rate_snapshot")
    op.drop_column("warehouse_receipt_lines", "freight_share")
    op.drop_column("warehouse_receipt_lines", "seq")
    op.drop_constraint("ck_warehouse_receipts_freight_basis", "warehouse_receipts")
    op.drop_column("warehouse_receipts", "tax_rate")
    op.drop_column("warehouse_receipts", "freight_basis")
    op.drop_column("warehouse_receipts", "freight_duty")
    op.drop_column("warehouse_receipts", "freight_tax")
    op.drop_column("warehouse_receipts", "freight_amount")
