"""ماژول مراکز هزینه / پروژه

Revision ID: 0028
Revises: 0027

یک جدولِ تازه `cost_centers` (با RLS، همان الگوی 0026/0027) و یک ستونِ اختیاریِ
`cost_center_id` روی `journal_lines`، `sales_invoices` و `purchase_invoices`.

ستون‌ها nullable‌اند و ثبت‌های خودکارِ موجود آن‌ها را پر نمی‌کنند؛ پس این مهاجرت
هیچ داده‌ی قدیمی را نمی‌شکند — فقط امکانِ برچسب‌زدنِ سندهای تازه را اضافه می‌کند.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.tenancy import policy_name

revision: str = "0028"
down_revision: Union[str, None] = "0027"
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
        "cost_centers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("code", sa.String(30), nullable=False, server_default=""),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("notes", sa.Text, nullable=False, server_default=""),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_index("ix_cost_centers_tenant_id", "cost_centers", ["tenant_id"])

    op.add_column(
        "journal_lines",
        sa.Column("cost_center_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cost_centers.id"), nullable=True),
    )
    op.create_index("ix_journal_lines_cost_center_id", "journal_lines", ["cost_center_id"])
    op.add_column(
        "sales_invoices",
        sa.Column("cost_center_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cost_centers.id"), nullable=True),
    )
    op.add_column(
        "purchase_invoices",
        sa.Column("cost_center_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cost_centers.id"), nullable=True),
    )

    conn = op.get_bind()
    _enable_rls(conn, "cost_centers")


def downgrade() -> None:
    op.drop_column("purchase_invoices", "cost_center_id")
    op.drop_column("sales_invoices", "cost_center_id")
    op.drop_index("ix_journal_lines_cost_center_id", table_name="journal_lines")
    op.drop_column("journal_lines", "cost_center_id")
    op.drop_table("cost_centers")
