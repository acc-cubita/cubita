"""فاکتور خرید خدمات — نوعِ سند، کسوراتِ قانونی، و حسابِ هزینه روی ردیف.

* `purchase_invoices.kind`: `goods` برای همه‌ی فاکتورهای تا امروز (پیش‌فرضِ ستون روی
  ردیف‌های موجود می‌نشیند، پس هیچ `UPDATE`ی لازم نیست) و `service` برای فاکتور خرید
  خدمات. سریِ شماره‌ی خدمات جداست، پس یکتایی از (مستأجر، شماره) به (مستأجر، نوع،
  شماره) می‌رود. قیدِ قبلی سخت‌تر از قیدِ تازه است، پس هیچ ردیفِ موجودی نقضش نمی‌کند.
* `purchase_invoices.total_deductions`: جمعِ کسوراتِ فاکتور — صفر برای همه‌ی قبلی‌ها.
* `purchase_invoice_lines.expense_account_id`: حسابِ هزینه‌ای که ردیفِ خدمت **واقعاً**
  خورد. ردیف‌های قدیمی `NULL` می‌مانند و به نگاشتِ امروزِ خدمت برمی‌گردند؛ یعنی دقیقاً
  رفتارِ تا امروز. پُرکردنشان از نگاشتِ امروز حدس بود، نه تاریخ.
* دو جدولِ تازه: `purchase_deduction_types` و `purchase_invoice_deductions`.
* شمارنده‌ی `service_purchase_invoice` برای همه‌ی مستأجرها، زیرِ `rls_disabled`.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.migration_utils import rls_disabled
from app.tenancy import policy_name

revision: str = "0135"
down_revision: Union[str, None] = "0134"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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
    op.add_column(
        "purchase_invoices", sa.Column("kind", sa.String(10), server_default="goods", nullable=False)
    )
    op.create_check_constraint(
        "ck_purchase_invoices_kind", "purchase_invoices", "kind IN ('goods', 'service')"
    )
    op.add_column(
        "purchase_invoices",
        sa.Column("total_deductions", sa.Numeric(18, 0), server_default="0", nullable=False),
    )
    op.drop_constraint("uq_purchase_invoices_tenant_number", "purchase_invoices", type_="unique")
    op.create_unique_constraint(
        "uq_purchase_invoices_tenant_kind_number", "purchase_invoices", ["tenant_id", "kind", "number"]
    )
    op.add_column(
        "purchase_invoice_lines",
        sa.Column("expense_account_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=True),
    )

    op.create_table(
        "purchase_deduction_types",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("code", sa.String(30), server_default="", nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("nature", sa.String(20), nullable=False),
        sa.Column("basis", sa.String(20), server_default="net_before_tax", nullable=False),
        sa.Column("rate", sa.Numeric(7, 3), server_default="0", nullable=False),
        sa.Column("account_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("tenant_id", "name", name="uq_purchase_deduction_types_tenant_name"),
        sa.CheckConstraint(
            "nature IN ('withholding_tax', 'insurance')", name="ck_purchase_deduction_types_nature"
        ),
        sa.CheckConstraint("basis IN ('net_before_tax', 'gross')", name="ck_purchase_deduction_types_basis"),
        sa.CheckConstraint("rate >= 0 AND rate <= 100", name="ck_purchase_deduction_types_rate"),
    )
    _enable_rls("purchase_deduction_types")

    op.create_table(
        "purchase_invoice_deductions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column(
            "invoice_id", UUID(as_uuid=True),
            sa.ForeignKey("purchase_invoices.id", ondelete="CASCADE"), nullable=False, index=True,
        ),
        sa.Column("seq", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "deduction_type_id", UUID(as_uuid=True),
            sa.ForeignKey("purchase_deduction_types.id"), nullable=True, index=True,
        ),
        sa.Column("nature", sa.String(20), nullable=False),
        sa.Column("name_snapshot", sa.String(100), server_default="", nullable=False),
        sa.Column("basis", sa.String(20), nullable=False),
        sa.Column("basis_amount", sa.Numeric(18, 0), nullable=False),
        sa.Column("rate", sa.Numeric(7, 3), server_default="0", nullable=False),
        sa.Column("amount", sa.Numeric(18, 0), nullable=False),
        sa.Column("account_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_purchase_invoice_deductions_amount_positive"),
        sa.CheckConstraint(
            "nature IN ('withholding_tax', 'insurance')", name="ck_purchase_invoice_deductions_nature"
        ),
    )
    _enable_rls("purchase_invoice_deductions")

    conn = op.get_bind()
    with rls_disabled(conn, ["document_counters"]):
        conn.execute(sa.text("""
            INSERT INTO document_counters
                (id, tenant_id, doc_type, last_number, created_at, updated_at)
            SELECT gen_random_uuid(), t.id, 'service_purchase_invoice', 0, now(), now()
            FROM tenants t
            WHERE NOT EXISTS (
                SELECT 1 FROM document_counters dc
                WHERE dc.tenant_id = t.id AND dc.doc_type = 'service_purchase_invoice'
            )
        """))


def downgrade() -> None:
    #: پس از اولین فاکتور خرید خدمات بااتلاف است: کسورات و نوعِ سند می‌روند، ولی
    #: سندِ حسابداری‌شان (بستانکارِ مالیات تکلیفی و بیمه) در دفتر می‌ماند. و اگر
    #: شماره‌ی یک فاکتورِ خدمات با شماره‌ی یک فاکتورِ کالا یکی باشد، بازگرداندنِ
    #: قیدِ قدیمی شکست می‌خورد — که درست است: آن دو دیگر یک سری نیستند.
    conn = op.get_bind()
    with rls_disabled(conn, ["document_counters"]):
        conn.execute(sa.text("DELETE FROM document_counters WHERE doc_type = 'service_purchase_invoice'"))
    op.drop_table("purchase_invoice_deductions")
    op.drop_table("purchase_deduction_types")
    op.drop_column("purchase_invoice_lines", "expense_account_id")
    op.drop_constraint("uq_purchase_invoices_tenant_kind_number", "purchase_invoices", type_="unique")
    op.create_unique_constraint(
        "uq_purchase_invoices_tenant_number", "purchase_invoices", ["tenant_id", "number"]
    )
    op.drop_column("purchase_invoices", "total_deductions")
    op.drop_constraint("ck_purchase_invoices_kind", "purchase_invoices", type_="check")
    op.drop_column("purchase_invoices", "kind")
