from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, model_validator


class SalesReturnLineIn(BaseModel):
    item_id: UUID
    qty: Decimal
    description: str = ""

    @model_validator(mode="after")
    def validate_positive(self) -> "SalesReturnLineIn":
        if self.qty <= 0:
            raise ValueError("تعداد باید بزرگ‌تر از صفر باشد")
        return self


class SalesReturnIn(BaseModel):
    return_date: date
    sales_invoice_id: UUID
    description: str = ""
    lines: list[SalesReturnLineIn]

    @model_validator(mode="after")
    def validate_lines(self) -> "SalesReturnIn":
        if not self.lines:
            raise ValueError("برگشت از فروش باید حداقل یک ردیف داشته باشد")
        return self


class SalesReturnLineOut(BaseModel):
    id: UUID
    item_id: UUID
    qty: Decimal
    unit_price: Decimal
    unit_cost: Decimal
    description: str

    model_config = {"from_attributes": True}


class SalesReturnOut(BaseModel):
    id: UUID
    number: int | None
    return_date: date
    sales_invoice_id: UUID
    description: str
    total_amount: Decimal
    total_cost: Decimal
    tax_rate: Decimal
    tax_amount: Decimal
    journal_entry_id: UUID | None
    lines: list[SalesReturnLineOut]

    model_config = {"from_attributes": True}


class ReturnableLineOut(BaseModel):
    """یک ردیفِ «قابلِ برگشت» از یک فاکتور فروش."""
    item_id: UUID
    item_name: str
    unit: str
    sold: Decimal
    already_returned: Decimal
    remaining: Decimal
    unit_price: Decimal


class PurchaseReturnLineIn(BaseModel):
    item_id: UUID
    qty: Decimal
    description: str = ""

    @model_validator(mode="after")
    def validate_positive(self) -> "PurchaseReturnLineIn":
        if self.qty <= 0:
            raise ValueError("تعداد باید بزرگ‌تر از صفر باشد")
        return self


class PurchaseReturnIn(BaseModel):
    return_date: date
    purchase_invoice_id: UUID
    description: str = ""
    lines: list[PurchaseReturnLineIn]

    @model_validator(mode="after")
    def validate_lines(self) -> "PurchaseReturnIn":
        if not self.lines:
            raise ValueError("برگشت از خرید باید حداقل یک ردیف داشته باشد")
        return self


class PurchaseReturnLineOut(BaseModel):
    id: UUID
    item_id: UUID
    qty: Decimal
    unit_cost: Decimal
    description: str

    model_config = {"from_attributes": True}


class PurchaseReturnOut(BaseModel):
    id: UUID
    number: int | None
    return_date: date
    purchase_invoice_id: UUID
    description: str
    total_amount: Decimal
    tax_rate: Decimal
    tax_amount: Decimal
    journal_entry_id: UUID | None
    lines: list[PurchaseReturnLineOut]

    model_config = {"from_attributes": True}
