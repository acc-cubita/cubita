"""payroll: employees, salary contracts, payroll periods, attendance, payslips, payroll settings

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "employees",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("national_id", sa.String(20), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("email", sa.String(150), nullable=True),
        sa.Column("bank_account_number", sa.String(50), nullable=False, server_default=""),
        sa.Column("hire_date", sa.Date, nullable=False),
        sa.Column("termination_date", sa.Date, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("national_id"),
    )
    op.create_index("ix_employees_national_id", "employees", ["national_id"])

    op.create_table(
        "salary_contracts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("effective_from", sa.Date, nullable=False),
        sa.Column("base_salary", sa.Numeric(18, 0), nullable=False),
        sa.Column("housing_allowance", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("food_allowance", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("other_allowance", sa.Numeric(18, 0), nullable=False, server_default="0"),
    )
    op.create_index("ix_salary_contracts_employee_id", "salary_contracts", ["employee_id"])

    op.create_table(
        "payroll_periods",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("month", sa.Integer, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.UniqueConstraint("year", "month", name="uq_payroll_periods_year_month"),
        sa.CheckConstraint("status IN ('draft','finalized')", name="ck_payroll_periods_status"),
        sa.CheckConstraint("month BETWEEN 1 AND 12", name="ck_payroll_periods_month_range"),
    )

    op.create_table(
        "attendance",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("period_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("payroll_periods.id"), nullable=False),
        sa.Column("worked_days", sa.Numeric(5, 2), nullable=False, server_default="30"),
        sa.Column("absent_days", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("overtime_hours", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.UniqueConstraint("employee_id", "period_id", name="uq_attendance_employee_period"),
    )
    op.create_index("ix_attendance_employee_id", "attendance", ["employee_id"])
    op.create_index("ix_attendance_period_id", "attendance", ["period_id"])

    op.execute("CREATE SEQUENCE payslip_number_seq START 1")

    op.create_table(
        "payslips",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("number", sa.Integer, nullable=True),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("period_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("payroll_periods.id"), nullable=False),
        sa.Column("base_salary", sa.Numeric(18, 0), nullable=False),
        sa.Column("allowances_total", sa.Numeric(18, 0), nullable=False),
        sa.Column("overtime_pay", sa.Numeric(18, 0), nullable=False),
        sa.Column("gross_pay", sa.Numeric(18, 0), nullable=False),
        sa.Column("insurance_employee_share", sa.Numeric(18, 0), nullable=False),
        sa.Column("insurance_employer_share", sa.Numeric(18, 0), nullable=False),
        sa.Column("taxable_pay", sa.Numeric(18, 0), nullable=False),
        sa.Column("tax_amount", sa.Numeric(18, 0), nullable=False),
        sa.Column("net_pay", sa.Numeric(18, 0), nullable=False),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("journal_entries.id"), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.UniqueConstraint("number"),
        sa.UniqueConstraint("employee_id", "period_id", name="uq_payslips_employee_period"),
    )
    op.create_index("ix_payslips_number", "payslips", ["number"])
    op.create_index("ix_payslips_employee_id", "payslips", ["employee_id"])
    op.create_index("ix_payslips_period_id", "payslips", ["period_id"])

    op.create_table(
        "payroll_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("insurance_employee_rate", sa.Numeric(5, 4), nullable=False),
        sa.Column("insurance_employer_rate", sa.Numeric(5, 4), nullable=False),
        sa.Column("tax_exemption_annual", sa.Numeric(18, 0), nullable=False),
        sa.Column("tax_brackets", postgresql.JSONB, nullable=False),
        sa.Column("notes", sa.Text, nullable=False, server_default=""),
        sa.UniqueConstraint("year"),
    )


def downgrade() -> None:
    op.drop_table("payroll_settings")
    op.drop_table("payslips")
    op.execute("DROP SEQUENCE payslip_number_seq")
    op.drop_table("attendance")
    op.drop_table("payroll_periods")
    op.drop_table("salary_contracts")
    op.drop_table("employees")
