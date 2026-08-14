"""تکمیل حقوق و دستمزد — عیدی، سنوات، مرخصی

Revision ID: 0035
Revises: 0034

سه افزوده روی ماژول حقوق:
- دو ستون روی `payroll_settings`: `min_base_wage` (حداقل حقوق ماهانه‌ی همان سال —
  پایه‌ی سقف/کفِ عیدی) و `annual_leave_days` (روزهای مرخصی استحقاقیِ سالانه، پیش‌فرض ۲۶).
- جدول `leave_records`: مرخصی‌های استفاده‌شده‌ی هر کارمند (برای محاسبه‌ی مانده و طلبِ مرخصی).
- جدول `benefit_runs`: ثبتِ صدورِ عیدی/سنوات/بازخریدِ مرخصی با ارجاع به سندِ حسابداری،
  تا دوباره صادر نشوند.

هر دو جدولِ تازه با RLS (همان الگوی 0026/…). ستون‌های `payroll_settings` با پیش‌فرض
اضافه می‌شوند، پس تنظیماتِ موجود نمی‌شکنند.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.tenancy import policy_name

revision: str = "0035"
down_revision: Union[str, None] = "0034"
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
    op.add_column("payroll_settings", sa.Column("min_base_wage", sa.Numeric(18, 0), nullable=False, server_default="0"))
    op.add_column("payroll_settings", sa.Column("annual_leave_days", sa.Integer, nullable=False, server_default="26"))

    op.create_table(
        "leave_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("leave_date", sa.Date, nullable=False),
        sa.Column("days", sa.Numeric(5, 2), nullable=False),
        sa.Column("note", sa.Text, nullable=False, server_default=""),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_index("ix_leave_records_tenant_id", "leave_records", ["tenant_id"])
    op.create_index("ix_leave_records_employee_id", "leave_records", ["employee_id"])

    op.create_table(
        "benefit_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("kind", sa.String(20), nullable=False),  # eidi | severance | leave_payout
        sa.Column("year", sa.Integer, nullable=True),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("employees.id"), nullable=True),
        sa.Column("amount", sa.Numeric(18, 0), nullable=False),
        sa.Column("run_date", sa.Date, nullable=False),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("journal_entries.id"), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_index("ix_benefit_runs_tenant_id", "benefit_runs", ["tenant_id"])

    conn = op.get_bind()
    _enable_rls(conn, "leave_records")
    _enable_rls(conn, "benefit_runs")


def downgrade() -> None:
    op.drop_table("benefit_runs")
    op.drop_table("leave_records")
    op.drop_column("payroll_settings", "annual_leave_days")
    op.drop_column("payroll_settings", "min_base_wage")
