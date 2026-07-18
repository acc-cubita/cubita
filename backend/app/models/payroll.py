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

PAYROLL_PERIOD_STATUSES = ("draft", "finalized")


class Employee(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "employees"

    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    national_id: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    bank_account_number: Mapped[str] = mapped_column(String(50), default="")
    hire_date: Mapped[date_] = mapped_column(Date)
    termination_date: Mapped[date_ | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    contracts: Mapped[list["SalaryContract"]] = relationship(back_populates="employee", order_by="SalaryContract.effective_from")


class SalaryContract(UUIDPKMixin, TimestampMixin, Base):
    """حکم حقوقی. حکم جاری یک کارمند در تاریخ X = آخرین حکمی که effective_from آن <= X است."""

    __tablename__ = "salary_contracts"

    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), index=True)
    effective_from: Mapped[date_] = mapped_column(Date)
    base_salary: Mapped[float] = mapped_column(Numeric(18, 0))
    housing_allowance: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    food_allowance: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    other_allowance: Mapped[float] = mapped_column(Numeric(18, 0), default=0)

    employee: Mapped["Employee"] = relationship(back_populates="contracts")


class PayrollPeriod(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "payroll_periods"
    __table_args__ = (
        UniqueConstraint("year", "month", name="uq_payroll_periods_year_month"),
        CheckConstraint(f"status IN {PAYROLL_PERIOD_STATUSES}", name="ck_payroll_periods_status"),
        CheckConstraint("month BETWEEN 1 AND 12", name="ck_payroll_periods_month_range"),
    )

    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="draft")


class Attendance(UUIDPKMixin, Base):
    """کارکرد ماهانه‌ی ساده (حضور/غیاب دستی)؛ اتصال به دستگاه حضور و غیاب در فاز بعد."""

    __tablename__ = "attendance"
    __table_args__ = (UniqueConstraint("employee_id", "period_id", name="uq_attendance_employee_period"),)

    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), index=True)
    period_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("payroll_periods.id"), index=True)
    worked_days: Mapped[float] = mapped_column(Numeric(5, 2), default=30)
    absent_days: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    overtime_hours: Mapped[float] = mapped_column(Numeric(6, 2), default=0)


class Payslip(UUIDPKMixin, TimestampMixin, Base):
    """فیش حقوقی. اعداد در لحظه‌ی صدور از روی حکم حقوقی جاری و کارکرد همان دوره محاسبه و اسنپ‌شات می‌شوند."""

    __tablename__ = "payslips"
    __table_args__ = (UniqueConstraint("employee_id", "period_id", name="uq_payslips_employee_period"),)

    number: Mapped[int | None] = mapped_column(nullable=True, unique=True, index=True)
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


class PayrollSettings(UUIDPKMixin, TimestampMixin, Base):
    """نرخ‌های بیمه/مالیات حقوق. این نرخ‌ها هرسال طبق قانون بودجه/تأمین اجتماعی تغییر می‌کنند —
    مقادیر seed شده صرفاً placeholder هستند و باید قبل از صدور فیش واقعی توسط کاربر تأیید/ویرایش شوند."""

    __tablename__ = "payroll_settings"

    year: Mapped[int] = mapped_column(Integer, unique=True)
    insurance_employee_rate: Mapped[float] = mapped_column(Numeric(5, 4))
    insurance_employer_rate: Mapped[float] = mapped_column(Numeric(5, 4))
    tax_exemption_annual: Mapped[float] = mapped_column(Numeric(18, 0))
    # لیست پلکان مالیات سالانه: [{"up_to": <سقف تجمعی یا null برای نامحدود>, "rate": <نرخ 0..1>}, ...] به ترتیب صعودی
    tax_brackets: Mapped[list] = mapped_column(JSONB)
    notes: Mapped[str] = mapped_column(Text, default="")
