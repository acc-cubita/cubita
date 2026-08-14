from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, model_validator


class BankAccountIn(BaseModel):
    name: str
    bank_name: str = ""
    account_number: str = ""
    iban: str = ""
    gl_account_id: UUID | None = None  # اگر خالی باشد، حساب پیش‌فرض «۱۱۰۲ بانک» استفاده می‌شود


class BankAccountUpdateIn(BaseModel):
    """ویرایشِ حساب بانکی — فقط فیلدهای ارسال‌شده تغییر می‌کنند. حسابِ دفترِ کلِ
    متناظر (gl_account_id) پس از ساخت عوض نمی‌شود (روی اسناد نشسته)."""

    name: str | None = None
    bank_name: str | None = None
    account_number: str | None = None
    iban: str | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def _name_not_blank(self) -> "BankAccountUpdateIn":
        if self.name is not None and not self.name.strip():
            raise ValueError("نام حساب نمی‌تواند خالی باشد")
        return self


class BankAccountOut(BaseModel):
    id: UUID
    name: str
    bank_name: str
    account_number: str
    iban: str
    gl_account_id: UUID
    is_active: bool

    model_config = {"from_attributes": True}


class CheckIn(BaseModel):
    type: str
    number: str
    bank_name: str = ""
    amount: Decimal
    issue_date: date
    due_date: date
    contact_id: UUID | None = None
    description: str = ""

    @model_validator(mode="after")
    def validate_check(self) -> "CheckIn":
        if self.type not in ("receivable", "payable"):
            raise ValueError("نوع چک باید receivable یا payable باشد")
        if self.amount <= 0:
            raise ValueError("مبلغ چک باید بزرگ‌تر از صفر باشد")
        return self


class CheckOut(BaseModel):
    id: UUID
    type: str
    number: str
    bank_name: str
    amount: Decimal
    issue_date: date
    due_date: date
    status: str
    description: str
    contact_id: UUID | None
    contact_name: str | None = None
    bank_account_id: UUID | None

    model_config = {"from_attributes": True}


class CheckStatusUpdateIn(BaseModel):
    status: str
    bank_account_id: UUID | None = None


class BankDepositWithdrawIn(BaseModel):
    bank_account_id: UUID
    transaction_date: date
    amount: Decimal  # مثبت = واریز، منفی = برداشت
    counter_account_id: UUID
    description: str = ""

    @model_validator(mode="after")
    def validate_amount(self) -> "BankDepositWithdrawIn":
        if self.amount == 0:
            raise ValueError("مبلغ نمی‌تواند صفر باشد")
        return self


class BankTransactionOut(BaseModel):
    id: UUID
    bank_account_id: UUID
    transaction_date: date
    amount: Decimal
    description: str
    is_reconciled: bool
    source_type: str

    model_config = {"from_attributes": True}


class BankStatementLineIn(BaseModel):
    line_date: date
    amount: Decimal
    description: str = ""


class BankStatementImportIn(BaseModel):
    lines: list[BankStatementLineIn]

    @model_validator(mode="after")
    def validate_lines(self) -> "BankStatementImportIn":
        if not self.lines:
            raise ValueError("حداقل یک ردیف صورت‌حساب لازم است")
        return self


class BankStatementLineOut(BaseModel):
    id: UUID
    bank_account_id: UUID
    line_date: date
    amount: Decimal
    description: str
    matched_transaction_id: UUID | None

    model_config = {"from_attributes": True}


class MatchStatementLineIn(BaseModel):
    bank_transaction_id: UUID


class ReconciliationSummaryOut(BaseModel):
    statement_total: Decimal
    matched_count: int
    unmatched_statement_lines: list[BankStatementLineOut]
    unreconciled_system_transactions: list[BankTransactionOut]


class PettyCashChargeIn(BaseModel):
    transaction_date: date
    amount: Decimal
    source_account_id: UUID
    description: str = ""

    @model_validator(mode="after")
    def validate_positive(self) -> "PettyCashChargeIn":
        if self.amount <= 0:
            raise ValueError("مبلغ باید بزرگ‌تر از صفر باشد")
        return self


class PettyCashExpenseIn(BaseModel):
    transaction_date: date
    amount: Decimal
    expense_account_id: UUID
    description: str = ""

    @model_validator(mode="after")
    def validate_positive(self) -> "PettyCashExpenseIn":
        if self.amount <= 0:
            raise ValueError("مبلغ باید بزرگ‌تر از صفر باشد")
        return self


class PettyCashTransactionOut(BaseModel):
    id: UUID
    type: str
    transaction_date: date
    amount: Decimal
    description: str
    counter_account_id: UUID

    model_config = {"from_attributes": True}
