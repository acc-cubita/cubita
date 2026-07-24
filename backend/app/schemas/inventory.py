from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, model_validator


class WarehouseIn(BaseModel):
    code: str
    name: str


class WarehouseOut(BaseModel):
    id: UUID
    code: str
    name: str
    is_active: bool

    model_config = {"from_attributes": True}


class ContactIn(BaseModel):
    name: str
    type: str = "customer"
    phone: str | None = None
    email: str | None = None
    address: str = ""
    tax_id: str | None = None
    credit_limit: Decimal = Decimal(0)

    @model_validator(mode="after")
    def _check_credit_limit(self) -> "ContactIn":
        if self.credit_limit < 0:
            raise ValueError("سقف اعتبار نمی‌تواند منفی باشد")
        return self


class ContactOut(BaseModel):
    id: UUID
    name: str
    type: str
    phone: str | None
    email: str | None
    address: str
    tax_id: str | None
    is_active: bool
    credit_limit: Decimal

    model_config = {"from_attributes": True}


class CreditStatusOut(BaseModel):
    contact_id: UUID
    name: str
    credit_limit: Decimal
    outstanding: Decimal
    available: Decimal
    over_limit: bool


class ItemIn(BaseModel):
    sku: str
    name: str
    category: str = ""
    unit: str = "عدد"
    is_service: bool = False
    sales_price: Decimal = Decimal(0)


class ItemOut(BaseModel):
    id: UUID
    sku: str
    name: str
    category: str
    unit: str
    is_service: bool
    sales_price: Decimal
    average_cost: Decimal
    is_active: bool
    storefront_product_id: int | None

    model_config = {"from_attributes": True}


class ItemUpdateIn(BaseModel):
    """آپدیت جزئی کالا؛ فقط فیلدهای ارسال‌شده تغییر می‌کنند (بقیه دست‌نخورده می‌مانند)."""

    name: str | None = None
    sales_price: Decimal | None = None
    is_active: bool | None = None
    storefront_product_id: int | None = None


class StockLevelOut(BaseModel):
    item_id: UUID
    item_sku: str
    item_name: str
    warehouse_id: UUID
    warehouse_name: str
    qty: Decimal


class StockAdjustmentIn(BaseModel):
    item_id: UUID
    warehouse_id: UUID
    qty_diff: Decimal
    reason: str = ""
    adjustment_date: date

    @model_validator(mode="after")
    def validate_nonzero(self) -> "StockAdjustmentIn":
        if self.qty_diff == 0:
            raise ValueError("مقدار تعدیل نمی‌تواند صفر باشد")
        return self


class StockAdjustmentOut(BaseModel):
    id: UUID
    item_id: UUID
    warehouse_id: UUID
    qty_diff: Decimal
    unit_cost: Decimal
    reason: str
    adjustment_date: date
    journal_entry_id: UUID | None

    model_config = {"from_attributes": True}
