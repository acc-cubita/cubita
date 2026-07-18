from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, model_validator


class SalesQuotationLineIn(BaseModel):
    item_id: UUID
    qty: Decimal
    unit_price: Decimal
    description: str = ""

    @model_validator(mode="after")
    def validate_positive(self) -> "SalesQuotationLineIn":
        if self.qty <= 0:
            raise ValueError("تعداد باید بزرگ‌تر از صفر باشد")
        if self.unit_price < 0:
            raise ValueError("قیمت واحد نمی‌تواند منفی باشد")
        return self


class SalesQuotationIn(BaseModel):
    quotation_date: date
    valid_until: date | None = None
    warehouse_id: UUID
    contact_id: UUID | None = None
    description: str = ""
    lines: list[SalesQuotationLineIn]

    @model_validator(mode="after")
    def validate_lines(self) -> "SalesQuotationIn":
        if not self.lines:
            raise ValueError("پیش‌فاکتور باید حداقل یک ردیف داشته باشد")
        return self


class SalesQuotationStatusUpdateIn(BaseModel):
    status: str


class SalesQuotationLineOut(BaseModel):
    id: UUID
    item_id: UUID
    qty: Decimal
    unit_price: Decimal
    description: str

    model_config = {"from_attributes": True}


class SalesQuotationOut(BaseModel):
    id: UUID
    number: int | None
    quotation_date: date
    valid_until: date | None
    warehouse_id: UUID
    contact_id: UUID | None
    description: str
    status: str
    total_amount: Decimal
    converted_invoice_id: UUID | None
    lines: list[SalesQuotationLineOut]

    model_config = {"from_attributes": True}
