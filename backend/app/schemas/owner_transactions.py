from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, model_validator

from app.models.owner_transactions import OWNER_TRANSACTION_TYPES


class OwnerTransactionIn(BaseModel):
    """ورودیِ تراکنشِ مالک/شریک.

    `type` **اجباری و بی پیش‌فرض** است. پیش‌فرض‌دادنش دقیقاً همان چیزی می‌شد که
    قاعده‌ی ۵۲ منع می‌کند: نوعِ حسابداری از جهتِ پول حدس زده شود. کاربر باید
    بگوید این پول آورده‌ی سرمایه است یا وام یا بازپرداخت — سه رویدادِ متفاوت با
    یک جهت.
    """

    type: str
    transaction_date: date
    contact_id: UUID
    amount: Decimal
    method: str = "cash"  # cash | bank
    bank_account_id: UUID | None = None
    #: خالی = صندوقِ پیش‌فرض — همان قراردادِ `TreasuryTransactionIn`.
    cashbox_id: UUID | None = None
    description: str = ""
    evidence_ref: str = ""

    @model_validator(mode="after")
    def validate_fields(self) -> "OwnerTransactionIn":
        if self.type not in OWNER_TRANSACTION_TYPES:
            raise ValueError("نوعِ تراکنشِ شریک نامعتبر است")
        if self.amount <= 0:
            raise ValueError("مبلغ باید بزرگ‌تر از صفر باشد")
        if self.method not in ("cash", "bank"):
            raise ValueError("روش باید cash یا bank باشد")
        if self.method == "bank" and self.bank_account_id is None:
            raise ValueError("برای روش بانکی، انتخاب حساب بانکی الزامی است")
        return self


class OwnerTransactionOut(BaseModel):
    id: UUID
    type: str
    type_label: str
    transaction_date: date
    contact_id: UUID
    contact_name: str
    amount: Decimal
    method: str
    bank_account_id: UUID | None
    cashbox_id: UUID | None
    description: str
    evidence_ref: str
    journal_entry_id: UUID | None
    voided_at: datetime | None
    void_reason: str

    model_config = {"from_attributes": True}


class PartnerBalanceOut(BaseModel):
    """ماندهٔ «جاری شرکا»ی یک شریک.

    مثبت = شرکت به او بدهکار است؛ منفی = او به شرکت. سرمایه در این عدد **نیست** —
    آورده‌ی سرمایه بدهیِ شرکت به شریک نمی‌سازد.
    """

    contact_id: UUID
    contact_name: str
    share_percent: Decimal
    balance: Decimal
