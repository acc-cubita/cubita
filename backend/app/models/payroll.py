import uuid
from datetime import date as date_

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin

PAYROLL_PERIOD_STATUSES = ("draft", "finalized")


class Employee(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "employees"

    __table_args__ = (
        UniqueConstraint("tenant_id", "national_id", name="uq_employees_tenant_national_id"),
    )

    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    national_id: Mapped[str] = mapped_column(String(20), index=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    bank_account_number: Mapped[str] = mapped_column(String(50), default="")
    hire_date: Mapped[date_] = mapped_column(Date)
    termination_date: Mapped[date_ | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    contracts: Mapped[list["SalaryContract"]] = relationship(back_populates="employee", order_by="SalaryContract.effective_from")


class SalaryContract(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """حکم حقوقی. حکم جاری یک کارمند در تاریخ X = آخرین حکمی که effective_from آن <= X است."""

    __tablename__ = "salary_contracts"

    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), index=True)
    effective_from: Mapped[date_] = mapped_column(Date)
    base_salary: Mapped[float] = mapped_column(Numeric(18, 0))
    housing_allowance: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    food_allowance: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    other_allowance: Mapped[float] = mapped_column(Numeric(18, 0), default=0)

    employee: Mapped["Employee"] = relationship(back_populates="contracts")


class PayrollPeriod(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "payroll_periods"
    __table_args__ = (
        CheckConstraint(f"status IN {PAYROLL_PERIOD_STATUSES}", name="ck_payroll_periods_status"),
        CheckConstraint("month BETWEEN 1 AND 12", name="ck_payroll_periods_month_range"),
        UniqueConstraint("tenant_id", "year", "month", name="uq_payroll_periods_tenant_year_month"),
    )

    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="draft")


class Attendance(TenantMixin, UUIDPKMixin, Base):
    """کارکرد ماهانه‌ی ساده (حضور/غیاب دستی)؛ اتصال به دستگاه حضور و غیاب در فاز بعد."""

    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint("tenant_id", "employee_id", "period_id", name="uq_attendance_tenant_employee_id_period_id"),
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), index=True)
    period_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("payroll_periods.id"), index=True)
    worked_days: Mapped[float] = mapped_column(Numeric(5, 2), default=30)
    absent_days: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    overtime_hours: Mapped[float] = mapped_column(Numeric(6, 2), default=0)


class Payslip(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """فیش حقوقی. اعداد در لحظه‌ی صدور از روی حکم حقوقی جاری و کارکرد همان دوره محاسبه و اسنپ‌شات می‌شوند."""

    __tablename__ = "payslips"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_payslips_tenant_number"),
        UniqueConstraint("tenant_id", "employee_id", "period_id", name="uq_payslips_tenant_employee_id_period_id"),
    )

    number: Mapped[int | None] = mapped_column(nullable=True, index=True)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), index=True)
    period_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("payroll_periods.id"), index=True)

    base_salary: Mapped[float] = mapped_column(Numeric(18, 0))
    allowances_total: Mapped[float] = mapped_column(Numeric(18, 0))
    overtime_pay: Mapped[float] = mapped_column(Numeric(18, 0))
    gross_pay: Mapped[float] = mapped_column(Numeric(18, 0))
    insurance_employee_share: Mapped[float] = mapped_column(Numeric(18, 0))
    insurance_employer_share: Mapped[float] = mapped_column(Numeric(18, 0))
    taxable_pay: Mapped[float] = mapped_column(Numeric(18, 0))
    tax_amount: Mapped[float] = mapped_column(Numeric(18, 0))
    net_pay: Mapped[float] = mapped_column(Numeric(18, 0))

    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))


class PayrollSettings(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """نرخ‌های بیمه/مالیات حقوق. این نرخ‌ها هرسال طبق قانون بودجه/تأمین اجتماعی تغییر می‌کنند —
    مقادیر seed شده صرفاً placeholder هستند و باید قبل از صدور فیش واقعی توسط کاربر تأیید/ویرایش شوند."""

    __tablename__ = "payroll_settings"

    __table_args__ = (
        UniqueConstraint("tenant_id", "year", name="uq_payroll_settings_tenant_year"),
    )

    year: Mapped[int] = mapped_column(Integer)
    insurance_employee_rate: Mapped[float] = mapped_column(Numeric(5, 4))
    insurance_employer_rate: Mapped[float] = mapped_column(Numeric(5, 4))
    tax_exemption_annual: Mapped[float] = mapped_column(Numeric(18, 0))
    # لیست پلکان مالیات سالانه: [{"up_to": <سقف تجمعی یا null برای نامحدود>, "rate": <نرخ 0..1>}, ...] به ترتیب صعودی
    tax_brackets: Mapped[list] = mapped_column(JSONB)
    #: حداقل حقوق ماهانه‌ی مصوبِ همان سال — پایه‌ی سقف/کفِ عیدی (۲ تا ۳ برابر). صفر = بدون سقف.
    min_base_wage: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    #: روزهای مرخصی استحقاقیِ سالانه (قانون کار: ۲۶ روز کاری).
    annual_leave_days: Mapped[int] = mapped_column(Integer, default=26, server_default="26")
    notes: Mapped[str] = mapped_column(Text, default="")


class LeaveRecord(TenantMixin, UUIDPKMixin, Base):
    """یک مرخصیِ استفاده‌شده. مانده‌ی مرخصی = استحقاقی − جمعِ همین رکوردها در همان سال."""

    __tablename__ = "leave_records"

    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), index=True)
    leave_date: Mapped[date_] = mapped_column(Date)
    days: Mapped[float] = mapped_column(Numeric(5, 2))
    note: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))


class BenefitRun(TenantMixin, UUIDPKMixin, Base):
    """ثبتِ صدورِ یک مزیت (عیدی/سنوات/بازخریدِ مرخصی) با سندِ حسابداری، تا دوباره صادر نشود."""

    __tablename__ = "benefit_runs"

    kind: Mapped[str] = mapped_column(String(20))  # eidi | severance | leave_payout
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    employee_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(18, 0))
    run_date: Mapped[date_] = mapped_column(Date)
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
