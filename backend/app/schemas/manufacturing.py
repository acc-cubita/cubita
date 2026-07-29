from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, field_validator


# ── فرمولِ ساخت (BOM) ───────────────────────────────────
class BomLineIn(BaseModel):
    component_item_id: UUID
    qty: Decimal

    @field_validator("qty")
    @classmethod
    def qty_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("مقدارِ جزء باید بزرگ‌تر از صفر باشد")
        return v


class BomIn(BaseModel):
    finished_item_id: UUID
    name: str = ""
    yield_qty: Decimal = Decimal(1)
    notes: str = ""
    lines: list[BomLineIn]

    @field_validator("yield_qty")
    @classmethod
    def yield_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("بازدهِ فرمول باید بزرگ‌تر از صفر باشد")
        return v

    @field_validator("lines")
    @classmethod
    def has_lines(cls, v: list) -> list:
        if not v:
            raise ValueError("فرمول باید حداقل یک جزء داشته باشد")
        return v


class BomUpdateIn(BaseModel):
    name: str | None = None
    yield_qty: Decimal | None = None
    is_active: bool | None = None
    notes: str | None = None
    #: اگر داده شود، همه‌ی اجزای فرمول با این فهرست جایگزین می‌شوند.
    lines: list[BomLineIn] | None = None

    @field_validator("yield_qty")
    @classmethod
    def yield_positive(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and v <= 0:
            raise ValueError("بازدهِ فرمول باید بزرگ‌تر از صفر باشد")
        return v


class BomLineOut(BaseModel):
    id: UUID
    component_item_id: UUID
    qty: Decimal

    model_config = {"from_attributes": True}


class BomOut(BaseModel):
    id: UUID
    finished_item_id: UUID
    name: str
    yield_qty: Decimal
    is_active: bool
    notes: str
    lines: list[BomLineOut]

    model_config = {"from_attributes": True}


# ── سفارشِ تولید ────────────────────────────────────────
class ProductionOrderIn(BaseModel):
    bom_id: UUID
    warehouse_id: UUID
    production_date: date
    qty_produced: Decimal
    overhead_cost: Decimal = Decimal(0)

    @field_validator("qty_produced")
    @classmethod
    def qty_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("تعدادِ تولید باید بزرگ‌تر از صفر باشد")
        return v

    @field_validator("overhead_cost")
    @classmethod
    def overhead_nonneg(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("سربار نمی‌تواند منفی باشد")
        return v


class ProductionOrderLineOut(BaseModel):
    component_item_id: UUID
    qty: Decimal
    unit_cost: Decimal

    model_config = {"from_attributes": True}


class ProductionOrderOut(BaseModel):
    id: UUID
    number: int | None
    bom_id: UUID
    finished_item_id: UUID
    warehouse_id: UUID
    production_date: date
    qty_produced: Decimal
    component_cost: Decimal
    overhead_cost: Decimal
    unit_cost: Decimal
    lines: list[ProductionOrderLineOut]

    model_config = {"from_attributes": True}
