from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class GeneralLedgerLineOut(BaseModel):
    entry_id: UUID
    entry_number: int | None
    entry_date: date
    description: str
    debit: Decimal
    credit: Decimal
    balance: Decimal


class GeneralLedgerOut(BaseModel):
    account_id: UUID
    account_code: str
    account_name: str
    opening_balance: Decimal
    lines: list[GeneralLedgerLineOut]
    closing_balance: Decimal


class TrialBalanceRowOut(BaseModel):
    account_id: UUID
    account_code: str
    account_name: str
    account_type: str
    total_debit: Decimal
    total_credit: Decimal
    balance: Decimal


class AccountBalanceOut(BaseModel):
    account_id: UUID
    account_code: str
    account_name: str
    balance: Decimal


class BalanceSheetOut(BaseModel):
    as_of: date
    assets: list[AccountBalanceOut]
    liabilities: list[AccountBalanceOut]
    equity: list[AccountBalanceOut]
    total_assets: Decimal
    total_liabilities: Decimal
    total_equity: Decimal
    current_period_profit: Decimal


class IncomeStatementOut(BaseModel):
    date_from: date | None
    date_to: date | None
    income: list[AccountBalanceOut]
    expenses: list[AccountBalanceOut]
    total_income: Decimal
    total_expenses: Decimal
    net_profit: Decimal


class AgingRowOut(BaseModel):
    contact_id: UUID
    contact_name: str
    current: Decimal  # ۰ تا ۳۰ روز
    d31_60: Decimal
    d61_90: Decimal
    over_90: Decimal  # بیش از ۹۰ روز
    total: Decimal


class AgingReportOut(BaseModel):
    """تحلیل سنیِ مطالبات یا بدهی‌ها به تفکیک شخص و بازه‌ی سنی."""

    as_of: date
    kind: str  # receivable | payable
    rows: list[AgingRowOut]
    total_current: Decimal
    total_31_60: Decimal
    total_61_90: Decimal
    total_over_90: Decimal
    grand_total: Decimal


class CashFlowLineOut(BaseModel):
    account_id: UUID
    account_code: str
    account_name: str
    #: جریانِ نقدِ منسوب به این حساب؛ مثبت = ورود نقد، منفی = خروج نقد
    amount: Decimal


class CashFlowOut(BaseModel):
    """صورت جریان وجوه نقد در یک بازه، به تفکیک سه فعالیت."""

    date_from: date | None
    date_to: date | None
    opening_cash: Decimal  # ماندهٔ نقد ابتدای دوره
    operating: list[CashFlowLineOut]
    investing: list[CashFlowLineOut]
    financing: list[CashFlowLineOut]
    net_operating: Decimal
    net_investing: Decimal
    net_financing: Decimal
    net_change: Decimal  # جمعِ سه فعالیت = تغییرِ نقد در دوره
    closing_cash: Decimal  # = opening_cash + net_change


class VatReportOut(BaseModel):
    """خلاصه‌ی مالیات بر ارزش افزوده در یک بازه — مبنای اظهارنامه/تسویه."""

    date_from: date | None
    date_to: date | None
    sales_net: Decimal  # جمع خالصِ فروش، پس از کسرِ برگشت از فروش
    output_vat: Decimal  # مالیاتِ فروش، پس از کسرِ مالیاتِ برگشت از فروش
    purchase_net: Decimal  # جمع خالصِ خرید، پس از کسرِ برگشت از خرید
    input_vat: Decimal  # اعتبار مالیاتیِ خرید، پس از کسرِ مالیاتِ برگشت از خرید
    net_vat: Decimal  # قابل‌پرداخت به سازمان = output − input (منفی یعنی طلبکار/انتقالی)
    # برگشت‌ها جدا هم گزارش می‌شوند تا معلوم باشد رقمِ خالص از کجا آمده
    sales_returns_net: Decimal
    sales_returns_vat: Decimal
    purchase_returns_net: Decimal
    purchase_returns_vat: Decimal
