from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, model_validator


class BudgetLineIn(BaseModel):
    account_id: UUID
    period_date: date
    amount: Decimal
    notes: str = ""
    #: بُعدِ اختیاریِ مرکز هزینه. خالی یعنی بودجه‌ی کلِ کسب‌وکار.
    cost_center_id: UUID | None = None

    @model_validator(mode="after")
    def validate(self) -> "BudgetLineIn":
        if self.amount < 0:
            raise ValueError("مبلغ بودجه نمی‌تواند منفی باشد")
        return self


class BudgetLineOut(BaseModel):
    id: UUID
    account_id: UUID
    account_code: str
    account_name: str
    account_type: str
    period_date: date
    amount: Decimal
    notes: str
    cost_center_id: UUID | None = None
    cost_center_name: str = ""


class BudgetReportRow(BaseModel):
    account_id: UUID
    account_code: str
    account_name: str
    account_type: str
    budget: Decimal
    actual: Decimal
    #: عملکرد منهای بودجه، در جهتِ طبیعیِ حساب
    variance: Decimal
    #: درصدِ انحراف نسبت به بودجه؛ وقتی بودجه صفر باشد None است
    variance_pct: Decimal | None
    #: آیا انحراف مطلوب است؟ درآمدِ بیشتر یا هزینه‌ی کمتر مطلوب است
    favorable: bool


class BudgetReportOut(BaseModel):
    date_from: date | None
    date_to: date | None
    rows: list[BudgetReportRow]
    total_budget: Decimal
    total_actual: Decimal
    total_variance: Decimal
