"""فاکتور خرید تجاری و رسید مستقل ورود فیزیکی."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.tenancy import policy_name

revision: str = "0113"
down_revision: Union[str, None] = "0112"
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
    op.alter_column("purchase_invoices", "warehouse_id", existing_type=UUID(as_uuid=True), nullable=True)
    op.add_column("purchase_invoices", sa.Column("supplier_invoice_number", sa.String(80), server_default="", nullable=False))
    op.add_column("purchase_invoices", sa.Column("description2", sa.String(200), server_default="", nullable=False))
    op.add_column("purchase_invoices", sa.Column("total_additions", sa.Numeric(18, 0), server_default="0", nullable=False))
    op.add_column("purchase_invoices", sa.Column("total_duties", sa.Numeric(18, 0), server_default="0", nullable=False))

    for name, column in (
        ("item_code_snapshot", sa.Column("item_code_snapshot", sa.String(50), server_default="", nullable=False)),
        ("item_name_snapshot", sa.Column("item_name_snapshot", sa.String(300), server_default="", nullable=False)),
        ("unit_snapshot", sa.Column("unit_snapshot", sa.String(20), server_default="", nullable=False)),
        ("addition", sa.Column("addition", sa.Numeric(18, 0), server_default="0", nullable=False)),
        ("duty_amount", sa.Column("duty_amount", sa.Numeric(18, 0), server_default="0", nullable=False)),
        ("tax_rate_snapshot", sa.Column("tax_rate_snapshot", sa.Numeric(5, 2), server_default="0", nullable=False)),
        ("tax_amount_snapshot", sa.Column("tax_amount_snapshot", sa.Numeric(18, 0), server_default="0", nullable=False)),
    ):
        op.add_column("purchase_invoice_lines", column)

    op.create_table(
        "warehouse_receipts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("number", sa.BigInteger(), nullable=False, index=True),
        sa.Column("receipt_date", sa.Date(), nullable=False),
        sa.Column("purchase_invoice_id", UUID(as_uuid=True), sa.ForeignKey("purchase_invoices.id"), nullable=False, index=True),
        sa.Column("warehouse_id", UUID(as_uuid=True), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("status", sa.String(20), server_default="posted", nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("created_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column("void_reason", sa.Text(), server_default="", nullable=False),
        sa.Column("voided_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("tenant_id", "number", name="uq_warehouse_receipts_tenant_number"),
    )
    _enable_rls("warehouse_receipts")
    op.create_table(
        "warehouse_receipt_lines",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("receipt_id", UUID(as_uuid=True), sa.ForeignKey("warehouse_receipts.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("purchase_invoice_line_id", UUID(as_uuid=True), sa.ForeignKey("purchase_invoice_lines.id"), nullable=False, index=True),
        sa.Column("item_id", UUID(as_uuid=True), sa.ForeignKey("items.id"), nullable=False, index=True),
        sa.Column("qty", sa.Numeric(18, 3), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 0), nullable=False),
        sa.Column("item_code_snapshot", sa.String(50), server_default="", nullable=False),
        sa.Column("item_name_snapshot", sa.String(300), server_default="", nullable=False),
        sa.Column("unit_snapshot", sa.String(20), server_default="", nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.CheckConstraint("qty > 0", name="ck_warehouse_receipt_lines_qty_positive"),
    )
    _enable_rls("warehouse_receipt_lines")


def downgrade() -> None:
    op.drop_table("warehouse_receipt_lines")
    op.drop_table("warehouse_receipts")
    for name in (
        "tax_amount_snapshot", "tax_rate_snapshot", "duty_amount", "addition",
        "unit_snapshot", "item_name_snapshot", "item_code_snapshot",
    ):
        op.drop_column("purchase_invoice_lines", name)
    for name in ("total_duties", "total_additions", "description2", "supplier_invoice_number"):
        op.drop_column("purchase_invoices", name)
    op.alter_column("purchase_invoices", "warehouse_id", existing_type=UUID(as_uuid=True), nullable=False)
