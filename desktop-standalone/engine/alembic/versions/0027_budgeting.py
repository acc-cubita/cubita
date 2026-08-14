"""ماژول بودجه‌بندی

Revision ID: 0027
Revises: 0026

یک جدولِ تازه: `budget_lines` (بودجه‌ی هر حساب برای هر ماه). چون بعد از مهاجرتِ
چند‌مستأجری (0015) اضافه می‌شود، RLS و سیاست جداسازی باید همین‌جا صریح راه بیفتد —
همان الگوی 0023 و 0026.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.tenancy import policy_name

revision: str = "0027"
down_revision: Union[str, None] = "0026"
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
        "budget_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("period_date", sa.Date, nullable=False),
        sa.Column("amount", sa.Numeric(18, 0), nullable=False),
        sa.Column("notes", sa.Text, nullable=False, server_default=""),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.UniqueConstraint("tenant_id", "account_id", "period_date", name="uq_budget_account_period"),
    )
    op.create_index("ix_budget_lines_tenant_id", "budget_lines", ["tenant_id"])
    op.create_index("ix_budget_lines_period_date", "budget_lines", ["period_date"])

    conn = op.get_bind()
    _enable_rls(conn, "budget_lines")


def downgrade() -> None:
    op.drop_table("budget_lines")
