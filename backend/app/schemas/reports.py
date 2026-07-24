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


class InventoryRowOut(BaseModel):
    item_id: UUID
    sku: str
    name: str
    unit: str
    category: str
    qty_on_hand: Decimal
    unit_cost: Decimal  # بهای تمام‌شده‌ی میانگین موزون
    stock_value: Decimal  # qty_on_hand × unit_cost


class InventoryReportOut(BaseModel):
    """ارزش‌گذاری موجودی انبار — تعداد و ارزش ریالیِ هر کالای موجود."""

    as_of: date | None
    rows: list[InventoryRowOut]
    total_value: Decimal
    item_count: int


class ContactStatementLineOut(BaseModel):
    txn_date: date
    kind: str  # sales_invoice | sales_return | purchase_invoice | purchase_return | receipt | payment
    number: int | None
    description: str
    debit: Decimal  # بدهیِ شخص به ما را زیاد می‌کند
    credit: Decimal  # بدهیِ شخص به ما را کم می‌کند
    balance: Decimal  # ماندهٔ در حال اجرا؛ مثبت = شخص به ما بدهکار است


class ContactStatementOut(BaseModel):
    """کارت حساب یک طرف‌حساب: گردشِ کاملِ فاکتور/برگشت/دریافت/پرداخت با ماندهٔ در حال اجرا."""

    contact_id: UUID
    contact_name: str
    date_from: date | None
    date_to: date | None
    opening_balance: Decimal
    lines: list[ContactStatementLineOut]
    total_debit: Decimal
    total_credit: Decimal
    closing_balance: Decimal


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
