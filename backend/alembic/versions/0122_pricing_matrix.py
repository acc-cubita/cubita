"""اعلامیه‌ی قیمت یک ماتریس بود که هیچ راهی برای پرکردنش نبود

Revision ID: 0122
Revises: 0121

## چهار ستون، و یک ایندکس که باید بازساخته شود

**گروهِ فروشِ کالا (§۱۴).** ماتریسِ مشاهده‌شده ستونِ «گروه فروش کالا» دارد، ولی
`price_list_items` فقط `item_id` داشت — یعنی قیمت‌گذاری برای یک گروهِ کالا
ناممکن بود. حالا قاعده یا کالا را نام می‌برد یا گروهش را، و `item_id` به همین
دلیل nullable می‌شود. قیدِ `ck_price_list_items_has_target` جلوی قاعده‌ای را
می‌گیرد که هیچ‌کدام را نام نبرده باشد — چنین ردیفی یک قیمتِ سراسریِ ناخواسته است.

**امکانِ تغییرِ تخفیف (§۲۵).** تا امروز فقط `allow_rate_change` بود. فصل صریح
است که این دو یک پرچم نیستند: فروشنده‌ای که حق ندارد فی را عوض کند ممکن است
حقِ تخفیف داشته باشد.

**درصدِ اضافات (§۲۲).** ذخیره می‌شود و نمایش داده می‌شود، ولی **اعمال نمی‌شود**
— §۲۳ می‌گوید ربطش به «اضافاتِ فاکتور» و «عاملِ افزاینده» هنوز معلوم نیست، و
حدس‌زدنش یعنی ساختنِ یک قاعده‌ی مالیِ نانوشته.

**ردِ قیمت روی ردیفِ فاکتور (§۹ §۵۹ §۹۱).** `declared_unit_price` و
`price_rule_id` می‌گویند اعلامیه در لحظه‌ی ثبت چه نرخی داد و کدام قاعده دادش.
با همین دو، «کاربر قیمت را دست‌کاری کرده» **مشتق** می‌شود و نیازی به پرچمِ
`price_changed` نیست (§۶۱).

## ایندکسِ یکتا

`uq_price_list_items_context` باید دو بُعدِ تازه را ببیند، وگرنه یک قاعده‌ی
گروه‌محور می‌توانست بی‌نهایت بار تکرار شود. `COALESCE` لازم است چون در Postgres
دو `NULL` در ایندکسِ یکتا با هم برابر شمرده نمی‌شوند.

## بدونِ backfill

قاعده‌ی پروژه: مهاجرت روی جدولِ RLS‌دار `UPDATE` نمی‌زند. ستون‌های تازه‌ی سیاست
`server_default` دارند (پیش‌فرضِ «بی‌حد»، یعنی رفتارِ امروز)، و دو ستونِ ردِ
قیمت `NULL` می‌مانند — یعنی «ردِ نامعلوم»، که همان حقیقتِ ردیف‌های موجود است.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0122"
down_revision: Union[str, None] = "0121"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: شناسه‌ی ساختگیِ «هیچ» برای `COALESCE` — تا `NULL`های ایندکسِ یکتا با هم برابر شوند.
_NONE = "'00000000-0000-0000-0000-000000000000'::uuid"

_CONTEXT_INDEX = (
    "tenant_id, price_list_id, "
    f"COALESCE(item_id, {_NONE}), "
    f"COALESCE(item_group_id, {_NONE}), "
    f"COALESCE(sale_type_id, {_NONE}), "
    f"COALESCE(unit_id, {_NONE}), "
    f"COALESCE(contact_group_id, {_NONE}), "
    "currency_code"
)

#: شکلِ ایندکس پیش از این مهاجرت — برای اینکه downgrade واقعاً برگرداند.
_CONTEXT_INDEX_0120 = (
    "tenant_id, price_list_id, item_id, "
    f"COALESCE(sale_type_id, {_NONE}), "
    f"COALESCE(unit_id, {_NONE}), "
    f"COALESCE(contact_group_id, {_NONE}), "
    "currency_code"
)


def upgrade() -> None:
    op.add_column(
        "price_list_items",
        sa.Column("item_group_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_price_list_items_item_group",
        "price_list_items",
        "discount_item_groups",
        ["item_group_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_price_list_items_item_group_id", "price_list_items", ["item_group_id"])

    op.add_column(
        "price_list_items",
        sa.Column("allow_discount_change", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        "price_list_items",
        sa.Column("addition_percent", sa.Numeric(5, 2), nullable=False, server_default="0"),
    )

    #: کالا اختیاری می‌شود تا قاعده‌ی گروه‌محور جا باز کند — ولی «نه کالا نه گروه» نه.
    op.alter_column("price_list_items", "item_id", existing_type=UUID(as_uuid=True), nullable=True)
    op.create_check_constraint(
        "ck_price_list_items_has_target",
        "price_list_items",
        "item_id IS NOT NULL OR item_group_id IS NOT NULL",
    )

    op.drop_index("uq_price_list_items_context", table_name="price_list_items")
    op.execute(
        f"CREATE UNIQUE INDEX uq_price_list_items_context "
        f"ON price_list_items ({_CONTEXT_INDEX})"
    )

    op.add_column(
        "sales_invoice_lines",
        sa.Column("declared_unit_price", sa.Numeric(18, 0), nullable=True),
    )
    op.add_column(
        "sales_invoice_lines",
        sa.Column("price_rule_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_sales_invoice_lines_price_rule",
        "sales_invoice_lines",
        "price_list_items",
        ["price_rule_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_sales_invoice_lines_price_rule", "sales_invoice_lines", type_="foreignkey")
    op.drop_column("sales_invoice_lines", "price_rule_id")
    op.drop_column("sales_invoice_lines", "declared_unit_price")

    op.drop_index("uq_price_list_items_context", table_name="price_list_items")
    op.drop_constraint("ck_price_list_items_has_target", "price_list_items", type_="check")
    #: برگرداندنِ `item_id` به NOT NULL فقط وقتی ممکن است که قاعده‌ی گروه‌محوری
    #: نمانده باشد؛ آن‌ها اصلاً پیش از این مهاجرت وجود نداشتند، پس حذف می‌شوند.
    op.execute("DELETE FROM price_list_items WHERE item_id IS NULL")
    op.alter_column("price_list_items", "item_id", existing_type=UUID(as_uuid=True), nullable=False)
    op.execute(
        f"CREATE UNIQUE INDEX uq_price_list_items_context "
        f"ON price_list_items ({_CONTEXT_INDEX_0120})"
    )

    op.drop_column("price_list_items", "addition_percent")
    op.drop_column("price_list_items", "allow_discount_change")
    op.drop_index("ix_price_list_items_item_group_id", table_name="price_list_items")
    op.drop_constraint("fk_price_list_items_item_group", "price_list_items", type_="foreignkey")
    op.drop_column("price_list_items", "item_group_id")
