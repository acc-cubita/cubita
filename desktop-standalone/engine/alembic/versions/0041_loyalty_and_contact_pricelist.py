"""عمیق‌سازی — لیستِ قیمتِ پیش‌فرضِ مشتری و تنظیماتِ کسبِ خودکارِ امتیاز

Revision ID: 0041
Revises: 0040

  الف) ستونِ `default_price_list_id` روی `contacts` (اختیاری) — لیستِ قیمتِ هر مشتری.
  ب) جدولِ `loyalty_settings` (یک ردیف به‌ازای هر مستأجر) برای کسبِ خودکارِ امتیاز.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.tenancy import policy_name

revision: str = "0041"
down_revision: Union[str, None] = "0040"
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
    op.add_column(
        "contacts",
        sa.Column("default_price_list_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("price_lists.id"), nullable=True),
    )

    op.create_table(
        "loyalty_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("amount_per_point", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.UniqueConstraint("tenant_id", name="uq_loyalty_settings_tenant"),
    )
    op.create_index("ix_loyalty_settings_tenant_id", "loyalty_settings", ["tenant_id"])

    conn = op.get_bind()
    _enable_rls(conn, "loyalty_settings")


def downgrade() -> None:
    op.drop_table("loyalty_settings")
    op.drop_column("contacts", "default_price_list_id")
