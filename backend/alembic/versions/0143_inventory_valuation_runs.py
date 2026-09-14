"""قیمت‌گذاری اسناد انبار — اجرای ثبت‌شده و اصلاحِ بهای حرکات (نوبتِ دومِ فصل).

* `inventory_valuation_runs`: هر اجرای ثبت‌شده — دامنه، توکنِ دفتر، جمع‌ها، سندِ اصلاحی و ابطال.
* `inventory_valuation_adjustments`: بهای قبل و بعدِ هر حرکتِ اصلاح‌شده. دفترِ موجودی
  (`stock_ledger`) دست نمی‌خورد.
* شمارنده‌ی `inventory_valuation` برای همه‌ی مستأجرها، زیرِ `rls_disabled`.

هیچ `UPDATE`ی روی داده‌ی موجود ندارد.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.migration_utils import rls_disabled
from app.tenancy import policy_name

revision: str = "0143"
down_revision: Union[str, None] = "0142"
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
        "inventory_valuation_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("date_from", sa.Date(), nullable=True),
        sa.Column("date_to", sa.Date(), nullable=False),
        sa.Column("warehouse_id", UUID(as_uuid=True), sa.ForeignKey("warehouses.id"), nullable=True),
        sa.Column("item_id", UUID(as_uuid=True), sa.ForeignKey("items.id"), nullable=True),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("ledger_token", sa.String(80), server_default="", nullable=False),
        sa.Column("move_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("item_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_delta", sa.Numeric(18, 0), server_default="0", nullable=False),
        sa.Column("journal_entry_id", UUID(as_uuid=True), sa.ForeignKey("journal_entries.id"), nullable=True, index=True),
        sa.Column("void_entry_id", UUID(as_uuid=True), sa.ForeignKey("journal_entries.id"), nullable=True),
        sa.Column("created_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column("void_reason", sa.Text(), server_default="", nullable=False),
        sa.Column("voided_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("tenant_id", "number", name="uq_inventory_valuation_runs_tenant_number"),
    )
    _enable_rls("inventory_valuation_runs")

    op.create_table(
        "inventory_valuation_adjustments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column(
            "run_id", UUID(as_uuid=True),
            sa.ForeignKey("inventory_valuation_runs.id", ondelete="CASCADE"), nullable=False, index=True,
        ),
        sa.Column("stock_ledger_id", UUID(as_uuid=True), sa.ForeignKey("stock_ledger.id"), nullable=False, index=True),
        sa.Column("item_id", UUID(as_uuid=True), sa.ForeignKey("items.id"), nullable=False, index=True),
        sa.Column("warehouse_id", UUID(as_uuid=True), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_id", UUID(as_uuid=True), nullable=True),
        sa.Column("qty", sa.Numeric(18, 3), nullable=False),
        sa.Column("previous_cost", sa.Numeric(18, 4), nullable=False),
        sa.Column("new_cost", sa.Numeric(18, 4), nullable=False),
        sa.Column("value_delta", sa.Numeric(18, 0), nullable=False),
        sa.Column("inventory_account_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("counter_account_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=True),
        sa.Column("cost_center_id", UUID(as_uuid=True), sa.ForeignKey("cost_centers.id"), nullable=True),
    )
    _enable_rls("inventory_valuation_adjustments")

    conn = op.get_bind()
    with rls_disabled(conn, ["document_counters"]):
        conn.execute(sa.text("""
            INSERT INTO document_counters
                (id, tenant_id, doc_type, last_number, created_at, updated_at)
            SELECT gen_random_uuid(), t.id, 'inventory_valuation', 0, now(), now()
            FROM tenants t
            WHERE NOT EXISTS (
                SELECT 1 FROM document_counters dc
                WHERE dc.tenant_id = t.id AND dc.doc_type = 'inventory_valuation'
            )
        """))


def downgrade() -> None:
    #: بااتلاف پس از اولین اجرا: ردِ اصلاح‌ها می‌رود ولی سندِ اصلاحی در دفتر می‌ماند —
    #: و «بهای فعال» دوباره بهای خودِ حرکت می‌شود، پس دفتر و انبار از هم جدا می‌افتند.
    conn = op.get_bind()
    with rls_disabled(conn, ["document_counters"]):
        conn.execute(sa.text("DELETE FROM document_counters WHERE doc_type = 'inventory_valuation'"))
    op.drop_table("inventory_valuation_adjustments")
    op.drop_table("inventory_valuation_runs")
