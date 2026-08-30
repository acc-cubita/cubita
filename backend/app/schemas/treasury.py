from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, model_validator


class TreasuryTransactionIn(BaseModel):
    transaction_date: date
    contact_id: UUID
    amount: Decimal
    method: str = "cash"  # cash | bank
    bank_account_id: UUID | None = None
    description: str = ""

    @model_validator(mode="after")
    def validate_fields(self) -> "TreasuryTransactionIn":
        if self.amount <= 0:
            raise ValueError("مبلغ باید بزرگ‌تر از صفر باشد")
        if self.method not in ("cash", "bank"):
            raise ValueError("روش باید cash یا bank باشد")
        if self.method == "bank" and self.bank_account_id is None:
            raise ValueError("برای روش بانکی، انتخاب حساب بانکی الزامی است")
        return self


class CardPaymentIn(BaseModel):
    """پرداختِ کارتیِ موفق از دستگاهِ کارتخوان — رسیدِ بانکی ثبت می‌کند.

    contact_id خالی = فروشِ گذری (بدونِ طرف‌حساب): سرور طرف‌حسابِ سیستمیِ «فروشِ کارتیِ
    گذری» را می‌سازد/می‌یابد. reference_no (RRN) کلیدِ idempotency است.
    """

    transaction_date: date
    amount: Decimal
    bank_account_id: UUID  # حسابِ تسویه‌ی کارتخوان (رسید به معینِ همین می‌خورد)
    contact_id: UUID | None = None
    reference_no: str  # شماره‌ی مرجع/پیگیری (RRN)
    trace_no: str = ""
    card_mask: str = ""
    terminal_no: str = ""
    psp: str = ""
    description: str = ""

    @model_validator(mode="after")
    def validate_fields(self) -> "CardPaymentIn":
        if self.amount <= 0:
            raise ValueError("مبلغ باید بزرگ‌تر از صفر باشد")
        if not (self.reference_no or "").strip():
            raise ValueError("شماره‌ی مرجعِ تراکنش (RRN) الزامی است")
        return self


class TreasuryTransactionOut(BaseModel):
    id: UUID
    type: str
    transaction_date: date
    contact_id: UUID
    contact_name: str
    amount: Decimal
    method: str
    bank_account_id: UUID | None
    description: str
    journal_entry_id: UUID
    # متادیتای پرداختِ کارتی (اگر از کارتخوان آمده باشد)
    paid_via: str | None = None
    reference_no: str | None = None
    trace_no: str | None = None
    card_mask: str | None = None
    terminal_no: str | None = None
    psp: str | None = None
    #: لحظه‌ی تسویه‌ی کارتخوان. NULL = هنوز تسویه نشده. دفترِ «تسویه‌های کارتخوان»
    #: از همین ساخته می‌شود، بی‌آنکه اندپوینتِ جدایی لازم باشد.
    settled_at: datetime | None = None

    model_config = {"from_attributes": True}


class ContactBalanceOut(BaseModel):
    contact_id: UUID
    receivable_total: Decimal  # جمع فاکتورهای فروش این طرف حساب
    received_total: Decimal  # جمع دریافت‌ها از او
    payable_total: Decimal  # جمع فاکتورهای خرید از او
    paid_total: Decimal  # جمع پرداخت‌ها به او
