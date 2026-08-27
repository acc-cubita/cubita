from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, model_validator

from app.models.cost_center import COST_CENTER_KINDS


class CostCenterIn(BaseModel):
    code: str = ""
    name: str
    kind: str = "project"
    parent_id: UUID | None = None
    manager: str = ""
    start_date: date | None = None
    end_date: date | None = None
    is_active: bool = True
    notes: str = ""

    @model_validator(mode="after")
    def validate(self) -> "CostCenterIn":
        if not self.name.strip():
            raise ValueError("نام مرکز هزینه/پروژه الزامی است")
        if self.kind not in COST_CENTER_KINDS:
            raise ValueError("نوع مرکز نامعتبر است")
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("تاریخ پایان نمی‌تواند پیش از تاریخ شروع باشد")
        return self


class CostCenterOut(BaseModel):
    id: UUID
    code: str
    name: str
    kind: str
    parent_id: UUID | None
    manager: str
    start_date: date | None
    end_date: date | None
    is_active: bool
    notes: str
    #: عمق در درخت (ریشه = ۰) و مسیرِ خوانا «شعبه تهران / پروژه الف» — هر دو در سرور
    #: ساخته می‌شوند تا کلاینت مجبور نباشد درخت را دوباره بپیماید.
    depth: int = 0
    path: str = ""
    child_count: int = 0

    model_config = {"from_attributes": True}


class CostCenterReportRow(BaseModel):
    #: NULL یعنی سطرِ «بدون مرکز هزینه» (سندهای برچسب‌نخورده)
    cost_center_id: UUID | None
    cost_center_code: str
    cost_center_name: str
    kind: str = "other"
    parent_id: UUID | None = None
    depth: int = 0
    path: str = ""
    is_active: bool = True
    #: عددِ خودِ مرکز — فقط ردیف‌هایی که مستقیم به آن برچسب خورده‌اند
    income: Decimal
    expense: Decimal
    profit: Decimal
    #: عددِ تجمیعی — خودِ مرکز به‌علاوه‌ی همه‌ی زیرشاخه‌ها
    rollup_income: Decimal = Decimal(0)
    rollup_expense: Decimal = Decimal(0)
    rollup_profit: Decimal = Decimal(0)
    #: بودجه‌ی همان بازه (از ردیف‌های بودجه‌ی همین مرکز)؛ تجمیعی، مثل بقیه‌ی ارقام
    budget_income: Decimal = Decimal(0)
    budget_expense: Decimal = Decimal(0)
    #: انحرافِ سود نسبت به بودجه؛ وقتی بودجه‌ای تعریف نشده None است
    profit_variance: Decimal | None = None
    entry_count: int = 0


class CostCenterReportOut(BaseModel):
    date_from: date | None
    date_to: date | None
    rows: list[CostCenterReportRow]
    total_income: Decimal
    total_expense: Decimal
    total_profit: Decimal
    #: سهمِ فعالیتِ برچسب‌نخورده از کلِ گردش — سنجه‌ی کیفیتِ برچسب‌زنی
    untagged_share_pct: Decimal = Decimal(0)


class AccountBreakdownRow(BaseModel):
    account_id: UUID
    account_code: str
    account_name: str
    account_type: str
    amount: Decimal
    share_pct: Decimal


class MonthPoint(BaseModel):
    #: برچسبِ شمسی «۱۴۰۴/۰۵»
    label: str
    income: Decimal
    expense: Decimal
    profit: Decimal


class CostCenterLedgerRow(BaseModel):
    line_id: UUID
    entry_id: UUID
    entry_number: int | None
    entry_date: date
    description: str
    source_type: str
    account_code: str
    account_name: str
    account_type: str
    debit: Decimal
    credit: Decimal
    cost_center_id: UUID
    cost_center_name: str


class CostCenterChildRow(BaseModel):
    id: UUID
    code: str
    name: str
    kind: str
    is_active: bool
    income: Decimal
    expense: Decimal
    profit: Decimal


class CostCenterAnalysisOut(BaseModel):
    center: CostCenterOut
    date_from: date | None
    date_to: date | None
    include_children: bool
    income: Decimal
    expense: Decimal
    profit: Decimal
    margin_pct: Decimal | None
    budget_income: Decimal
    budget_expense: Decimal
    budget_profit: Decimal
    profit_variance: Decimal | None
    has_budget: bool
    entry_count: int
    first_entry_date: date | None
    last_entry_date: date | None
    #: پیشرفتِ زمانیِ پروژه بر پایه‌ی بازه‌ی تعریف‌شده؛ بدونِ بازه None است
    elapsed_pct: Decimal | None
    income_accounts: list[AccountBreakdownRow]
    expense_accounts: list[AccountBreakdownRow]
    monthly: list[MonthPoint]
    children: list[CostCenterChildRow]


class CostCenterBudgetIn(BaseModel):
    account_id: UUID
    period_date: date
    amount: Decimal
    notes: str = ""
