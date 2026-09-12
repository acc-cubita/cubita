"""قرارداد API اعلامیه‌ی پرداختِ چندابزاری."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, model_validator

from app.models.payment import PAYMENT_TYPES


class _PositiveAmount(BaseModel):
    amount: Decimal
    description: str = ""

    @model_validator(mode="after")
    def validate_amount(self):
        if self.amount <= 0:
            raise ValueError("مبلغ هر جزء باید بزرگ‌تر از صفر باشد")
        return self


class PaymentCashIn(_PositiveAmount):
    cashbox_id: UUID | None = None


class PaymentBankWithdrawalIn(_PositiveAmount):
    bank_account_id: UUID
    number: str = ""
    withdrawal_date: date | None = None
    bank_fee: Decimal = Decimal(0)
    description2: str = ""

    @model_validator(mode="after")
    def validate_fee(self):
        if self.bank_fee < 0:
            raise ValueError("کارمزد بانکی نمی‌تواند منفی باشد")
        return self


class PaymentPayableChequeIn(_PositiveAmount):
    checkbook_id: UUID | None = None
    bank_account_id: UUID | None = None
    number: str
    due_date: date
    sayad_id: str = ""
    back_number: str = ""
    description2: str = ""

    @model_validator(mode="after")
    def validate_cheque(self):
        self.number = self.number.strip()
        if not self.number:
            raise ValueError("شماره‌ی چک لازم است")
        if self.checkbook_id is None and self.bank_account_id is None:
            raise ValueError("حساب بانکی یا دسته‌چکِ چک پرداختنی لازم است")
        self.sayad_id = self.sayad_id.strip()
        if self.sayad_id and (not self.sayad_id.isdigit() or len(self.sayad_id) != 16):
            raise ValueError("کد صیادی باید ۱۶ رقم باشد")
        return self


class PaymentEndorsedChequeIn(BaseModel):
    check_id: UUID


class PaymentRelatedDocumentIn(BaseModel):
    document_type: str
    document_id: UUID
    allocated_amount: Decimal = Decimal(0)

    @model_validator(mode="after")
    def validate_related(self):
        self.document_type = self.document_type.strip()
        if not self.document_type:
            raise ValueError("نوع سند مرتبط لازم است")
        if self.allocated_amount != 0:
            raise ValueError(
                "سند مرتبط در اعلامیه فقط مرجع است؛ مبلغ تخصیص را موتور تسویه طرف حساب ثبت می‌کند"
            )
        return self


class PaymentIn(BaseModel):
    payment_type: str = "supplier"
    contact_id: UUID
    payment_date: date
    counterparty_account_id: UUID | None = None
    bank_fee_account_id: UUID | None = None
    discount_account_id: UUID | None = None
    currency_code: str = "IRR"
    exchange_rate: Decimal = Decimal(1)
    discount_amount: Decimal = Decimal(0)
    description: str = ""
    description2: str = ""
    establishment: str = ""

    cash: list[PaymentCashIn] = []
    bank_withdrawals: list[PaymentBankWithdrawalIn] = []
    payable_cheques: list[PaymentPayableChequeIn] = []
    endorsed_cheques: list[PaymentEndorsedChequeIn] = []
    related_documents: list[PaymentRelatedDocumentIn] = []

    @model_validator(mode="after")
    def validate_payment(self):
        self.payment_type = self.payment_type.strip().lower()
        if not self.payment_type or len(self.payment_type) > 20:
            raise ValueError("نوع پرداخت معتبر نیست")
        if self.payment_type not in PAYMENT_TYPES and self.counterparty_account_id is None:
            raise ValueError("برای نوع پرداخت سفارشی، حساب معین را انتخاب کنید")
        if not (self.cash or self.bank_withdrawals or self.payable_cheques or self.endorsed_cheques):
            raise ValueError("اعلامیه باید دست‌کم یک جزء پرداخت داشته باشد")
        if self.exchange_rate <= 0:
            raise ValueError("نرخ ارز باید بزرگ‌تر از صفر باشد")
        if self.discount_amount < 0:
            raise ValueError("تخفیف نمی‌تواند منفی باشد")
        if self.discount_amount and self.discount_account_id is None:
            raise ValueError("برای تخفیف، انتخاب حساب تخفیف الزامی است")
        self.description = self.description.strip()
        self.description2 = self.description2.strip()
        if not self.description or not self.description2:
            raise ValueError("شرح و شرح دوم الزامی‌اند")
        self.currency_code = self.currency_code.strip().upper() or "IRR"
        if len(self.currency_code) != 3:
            raise ValueError("کد ارز باید سه حرف باشد")
        return self


class PaymentComponentOut(BaseModel):
    kind: str
    label: str
    amount: Decimal
    bank_fee: Decimal = Decimal(0)
    source_id: UUID | None = None
    reference_no: str = ""
    due_date: date | None = None
    status: str = ""
    description: str = ""


class PaymentRelatedDocumentOut(BaseModel):
    document_type: str
    document_id: UUID
    allocated_amount: Decimal


class PaymentOut(BaseModel):
    id: UUID
    number: int
    payment_type: str
    payment_type_label: str
    contact_id: UUID
    contact_name: str
    payment_date: date
    counterparty_account_id: UUID
    bank_fee_account_id: UUID | None
    discount_account_id: UUID | None
    currency_code: str
    exchange_rate: Decimal
    payment_amount: Decimal
    base_currency_amount: Decimal
    discount_amount: Decimal
    settlement_total: Decimal
    bank_fee_amount: Decimal
    description: str
    description2: str
    establishment: str
    journal_entry_id: UUID
    items_summary: str
    components: list[PaymentComponentOut] = []
    related_documents: list[PaymentRelatedDocumentOut] = []
    voided_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    created_by_name: str = ""
    updated_by_name: str = ""


class PaymentVoidIn(BaseModel):
    reason: str = ""
    void_date: date | None = None
