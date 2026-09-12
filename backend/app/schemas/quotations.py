from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


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
    warehouse_id: UUID | None = None
    contact_id: UUID | None = None
    customer_name: str | None = None
    customer_name2: str = ""
    delivery_location: str = ""
    sale_type_id: UUID | None = None
    currency_code: str | None = None
    exchange_rate: Decimal = Decimal(1)
    description: str = ""
    lines: list[SalesQuotationLineIn]

    @model_validator(mode="after")
    def validate_lines(self) -> "SalesQuotationIn":
        if not self.lines:
            raise ValueError("پیش‌فاکتور باید حداقل یک ردیف داشته باشد")
        if self.currency_code and self.exchange_rate <= 0:
            raise ValueError("نرخ ارز باید بزرگ‌تر از صفر باشد")
        return self


class SalesQuotationStatusUpdateIn(BaseModel):
    status: str


class SalesQuotationConvertLineIn(BaseModel):
    quotation_line_id: UUID
    qty: Decimal

    @model_validator(mode="after")
    def validate_qty(self) -> "SalesQuotationConvertLineIn":
        if self.qty <= 0:
            raise ValueError("مقدار تبدیل باید بزرگ‌تر از صفر باشد")
        return self


class SalesQuotationConvertIn(BaseModel):
    warehouse_id: UUID | None = None
    lines: list[SalesQuotationConvertLineIn] = Field(default_factory=list)


class SalesQuotationLineOut(BaseModel):
    id: UUID
    item_id: UUID
    qty: Decimal
    unit_price: Decimal
    description: str
    item_code_snapshot: str = ""
    item_name_snapshot: str = ""
    unit_snapshot: str = ""
    invoiced_qty: Decimal = Decimal(0)
    remaining_invoiceable_qty: Decimal = Decimal(0)
    issued_qty: Decimal = Decimal(0)
    remaining_issueable_qty: Decimal = Decimal(0)

    model_config = {"from_attributes": True}


class SalesQuotationOut(BaseModel):
    id: UUID
    number: int | None
    quotation_date: date
    valid_until: date | None
    warehouse_id: UUID | None
    contact_id: UUID | None
    customer_name: str | None
    customer_name2: str = ""
    delivery_location: str = ""
    sale_type_id: UUID | None = None
    currency_code: str | None = None
    exchange_rate: Decimal = Decimal(1)
    description: str
    status: str
    total_amount: Decimal
    converted_invoice_id: UUID | None
    terminated_at: datetime | None = None
    is_expired: bool = False
    commercial_status: str = "not_invoiced"
    invoiced_invoice_ids: list[UUID] = Field(default_factory=list)
    lines: list[SalesQuotationLineOut]

    model_config = {"from_attributes": True}
