from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator
from app.schemas.item_units import ObservedRatioIn
from app.schemas.invoices import BatchAllocationIn


class StockTransferLineIn(BaseModel):
    item_id: UUID
    qty: Decimal
    unit_id: UUID | None = None
    observations: list[ObservedRatioIn] = Field(default_factory=list, max_length=100)
    batch_allocations: list[BatchAllocationIn] | None = None

    @model_validator(mode="after")
    def validate_positive(self) -> "StockTransferLineIn":
        if self.qty <= 0:
            raise ValueError("تعداد باید بزرگ‌تر از صفر باشد")
        return self


class StockTransferIn(BaseModel):
    transfer_date: date
    from_warehouse_id: UUID
    to_warehouse_id: UUID
    description: str = ""
    lines: list[StockTransferLineIn]

    @model_validator(mode="after")
    def validate_transfer(self) -> "StockTransferIn":
        if not self.lines:
            raise ValueError("حواله باید حداقل یک ردیف داشته باشد")
        if self.from_warehouse_id == self.to_warehouse_id:
            raise ValueError("انبار مبدأ و مقصد نمی‌توانند یکسان باشند")
        return self


class StockTransferLineOut(BaseModel):
    id: UUID
    item_id: UUID
    qty: Decimal
    entered_qty: Decimal | None = None
    entered_unit_id: UUID | None = None
    base_unit_id: UUID | None = None
    unit_conversion_snapshot: dict | None = None

    model_config = {"from_attributes": True}


class StockTransferOut(BaseModel):
    id: UUID
    number: int | None
    transfer_date: date
    from_warehouse_id: UUID
    to_warehouse_id: UUID
    description: str
    journal_entry_id: UUID | None = None
    voided_at: datetime | None = None
    void_reason: str = ""
    lines: list[StockTransferLineOut]

    model_config = {"from_attributes": True}
