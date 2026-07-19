from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, model_validator


class SalesInvoiceLineIn(BaseModel):
    item_id: UUID
    qty: Decimal
    unit_price: Decimal
    description: str = ""

    @model_validator(mode="after")
    def validate_positive(self) -> "SalesInvoiceLineIn":
        if self.qty <= 0:
            raise ValueError("تعداد باید بزرگ‌تر از صفر باشد")
        if self.unit_price < 0:
            raise ValueError("قیمت واحد نمی‌تواند منفی باشد")
        return self


class SalesInvoiceIn(BaseModel):
    invoice_date: date
    warehouse_id: UUID
    contact_id: UUID | None = None
    description: str = ""
    lines: list[SalesInvoiceLineIn]
    source_order_id: int | None = None  # فقط برای فاکتورهای وارداتی از سایت فروشگاهی پر می‌شود

    @model_validator(mode="after")
    def validate_lines(self) -> "SalesInvoiceIn":
        if not self.lines:
            raise ValueError("فاکتور باید حداقل یک ردیف داشته باشد")
        return self


class SalesInvoiceLineOut(BaseModel):
    id: UUID
    item_id: UUID
    qty: Decimal
    unit_price: Decimal
    unit_cost: Decimal
    description: str

    model_config = {"from_attributes": True}


class SalesInvoiceOut(BaseModel):
    id: UUID
    number: int | None
    invoice_date: date
    warehouse_id: UUID
    contact_id: UUID | None
    description: str
    total_amount: Decimal
    total_cost: Decimal
    journal_entry_id: UUID | None
    source_order_id: int | None
    #: بدون این، رابط کاربری فاکتور باطل را عیناً مثل معتبر نشان می‌دهد
    voided_at: datetime | None = None
    void_reason: str = ""
    lines: list[SalesInvoiceLineOut]

    model_config = {"from_attributes": True}


class PurchaseInvoiceLineIn(BaseModel):
    item_id: UUID
    qty: Decimal
    unit_cost: Decimal
    description: str = ""

    @model_validator(mode="after")
    def validate_positive(self) -> "PurchaseInvoiceLineIn":
        if self.qty <= 0:
            raise ValueError("تعداد باید بزرگ‌تر از صفر باشد")
        if self.unit_cost < 0:
            raise ValueError("بهای واحد نمی‌تواند منفی باشد")
        return self


class PurchaseInvoiceIn(BaseModel):
    invoice_date: date
    warehouse_id: UUID
    contact_id: UUID | None = None
    description: str = ""
    lines: list[PurchaseInvoiceLineIn]

    @model_validator(mode="after")
    def validate_lines(self) -> "PurchaseInvoiceIn":
        if not self.lines:
            raise ValueError("فاکتور باید حداقل یک ردیف داشته باشد")
        return self


class PurchaseInvoiceLineOut(BaseModel):
    id: UUID
    item_id: UUID
    qty: Decimal
    unit_cost: Decimal
    description: str

    model_config = {"from_attributes": True}


class PurchaseInvoiceOut(BaseModel):
    id: UUID
    number: int | None
    invoice_date: date
    warehouse_id: UUID
    contact_id: UUID | None
    description: str
    total_amount: Decimal
    journal_entry_id: UUID | None
    voided_at: datetime | None = None
    void_reason: str = ""
    lines: list[PurchaseInvoiceLineOut]

    model_config = {"from_attributes": True}
