"""ماژول اسناد تکرارشونده

Revision ID: 0033
Revises: 0032

دو جدولِ تازه (هر دو با RLS، همان الگوی 0026/0027/0028/0032):

- `recurring_journal_entries`: قالبِ یک سندِ دوره‌ای (اجاره، بیمه، استهلاکِ ثابت و
  مانند آن‌ها) با تناوب (هفتگی/ماهانه/سالانه × فاصله)، تاریخِ شروع/پایان، و
  `next_run_date` که «سررسیدِ بعدی» را نگه می‌دارد.
- `recurring_journal_lines`: ردیف‌های ثابتِ سند (حساب + بدهکار/بستانکار).

تولید **بر اساس تقاضا** است (اندپوینت «تولید سررسیدها»)، نه زمان‌بندِ پس‌زمینه:
با هر اجرا همه‌ی سررسیدهای گذشته تا امروز ساخته می‌شوند و `next_run_date` جلو
می‌رود؛ چون این تاریخ ذخیره می‌شود، اجرای دوباره سندِ تکراری نمی‌سازد.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.tenancy import policy_name

revision: str = "0033"
down_revision: Union[str, None] = "0032"
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
        "recurring_journal_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("frequency", sa.String(20), nullable=False),
        sa.Column("interval", sa.Integer, nullable=False, server_default="1"),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=True),
        sa.Column("next_run_date", sa.Date, nullable=False),
        sa.Column("last_run_date", sa.Date, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("cost_center_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cost_centers.id"), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_index("ix_recurring_journal_entries_tenant_id", "recurring_journal_entries", ["tenant_id"])

    op.create_table(
        "recurring_journal_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recurring_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("recurring_journal_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("debit", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("credit", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
    )
    op.create_index("ix_recurring_journal_lines_tenant_id", "recurring_journal_lines", ["tenant_id"])
    op.create_index("ix_recurring_journal_lines_recurring_id", "recurring_journal_lines", ["recurring_id"])

    conn = op.get_bind()
    _enable_rls(conn, "recurring_journal_entries")
    _enable_rls(conn, "recurring_journal_lines")


def downgrade() -> None:
    op.drop_table("recurring_journal_lines")
    op.drop_table("recurring_journal_entries")
