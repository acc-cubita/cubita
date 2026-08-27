from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, model_validator


class InstallmentPlanIn(BaseModel):
    contact_id: UUID
    sales_invoice_id: UUID | None = None
    title: str = ""
    total_amount: Decimal
    #: قیمتِ نقدی و سودِ فروشِ اقساطی. اگر داده نشوند، کلِ مبلغ «نقدی» و سود صفر
    #: فرض می‌شود — یعنی رفتارِ قبلی، پس فرم‌ها و APIهای موجود نمی‌شکنند.
    cash_price: Decimal | None = None
    profit_amount: Decimal | None = None
    down_payment: Decimal = Decimal(0)
    num_installments: int
    interval_months: int = 1
    start_date: date
    #: درصدِ جریمه‌ی دیرکرد به‌ازای هر ماه تأخیر (۰ = بدونِ جریمه).
    penalty_rate: Decimal = Decimal(0)
    guarantor_name: str = ""
    guarantor_phone: str = ""
    guarantor_national_id: str = ""
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
        if self.penalty_rate < 0 or self.penalty_rate > 100:
            raise ValueError("نرخ جریمه باید بین ۰ تا ۱۰۰ درصد باشد")
        cash = self.total_amount if self.cash_price is None else self.cash_price
        profit = self.total_amount - cash if self.profit_amount is None else self.profit_amount
        if cash <= 0:
            raise ValueError("قیمت نقدی باید بزرگ‌تر از صفر باشد")
        if profit < 0:
            raise ValueError("سود فروش اقساطی نمی‌تواند منفی باشد")
        if cash + profit != self.total_amount:
            raise ValueError("قیمت نقدی + سود باید برابرِ مبلغ کل باشد")
        self.cash_price, self.profit_amount = cash, profit
        return self


class InstallmentPayIn(BaseModel):
    amount: Decimal
    transaction_date: date
    method: str = "cash"  # cash | bank
    bank_account_id: UUID | None = None
    notes: str = ""

    @model_validator(mode="after")
    def _validate(self) -> "InstallmentPayIn":
        if self.amount <= 0:
            raise ValueError("مبلغ باید بزرگ‌تر از صفر باشد")
        if self.method not in ("cash", "bank"):
            raise ValueError("روش باید نقدی یا بانکی باشد")
        if self.method == "bank" and self.bank_account_id is None:
            raise ValueError("برای روش بانکی، حساب بانکی الزامی است")
        return self


class InstallmentSettleIn(InstallmentPayIn):
    """یک فیش، چند قسط: مبلغ از قدیمی‌ترین قسطِ باز به بعد تسهیم می‌شود."""


class RescheduleLineIn(BaseModel):
    installment_id: UUID
    due_date: date
    amount: Decimal

    @model_validator(mode="after")
    def _validate(self) -> "RescheduleLineIn":
        if self.amount <= 0:
            raise ValueError("مبلغ قسط باید بزرگ‌تر از صفر باشد")
        return self


class RescheduleIn(BaseModel):
    lines: list[RescheduleLineIn]

    @model_validator(mode="after")
    def _validate(self) -> "RescheduleIn":
        if not self.lines:
            raise ValueError("دستِ‌کم یک قسط باید داده شود")
        return self


class InstallmentPaymentOut(BaseModel):
    id: UUID
    installment_id: UUID
    installment_seq: int
    amount: Decimal
    paid_on: date
    method: str
    treasury_transaction_id: UUID | None
    notes: str


class InstallmentOut(BaseModel):
    id: UUID
    seq: int
    due_date: date
    amount: Decimal
    paid_amount: Decimal
    remaining: Decimal
    paid_date: date | None
    status: str  # pending | partial | paid | overdue
    #: روزهای تأخیر و جریمه‌ی برآوردی — هر دو محاسبه‌شده با تاریخِ امروز، ذخیره‌نشده.
    days_late: int = 0
    penalty: Decimal = Decimal(0)


class InstallmentPlanOut(BaseModel):
    id: UUID
    number: int | None
    contact_id: UUID
    contact_name: str
    sales_invoice_id: UUID | None
    title: str
    total_amount: Decimal
    cash_price: Decimal
    profit_amount: Decimal
    profit_pct: Decimal
    down_payment: Decimal
    financed: Decimal  # total_amount - down_payment
    num_installments: int
    interval_months: int
    start_date: date
    status: str
    penalty_rate: Decimal
    guarantor_name: str
    guarantor_phone: str
    guarantor_national_id: str
    notes: str
    installments: list[InstallmentOut]
    payments: list[InstallmentPaymentOut]
    # خلاصه‌ی وصول
    total_paid: Decimal
    total_remaining: Decimal
    next_due_date: date | None
    next_due_amount: Decimal
    overdue_amount: Decimal
    overdue_count: int
    penalty_total: Decimal
    #: درصدِ وصول‌شده از مبلغِ تسهیم‌شده
    collected_pct: Decimal
    #: بیشترین روزِ تأخیر در این قرارداد — سنجه‌ی ریسکِ مشتری
    worst_days_late: int


class EarlySettlementOut(BaseModel):
    remaining: Decimal
    #: سهمِ وصول‌نشده‌ی سود — سقفِ تخفیفِ تعجیل
    unearned_profit: Decimal
    discount: Decimal
    payable: Decimal


class AgingBucket(BaseModel):
    key: str
    label: str
    count: int
    amount: Decimal


class DebtorRow(BaseModel):
    contact_id: UUID
    contact_name: str
    remaining: Decimal
    overdue: Decimal
    plans: int


class InstallmentSummaryOut(BaseModel):
    """نمای مدیریتیِ سبد اقساط — سررسیدهای پیشِ‌رو، معوق‌ها، و بدهکارانِ بزرگ."""

    active_plans: int
    total_financed: Decimal
    total_collected: Decimal
    total_remaining: Decimal
    collected_pct: Decimal
    overdue_amount: Decimal
    overdue_count: int
    penalty_total: Decimal
    due_this_week: Decimal
    due_this_month: Decimal
    buckets: list[AgingBucket]
    top_debtors: list[DebtorRow]
