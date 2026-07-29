"""باشگاه مشتریان / CRM — سرنخ‌ها، پیگیری‌ها و امتیازِ وفاداری

Revision ID: 0037
Revises: 0036

سه جدولِ مستأجرمحور که مثلِ بقیه زیرِ RLS می‌روند. بدونِ RLS، تستِ ایزوله‌سازی قرمز
می‌شود و دادهٔ یک کسب‌وکار به کسب‌وکارِ دیگر نشت می‌کند.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.tenancy import policy_name

revision: str = "0037"
down_revision: Union[str, None] = "0036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ("crm_leads", "crm_activities", "crm_loyalty_transactions")


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
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    ]


def upgrade() -> None:
    op.create_table(
        "crm_leads",
        *_tenant_cols(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("phone", sa.String(30), nullable=False, server_default=""),
        sa.Column("email", sa.String(150), nullable=False, server_default=""),
        sa.Column("company", sa.String(200), nullable=False, server_default=""),
        sa.Column("source", sa.String(80), nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="new"),
        sa.Column("estimated_value", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text, nullable=False, server_default=""),
        sa.Column("next_action_date", sa.Date, nullable=True),
        sa.Column("assigned_to_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("converted_contact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contacts.id"), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_index("ix_crm_leads_tenant_id", "crm_leads", ["tenant_id"])

    op.create_table(
        "crm_activities",
        *_tenant_cols(),
        sa.Column("kind", sa.String(20), nullable=False, server_default="call"),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("body", sa.Text, nullable=False, server_default=""),
        sa.Column("activity_date", sa.Date, nullable=False),
        sa.Column("done", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("crm_leads.id", ondelete="CASCADE"), nullable=True),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contacts.id"), nullable=True),
        sa.Column("assigned_to_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_index("ix_crm_activities_tenant_id", "crm_activities", ["tenant_id"])
    op.create_index("ix_crm_activities_lead_id", "crm_activities", ["lead_id"])
    op.create_index("ix_crm_activities_contact_id", "crm_activities", ["contact_id"])

    op.create_table(
        "crm_loyalty_transactions",
        *_tenant_cols(),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contacts.id"), nullable=False),
        sa.Column("points", sa.Integer, nullable=False, server_default="0"),
        sa.Column("reason", sa.String(200), nullable=False, server_default=""),
        sa.Column("txn_date", sa.Date, nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_index("ix_crm_loyalty_transactions_tenant_id", "crm_loyalty_transactions", ["tenant_id"])
    op.create_index("ix_crm_loyalty_transactions_contact_id", "crm_loyalty_transactions", ["contact_id"])

    conn = op.get_bind()
    for t in TABLES:
        _enable_rls(conn, t)


def downgrade() -> None:
    op.drop_table("crm_loyalty_transactions")
    op.drop_table("crm_activities")
    op.drop_table("crm_leads")
