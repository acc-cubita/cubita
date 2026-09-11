"""شکلِ ورودی/خروجیِ عملیاتِ چک."""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, model_validator


class CheckEventOut(BaseModel):
    """یک گامِ تاریخچه (§۳۶).

    `operation` و `to_status` هر دو هستند و هیچ‌کدام از دیگری مشتق نمی‌شود:
    «بازگشت از بانک» و «برگشت از خرج» هر دو به «نزدِ ما» می‌رسند.
    """

    id: UUID
    check_id: UUID
    operation: str
    operation_label: str
    from_status: str | None = None
    to_status: str
    to_status_label: str
    event_date: date
    at: datetime
    operation_no: int | None = None
    batch_id: UUID | None = None
    bank_account_id: UUID | None = None
    bank_account_name: str | None = None
    cashbox_id: UUID | None = None
    cashbox_name: str | None = None
    contact_id: UUID | None = None
    contact_name: str | None = None
    journal_entry_id: UUID | None = None
    note: str = ""


class CheckOperationRowOut(CheckEventOut):
    """ردیفِ فهرستِ عملیات — همان رویداد، به‌علاوه‌ی شناسه‌ی خودِ چک."""

    check_number: str = ""
    check_amount: Decimal = Decimal(0)
    check_type: str = ""


class CheckOperationIn(BaseModel):
    """یک عملیات روی یک یا چند چک."""

    check_ids: list[UUID]
    #: وضعیتِ مقصد. عملیات از جفتِ (وضعیتِ فعلی، مقصد) مشتق می‌شود، چون یک مقصد
    #: می‌تواند از دو راهِ متفاوت آمده باشد.
    status: str
    bank_account_id: UUID | None = None
    cashbox_id: UUID | None = None
    contact_id: UUID | None = None
    event_date: date | None = None
    note: str = ""

    @model_validator(mode="after")
    def validate_selection(self) -> "CheckOperationIn":
        if not self.check_ids:
            raise ValueError("هیچ چکی انتخاب نشده است")
        if len(set(self.check_ids)) != len(self.check_ids):
            raise ValueError("یک چک دو بار در فهرست آمده است")
        return self


class CheckOperationResultRow(BaseModel):
    check_id: UUID
    number: str
    amount: Decimal


class CheckOperationFailureRow(BaseModel):
    check_id: UUID
    #: پیامِ فارسیِ همان چک — نه یک «ناموفق»ِ کلی (§۴۵).
    reason: str


class CheckOperationOut(BaseModel):
    operation_no: int | None = None
    batch_id: UUID
    operation: str
    operation_label: str
    done: list[CheckOperationResultRow]
    failed: list[CheckOperationFailureRow]
    total_amount: Decimal
