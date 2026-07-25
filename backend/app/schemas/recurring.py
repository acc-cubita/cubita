from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, model_validator

from app.models.recurring import RECURRING_FREQUENCIES


class RecurringLineIn(BaseModel):
    account_id: UUID
    debit: Decimal = Decimal(0)
    credit: Decimal = Decimal(0)
    description: str = ""


class RecurringEntryIn(BaseModel):
    title: str
    description: str = ""
    frequency: str
    interval: int = 1
    start_date: date
    end_date: date | None = None
    cost_center_id: UUID | None = None
    lines: list[RecurringLineIn]

    @model_validator(mode="after")
    def _validate(self) -> "RecurringEntryIn":
        if not self.title.strip():
            raise ValueError("عنوان الزامی است")
        if self.frequency not in RECURRING_FREQUENCIES:
            raise ValueError("تناوب نامعتبر است")
        if self.interval < 1:
            raise ValueError("فاصله باید حداقل ۱ باشد")
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("تاریخ پایان نمی‌تواند قبل از تاریخ شروع باشد")
        if len(self.lines) < 2:
            raise ValueError("سند باید حداقل دو ردیف داشته باشد")
        total_debit = sum(line.debit for line in self.lines)
        total_credit = sum(line.credit for line in self.lines)
        if total_debit != total_credit:
            raise ValueError(f"سند متوازن نیست: بدهکار={total_debit} بستانکار={total_credit}")
        if total_debit == 0:
            raise ValueError("مجموع سند نمی‌تواند صفر باشد")
        return self


class RecurringLineOut(BaseModel):
    id: UUID
    account_id: UUID
    account_code: str
    account_name: str
    debit: Decimal
    credit: Decimal
    description: str


class RecurringEntryOut(BaseModel):
    id: UUID
    title: str
    description: str
    frequency: str
    interval: int
    start_date: date
    end_date: date | None
    next_run_date: date
    last_run_date: date | None
    is_active: bool
    cost_center_id: UUID | None
    created_at: datetime | None
    is_due: bool
    amount: Decimal
    lines: list[RecurringLineOut]


class GeneratedEntryOut(BaseModel):
    id: UUID
    number: int | None
    entry_date: date
    title: str


class RunResultOut(BaseModel):
    generated: int
    skipped: int
    entries: list[GeneratedEntryOut]
