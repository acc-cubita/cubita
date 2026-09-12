"""رسید انبار بدونِ فاکتورِ خرید ممکن نبود

Revision ID: 0129
Revises: 0128

## چه چیزی غلط بود

`warehouse_receipts.purchase_invoice_id` **اجباری** بود و تنها راهِ ساختِ رسید
`POST /api/purchase-invoices/{id}/warehouse-receipts` بود. یعنی خریدی که
فاکتورش بعداً می‌آید — یا اصلاً نمی‌آید — هیچ راهی برای ورودِ کالا نداشت.

فصل صریح است: در گردشِ نمایش‌داده‌شده، رسیدِ خریدِ داخلی **بدونِ انتخابِ فاکتور**
ثبت می‌شود و حتی سندِ حسابداری می‌گیرد. پس هر دو مسیر باید ممکن باشند.

## نقطه‌ی ثبتِ حسابداری — صریح، نه حدسی

مهم‌ترین هشدارِ فصل این است که فاکتور و رسید نباید **یک بدهی را دو بار** ثبت
کنند. سیاستِ فعلیِ کوبیتا سنجیده شد و منسجم است: بدهی را *فاکتور* می‌شناسد و
رسید هیچ سندی نمی‌زند. آن دست نمی‌خورد.

ولی رسیدِ **مستقیم** فاکتوری ندارد که بدهی را شناخته باشد. نزدنِ سند برایش
یعنی کالا بی‌هیچ اثرِ حسابداری وارد انبار شود و دفتر با گزارشِ انبار برای همیشه
واگرا بماند. پس:

* رسیدِ گره‌خورده به فاکتور → فقط حرکتِ فیزیکی (بدونِ تغییر).
* رسیدِ مستقیم → خودش منشأِ مالی است.

`journal_entry_id` روی رسید می‌گوید کدام‌یک اتفاق افتاده — §۴۴ می‌خواهد «اثرِ
انباری» و «اثرِ حسابداری» دو چیزِ جدا باشند، نه یک بولینِ مبهم.

## سه نقشِ جدا، نه یک `supplier`

تحویل‌دهنده، حمل‌کننده و واسطِ حمل سه مفهومِ مستقل‌اند (§۶ §۷). معنای دقیقِ
واسطِ حمل را فصل تثبیت نمی‌کند، پس فقط *ارجاع* ذخیره می‌شود و هیچ رفتارِ
مالی‌ای از رویش ساخته نمی‌شود.

## هیچ داده‌ای نوشته نمی‌شود

رسیدهای موجود همه گره‌خورده به فاکتورند، پس `receipt_type` پیش‌فرضِ «خرید
(داخلی)» درست است و `journal_entry_id`شان `NULL` می‌ماند — که دقیقاً حقیقت
است: هیچ‌کدام سند نزده‌اند.
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

TABLE = "warehouse_receipts"
LINES = "warehouse_receipt_lines"

RECEIPT_TYPES = (
    "purchase_domestic",
    "purchase_import",
    "production",
    "other",
    "opening",
)


def upgrade() -> None:
    conn = op.get_bind()

    #: §۸ §۹ — ارجاع است، نه پیش‌نیاز.
    op.alter_column(TABLE, "purchase_invoice_id", existing_type=UUID(as_uuid=True), nullable=True)
    op.alter_column(LINES, "purchase_invoice_line_id", existing_type=UUID(as_uuid=True), nullable=True)

    op.add_column(
        TABLE,
        sa.Column(
            "receipt_type", sa.String(20), server_default="purchase_domestic", nullable=False
        ),
    )
    op.create_check_constraint(
        "ck_warehouse_receipts_type", TABLE, f"receipt_type IN {RECEIPT_TYPES}"
    )

    op.add_column(TABLE, sa.Column("description2", sa.Text(), server_default="", nullable=False))
    op.add_column(TABLE, sa.Column("currency_code", sa.String(3), nullable=True))
    op.add_column(
        TABLE, sa.Column("exchange_rate", sa.Numeric(18, 4), server_default="1", nullable=False)
    )

    #: **FORCE موقتاً برداشته می‌شود.** افزودنِ کلیدِ خارجی به جدولی که مرجعش
    #: FORCE RLS دارد، اسکنِ اعتبارسنجیِ Postgres را راه می‌اندازد و آن اسکن
    #: `current_setting('app.tenant_id')` را می‌خواند — که وسطِ مهاجرت وجود
    #: ندارد. همان درسِ مهاجرت‌های ۰۱۰۹ و ۰۱۲۰.
    with rls_disabled(conn, [TABLE, "contacts", "journal_entries"]):
        for column, target in (
            ("contact_id", "contacts.id"),
            ("carrier_id", "contacts.id"),
            ("freight_agent_id", "contacts.id"),
            ("journal_entry_id", "journal_entries.id"),
        ):
            op.add_column(
                TABLE,
                sa.Column(column, UUID(as_uuid=True), sa.ForeignKey(target), nullable=True),
            )

    op.create_index("ix_warehouse_receipts_contact", TABLE, ["tenant_id", "contact_id"])
    op.create_index("ix_warehouse_receipts_journal", TABLE, ["tenant_id", "journal_entry_id"])


def downgrade() -> None:
    op.drop_index("ix_warehouse_receipts_journal", table_name=TABLE)
    op.drop_index("ix_warehouse_receipts_contact", table_name=TABLE)
    for column in (
        "journal_entry_id",
        "freight_agent_id",
        "carrier_id",
        "contact_id",
        "exchange_rate",
        "currency_code",
        "description2",
    ):
        op.drop_column(TABLE, column)
    op.drop_constraint("ck_warehouse_receipts_type", TABLE, type_="check")
    op.drop_column(TABLE, "receipt_type")
    op.alter_column(LINES, "purchase_invoice_line_id", existing_type=UUID(as_uuid=True), nullable=False)
    op.alter_column(TABLE, "purchase_invoice_id", existing_type=UUID(as_uuid=True), nullable=False)
