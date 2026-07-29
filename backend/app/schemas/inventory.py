from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, field_validator, model_validator


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
    barcode: str | None = None

    @field_validator("barcode")
    @classmethod
    def _blank_barcode_is_null(cls, v: str | None) -> str | None:
        # بارکدِ خالی = بدونِ بارکد (NULL)، تا با یکتاییِ منطقی جور باشد
        if v is None:
            return None
        v = v.strip()
        return v or None


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
    barcode: str | None
    storefront_product_id: int | None

    model_config = {"from_attributes": True}


class ItemUpdateIn(BaseModel):
    """آپدیت جزئی کالا؛ فقط فیلدهای ارسال‌شده تغییر می‌کنند (بقیه دست‌نخورده می‌مانند).

    `average_cost` را می‌توان دستی ویرایش کرد (بهای تمام‌شده‌ی جاری برای محاسبه‌ی سود/بهای
    فروش‌رفته). توجه: این فقط مبنای بهای رو به جلو را عوض می‌کند و ارزشِ ثبت‌شده‌ی موجودی در
    دفترِ کل را بازارزیابی نمی‌کند؛ برای افتتاحیه، سندِ جداگانه‌ی موجودی/سرمایه زده می‌شود.
    """

    name: str | None = None
    sales_price: Decimal | None = None
    average_cost: Decimal | None = None
    is_active: bool | None = None
    barcode: str | None = None
    storefront_product_id: int | None = None

    @field_validator("barcode")
    @classmethod
    def _blank_barcode_is_null(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None

    @model_validator(mode="after")
    def _non_negative_cost(self) -> "ItemUpdateIn":
        if self.average_cost is not None and self.average_cost < 0:
            raise ValueError("بهای تمام‌شده نمی‌تواند منفی باشد")
        return self


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
