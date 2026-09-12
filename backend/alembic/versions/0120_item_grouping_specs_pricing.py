"""گروه یک متن بود، مشخصه‌ای نبود، و قیمت فقط یک عدد داشت

Revision ID: 0120
Revises: 0119

## سه چیز

**گروه‌بندی (§۳۴).** `Item.category` یک متنِ آزاد بود، پس «لوازم خانگی» و
«لوازم‌خانگی» دو گروهِ متفاوت می‌شدند و گزارشِ گروهی قابلِ اعتماد نبود.

**مشخصات (§۳۵ §۳۶).** جایی برای «رنگ»، «سایز»، «کشور سازنده» نبود — و فصل
صریح است که برای هر مشخصه نباید ستونِ تازه‌ای روی `items` بنشیند. پس الگو
*تعریفِ مشخصه* ← *مقدارِ کالا* است.

**قیمت (§۳۷–§۴۲).** `price_list_items` برای هر کالا در هر لیست **یک** قیمت
داشت. ولی یک کالا می‌تواند هم‌زمان قیمتِ عمده به ریال، خرده به ریال و صادراتی
به دلار داشته باشد، و قیمتِ کارتن با قیمتِ عدد یکی نیست.

## چه چیزی نوشته می‌شود، و چرا فبریکه نیست

**گروه‌ها از خودِ داده.** هر نوشتاری که امروز در `items.category` هست همان
می‌شود یک گروه، و کالا به آن پیوند می‌خورد. این *بازسازیِ* چیزی است که کاربر
خودش نوشته، نه دسته‌بندیِ تازه‌ای که ما از خودمان درآورده باشیم. `category`
می‌ماند و از این پس پرتوِ نامِ گروه است.

**ابعادِ تازه‌ی قیمت همه `NULL` می‌مانند** — یعنی «هر زمینه‌ای»، یعنی دقیقاً
رفتارِ امروز. و حدهای تغییرِ نرخ صفر می‌مانند، که یعنی **بی‌حد**: هیچ فروشی
یک‌شبه مسدود نمی‌شود.

## یکتاییِ قیمت با COALESCE

در Postgres دو `NULL` در ایندکسِ یکتا با هم برابر شمرده نمی‌شوند. بدونِ
`COALESCE`، همان ردیفِ «بی‌زمینه» می‌توانست بی‌نهایت بار تکرار شود و
`quote_line` هر بار یکی‌شان را تصادفی برمی‌داشت.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.migration_utils import rls_disabled
from app.tenancy import policy_name

revision: str = "0120"
down_revision: Union[str, None] = "0119"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GROUPS = "item_groups"
ATTRS = "item_attributes"
VALUES = "item_attribute_values"
NEW_TABLES = (GROUPS, ATTRS, VALUES)

ZERO = "'00000000-0000-0000-0000-000000000000'::uuid"


def upgrade() -> None:
    conn = op.get_bind()

    op.create_table(
        GROUPS,
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("code", sa.String(30), server_default="", nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("name2", sa.String(100), server_default="", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("notes", sa.Text(), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("tenant_id", "name", name="uq_item_groups_tenant_name"),
    )

    op.create_table(
        ATTRS,
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("name2", sa.String(100), server_default="", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("tenant_id", "name", name="uq_item_attributes_tenant_name"),
    )

    op.create_table(
        VALUES,
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column(
            "item_id", UUID(as_uuid=True), sa.ForeignKey("items.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column(
            "attribute_id", UUID(as_uuid=True), sa.ForeignKey(f"{ATTRS}.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column("value", sa.Text(), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("tenant_id", "item_id", "attribute_id", name="uq_item_attribute_values_pair"),
    )

    op.add_column(
        "items",
        sa.Column("group_id", UUID(as_uuid=True), sa.ForeignKey(f"{GROUPS}.id", ondelete="SET NULL"), nullable=True),
    )

    # ── ابعادِ قیمت و کنترلِ تغییرِ نرخ ────────────────────────────────────
    #
    #: **FORCE موقتاً برداشته می‌شود.** افزودنِ کلیدِ خارجی به جدولی که مرجعش
    #: FORCE RLS دارد، اسکنِ اعتبارسنجیِ Postgres را راه می‌اندازد و آن اسکن
    #: `current_setting('app.tenant_id')` را می‌خواند — که وسطِ مهاجرت وجود
    #: ندارد و خطای «unrecognized configuration parameter» می‌دهد. همان درسی که
    #: مهاجرتِ ۰۱۰۹ داد، این بار از سمتِ جدولِ *مرجع*.
    with rls_disabled(
        conn, ["price_list_items", "sale_types", "units_of_measure", "contact_groups"]
    ):
        for name, fk in (
            ("sale_type_id", "sale_types.id"),
            ("unit_id", "units_of_measure.id"),
            ("contact_group_id", "contact_groups.id"),
        ):
            op.add_column(
                "price_list_items",
                sa.Column(name, UUID(as_uuid=True), sa.ForeignKey(fk, ondelete="CASCADE"), nullable=True),
            )
    op.add_column(
        "price_list_items",
        sa.Column("currency_code", sa.String(3), server_default="IRR", nullable=False),
    )
    op.add_column(
        "price_list_items",
        sa.Column("allow_rate_change", sa.Boolean(), server_default="true", nullable=False),
    )
    op.add_column(
        "price_list_items",
        sa.Column("max_increase_percent", sa.Numeric(5, 2), server_default="0", nullable=False),
    )
    op.add_column(
        "price_list_items",
        sa.Column("max_decrease_percent", sa.Numeric(5, 2), server_default="0", nullable=False),
    )

    #: قیدِ قدیمی «هر کالا یک قیمت در هر لیست» جایش را به یکتاییِ **کلِ زمینه**
    #: می‌دهد؛ نگه‌داشتنش یعنی قیمتِ عمده و خرده هم‌زمان ممکن نباشند.
    op.drop_constraint("uq_price_list_items_list_item", "price_list_items", type_="unique")
    op.create_index(
        "uq_price_list_items_context",
        "price_list_items",
        [
            "tenant_id",
            "price_list_id",
            "item_id",
            sa.text(f"COALESCE(sale_type_id, {ZERO})"),
            sa.text(f"COALESCE(unit_id, {ZERO})"),
            sa.text(f"COALESCE(contact_group_id, {ZERO})"),
            "currency_code",
        ],
        unique=True,
    )

    #: RLS پس از ساختِ جدول‌ها و کلیدهای خارجی — درسِ مهاجرتِ ۰۱۰۹.
    for table in NEW_TABLES:
        conn.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
        conn.execute(sa.text(f"DROP POLICY IF EXISTS {policy_name(table)} ON {table}"))
        conn.execute(
            sa.text(
                f"CREATE POLICY {policy_name(table)} ON {table} "
                "USING (tenant_id = current_setting('app.tenant_id')::uuid) "
                "WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)"
            )
        )

    with rls_disabled(conn, [GROUPS, "items"]):
        #: گروه‌ها از خودِ داده — بازسازیِ چیزی که کاربر خودش نوشته، نه
        #: دسته‌بندیِ تازه‌ای که ما از خودمان درآورده باشیم.
        conn.execute(
            sa.text(
                f"""
                INSERT INTO {GROUPS} (id, tenant_id, code, name, name2, is_active, notes)
                SELECT gen_random_uuid(), i.tenant_id, '', TRIM(i.category), '', true, ''
                  FROM items i
                 WHERE COALESCE(TRIM(i.category), '') <> ''
                 GROUP BY i.tenant_id, TRIM(i.category)
                """
            )
        )
        conn.execute(
            sa.text(
                f"""
                UPDATE items i
                   SET group_id = g.id
                  FROM {GROUPS} g
                 WHERE g.tenant_id = i.tenant_id AND g.name = TRIM(i.category)
                """
            )
        )


def downgrade() -> None:
    op.drop_index("uq_price_list_items_context", table_name="price_list_items")
    op.create_unique_constraint(
        "uq_price_list_items_list_item",
        "price_list_items",
        ["tenant_id", "price_list_id", "item_id"],
    )
    for column in (
        "max_decrease_percent",
        "max_increase_percent",
        "allow_rate_change",
        "currency_code",
        "contact_group_id",
        "unit_id",
        "sale_type_id",
    ):
        op.drop_column("price_list_items", column)
    op.drop_column("items", "group_id")
    op.drop_table(VALUES)
    op.drop_table(ATTRS)
    op.drop_table(GROUPS)
