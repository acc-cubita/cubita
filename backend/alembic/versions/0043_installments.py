"""فروش اقساطی — قرارداد و اقساط

Revision ID: 0043
Revises: 0042

دو جدولِ مستأجرمحور با RLS (`installment_plans`, `installments`) + شمارنده‌ی
`installment_plan` (بک‌فیل برای مستأجرهای موجود).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.migration_utils import rls_disabled
from app.tenancy import policy_name

revision: str = "0043"
down_revision: Union[str, None] = "0042"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ("installment_plans", "installments")


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


def _tenant_cols() -> list[sa.Column]:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    ]


def upgrade() -> None:
    op.create_table(
        "installment_plans",
        *_tenant_cols(),
        sa.Column("number", sa.Integer, nullable=True),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contacts.id"), nullable=False),
        sa.Column("sales_invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sales_invoices.id"), nullable=True),
        sa.Column("title", sa.String(200), nullable=False, server_default=""),
        sa.Column("total_amount", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("down_payment", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("num_installments", sa.Integer, nullable=False, server_default="1"),
        sa.Column("interval_months", sa.Integer, nullable=False, server_default="1"),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("notes", sa.Text, nullable=False, server_default=""),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_index("ix_installment_plans_tenant_id", "installment_plans", ["tenant_id"])
    op.create_index("ix_installment_plans_number", "installment_plans", ["number"])
    op.create_index("ix_installment_plans_contact_id", "installment_plans", ["contact_id"])

    op.create_table(
        "installments",
        *_tenant_cols(),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("installment_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seq", sa.Integer, nullable=False),
        sa.Column("due_date", sa.Date, nullable=False),
        sa.Column("amount", sa.Numeric(18, 0), nullable=False),
        sa.Column("paid_amount", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("paid_date", sa.Date, nullable=True),
    )
    op.create_index("ix_installments_tenant_id", "installments", ["tenant_id"])
    op.create_index("ix_installments_plan_id", "installments", ["plan_id"])

    conn = op.get_bind()
    for t in TABLES:
        _enable_rls(conn, t)

    # شمارنده‌ی «قرارداد اقساط» را برای مستأجرهای موجود بک‌فیل کن.
    with rls_disabled(conn, ["document_counters"]):
        conn.execute(
            sa.text(
                "INSERT INTO document_counters (id, tenant_id, doc_type, last_number, created_at, updated_at) "
                "SELECT gen_random_uuid(), t.id, 'installment_plan', 0, now(), now() FROM tenants t "
                "WHERE NOT EXISTS ("
                "  SELECT 1 FROM document_counters dc WHERE dc.tenant_id = t.id AND dc.doc_type = 'installment_plan'"
                ")"
            )
        )


def downgrade() -> None:
    op.drop_table("installments")
    op.drop_table("installment_plans")
