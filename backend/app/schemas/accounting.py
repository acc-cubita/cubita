from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, model_validator


class AccountOut(BaseModel):
    id: UUID
    code: str
    name: str
    type: str
    is_group: bool
    parent_id: UUID | None

    model_config = {"from_attributes": True}


class JournalLineIn(BaseModel):
    account_id: UUID
    debit: Decimal = Decimal(0)
    credit: Decimal = Decimal(0)
    description: str = ""


class JournalEntryIn(BaseModel):
    entry_date: date
    description: str = ""
    lines: list[JournalLineIn]

    @model_validator(mode="after")
    def validate_balance(self) -> "JournalEntryIn":
        if len(self.lines) < 2:
            raise ValueError("سند حسابداری باید حداقل دو ردیف داشته باشد")
        total_debit = sum(line.debit for line in self.lines)
        total_credit = sum(line.credit for line in self.lines)
        if total_debit != total_credit:
            raise ValueError(f"سند متوازن نیست: بدهکار={total_debit} بستانکار={total_credit}")
        if total_debit == 0:
            raise ValueError("مجموع سند نمی‌تواند صفر باشد")
        return self


class JournalLineOut(BaseModel):
    id: UUID
    account_id: UUID
    debit: Decimal
    credit: Decimal
    description: str

    model_config = {"from_attributes": True}


class JournalEntryOut(BaseModel):
    id: UUID
    number: int | None
    entry_date: date
    description: str
    source_type: str
    lines: list[JournalLineOut]

    model_config = {"from_attributes": True}
