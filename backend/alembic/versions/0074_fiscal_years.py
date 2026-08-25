"""سال مالی — تعریفِ رسمیِ دوره‌ی حسابداری

Revision ID: 0074
Revises: 0073

جدولِ مستأجرمحورِ `fiscal_years` با RLS. عمداً هیچ بک‌فیلی ندارد: حساب‌های موجود
بدونِ سالِ مالی می‌مانند و سرویس در آن حالت هیچ محدودیتی روی تاریخِ اسناد نمی‌گذارد،
پس ارتقا برای هیچ‌کس رفتارِ ثبتِ سند را عوض نمی‌کند. محدودیت فقط از لحظه‌ای شروع
می‌شود که خودِ کاربر اولین سالِ مالی را تعریف کند.

هم‌پوشانی‌نداشتنِ بازه‌ها و «حداکثر یک سالِ جاری» در سرویس تضمین می‌شوند، نه با قیدِ
دیتابیس (مقایسه‌ی بازه‌ای به EXCLUDE/btree_gist نیاز دارد و ارزشِ افزوده‌اش کم است).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.tenancy import policy_name

revision: str = "0074"
down_revision: Union[str, None] = "0073"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "fiscal_years"


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
        TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("title", sa.String(60), nullable=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="open"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text, nullable=False, server_default=""),
        sa.Column(
            "opening_entry_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("journal_entries.id"),
            nullable=True,
        ),
        sa.Column(
            "closing_entry_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("journal_entries.id"),
            nullable=True,
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint("tenant_id", "title", name="uq_fiscal_years_tenant_title"),
    )
    op.create_index("ix_fiscal_years_tenant_range", TABLE, ["tenant_id", "start_date", "end_date"])

    conn = op.get_bind()
    _enable_rls(conn, TABLE)


def downgrade() -> None:
    op.drop_index("ix_fiscal_years_tenant_range", table_name=TABLE)
    op.drop_table(TABLE)
