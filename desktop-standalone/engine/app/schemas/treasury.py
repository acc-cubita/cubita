from datetime import date
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

    model_config = {"from_attributes": True}


class ContactBalanceOut(BaseModel):
    contact_id: UUID
    receivable_total: Decimal  # جمع فاکتورهای فروش این طرف حساب
    received_total: Decimal  # جمع دریافت‌ها از او
    payable_total: Decimal  # جمع فاکتورهای خرید از او
    paid_total: Decimal  # جمع پرداخت‌ها به او
