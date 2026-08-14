"""ماژول چندارزی (لایه‌ی تراکنش/نمایش)

Revision ID: 0034
Revises: 0033

**دامنه‌ی عمداً کران‌دار:** دفترها پایه (ریال) می‌مانند. ارز یک لایه‌ی تراکنش/نمایش
روی فاکتور است — مبالغِ سطرها هنگام ثبت به پایه تبدیل و ذخیره می‌شوند، پس سند
حسابداری، بهای موجودی، مالیات و همه‌ی گزارش‌ها بدون تغییر و درست می‌مانند. فقط
`currency_code` و `exchange_rate` روی سرِ فاکتور نگه داشته می‌شوند تا نمایش/PDF
بتواند مبلغِ ارزی و نرخ را نشان دهد. بازارزیابیِ ماندهٔ ارزیِ باز و سود/زیانِ تسعیر
عمداً بیرون است (نیازمند لایه‌ی کاملِ چند‌ارزیِ دفتر).

سه‌چیز اضافه می‌شود (جدول‌های ارز با RLS، همان الگوی 0026/…):
- `currencies`: ارزهای خارجیِ تعریف‌شده‌ی هر کسب‌وکار (پایه/ریال ضمنی است).
- `exchange_rates`: نرخِ هر ارز در یک تاریخ (چند ریال به‌ازای یک واحد).
- `currency_code` (nullable = پایه) و `exchange_rate` (پیش‌فرض ۱) روی فاکتورها.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.tenancy import policy_name

revision: str = "0034"
down_revision: Union[str, None] = "0033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enable_rls(conn, table: str) -> None:
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
    op.create_table(
        "currencies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("code", sa.String(3), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("symbol", sa.String(10), nullable=False, server_default=""),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.UniqueConstraint("tenant_id", "code", name="uq_currencies_tenant_code"),
    )
    op.create_index("ix_currencies_tenant_id", "currencies", ["tenant_id"])

    op.create_table(
        "exchange_rates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("currency_code", sa.String(3), nullable=False),
        sa.Column("rate_date", sa.Date, nullable=False),
        sa.Column("rate", sa.Numeric(18, 4), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.UniqueConstraint("tenant_id", "currency_code", "rate_date", name="uq_exchange_rates_tenant_code_date"),
    )
    op.create_index("ix_exchange_rates_tenant_id", "exchange_rates", ["tenant_id"])

    for table in ("sales_invoices", "purchase_invoices"):
        op.add_column(table, sa.Column("currency_code", sa.String(3), nullable=True))
        op.add_column(table, sa.Column("exchange_rate", sa.Numeric(18, 4), nullable=False, server_default="1"))

    conn = op.get_bind()
    _enable_rls(conn, "currencies")
    _enable_rls(conn, "exchange_rates")


def downgrade() -> None:
    for table in ("purchase_invoices", "sales_invoices"):
        op.drop_column(table, "exchange_rate")
        op.drop_column(table, "currency_code")
    op.drop_table("exchange_rates")
    op.drop_table("currencies")
