"""کالا نمی‌دانست در کدام انبارها جا دارد

Revision ID: 0119
Revises: 0118

## چه چیزی نبود

**رابطه‌ی کالا و انبار.** هر کالا در هر انباری می‌نشست و هیچ‌جا نمی‌شد گفت
«موادِ اولیه فقط در انبارِ مواد اولیه» یا «انبارِ پیش‌فرضِ این کالا کدام است».
فصل این رابطه را ذاتاً **چندبه‌چند** می‌داند (§۳۰).

**کنترلِ موجودی.** `reorder_point` بود، ولی حداقل و حداکثر نبود. §۲۴ سه مفهومِ
جدا می‌شناسد و §۲۶ می‌گوید هر سه **قاعده‌ی برنامه‌ریزی‌اند، نه سدِ تراکنش**.

## هیچ داده‌ای نوشته نمی‌شود — و این مهم است

`item_warehouses` **خالی** می‌ماند. پرکردنش از روی حرکاتِ گذشته وسوسه‌انگیز است
(«هر کالایی که در انبارِ الف گردش داشته، پس مجازِ انبارِ الف است») ولی آن یک
*استنتاج* است نه یک واقعیت: شاید آن ورود اشتباه بوده و کاربر اصلاً نمی‌خواهد
تکرار شود.

و لازم هم نیست: **فهرستِ خالی یعنی «همه‌ی انبارها»**، که دقیقاً رفتارِ امروزِ
کوبیتاست. پس هیچ کالای موجودی محدود نمی‌شود و فقط کسی که صریحاً فهرست بگذارد
محدودیت می‌گیرد.

## §۳۳ — حذفِ رابطه گذشته را پاک نمی‌کند

`stock_ledger` و کاردکس جای دیگری زندگی می‌کنند و این جدول به آن‌ها دست
نمی‌زند. فهرستِ مجاز فقط درباره‌ی **آینده** حرف می‌زند.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.tenancy import policy_name

revision: str = "0119"
down_revision: Union[str, None] = "0118"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "item_warehouses"


def upgrade() -> None:
    conn = op.get_bind()

    op.add_column("items", sa.Column("min_stock", sa.Numeric(18, 3), server_default="0", nullable=False))
    op.add_column("items", sa.Column("max_stock", sa.Numeric(18, 3), server_default="0", nullable=False))

    op.create_table(
        TABLE,
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True
        ),
        sa.Column(
            "item_id",
            UUID(as_uuid=True),
            sa.ForeignKey("items.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "warehouse_id",
            UUID(as_uuid=True),
            sa.ForeignKey("warehouses.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("is_default", sa.Boolean(), server_default="false", nullable=False),
        #: override‌های انبارمحور (§۲۸). `NULL` = «همان عددِ کالا» — فصل تصمیم
        #: نمی‌گیرد که کنترل سراسری باشد یا انبارمحور، پس هیچ‌کدام تحمیل نمی‌شود.
        sa.Column("min_stock", sa.Numeric(18, 3), nullable=True),
        sa.Column("max_stock", sa.Numeric(18, 3), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.UniqueConstraint("tenant_id", "item_id", "warehouse_id", name="uq_item_warehouses_pair"),
    )
    #: یک انبارِ پیش‌فرض برای هر کالا — نه صفر، نه دو تا. جزئی، چون نبودِ
    #: پیش‌فرض مجاز است (§۳۲: پیش‌فرض مالکیت نیست).
    op.create_index(
        "uq_item_warehouses_default",
        TABLE,
        ["tenant_id", "item_id"],
        unique=True,
        postgresql_where=sa.text("is_default"),
    )

    #: RLS پس از ساختِ جدول و کلیدهای خارجی — درسِ مهاجرتِ ۰۱۰۹.
    conn.execute(sa.text(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"DROP POLICY IF EXISTS {policy_name(TABLE)} ON {TABLE}"))
    conn.execute(
        sa.text(
            f"CREATE POLICY {policy_name(TABLE)} ON {TABLE} "
            "USING (tenant_id = current_setting('app.tenant_id')::uuid) "
            "WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid)"
        )
    )


def downgrade() -> None:
    op.drop_table(TABLE)
    op.drop_column("items", "max_stock")
    op.drop_column("items", "min_stock")
