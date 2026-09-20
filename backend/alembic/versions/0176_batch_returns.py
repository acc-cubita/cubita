"""مرجوعیِ بارمحور و جایگزینیِ بار

Revision ID: 0176
Revises: 0175

## چه چیزی اضافه می‌شود

**`batch_substitutions`** — هر بار که بارِ یک خروج عوض می‌شود، یک ردیف (§۱۳).
جدولِ مستأجرمحور با RLS.

**روی ردیف‌های مرجوعی دو ستون** (`sales_return_lines`،
`warehouse_issue_return_lines`): `batch_id` و `return_condition`.

## چرا «وضعیتِ کالای برگشتی» ستونِ خودش را دارد (§۱۴)

مرجوعی یک عدد نیست، یک **تصمیم** است: کالایی که سالم برگشته باید به موجودیِ
قابلِ فروش برگردد، و کالایی که خراب یا منقضی برگشته نباید. تا امروز مرجوعی این
تفاوت را نمی‌شناخت و هر برگشتی مستقیم قابلِ فروش می‌شد.

    sellable    → به موجودیِ قابلِ فروشِ همان بار برمی‌گردد
    damaged     ┐
    expired     ├ فیزیکی برمی‌گردد ولی **قابلِ فروش نیست**
    quarantine  │
    blocked     ┘

## چرا «قابلِ فروش نیست» مکانیزمِ تازه نگرفت

وسوسه‌ی طبیعی یک ستونِ `blocked_qty` روی بار بود. ولی موتورِ رزرو (مهاجرتِ
۰۱۷۳) دقیقاً همین کار را می‌کند: ردیفِ ادعا با `kind='blocked'` از
`available` کم می‌شود بی آنکه `physical` تکان بخورد — که عیناً خواسته‌ی §۱۴
است. ستونِ تازه یعنی دو کم‌شونده که دو مکانیزمِ مختلف نگهشان می‌دارند و روزی
با هم اختلاف پیدا می‌کنند.

پس برگشتِ **غیرِ سالم** دو چیز می‌نویسد: حرکتِ ورودیِ برچسب‌خورده (فیزیکی
برگشت) و یک ادعای `blocked` به همان اندازه (قابلِ فروش نشد). هر دو در دفتر
دیده می‌شوند و هیچ‌کدام ستونِ تازه‌ای نمی‌خواهند.

## چرا جایگزینی جدول می‌خواهد ولی مرجوعی نه

§۱۳ صریح است: «این تغییر نباید بدون Audit Trail انجام شود» و شش فیلد نام
می‌برد که هیچ‌کدام از داده‌ی موجود مشتق نمی‌شوند — مخصوصاً **دلیل**. حرکتِ
دفتر می‌گوید از کدام بار چه‌قدر رفت، ولی نمی‌گوید چرا بارِ اول کنار گذاشته شد.

مرجوعی برعکس: دو ستون روی ردیفِ موجود کافی است، چون خودِ سند از قبل هست.

## چرا `rls_disabled` برای دو ستونِ `batch_id` لازم است

هر دو کلیدِ خارجی به `stock_batches` دارند و جدول‌های مرجوعی ردیف دارند. اسکنِ
اعتبارسنجیِ Postgres مشمولِ سیاستِ RLS است و روی PG14 — همان که تولید دارد —
می‌ترکد. شرحِ کامل در `app/migration_utils.py`.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.migration_utils import rls_disabled
from app.tenancy import policy_name

revision: str = "0176"
down_revision: Union[str, None] = "0175"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RETURN_CONDITIONS = ("sellable", "damaged", "expired", "quarantine", "blocked")

#: جدول‌هایی که ردیفِ مرجوعی دارند و باید بارمحور شوند.
_RETURN_LINE_TABLES = ("sales_return_lines", "warehouse_issue_return_lines")


def _enable_rls(table: str) -> None:
    conn = op.get_bind()
    conn.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"DROP POLICY IF EXISTS {policy_name(table)} ON {table}"))
    conn.execute(sa.text(
        f"CREATE POLICY {policy_name(table)} ON {table} "
        "USING (tenant_id = current_setting('app.tenant_id', true)::uuid) "
        "WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)"
    ))


def upgrade() -> None:
    conn = op.get_bind()

    op.create_table(
        "batch_substitutions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column(
            "original_batch_id",
            UUID(as_uuid=True),
            sa.ForeignKey("stock_batches.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "new_batch_id",
            UUID(as_uuid=True),
            sa.ForeignKey("stock_batches.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("qty", sa.Numeric(18, 3), nullable=False),
        #: سندی که جایگزینی در آن رخ داد — چندریختی، مثلِ `source_id`ِ دفتر.
        sa.Column("source_type", sa.String(50), server_default="", nullable=False),
        sa.Column("source_id", UUID(as_uuid=True), nullable=True),
        #: §۱۳ — **دلیل اجباری است.** جایگزینیِ بی‌دلیل، ماهِ بعد هیچ‌کس نمی‌داند
        #: چرا بارِ اول کنار گذاشته شد، و همین گزارش را بی‌معنا می‌کند.
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("changed_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("qty > 0", name="ck_batch_substitutions_qty"),
        sa.CheckConstraint("original_batch_id <> new_batch_id", name="ck_batch_substitutions_distinct"),
    )
    _enable_rls("batch_substitutions")

    with rls_disabled(conn, ["sales_return_lines", "warehouse_issue_return_lines", "stock_batches"]):
        for table in _RETURN_LINE_TABLES:
            op.add_column(
                table,
                sa.Column(
                    "batch_id",
                    UUID(as_uuid=True),
                    sa.ForeignKey("stock_batches.id", ondelete="RESTRICT"),
                    nullable=True,
                ),
            )

    for table in _RETURN_LINE_TABLES:
        #: پیش‌فرضِ `sellable` یعنی **رفتارِ دیروز**: تا امروز هر برگشتی مستقیم
        #: قابلِ فروش می‌شد، و هیچ مرجوعیِ ثبت‌شده‌ای یک‌شبه مسدود نمی‌شود.
        op.add_column(
            table,
            sa.Column("return_condition", sa.String(20), server_default="sellable", nullable=False),
        )
        op.create_check_constraint(
            f"ck_{table}_condition", table, f"return_condition IN {RETURN_CONDITIONS}"
        )


def downgrade() -> None:
    for table in _RETURN_LINE_TABLES:
        op.drop_constraint(f"ck_{table}_condition", table, type_="check")
        op.drop_column(table, "return_condition")
        op.drop_column(table, "batch_id")
    op.drop_table("batch_substitutions")
