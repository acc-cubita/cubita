"""فاکتور فروش تجاری، سند فروش و خروج مستقل انبار."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.migration_utils import rls_disabled
from app.tenancy import policy_name

revision: str = "0116"
down_revision: Union[str, None] = "0115"
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
    op.alter_column("sales_invoices", "warehouse_id", existing_type=UUID(as_uuid=True), nullable=True)
    for column in (
        sa.Column("customer_snapshot", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("seller_snapshot", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("customer_name2", sa.String(200), server_default="", nullable=False),
        sa.Column("delivery_location", sa.Text(), server_default="", nullable=False),
        sa.Column("receivable_account_id", UUID(as_uuid=True), nullable=True),
        sa.Column("settlement_terms", sa.String(10), server_default="credit", nullable=False),
        sa.Column("statement_date", sa.Date(), nullable=True),
        sa.Column("total_additions", sa.Numeric(18, 0), server_default="0", nullable=False),
        sa.Column("total_duties", sa.Numeric(18, 0), server_default="0", nullable=False),
    ):
        op.add_column("sales_invoices", column)
    op.create_foreign_key(
        "fk_sales_invoices_receivable_account", "sales_invoices", "accounts",
        ["receivable_account_id"], ["id"],
    )
    op.create_check_constraint(
        "ck_sales_invoices_settlement_terms", "sales_invoices",
        "settlement_terms IN ('cash', 'credit', 'mixed')",
    )

    for column in (
        sa.Column("addition", sa.Numeric(18, 0), server_default="0", nullable=False),
        sa.Column("duty_amount", sa.Numeric(18, 0), server_default="0", nullable=False),
        sa.Column("item_code_snapshot", sa.String(50), server_default="", nullable=False),
        sa.Column("item_name_snapshot", sa.String(300), server_default="", nullable=False),
        sa.Column("unit_snapshot", sa.String(20), server_default="", nullable=False),
        sa.Column("tax_rate_snapshot", sa.Numeric(5, 2), server_default="0", nullable=False),
        sa.Column("tax_amount_snapshot", sa.Numeric(18, 0), server_default="0", nullable=False),
    ):
        op.add_column("sales_invoice_lines", column)

    for name in (
        "goods_revenue_account_id", "service_revenue_account_id",
        "goods_discount_account_id", "service_discount_account_id",
        "addition_account_id",
    ):
        op.add_column("sale_types", sa.Column(name, UUID(as_uuid=True), nullable=True))
        op.create_foreign_key(f"fk_sale_types_{name}", "sale_types", "accounts", [name], ["id"])

    op.create_table(
        "warehouse_issues",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("number", sa.BigInteger(), nullable=False, index=True),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("sales_invoice_id", UUID(as_uuid=True), sa.ForeignKey("sales_invoices.id"), nullable=False, index=True),
        sa.Column("warehouse_id", UUID(as_uuid=True), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("status", sa.String(20), server_default="posted", nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("journal_entry_id", UUID(as_uuid=True), sa.ForeignKey("journal_entries.id"), nullable=True, index=True),
        sa.Column("created_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column("void_reason", sa.Text(), server_default="", nullable=False),
        sa.Column("voided_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("tenant_id", "number", name="uq_warehouse_issues_tenant_number"),
    )
    _enable_rls("warehouse_issues")
    op.create_table(
        "warehouse_issue_lines",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("issue_id", UUID(as_uuid=True), sa.ForeignKey("warehouse_issues.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("sales_invoice_line_id", UUID(as_uuid=True), sa.ForeignKey("sales_invoice_lines.id"), nullable=False, index=True),
        sa.Column("item_id", UUID(as_uuid=True), sa.ForeignKey("items.id"), nullable=False, index=True),
        sa.Column("qty", sa.Numeric(18, 3), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 0), nullable=False),
        sa.Column("item_code_snapshot", sa.String(50), server_default="", nullable=False),
        sa.Column("item_name_snapshot", sa.String(300), server_default="", nullable=False),
        sa.Column("unit_snapshot", sa.String(20), server_default="", nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.CheckConstraint("qty > 0", name="ck_warehouse_issue_lines_qty_positive"),
    )
    _enable_rls("warehouse_issue_lines")

    conn = op.get_bind()
    with rls_disabled(conn, ["document_counters"]):
        conn.execute(sa.text("""
            INSERT INTO document_counters
                (id, tenant_id, doc_type, last_number, created_at, updated_at)
            SELECT gen_random_uuid(), t.id, d.doc_type, 0, now(), now()
            FROM tenants t
            CROSS JOIN (VALUES ('warehouse_receipt'), ('warehouse_issue')) AS d(doc_type)
            WHERE NOT EXISTS (
                SELECT 1 FROM document_counters dc
                WHERE dc.tenant_id = t.id AND dc.doc_type = d.doc_type
            )
        """))


def downgrade() -> None:
    conn = op.get_bind()
    with rls_disabled(conn, ["document_counters"]):
        conn.execute(sa.text("DELETE FROM document_counters WHERE doc_type = 'warehouse_issue'"))
    op.drop_table("warehouse_issue_lines")
    op.drop_table("warehouse_issues")
    for name in (
        "addition_account_id", "service_discount_account_id", "goods_discount_account_id",
        "service_revenue_account_id", "goods_revenue_account_id",
    ):
        op.drop_constraint(f"fk_sale_types_{name}", "sale_types", type_="foreignkey")
        op.drop_column("sale_types", name)
    for name in (
        "tax_amount_snapshot", "tax_rate_snapshot", "unit_snapshot", "item_name_snapshot",
        "item_code_snapshot", "duty_amount", "addition",
    ):
        op.drop_column("sales_invoice_lines", name)
    op.drop_constraint("ck_sales_invoices_settlement_terms", "sales_invoices", type_="check")
    op.drop_constraint("fk_sales_invoices_receivable_account", "sales_invoices", type_="foreignkey")
    for name in (
        "total_duties", "total_additions", "statement_date", "settlement_terms",
        "receivable_account_id", "delivery_location", "customer_name2", "seller_snapshot", "customer_snapshot",
    ):
        op.drop_column("sales_invoices", name)
    op.alter_column("sales_invoices", "warehouse_id", existing_type=UUID(as_uuid=True), nullable=False)
