"""قیمت‌گذاری اسناد انبار — پیش‌نمایش، اجرا و ابطال."""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, model_validator


class ValuationRunIn(BaseModel):
    date_from: date | None = None
    date_to: date
    warehouse_id: UUID | None = None
    item_id: UUID | None = None
    #: توکنِ دفتر از پیش‌نمایش — ثبت روی داده‌ی کهنه رد می‌شود.
    token: str
    description: str = ""

    @model_validator(mode="after")
    def _range(self) -> "ValuationRunIn":
        if self.date_from is not None and self.date_from > self.date_to:
            raise ValueError("«از تاریخ» بعد از «تا تاریخ» است.")
        if not self.token.strip():
            raise ValueError("اول «محاسبه» بزنید؛ ثبت بدونِ پیش‌نمایش ممکن نیست.")
        return self


class ValuationSourceOut(BaseModel):
    source_type: str
    source_label: str
    source_number: int | None = None


class ValuationNegativeOut(ValuationSourceOut):
    item_id: UUID
    item_name: str
    warehouse_name: str
    entry_date: date
    qty: Decimal


class ValuationItemOut(BaseModel):
    item_id: UUID
    sku: str
    name: str
    move_count: int
    value_delta: Decimal
    from_date: date


class ValuationMoveOut(ValuationSourceOut):
    stock_ledger_id: UUID
    item_id: UUID
    item_name: str
    entry_date: date
    warehouse_name: str
    qty: Decimal
    previous_cost: Decimal
    new_cost: Decimal
    #: اثرِ علامت‌دار بر ارزشِ موجودی (ریال).
    value_delta: Decimal
    counter_account_name: str


class ValuationAccountOut(BaseModel):
    account_id: UUID
    code: str
    name: str
    debit: Decimal
    credit: Decimal


class ValuationSkippedOut(ValuationSourceOut):
    item_name: str
    entry_date: date
    qty: Decimal
    reason: str


class ValuationPreviewOut(BaseModel):
    date_from: date | None
    date_to: date
    warehouse_id: UUID | None
    item_id: UUID | None
    token: str
    #: موجودیِ منفی در خطِ زمان — ثبت ممکن نیست.
    blocked: bool
    negatives: list[ValuationNegativeOut]
    items: list[ValuationItemOut]
    moves: list[ValuationMoveOut]
    moves_truncated: bool
    #: سندِ اصلاحی‌ای که ثبت خواهد شد.
    accounts: list[ValuationAccountOut]
    skipped: list[ValuationSkippedOut]
    move_count: int
    item_count: int
    total_delta: Decimal


class ValuationRunOut(BaseModel):
    id: UUID
    number: int
    date_from: date | None
    date_to: date
    warehouse_id: UUID | None
    warehouse_name: str
    item_id: UUID | None
    item_name: str
    description: str
    move_count: int
    item_count: int
    total_delta: Decimal
    journal_entry_id: UUID | None
    journal_entry_number: int | None
    created_at: datetime
    created_by_name: str
    voided_at: datetime | None
    voided_by_name: str
    void_reason: str
    void_entry_number: int | None
    #: فقط آخرین اجرای باطل‌نشده.
    voidable: bool


class ValuationRunDetailOut(ValuationRunOut):
    adjustments: list[ValuationMoveOut]
    adjustments_truncated: bool
