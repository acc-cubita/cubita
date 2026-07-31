from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, model_validator


class InstallmentPlanIn(BaseModel):
    contact_id: UUID
    sales_invoice_id: UUID | None = None
    title: str = ""
    total_amount: Decimal
    down_payment: Decimal = Decimal(0)
    num_installments: int
    interval_months: int = 1
    start_date: date
    notes: str = ""

    @model_validator(mode="after")
    def _validate(self) -> "InstallmentPlanIn":
        if self.total_amount <= 0:
            raise ValueError("مبلغ کل باید بزرگ‌تر از صفر باشد")
        if self.down_payment < 0 or self.down_payment >= self.total_amount:
            raise ValueError("پیش‌پرداخت باید بین صفر و مبلغ کل باشد")
        if self.num_installments < 1:
            raise ValueError("تعداد اقساط باید حداقل ۱ باشد")
        if self.interval_months < 1:
            raise ValueError("فاصله‌ی اقساط باید حداقل ۱ ماه باشد")
        return self


class InstallmentPayIn(BaseModel):
    amount: Decimal
    transaction_date: date
    method: str = "cash"  # cash | bank
    bank_account_id: UUID | None = None

    @model_validator(mode="after")
    def _validate(self) -> "InstallmentPayIn":
        if self.amount <= 0:
            raise ValueError("مبلغ باید بزرگ‌تر از صفر باشد")
        if self.method not in ("cash", "bank"):
            raise ValueError("روش باید نقدی یا بانکی باشد")
        if self.method == "bank" and self.bank_account_id is None:
            raise ValueError("برای روش بانکی، حساب بانکی الزامی است")
        return self


class InstallmentOut(BaseModel):
    id: UUID
    seq: int
    due_date: date
    amount: Decimal
    paid_amount: Decimal
    remaining: Decimal
    paid_date: date | None
    status: str  # pending | partial | paid | overdue


class InstallmentPlanOut(BaseModel):
    id: UUID
    number: int | None
    contact_id: UUID
    contact_name: str
    sales_invoice_id: UUID | None
    title: str
    total_amount: Decimal
    down_payment: Decimal
    financed: Decimal  # total_amount - down_payment
    num_installments: int
    interval_months: int
    start_date: date
    status: str
    notes: str
    installments: list[InstallmentOut]
    # خلاصه‌ی وصول
    total_paid: Decimal
    total_remaining: Decimal
    next_due_date: date | None
    overdue_amount: Decimal
    overdue_count: int
