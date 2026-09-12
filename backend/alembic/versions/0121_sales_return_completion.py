"""برگشت نه ردیفِ مبدأش را می‌شناخت، نه می‌شد پسش گرفت

Revision ID: 0121
Revises: 0120

## چهار چیز

**ردیفِ مبدأ (§۷ §۸۰ §۱۰۴).** `sales_return_lines` فقط `item_id` داشت. پس
فاکتوری با دو ردیفِ یک کالا به دو قیمت، هنگامِ برگشت **میانگین** می‌گرفت — و
مشتری مبلغی پس می‌گرفت که هرگز نپرداخته بود. حالا هر ردیفِ برگشت به ردیفِ
فاکتور گره می‌خورد.

**ابطال (§۷۱–§۷۸).** `SalesReturn` نه `voided_at` داشت نه مسیرِ حذف. و
`voiding._guard_no_active_returns` هنگامِ ابطالِ فاکتور می‌گفت «اول سندِ برگشت
را برگردانید» — کاری که **هیچ راهی برایش نبود**. یعنی یک برگشتِ اشتباهی،
فاکتورش را برای همیشه از ابطال قفل می‌کرد.

**علتِ برگشت (§۲۴–§۲۸).** جدولِ مِستر، نه متنِ آزاد: «خرابی»، «خراب بود» و
«کالا خراب» سه نوشته‌ی یک علت‌اند و با متنِ آزاد هیچ‌وقت با هم جمع نمی‌شوند.

**قرینه‌ی خرید.** `purchase_return_lines` هم همان ستونِ ردیفِ مبدأ را می‌گیرد و
`purchase_returns` هم ابطال — وگرنه دو سمتِ یک ماژول دو رفتار پیدا می‌کنند.

## هیچ backfill‌ای نیست، و این عمدی است

قاعده‌ی پروژه: مهاجرت روی جدولِ RLS‌دار `UPDATE` نمی‌زند (بی‌زمینه‌ی مستأجر
اجرا می‌شود). پس ردیف‌های موجود `sales_invoice_line_id = NULL` می‌گیرند و
`returns._drain_legacy` هنگامِ محاسبه‌ی مانده، مقدارشان را از استخرِ همان کالا
کم می‌کند. بدونِ آن، لحظه‌ی مهاجرت مانده‌ی قابلِ برگشت بی‌صدا بالا می‌پرید و
کالایی که کامل برگشت خورده بود دوباره قابلِ برگشت می‌شد.

`voided_at` هم روی ردیف‌های موجود `NULL` می‌ماند — یعنی «باطل نشده»، که همان
حقیقتِ امروزشان است.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.tenancy import policy_name

revision: str = "0121"
down_revision: Union[str, None] = "0120"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

REASONS = "sales_return_reasons"

#: دو سربرگِ برگشت که ابطال‌پذیر می‌شوند.
RETURN_HEADERS = ("sales_returns", "purchase_returns")

#: (جدولِ ردیف, ستونِ تازه, جدولِ مقصد, نامِ کلیدِ خارجی)
SOURCE_LINKS = (
    ("sales_return_lines", "sales_invoice_line_id", "sales_invoice_lines", "fk_sales_return_lines_source"),
    (
        "purchase_return_lines",
        "purchase_invoice_line_id",
        "purchase_invoice_lines",
        "fk_purchase_return_lines_source",
    ),
)


def _enable_rls(table: str) -> None:
    """همان سه دستورِ همیشگی — بدونِ این، جدولِ تازه بینِ مستأجرها نشت می‌کند."""
    conn = op.get_bind()
    conn.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"DROP POLICY IF EXISTS {policy_name(table)} ON {table}"))
    conn.execute(
        sa.text(
            f"CREATE POLICY {policy_name(table)} ON {table} "
            "USING (tenant_id = current_setting('app.tenant_id', true)::uuid) "
            "WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)"
        )
    )


def upgrade() -> None:
    # ── ۱) مِسترِ علتِ برگشت ────────────────────────────────────────────────
    op.create_table(
        REASONS,
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("title2", sa.String(120), server_default="", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("tenant_id", "title", name="uq_sales_return_reasons_tenant_title"),
    )
    _enable_rls(REASONS)

    # ── ۲) ردیفِ برگشت، ردیفِ فاکتورش را می‌شناسد ───────────────────────────
    for table, column, target, fk_name in SOURCE_LINKS:
        op.add_column(table, sa.Column(column, UUID(as_uuid=True), nullable=True))
        op.create_foreign_key(fk_name, table, target, [column], ["id"])
        op.create_index(f"ix_{table}_{column}", table, [column])

    op.add_column(
        "sales_return_lines",
        sa.Column("return_reason_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_sales_return_lines_reason", "sales_return_lines", REASONS, ["return_reason_id"], ["id"]
    )
    op.create_index("ix_sales_return_lines_return_reason_id", "sales_return_lines", ["return_reason_id"])

    # ── ۳) سربرگِ برگشت ابطال‌پذیر می‌شود ───────────────────────────────────
    for table in RETURN_HEADERS:
        op.add_column(table, sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column(table, sa.Column("void_reason", sa.Text(), server_default="", nullable=False))
        op.add_column(table, sa.Column("voided_by_id", UUID(as_uuid=True), nullable=True))
        op.create_foreign_key(f"fk_{table}_voided_by", table, "users", ["voided_by_id"], ["id"])
        op.create_index(f"ix_{table}_voided_at", table, ["voided_at"])


def downgrade() -> None:
    for table in RETURN_HEADERS:
        op.drop_index(f"ix_{table}_voided_at", table_name=table)
        op.drop_constraint(f"fk_{table}_voided_by", table, type_="foreignkey")
        for column in ("voided_by_id", "void_reason", "voided_at"):
            op.drop_column(table, column)

    op.drop_index("ix_sales_return_lines_return_reason_id", table_name="sales_return_lines")
    op.drop_constraint("fk_sales_return_lines_reason", "sales_return_lines", type_="foreignkey")
    op.drop_column("sales_return_lines", "return_reason_id")

    for table, column, _target, fk_name in SOURCE_LINKS:
        op.drop_index(f"ix_{table}_{column}", table_name=table)
        op.drop_constraint(fk_name, table, type_="foreignkey")
        op.drop_column(table, column)

    op.drop_table(REASONS)
