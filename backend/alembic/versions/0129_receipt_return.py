"""برگشت، کالا را در انبارِ اشتباه دنبال می‌کرد

Revision ID: 0129
Revises: 0128

## نقصِ زنده‌ای که ثابت شد

از مهاجرتِ ۰۱۲۷ به بعد، فاکتورِ خرید `warehouse_id` ندارد — کالا با رسیدِ انبار
وارد می‌شود. ولی `post_purchase_return` هنوز موجودی را در
`invoice.warehouse_id` می‌جست:

    خریدِ ۱۰۰ عدد → رسیدِ ۱۰۰ عدد به انبار اصلی → برگشتِ ۲۰ عدد
    ⛔ «موجودی «لیوان» برای این میزان برگشت کافی نیست (موجود: ۰)»

کالا در انبار بود. یعنی روی گردشِ رسیدِ انبار، برگشت از خرید **اصلاً کار
نمی‌کرد** — و پیامِ خطا هم گمراه‌کننده بود.

## درمان: لنگرِ دوم، نه جدولِ دوم

فصل می‌پرسد «Entity دوم بسازیم؟» و خودش محدودش می‌کند: «نباید کورکورانه Entity
دوم ساخته شود» و «Keep commercial and physical return distinguishable **even if
Cubita intentionally combines them in one workflow**».

`PurchaseReturn` همین حالا هر دو نیمه را انجام می‌دهد (بدهیِ تأمین‌کننده را
بدهکار می‌کند **و** موجودی را کم می‌کند). ساختنِ `WarehouseReceiptReturn` کنارش
یعنی دو سند یک بدهی را برگردانند — همان دوباره‌ثبتی که فصلِ پیش ازش هشدار
می‌داد.

پس همان سند **لنگرِ دوم** می‌گیرد:

    PurchaseInvoiceLine   ──┐
                            ├──→  PurchaseReturnLine
    WarehouseReceiptLine  ──┘

و «باقیمانده‌ی قابلِ برگشت» مثل همیشه **مشتق** می‌ماند: مقدارِ رسید منهای
برگشت‌های معتبر. هیچ شمارنده‌ی ذخیره‌شده‌ای اضافه نمی‌شود.

## دو مبلغ که نباید یکی شوند

فصل صریح است: ارزشِ موجودیِ کالای خارج‌شده لزوماً همان مبلغی نیست که با
تأمین‌کننده توافق شده.

    Inventory Value   =  ۱۰۰٬۰۰۰      (بهای تمام‌شده‌ی ورود)
    Agreed Return     =   ۹۵٬۰۰۰      (توافقِ تجاری)

و همان‌جا می‌گوید **حسابِ اختلاف را اختراع نکن** («DO NOT invent a difference
account»). پس هر دو عدد ذخیره می‌شوند و قابلِ تفکیک‌اند، ولی تا وقتی سیاستِ
حسابداریِ اختلاف تعریف نشده، سندی که این دو در آن برابر نیستند **ثبت نمی‌شود**
و کاربر پیامِ روشن می‌گیرد. پیش‌فرضِ مبلغِ توافقی همان ارزشِ موجودی است، پس
گردشِ عادی دست‌نخورده کار می‌کند.

## «تحویل‌گیرنده» با «تحویل‌دهنده» یکی نیست

در رسید، کالا را شرکت **تحویل می‌گیرد**. در برگشت، کالا از شرکت **خارج** می‌شود
و کسی آن را تحویل می‌گیرد. فصل می‌گوید این دو را در یک فیلدِ مبهم گم نکنیم.

## نوعِ برگشت — چهار تا، نه پنج تا

فرمِ برگشت «موجودی اول دوره» را **ندارد**، و فصل هشدار می‌دهد فهرستِ نوع‌های
رسید را کورکورانه کپی نکنیم. پس چهار نوع، و همین.

## ترتیبِ ردیف‌ها

`PurchaseReturnLine` هم با `id` مرتب می‌شد و `id` یک UUIDِ تصادفی است — همان
نقصی که در ۰۱۲۸ برای ردیف‌های رسید بسته شد. چاپِ برگشت (که فصل ستون «ردیف»
دارد) بدونِ ترتیبِ پایدار هر بار می‌توانست چیزِ دیگری بدهد.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.migration_utils import rls_disabled

revision: str = "0129"
down_revision: Union[str, None] = "0128"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: چهار نوع — «موجودی اول دوره» عمداً نیست (فرمِ برگشت ندارَدش).
RETURN_TYPES = ("purchase_domestic", "purchase_import", "production", "other")

#: افزودنِ کلیدِ خارجی زیرِ `FORCE ROW LEVEL SECURITY` یک اسکنِ اعتبارسنجی راه
#: می‌اندازد که `app.tenant_id` را می‌خواند — و آن وسطِ مهاجرت وجود ندارد. هر دو
#: سرِ رابطه باید در فهرست باشند (درسِ ۰۱۰۹ و ۰۱۲۰).
_FK_TABLES = (
    "purchase_returns",
    "purchase_return_lines",
    "warehouse_receipts",
    "warehouse_receipt_lines",
    "warehouses",
    "contacts",
)


def upgrade() -> None:
    conn = op.get_bind()

    op.add_column("purchase_returns", sa.Column("warehouse_receipt_id", UUID(as_uuid=True), nullable=True))
    op.add_column("purchase_returns", sa.Column("warehouse_id", UUID(as_uuid=True), nullable=True))
    #: «تحویل‌گیرنده» — کسی که کالای خارج‌شده را می‌گیرد. با `contact_id`ِ فاکتور
    #: (تأمین‌کننده) یکی نیست و نباید در یک فیلد گم شوند.
    op.add_column("purchase_returns", sa.Column("receiver_id", UUID(as_uuid=True), nullable=True))
    op.add_column(
        "purchase_returns",
        sa.Column("return_type", sa.String(20), server_default="purchase_domestic", nullable=False),
    )
    op.add_column("purchase_returns", sa.Column("currency_code", sa.String(3), nullable=True))
    op.add_column(
        "purchase_returns",
        sa.Column("exchange_rate", sa.Numeric(18, 4), server_default="1", nullable=False),
    )
    op.create_index(
        "ix_purchase_returns_warehouse_receipt_id", "purchase_returns", ["warehouse_receipt_id"]
    )

    op.add_column(
        "purchase_return_lines", sa.Column("seq", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column(
        "purchase_return_lines",
        sa.Column("warehouse_receipt_line_id", UUID(as_uuid=True), nullable=True),
    )
    #: سهمِ حملِ برگشتی — جزءِ بهای تمام‌شده‌ی کالایی که از انبار خارج می‌شود.
    #: جدا از `unit_cost` می‌ماند تا §۲۰ («فی» ≠ «فی تمام‌شده») حفظ شود.
    op.add_column(
        "purchase_return_lines",
        sa.Column("freight_share", sa.Numeric(18, 0), server_default="0", nullable=False),
    )
    #: **مبالغ مرجوعی توافقی** — مستقل از ارزشِ موجودی، به‌خواستِ صریحِ فصل.
    op.add_column(
        "purchase_return_lines",
        sa.Column("agreed_unit_value", sa.Numeric(18, 4), server_default="0", nullable=False),
    )
    op.add_column(
        "purchase_return_lines",
        sa.Column("agreed_amount", sa.Numeric(18, 0), server_default="0", nullable=False),
    )
    #: مالیاتِ همین ردیف — تا «مالیات و عوارض»ِ چاپ از اجزای خودش توضیح‌پذیر باشد.
    op.add_column(
        "purchase_return_lines",
        sa.Column("tax_rate_snapshot", sa.Numeric(5, 2), server_default="0", nullable=False),
    )
    op.add_column(
        "purchase_return_lines",
        sa.Column("tax_amount_snapshot", sa.Numeric(18, 0), server_default="0", nullable=False),
    )
    op.create_index(
        "ix_purchase_return_lines_receipt_line",
        "purchase_return_lines",
        ["warehouse_receipt_line_id"],
    )

    op.create_check_constraint(
        "ck_purchase_returns_return_type",
        "purchase_returns",
        "return_type IN ({})".format(", ".join(f"'{t}'" for t in RETURN_TYPES)),
    )

    with rls_disabled(conn, _FK_TABLES):
        op.create_foreign_key(
            "fk_purchase_returns_warehouse_receipt",
            "purchase_returns",
            "warehouse_receipts",
            ["warehouse_receipt_id"],
            ["id"],
        )
        op.create_foreign_key(
            "fk_purchase_returns_warehouse", "purchase_returns", "warehouses", ["warehouse_id"], ["id"]
        )
        op.create_foreign_key(
            "fk_purchase_returns_receiver", "purchase_returns", "contacts", ["receiver_id"], ["id"]
        )
        op.create_foreign_key(
            "fk_purchase_return_lines_receipt_line",
            "purchase_return_lines",
            "warehouse_receipt_lines",
            ["warehouse_receipt_line_id"],
            ["id"],
        )

    #: **`purchase_invoice_id` اجباری بود.** برگشتی که به رسید لنگر می‌زند
    #: می‌تواند هیچ فاکتوری نداشته باشد (رسیدِ مستقیم) — همان کاری که ۰۱۲۶ با
    #: خودِ رسید کرد.
    op.alter_column(
        "purchase_returns", "purchase_invoice_id", existing_type=UUID(as_uuid=True), nullable=True
    )


def downgrade() -> None:
    op.alter_column(
        "purchase_returns", "purchase_invoice_id", existing_type=UUID(as_uuid=True), nullable=False
    )
    op.drop_constraint("fk_purchase_return_lines_receipt_line", "purchase_return_lines")
    op.drop_constraint("fk_purchase_returns_receiver", "purchase_returns")
    op.drop_constraint("fk_purchase_returns_warehouse", "purchase_returns")
    op.drop_constraint("fk_purchase_returns_warehouse_receipt", "purchase_returns")
    op.drop_constraint("ck_purchase_returns_return_type", "purchase_returns")
    op.drop_index("ix_purchase_return_lines_receipt_line", "purchase_return_lines")
    for column in (
        "tax_amount_snapshot",
        "tax_rate_snapshot",
        "agreed_amount",
        "agreed_unit_value",
        "freight_share",
        "warehouse_receipt_line_id",
        "seq",
    ):
        op.drop_column("purchase_return_lines", column)
    op.drop_index("ix_purchase_returns_warehouse_receipt_id", "purchase_returns")
    for column in (
        "exchange_rate",
        "currency_code",
        "return_type",
        "receiver_id",
        "warehouse_id",
        "warehouse_receipt_id",
    ):
        op.drop_column("purchase_returns", column)
