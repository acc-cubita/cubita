from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, field_validator

from app.models.contracting import CONTRACT_STATUSES


class ContractIn(BaseModel):
    contact_id: UUID
    external_reference: str = ""
    subject: str = ""
    total_amount: Decimal
    start_date: date
    end_date: date | None = None
    retention_percent: Decimal = Decimal(0)
    advance_percent: Decimal = Decimal(0)
    cost_center_id: UUID | None = None
    notes: str = ""

    @field_validator("total_amount")
    @classmethod
    def amount_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("مبلغِ پیمان باید بزرگ‌تر از صفر باشد")
        return v

    @field_validator("retention_percent", "advance_percent")
    @classmethod
    def percent_in_range(cls, v: Decimal) -> Decimal:
        if v < 0 or v > 100:
            raise ValueError("درصد باید بینِ ۰ و ۱۰۰ باشد")
        return v

    @field_validator("end_date")
    @classmethod
    def end_after_start(cls, v: date | None, info) -> date | None:
        start = info.data.get("start_date")
        if v is not None and start is not None and v < start:
            raise ValueError("تاریخِ پایان نمی‌تواند پیش از تاریخِ شروع باشد")
        return v


class ContractStatusIn(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def status_known(cls, v: str) -> str:
        if v not in CONTRACT_STATUSES:
            raise ValueError("وضعیتِ نامعتبر")
        return v


class ContractOut(BaseModel):
    id: UUID
    number: int
    external_reference: str
    contact_id: UUID
    contact_name: str
    subject: str
    total_amount: Decimal
    start_date: date
    end_date: date | None
    retention_percent: Decimal
    advance_percent: Decimal
    status: str
    cost_center_id: UUID | None
    notes: str

    model_config = {"from_attributes": True}
