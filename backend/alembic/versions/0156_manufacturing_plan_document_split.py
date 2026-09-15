"""تولید — تفکیکِ سفارش (برنامه) از سند (اجرا).

* `production_plans`: سفارشِ تولید — فقط برنامه‌ریزی (فرمول، انبار، تاریخ، مقدار)،
  بدونِ ستونِ بها یا اثرِ انبار. جدولِ تازه، بی ردیف در لحظه‌ی ساخت.
* `production_orders.production_plan_id`: FKِ اختیاری از سندِ تولید (اجرا) به
  سفارشِ مبنا — جدولِ **موجود با ردیفِ واقعی**، پس زیرِ `rls_disabled` می‌رود
  (باگِ مستندِ اعتبارسنجیِ FK روی PG14، توضیحِ کامل در `app/migration_utils.py`).
* شمارنده‌ی `production_plan` برای همه‌ی مستأجرها، زیرِ `rls_disabled` (الگوی `0155`).

هیچ `UPDATE`ی روی داده‌ی موجودِ `production_orders` ندارد — فقط یک ستونِ تازه‌ی
`NULL`پذیر اضافه می‌شود.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.migration_utils import rls_disabled
from app.tenancy import policy_name

revision: str = "0156"
down_revision: Union[str, None] = "0155"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PRODUCTION_PLAN_STATUSES = ("draft", "started", "in_progress", "stopped", "finished", "cancelled")


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
        "production_plans",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("number", sa.Integer(), nullable=False, index=True),
        sa.Column("bom_id", UUID(as_uuid=True), sa.ForeignKey("boms.id"), nullable=False),
        sa.Column("finished_item_id", UUID(as_uuid=True), sa.ForeignKey("items.id"), nullable=False, index=True),
        sa.Column("warehouse_id", UUID(as_uuid=True), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("planned_date", sa.Date(), nullable=False),
        sa.Column("qty_planned", sa.Numeric(18, 3), nullable=False),
        sa.Column("qty_produced", sa.Numeric(18, 3), server_default="0", nullable=False),
        sa.Column("status", sa.String(20), server_default="draft", nullable=False),
        sa.Column("notes", sa.Text(), server_default="", nullable=False),
        sa.Column("created_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(f"status IN {PRODUCTION_PLAN_STATUSES}", name="ck_production_plans_status"),
    )
    _enable_rls("production_plans")

    conn = op.get_bind()

    #: جدولِ `production_orders` ردیفِ واقعی دارد — افزودنِ ستونی با FKِ درون‌خطی
    #: باید زیرِ `rls_disabled` برود، وگرنه اعتبارسنجیِ خودکارِ Postgres روی PG14
    #: به سیاستِ RLS می‌خورد و با `invalid input syntax for type uuid: ""` می‌شکند.
    with rls_disabled(conn, ["production_orders", "production_plans"]):
        op.add_column(
            "production_orders",
            sa.Column(
                "production_plan_id",
                UUID(as_uuid=True),
                sa.ForeignKey("production_plans.id"),
                nullable=True,
            ),
        )
    op.create_index(
        "ix_production_orders_production_plan_id", "production_orders", ["production_plan_id"]
    )

    with rls_disabled(conn, ["document_counters"]):
        conn.execute(sa.text("""
            INSERT INTO document_counters
                (id, tenant_id, doc_type, last_number, created_at, updated_at)
            SELECT gen_random_uuid(), t.id, 'production_plan', 0, now(), now()
            FROM tenants t
            WHERE NOT EXISTS (
                SELECT 1 FROM document_counters dc
                WHERE dc.tenant_id = t.id AND dc.doc_type = 'production_plan'
            )
        """))


def downgrade() -> None:
    conn = op.get_bind()
    with rls_disabled(conn, ["document_counters"]):
        conn.execute(sa.text("DELETE FROM document_counters WHERE doc_type = 'production_plan'"))
    op.drop_index("ix_production_orders_production_plan_id", table_name="production_orders")
    op.drop_column("production_orders", "production_plan_id")
    op.drop_table("production_plans")
