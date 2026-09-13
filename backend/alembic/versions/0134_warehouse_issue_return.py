"""برگشتِ خروجِ انبار، و جداشدنِ برگشتِ فیزیکی از فاکتور برگشتی.

* دو جدولِ تازه: `warehouse_issue_returns` و `warehouse_issue_return_lines`.
* `sales_returns.stock_mode`: `inline` یعنی خودِ برگشت موجودی را برگردانده (همه‌ی
  برگشت‌های تا امروز — مقدارِ پیش‌فرضِ ستون روی ردیف‌های موجود می‌نشیند و هیچ `UPDATE`ی
  لازم نیست)، `issue_return` یعنی برگشتِ فیزیکی مالِ سندِ «برگشت خروج انبار» است.
* شمارنده‌ی `warehouse_issue_return` برای همه‌ی مستأجرها، زیرِ `rls_disabled`.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.migration_utils import rls_disabled
from app.tenancy import policy_name

revision: str = "0134"
down_revision: Union[str, None] = "0133"
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
    op.create_table(
        "warehouse_issue_returns",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("number", sa.BigInteger(), nullable=False, index=True),
        sa.Column("return_date", sa.Date(), nullable=False),
        sa.Column("return_type", sa.String(20), server_default="sale", nullable=False),
        sa.Column("origin", sa.String(12), server_default="direct", nullable=False),
        sa.Column("warehouse_id", UUID(as_uuid=True), sa.ForeignKey("warehouses.id"), nullable=False, index=True),
        sa.Column("deliverer_id", UUID(as_uuid=True), sa.ForeignKey("contacts.id"), nullable=True, index=True),
        sa.Column("sales_return_id", UUID(as_uuid=True), sa.ForeignKey("sales_returns.id"), nullable=True, index=True),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("journal_entry_id", UUID(as_uuid=True), sa.ForeignKey("journal_entries.id"), nullable=True, index=True),
        sa.Column("created_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column("void_reason", sa.Text(), server_default="", nullable=False),
        sa.Column("voided_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("tenant_id", "number", name="uq_warehouse_issue_returns_tenant_number"),
        sa.CheckConstraint(
            "return_type IN ('sale', 'consumption', 'other')", name="ck_warehouse_issue_returns_type"
        ),
        sa.CheckConstraint("origin IN ('direct', 'sales_return')", name="ck_warehouse_issue_returns_origin"),
    )
    _enable_rls("warehouse_issue_returns")
    op.create_table(
        "warehouse_issue_return_lines",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column(
            "return_id", UUID(as_uuid=True),
            sa.ForeignKey("warehouse_issue_returns.id", ondelete="CASCADE"), nullable=False, index=True,
        ),
        sa.Column("seq", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "warehouse_issue_line_id", UUID(as_uuid=True),
            sa.ForeignKey("warehouse_issue_lines.id"), nullable=False, index=True,
        ),
        sa.Column(
            "sales_return_line_id", UUID(as_uuid=True),
            sa.ForeignKey("sales_return_lines.id"), nullable=True, index=True,
        ),
        sa.Column("item_id", UUID(as_uuid=True), sa.ForeignKey("items.id"), nullable=False, index=True),
        sa.Column("qty", sa.Numeric(18, 3), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 4), nullable=False),
        sa.Column("account_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=True),
        sa.Column("cost_center_id", UUID(as_uuid=True), sa.ForeignKey("cost_centers.id"), nullable=True),
        sa.Column("secondary_qty", sa.Numeric(18, 3), nullable=True),
        sa.Column("secondary_unit_snapshot", sa.String(20), server_default="", nullable=False),
        sa.Column("item_code_snapshot", sa.String(50), server_default="", nullable=False),
        sa.Column("item_name_snapshot", sa.String(300), server_default="", nullable=False),
        sa.Column("unit_snapshot", sa.String(20), server_default="", nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.CheckConstraint("qty > 0", name="ck_warehouse_issue_return_lines_qty_positive"),
    )
    _enable_rls("warehouse_issue_return_lines")

    #: پیش‌فرضِ ستون روی همه‌ی ردیف‌های موجود می‌نشیند — برگشت‌های گذشته موجودی را
    #: خودشان برگردانده‌اند و همین‌طور می‌مانند. هیچ `UPDATE`ی روی جدولِ RLS‌دار نیست.
    op.add_column(
        "sales_returns", sa.Column("stock_mode", sa.String(12), server_default="inline", nullable=False)
    )
    op.create_check_constraint(
        "ck_sales_returns_stock_mode", "sales_returns", "stock_mode IN ('inline', 'issue_return')"
    )

    conn = op.get_bind()
    with rls_disabled(conn, ["document_counters"]):
        conn.execute(sa.text("""
            INSERT INTO document_counters
                (id, tenant_id, doc_type, last_number, created_at, updated_at)
            SELECT gen_random_uuid(), t.id, 'warehouse_issue_return', 0, now(), now()
            FROM tenants t
            WHERE NOT EXISTS (
                SELECT 1 FROM document_counters dc
                WHERE dc.tenant_id = t.id AND dc.doc_type = 'warehouse_issue_return'
            )
        """))


def downgrade() -> None:
    #: بعد از اولین برگشتِ واقعی بااتلاف است: جدول‌ها و حرکت‌هایشان در دفترِ انبار
    #: می‌مانند ولی سندشان می‌رود. و برگشتِ `issue_return` پس از بازگشت «inline» خوانده
    #: نمی‌شود — ستونش دیگر نیست.
    conn = op.get_bind()
    with rls_disabled(conn, ["document_counters"]):
        conn.execute(sa.text("DELETE FROM document_counters WHERE doc_type = 'warehouse_issue_return'"))
    op.drop_constraint("ck_sales_returns_stock_mode", "sales_returns", type_="check")
    op.drop_column("sales_returns", "stock_mode")
    op.drop_table("warehouse_issue_return_lines")
    op.drop_table("warehouse_issue_returns")
