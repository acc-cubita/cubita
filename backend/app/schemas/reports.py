from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class GeneralLedgerLineOut(BaseModel):
    entry_id: UUID
    entry_number: int | None
    entry_date: date
    #: حسابِ خودِ ردیف — در دفترِ معین همان حسابِ انتخاب‌شده است، در دفترِ کل
    #: زیرحسابی که مبلغ از آن آمده.
    account_code: str
    account_name: str
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



class NatureViolationOut(BaseModel):
    """یک حسابِ خلافِ ماهیت. `balance` همیشه مثبت است و سمتش در `balance_side` می‌آید."""

    account_id: UUID
    account_code: str
    account_name: str
    account_type: str
    #: ماهیتِ مؤثر (debit/credit) — «any» هرگز این‌جا نمی‌آید چون تخلف ندارد.
    nature: str
    #: True یعنی کاربر خودش ماهیت را ست کرده، False یعنی از نوعِ حساب مشتق شده.
    nature_is_explicit: bool
    #: تیکِ «کنترل ماهیت طی دوره» روی همین حساب.
    nature_control: bool = False
    total_debit: Decimal
    total_credit: Decimal
    balance: Decimal
    balance_side: str


class MissingTafsiliOut(BaseModel):
    """ردیفی روی حسابِ «تفصیلی پذیر» که تفصیلی ندارد.

    در **هر سه** سطحِ اجبار پر می‌شود؛ سطحِ اجبار تعیین می‌کند چه چیزی *مسدود* شود،
    نه چه چیزی *دیده* شود.
    """

    account_id: UUID
    account_code: str
    account_name: str
    entry_id: UUID
    entry_number: int | None
    entry_date: date
    source_type: str
    #: سندِ دستی یا ساخته‌ی ماژول — در حالتِ «ترکیبی» تقریباً همه‌ی این ردیف‌ها
    #: از ماژول‌ها می‌آیند، و همان است که باید دیده شود.
    is_manual: bool
    debit: Decimal
    credit: Decimal
    description: str


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


class KardexLineOut(BaseModel):
    entry_date: date
    source_type: str
    source_label: str
    qty_in: Decimal
    qty_out: Decimal
    unit_cost: Decimal
    balance_qty: Decimal  # موجودی در حال اجرا پس از این حرکت


class KardexReportOut(BaseModel):
    """کاردکس کالا: همه‌ی ورود/خروج‌های یک کالا با موجودیِ در حال اجرا."""

    item_id: UUID
    item_sku: str
    item_name: str
    unit: str
    warehouse_id: UUID | None
    date_from: date | None
    date_to: date | None
    opening_qty: Decimal
    lines: list[KardexLineOut]
    total_in: Decimal
    total_out: Decimal
    closing_qty: Decimal


class DashboardMonthOut(BaseModel):
    jy: int  # سال شمسی
    jm: int  # ماه شمسی (۱..۱۲)
    sales: Decimal
    purchases: Decimal


class DashboardItemOut(BaseModel):
    item_id: UUID
    name: str
    qty: Decimal
    revenue: Decimal


class DashboardCustomerOut(BaseModel):
    contact_id: UUID
    name: str
    total: Decimal


class SalesDashboardOut(BaseModel):
    """تحلیل فروش برای صفحه‌ی نمای کلی."""

    months: int
    monthly: list[DashboardMonthOut]
    top_items: list[DashboardItemOut]
    top_customers: list[DashboardCustomerOut]


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
    kind: str  # opening | sales_invoice | sales_return | purchase_invoice | purchase_return | receipt | payment
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


class SeasonalPartyRowOut(BaseModel):
    """یک طرف حساب در یک نوعِ معامله (خرید یا فروش) در یک فصل — تجمیعِ فاکتورها."""

    contact_id: UUID | None  # NULL = تجمیعِ معاملاتِ خرد بدونِ طرف حسابِ مشخص
    contact_name: str
    entity_type: str  # real | legal | aggregate
    national_id: str | None
    economic_code: str | None
    postal_code: str | None
    invoice_count: int
    gross: Decimal  # ناخالص = خالص + تخفیف (مبلغِ کلِ معامله پیش از تخفیف)
    discount: Decimal
    net: Decimal  # خالصِ پس از تخفیف (پایه‌ی مالیات)
    vat: Decimal  # مالیات و عوارضِ ارزش افزوده
    total: Decimal  # net + vat (مبلغِ نهاییِ قابلِ پرداخت)
    #: کمبودهای هویتِ مالیاتی، به‌صورتِ کدِ ماشین‌خوان — برچسبِ فارسی کارِ رابط است.
    #: خالی یعنی این ردیف آماده‌ی سامانه است. ردیفِ تجمیعیِ خرد همیشه خالی است.
    issues: list[str] = []


class SeasonalSectionOut(BaseModel):
    rows: list[SeasonalPartyRowOut]
    #: شمارشِ آمادگی — تا پیش از آپلود معلوم باشد چند ردیف رد خواهد شد.
    ready_count: int = 0
    incomplete_count: int = 0
    total_gross: Decimal
    total_discount: Decimal
    total_net: Decimal
    total_vat: Decimal
    total_total: Decimal


class SeasonalReportOut(BaseModel):
    """گزارشِ معاملاتِ فصلی (ماده ۱۶۹ ق.م.م) — تجمیعِ خرید و فروشِ هر فصلِ شمسی
    به تفکیکِ طرف حساب، برای سامانه‌ی معاملاتِ فصلیِ سازمانِ امور مالیاتی."""

    year: int  # سالِ شمسی
    quarter: int  # ۱=بهار ۲=تابستان ۳=پاییز ۴=زمستان ۰=کلِ سال
    quarter_label: str
    date_from: date
    date_to: date
    sales: SeasonalSectionOut
    purchases: SeasonalSectionOut


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
