from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, model_validator


class EmployeeIn(BaseModel):
    first_name: str
    last_name: str
    national_id: str
    phone: str | None = None
    email: str | None = None
    bank_account_number: str = ""
    hire_date: date


class EmployeeOut(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    national_id: str
    phone: str | None
    email: str | None
    bank_account_number: str
    hire_date: date
    termination_date: date | None
    is_active: bool

    model_config = {"from_attributes": True}


class SalaryContractIn(BaseModel):
    employee_id: UUID
    effective_from: date
    base_salary: Decimal
    housing_allowance: Decimal = Decimal(0)
    food_allowance: Decimal = Decimal(0)
    other_allowance: Decimal = Decimal(0)

    @model_validator(mode="after")
    def validate_positive(self) -> "SalaryContractIn":
        if self.base_salary <= 0:
            raise ValueError("حقوق پایه باید بزرگ‌تر از صفر باشد")
        return self


class SalaryContractOut(BaseModel):
    id: UUID
    employee_id: UUID
    effective_from: date
    base_salary: Decimal
    housing_allowance: Decimal
    food_allowance: Decimal
    other_allowance: Decimal

    model_config = {"from_attributes": True}


class PayrollPeriodIn(BaseModel):
    year: int
    month: int

    @model_validator(mode="after")
    def validate_month(self) -> "PayrollPeriodIn":
        if not (1 <= self.month <= 12):
            raise ValueError("ماه باید بین ۱ تا ۱۲ باشد")
        return self


class PayrollPeriodOut(BaseModel):
    id: UUID
    year: int
    month: int
    status: str

    model_config = {"from_attributes": True}


class AttendanceIn(BaseModel):
    employee_id: UUID
    period_id: UUID
    worked_days: Decimal = Decimal(30)
    absent_days: Decimal = Decimal(0)
    overtime_hours: Decimal = Decimal(0)


class AttendanceOut(BaseModel):
    id: UUID
    employee_id: UUID
    period_id: UUID
    worked_days: Decimal
    absent_days: Decimal
    overtime_hours: Decimal

    model_config = {"from_attributes": True}


class PayslipOut(BaseModel):
    id: UUID
    number: int | None
    employee_id: UUID
    period_id: UUID
    base_salary: Decimal
    allowances_total: Decimal
    overtime_pay: Decimal
    gross_pay: Decimal
    insurance_employee_share: Decimal
    insurance_employer_share: Decimal
    taxable_pay: Decimal
    tax_amount: Decimal
    net_pay: Decimal
    journal_entry_id: UUID | None

    model_config = {"from_attributes": True}


class TaxBracketIn(BaseModel):
    up_to: Decimal | None  # سقف تجمعی سالانه؛ None یعنی نامحدود (باید آخرین ردیف باشد)
    rate: Decimal  # بین ۰ و ۱


class PayrollSettingsIn(BaseModel):
    year: int
    insurance_employee_rate: Decimal
    insurance_employer_rate: Decimal
    tax_exemption_annual: Decimal
    tax_brackets: list[TaxBracketIn]
    notes: str = ""

    @model_validator(mode="after")
    def validate_brackets(self) -> "PayrollSettingsIn":
        if not self.tax_brackets:
            raise ValueError("حداقل یک پلکان مالیاتی لازم است")
        if self.tax_brackets[-1].up_to is not None:
            raise ValueError("آخرین پلکان مالیاتی باید سقف نامحدود (up_to=null) داشته باشد")
        for bracket in self.tax_brackets:
            if not (0 <= bracket.rate <= 1):
                raise ValueError("نرخ هر پلکان باید بین ۰ و ۱ باشد")
        return self


class PayrollSettingsOut(BaseModel):
    id: UUID
    year: int
    insurance_employee_rate: Decimal
    insurance_employer_rate: Decimal
    tax_exemption_annual: Decimal
    tax_brackets: list[dict]
    notes: str

    model_config = {"from_attributes": True}
