from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, field_validator


class StockCountCreateIn(BaseModel):
    warehouse_id: UUID
    count_date: date
    notes: str = ""


class CountLineUpdateIn(BaseModel):
    line_id: UUID
    counted_qty: Decimal

    @field_validator("counted_qty")
    @classmethod
    def _non_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("شمارش نمی‌تواند منفی باشد")
        return v


class SetCountsIn(BaseModel):
    lines: list[CountLineUpdateIn]


class StockCountLineOut(BaseModel):
    id: UUID
    item_id: UUID
    item_name: str
    item_sku: str
    unit: str
    system_qty: Decimal
    counted_qty: Decimal
    unit_cost: Decimal
    variance: Decimal
    variance_value: Decimal


class StockCountSessionOut(BaseModel):
    id: UUID
    warehouse_id: UUID
    warehouse_name: str
    count_date: date
    status: str
    notes: str
    journal_entry_id: UUID | None
    posted_at: datetime | None
    created_at: datetime | None
    line_count: int
    variance_line_count: int
    total_variance_value: Decimal
    lines: list[StockCountLineOut]


class StockCountSummaryOut(BaseModel):
    id: UUID
    warehouse_id: UUID
    warehouse_name: str
    count_date: date
    status: str
    notes: str
    posted_at: datetime | None
    created_at: datetime | None
    line_count: int
