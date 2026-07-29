from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, field_validator


# ── لیستِ قیمت ──────────────────────────────────────────
class PriceListIn(BaseModel):
    name: str
    notes: str = ""

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("نامِ لیستِ قیمت نمی‌تواند خالی باشد")
        return v.strip()


class PriceListUpdateIn(BaseModel):
    name: str | None = None
    is_active: bool | None = None
    notes: str | None = None


class PriceListOut(BaseModel):
    id: UUID
    name: str
    is_active: bool
    notes: str

    model_config = {"from_attributes": True}


class PriceListItemIn(BaseModel):
    item_id: UUID
    price: Decimal

    @field_validator("price")
    @classmethod
    def price_nonneg(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("قیمت نمی‌تواند منفی باشد")
        return v


class PriceListItemOut(BaseModel):
    id: UUID
    item_id: UUID
    price: Decimal

    model_config = {"from_attributes": True}


class SetPricesIn(BaseModel):
    items: list[PriceListItemIn]


# ── بچ / تاریخِ انقضا ───────────────────────────────────
class StockBatchIn(BaseModel):
    item_id: UUID
    warehouse_id: UUID
    batch_number: str
    expiry_date: date | None = None
    qty: Decimal = Decimal(0)
    received_date: date
    notes: str = ""

    @field_validator("batch_number")
    @classmethod
    def batch_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("شماره‌ی بچ/سری نمی‌تواند خالی باشد")
        return v.strip()


class StockBatchOut(BaseModel):
    id: UUID
    item_id: UUID
    warehouse_id: UUID
    batch_number: str
    expiry_date: date | None
    qty: Decimal
    received_date: date
    notes: str

    model_config = {"from_attributes": True}
