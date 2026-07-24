"""ماژول دارایی‌های ثابت و استهلاک

Revision ID: 0026
Revises: 0025

دو جدول تازه: `fixed_assets` (اقلام دارایی) و `depreciation_entries` (سندِ هر دوره
استهلاک). چون بعد از مهاجرتِ چند‌مستأجری (0015) اضافه می‌شوند، RLS و سیاست جداسازی
باید همین‌جا صریح راه بیفتد — همان الگوی 0023.

حساب‌های ۱۲۰۱ (دارایی ثابت)، ۱۲۰۲ (استهلاک انباشته) و ۵۱۰۶ (هزینه استهلاک) هنگام
اولین استفاده توسط سرویس ساخته می‌شوند (get_or_create_account)، پس اینجا لازم نیست.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.tenancy import policy_name

revision: str = "0026"
down_revision: Union[str, None] = "0025"
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
        "fixed_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("category", sa.String(100), nullable=False, server_default=""),
        sa.Column("acquired_date", sa.Date, nullable=False),
        sa.Column("cost", sa.Numeric(18, 0), nullable=False),
        sa.Column("salvage_value", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("useful_life_months", sa.Integer, nullable=False),
        sa.Column("method", sa.String(20), nullable=False, server_default="straight_line"),
        sa.Column("accumulated_depreciation", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("is_disposed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("disposed_date", sa.Date, nullable=True),
        sa.Column("notes", sa.Text, nullable=False, server_default=""),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.CheckConstraint("method IN ('straight_line')", name="ck_fixed_assets_method"),
        sa.CheckConstraint("cost >= 0 AND salvage_value >= 0", name="ck_fixed_assets_amounts_nonneg"),
        sa.CheckConstraint("useful_life_months > 0", name="ck_fixed_assets_life_positive"),
        sa.CheckConstraint("salvage_value <= cost", name="ck_fixed_assets_salvage_le_cost"),
    )
    op.create_index("ix_fixed_assets_tenant_id", "fixed_assets", ["tenant_id"])
    op.create_index("ix_fixed_assets_acquired_date", "fixed_assets", ["acquired_date"])

    op.create_table(
        "depreciation_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fixed_assets.id"), nullable=False),
        sa.Column("period_date", sa.Date, nullable=False),
        sa.Column("amount", sa.Numeric(18, 0), nullable=False),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("journal_entries.id"), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.UniqueConstraint("tenant_id", "asset_id", "period_date", name="uq_depreciation_asset_period"),
    )
    op.create_index("ix_depreciation_entries_tenant_id", "depreciation_entries", ["tenant_id"])
    op.create_index("ix_depreciation_entries_period_date", "depreciation_entries", ["period_date"])

    conn = op.get_bind()
    _enable_rls(conn, "fixed_assets")
    _enable_rls(conn, "depreciation_entries")


def downgrade() -> None:
    op.drop_table("depreciation_entries")
    op.drop_table("fixed_assets")
