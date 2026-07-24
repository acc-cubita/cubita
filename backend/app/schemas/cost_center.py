from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, model_validator


class CostCenterIn(BaseModel):
    code: str = ""
    name: str
    is_active: bool = True
    notes: str = ""

    @model_validator(mode="after")
    def validate(self) -> "CostCenterIn":
        if not self.name.strip():
            raise ValueError("نام مرکز هزینه/پروژه الزامی است")
        return self


class CostCenterOut(BaseModel):
    id: UUID
    code: str
    name: str
    is_active: bool
    notes: str

    model_config = {"from_attributes": True}


class CostCenterReportRow(BaseModel):
    #: NULL یعنی سطرِ «بدون مرکز هزینه» (سندهای برچسب‌نخورده)
    cost_center_id: UUID | None
    cost_center_code: str
    cost_center_name: str
    income: Decimal
    expense: Decimal
    profit: Decimal


class CostCenterReportOut(BaseModel):
    date_from: date | None
    date_to: date | None
    rows: list[CostCenterReportRow]
    total_income: Decimal
    total_expense: Decimal
    total_profit: Decimal
