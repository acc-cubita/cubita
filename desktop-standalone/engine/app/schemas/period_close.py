from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class FiscalPeriodCloseIn(BaseModel):
    closing_date: date
    notes: str = ""


class FiscalPeriodCloseOut(BaseModel):
    id: UUID
    closing_date: date
    net_profit: Decimal
    notes: str
    journal_entry_id: UUID

    model_config = {"from_attributes": True}
