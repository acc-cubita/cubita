from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class GeneralLedgerLineOut(BaseModel):
    #: شناسه‌ی خودِ ردیف — کلیدِ پایدارِ رابط و لنگرِ drill-down به سند.
    line_id: UUID
    entry_id: UUID
    entry_number: int | None
    entry_date: date
    entry_status: str
    source_type: str | None
    #: حسابِ خودِ ردیف — در دفترِ معین همان حسابِ انتخاب‌شده است، در دفترِ کل
    #: زیرحسابی که مبلغ از آن آمده.
    account_code: str
    account_name: str
    description: str
    debit: Decimal
    credit: Decimal
    balance: Decimal
    #: ارز و پیگیری از قبل روی ردیفِ سند بودند و هیچ گزارشی نشانشان نمی‌داد.
    currency_code: str | None = None
    fx_amount: Decimal | None = None
    fx_rate: Decimal | None = None
    tracking_no: str | None = None
    tracking_date: date | None = None
    #: تفصیلی و مرکزِ هزینه‌ی ردیف (اگر داشته باشد) — برای ستون‌های «مرور حساب».
    analytic_id: UUID | None = None
    analytic_code: str | None = None
    analytic_name: str | None = None
    cost_center_id: UUID | None = None
    cost_center_code: str | None = None
    cost_center_name: str | None = None


class LedgerFxTotalOut(BaseModel):
    """جمعِ ارزی به تفکیکِ ارز — دلار و یورو با هم جمع نمی‌شوند."""

    currency_code: str
    amount: Decimal


class GeneralLedgerOut(BaseModel):
    #: در «دفترِ تفصیلی» حسابِ واحدی در کار نیست، پس هر سه می‌توانند خالی باشند.
    account_id: UUID | None
    account_code: str | None
    account_name: str | None
    opening_balance: Decimal
    lines: list[GeneralLedgerLineOut]
    closing_balance: Decimal
    fx_totals: list[LedgerFxTotalOut] = []
    #: جمعِ گردشِ *کلِ دوره* — مستقل از این‌که `lines` یک برش است یا همه.
    period_debit: Decimal = Decimal(0)
    period_credit: Decimal = Decimal(0)
    #: شمارِ کلِ ردیف‌های دوره؛ با `offset`/`limit` صفحه‌بندی را ممکن می‌کند.
    total_lines: int = 0
    offset: int = 0
    #: `None` یعنی صفحه‌بندی نشده و `lines` همه‌ی ردیف‌هاست (رفتارِ پیشین).
    limit: int | None = None


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
    source_id: UUID | None = None
    source_number: int | None = None
    #: حرکتِ سندِ باطل یا جبرانِ آن — با بهای ثبت‌شده‌اش می‌آید و میانگین را تکان نمی‌دهد.
    voided: bool = False
    qty_in: Decimal
    qty_out: Decimal
    #: بهای ارزش‌گذاری (بازپخشِ زمانی)؛ `recorded_unit_cost` همانی است که سند نوشته.
    unit_cost: Decimal | None
    recorded_unit_cost: Decimal | None
    #: بهای ثبت‌شده با میانگینِ همان تاریخ نمی‌خواند — ارزش‌گذاریِ منقضی.
    stale: bool = False
    #: بهای این حرکت در «قیمت‌گذاری اسناد انبار» اصلاح شده؛ `recorded_unit_cost` بهای پس از اصلاح است.
    adjusted: bool = False
    value_in: Decimal | None
    value_out: Decimal | None
    balance_value: Decimal | None
    #: میانگینِ کلِ شرکت پس از این حرکت.
    average_cost: Decimal | None
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
    opening_value: Decimal | None
    lines: list[KardexLineOut]
    total_in: Decimal
    total_out: Decimal
    total_value_in: Decimal | None
    total_value_out: Decimal | None
    closing_qty: Decimal
    closing_value: Decimal | None
    average_cost: Decimal | None
    stale_count: int


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
    #: مانده‌ی اول، ورود، خروج — به مقدار و ریال. `qty_on_hand`/`stock_value` مانده‌ی پایان‌اند.
    opening_qty: Decimal = Decimal(0)
    opening_value: Decimal | None = Decimal(0)
    in_qty: Decimal = Decimal(0)
    in_value: Decimal | None = Decimal(0)
    out_qty: Decimal = Decimal(0)
    out_value: Decimal | None = Decimal(0)
    #: جمعِ «مقدار × بهای ثبت‌شده». اختلافش با `stock_value` ارزش‌گذاریِ منقضی است.
    book_value: Decimal | None = Decimal(0)
    stale_from: date | None = None
    qty_on_hand: Decimal
    unit_cost: Decimal | None  # بهای تمام‌شده‌ی میانگین موزون
    stock_value: Decimal | None  # qty_on_hand × unit_cost


class InventoryReportOut(BaseModel):
    """ارزش‌گذاری موجودی انبار — تعداد و ارزش ریالیِ هر کالای موجود."""

    as_of: date | None
    date_from: date | None = None
    warehouse_id: UUID | None = None
    rows: list[InventoryRowOut]
    total_value: Decimal | None
    total_opening_value: Decimal | None = Decimal(0)
    total_in_value: Decimal | None = Decimal(0)
    total_out_value: Decimal | None = Decimal(0)
    total_book_value: Decimal | None = Decimal(0)
    stale_item_count: int = 0
    item_count: int


class ContactStatementLineOut(BaseModel):
    txn_date: date
    kind: str  # opening | sales_invoice | sales_return | purchase_invoice | purchase_return | receipt | payment
    number: int | None
    description: str
    debit: Decimal  # بدهیِ شخص به ما را زیاد می‌کند
    credit: Decimal  # بدهیِ شخص به ما را کم می‌کند
    balance: Decimal  # ماندهٔ در حال اجرا؛ مثبت = شخص به ما بدهکار است
    #: ردیابی — کارتِ حساب بن‌بست نیست: از ردیف به خودِ سند و به سندِ حسابداری‌اش
    #: می‌شود رفت (فصلِ اعلامیه، §۲۲ §۲۳). مانده‌ی اول دوره هیچ‌کدام را ندارد.
    source_id: UUID | None = None
    entry_number: int | None = None
    entry_date: date | None = None


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


class EquityComponentOut(BaseModel):
    """یک جزءِ حقوق صاحبان سهام (سرمایه، سود انباشته، …) با مانده‌ی اول و پایان."""

    account_id: UUID
    account_code: str
    account_name: str
    opening: Decimal
    change: Decimal
    closing: Decimal


class EquityPartnerRowOut(BaseModel):
    """سهمِ هر شریک از آورده و برداشتِ دوره.

    از جدولِ تراکنش‌ها می‌آید نه از دفتر، چون سندِ حسابداری نامِ شریک را ندارد —
    پس آورده‌ای که با سندِ دستی ثبت شده در این تفکیک دیده نمی‌شود، هرچند در
    جمع‌های بالا هست.
    """

    contact_id: UUID
    contact_name: str
    contributed: Decimal
    withdrawn: Decimal


class EquityStatementOut(BaseModel):
    """صورت تغییرات در حقوق صاحبان سهام.

    تساویِ پایه: `opening + contributions − withdrawals + other_changes = closing`.

    `net_profit` عمداً **بیرونِ** این تساوی است: تا سندِ اختتامیه زده نشود سودِ
    دوره در هیچ حسابِ حقوق صاحبان سهامی ننشسته — همان کاری که ترازنامه با
    `current_period_profit` می‌کند.
    """

    date_from: date | None
    date_to: date
    opening_equity: Decimal
    contributions: Decimal  # آورده‌ی سرمایه در دوره
    withdrawals: Decimal  # کاهشِ سرمایه در دوره
    #: هر حرکتِ حقوق صاحبان سهام که تراکنشِ نوع‌دار ندارد — سندِ دستی، اختتامیه،
    #: افتتاحیه. باقی‌مانده است، پس تساوی همیشه برقرار می‌ماند.
    other_changes: Decimal
    closing_equity: Decimal
    net_profit: Decimal
    components: list[EquityComponentOut]
    partner_rows: list[EquityPartnerRowOut]
    reconciled: bool


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


class VatBreakdownOut(BaseModel):
    """تفکیکِ پایه‌ی مالیاتی — جوابِ «چقدر فروشِ معاف داشته‌ایم؟».

    وضعیت از **ردیفِ فاکتور** می‌آید (لحظه‌ی معامله)، و کالا/خدمت از خودِ کالا.
    """

    taxable_goods: Decimal
    taxable_services: Decimal
    exempt_goods: Decimal
    exempt_services: Decimal


class MixedVatInvoiceOut(BaseModel):
    """فاکتوری که ردیفِ معاف و مشمول را با هم دارد و نرخِ سربرگش غیرصفر است.

    یعنی روی ردیفِ معاف هم مالیات گرفته شده، چون مالیات یک نرخ روی کلِ فاکتور است.
    **گزارش است نه گارد** — فاکتورِ ثبت‌شده ویرایش نمی‌شود.
    """

    invoice_id: UUID
    number: int | None
    invoice_date: date
    tax_amount: Decimal
    #: خالصِ ردیف‌های معاف که ناخواسته در پایه‌ی مالیات آمده‌اند.
    exempt_net: Decimal


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
    #: ترکیبِ فروش/خریدِ دوره. برگشت‌ها این‌جا نمی‌آیند — ارقامِ بالا خالصِ پس از
    #: برگشت‌اند و این‌ها ترکیب را نشان می‌دهند؛ یکی‌کردنشان دو معنا را قاطی می‌کرد.
    sales_breakdown: VatBreakdownOut
    purchase_breakdown: VatBreakdownOut
    mixed_sales_invoices: list[MixedVatInvoiceOut] = []
    mixed_purchase_invoices: list[MixedVatInvoiceOut] = []


class IntegrityRowOut(BaseModel):
    """یک ردیفِ یافته — شکلش عمداً برای همه‌ی بررسی‌ها یکی است.

    یک شکل یعنی یک جدول در رابط، و یعنی افزودنِ بررسیِ تازه فقط کارِ بک‌اند است.
    `entry_id`/`account_id` لنگرِ drill-down‌اند: هر یافته باید بتواند کاربر را به
    خودِ سند یا دفترِ حساب ببرد.
    """

    label: str
    detail: str
    debit: Decimal
    credit: Decimal
    #: عددی که می‌گوید «چقدر پرت است». بررسی‌های ساختاری صفر می‌گذارند.
    difference: Decimal
    entry_id: UUID | None = None
    account_id: UUID | None = None
    #: لنگرِ کاردکس — برای بررسی‌های انبار.
    item_id: UUID | None = None


class IntegrityCheckOut(BaseModel):
    key: str
    title: str
    description: str
    #: error سلامتِ دفتر را زیر سؤال می‌برد؛ warning فقط دیده می‌شود.
    severity: str
    #: `ledger` = بررسیِ سازگاریِ دفتر (صفحه‌ی حسابدار)، `assurance` = بررسیِ
    #: حسابرسی. پیش‌فرض دارد تا پاسخِ اندپوینتِ موجود ذره‌ای عوض نشود.
    family: str = "ledger"
    ok: bool
    #: شمارشِ کاملِ یافته‌ها، حتی وقتی `rows` بریده شده.
    count: int
    rows: list[IntegrityRowOut]
    truncated: bool


class IntegrityReportOut(BaseModel):
    date_from: date | None
    date_to: date | None
    total_debit: Decimal
    total_credit: Decimal
    difference: Decimal
    ok: bool
    checks: list[IntegrityCheckOut]


# ───────────────────── مرور جامع طرف حساب ─────────────────────


class RolePositionOut(BaseModel):
    """مانده‌ی یک نقشِ طرف حساب — و اینکه با دفتر می‌خواند یا نه."""

    role: str
    role_label: str
    account_id: UUID
    account_code: str
    account_name: str
    debit_total: Decimal
    credit_total: Decimal
    net: Decimal
    #: مانده‌ی **قابلِ تسویه** — با `net` یکی نیست و نباید یکی گرفته شود.
    open_net: Decimal
    #: `None` یعنی این طرف حساب تفصیلی ندارد و مانده‌ی دفتریِ شخصی‌اش قابلِ
    #: استخراج نیست. با صفر یکی نیست.
    ledger_net: Decimal | None = None
    unattributed: Decimal | None = None
    document_count: int


class CounterpartySummaryOut(BaseModel):
    contact_id: UUID
    contact_name: str
    contact_type: str
    has_analytic: bool
    positions: list[RolePositionOut]
    #: جمعِ نقش‌ها — **مشتق**، نه ذخیره‌شده. و هیچ تهاتری در دفتر نمی‌کند.
    total_net: Decimal
    open_net: Decimal
    uncleared_cheques: Decimal
    net_without_uncleared_cheques: Decimal


class CounterpartyEventOut(BaseModel):
    """یک رویداد در خطِ زمانیِ طرف حساب — با لنگرِ ساختاریافته‌اش."""

    source_type: str
    source_id: UUID
    label: str
    number: int | None = None
    entry_number: int | None = None
    document_date: date
    role: str
    role_label: str
    account_id: UUID
    account_code: str
    account_name: str
    side: str
    document_amount: Decimal
    currency_code: str | None = None
    fx_amount: Decimal | None = None
    settled_amount: Decimal
    remaining_amount: Decimal
    status: str
    status_label: str
    running_balance: Decimal


class CounterpartyEventLineOut(BaseModel):
    """یک قلم — نوعش می‌گوید کدام ستون‌ها برایش معنی دارند."""

    kind: str
    seq: int
    code: str
    title: str
    description: str
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    net_unit_price: Decimal | None = None
    debit: Decimal | None = None
    credit: Decimal | None = None


class CounterpartyEventDetailOut(BaseModel):
    source_type: str
    source_id: UUID
    label: str
    journal_entry_id: UUID | None = None
    lines: list[CounterpartyEventLineOut]


# ───────────────────── مرور فروش ─────────────────────


class SalesReviewSummaryOut(BaseModel):
    invoice_count: int
    line_count: int
    gross_amount: Decimal
    discount: Decimal
    tax: Decimal
    return_amount: Decimal
    net_sales: Decimal
    sold_qty: Decimal
    issued_qty: Decimal
    #: فروخته‌شده منهای خارج‌شده — عددی که تا این فصل هیچ‌جا دیده نمی‌شد.
    unissued_qty: Decimal
    item_count: int


class SalesByItemOut(BaseModel):
    item_id: UUID
    item_code: str
    item_name: str
    is_service: bool
    unit_name: str
    secondary_unit_name: str = ""
    sold_qty: Decimal
    returned_qty: Decimal
    net_qty: Decimal
    issued_qty: Decimal
    unissued_qty: Decimal
    #: مقدار به واحدِ دوم — **همان مقدار** با واحدِ دیگر، نه فروشی جدا.
    #: `None` یعنی واحد دوم یا ضریبش تعریف نشده.
    sold_qty_secondary: Decimal | None = None
    issued_qty_secondary: Decimal | None = None
    line_count: int
    gross_amount: Decimal
    discount: Decimal
    tax: Decimal
    duty: Decimal
    addition: Decimal
    net_amount: Decimal
    return_amount: Decimal
    net_sales: Decimal
    #: فیِ متوسطِ **تاریخی و وزنی** — نه قیمتِ اعلامیه‌ی امروز.
    average_unit_price: Decimal | None = None
    #: از دفترِ موجودی، نه از «فروش منهای برگشت».
    stock_qty: Decimal


class SalesByCustomerOut(BaseModel):
    contact_id: UUID | None = None
    contact_name: str
    contact_type: str = ""
    group_name: str = ""
    credit_limit: Decimal = Decimal(0)
    invoice_count: int
    sold_qty: Decimal
    returned_qty: Decimal
    issued_qty: Decimal
    gross_amount: Decimal
    discount: Decimal
    tax: Decimal
    duty: Decimal
    addition: Decimal
    net_amount: Decimal
    return_amount: Decimal
    net_sales: Decimal


class SalesByWarehouseOut(BaseModel):
    warehouse_id: UUID
    warehouse_name: str
    issue_count: int
    invoice_count: int
    issued_qty: Decimal
    issued_cost: Decimal


class SalesDocumentOut(BaseModel):
    source_type: str
    source_id: UUID
    label: str
    number: int | None = None
    document_date: date
    contact_id: UUID | None = None
    contact_name: str
    sale_type_name: str = ""
    is_voided: bool
    line_count: int
    sold_qty: Decimal
    returned_qty: Decimal
    issued_qty: Decimal
    gross_amount: Decimal
    discount: Decimal
    tax: Decimal
    duty: Decimal
    addition: Decimal
    net_amount: Decimal
    return_amount: Decimal
    net_sales: Decimal


class SalesLineOut(BaseModel):
    line_id: UUID
    source_type: str
    source_id: UUID
    number: int | None = None
    document_date: date
    contact_id: UUID | None = None
    contact_name: str
    sale_type_name: str = ""
    item_id: UUID
    item_code: str
    item_name: str
    barcode: str = ""
    unit_name: str = ""
    sold_qty: Decimal
    sold_qty_secondary: Decimal | None = None
    returned_qty: Decimal
    issued_qty: Decimal
    unissued_qty: Decimal
    unit_price: Decimal
    #: انبارهایی که این ردیف واقعاً از آن‌ها خارج شده — می‌تواند چند تا باشد.
    warehouse_names: list[str] = []
    is_voided: bool
    gross_amount: Decimal
    discount: Decimal
    tax: Decimal
    duty: Decimal
    addition: Decimal
    net_amount: Decimal
    return_amount: Decimal
    net_sales: Decimal


class PreinvoiceProgressOut(BaseModel):
    quotation_id: UUID
    line_id: UUID
    number: int | None = None
    quotation_date: date
    contact_id: UUID | None = None
    contact_name: str
    status: str
    item_id: UUID
    item_name: str
    unit_price: Decimal
    #: سه عددِ مستقل. «فاکتورشده» و «خارج‌شده» هر دو **مشتق**اند، نه شمارنده.
    quoted_qty: Decimal
    invoiced_qty: Decimal
    issued_qty: Decimal
    invoice_line_count: int
    remaining_invoiceable: Decimal
    remaining_issueable: Decimal


class InventoryBreakdownRowOut(BaseModel):
    """یک ردیفِ گردشِ انبار روی یک بُعد — تأمین‌کننده، مشتری یا هدفِ حرکت."""

    key: str
    label: str
    item_count: int
    in_qty: Decimal
    out_qty: Decimal
    net_qty: Decimal
    #: مبالغ بی مجوزِ حسابداری `None` می‌شوند — نه صفر، چون صفر عددِ واقعی است.
    in_value: Decimal | None
    out_value: Decimal | None
    net_value: Decimal | None
    #: چند حرکتِ این ردیف ارزش‌گذاریِ منقضی دارد — «این مبلغ هنوز بازمحاسبه نشده».
    stale_count: int


class InventoryBreakdownOut(BaseModel):
    dimension: str
    dimension_label: str
    date_from: date | None
    date_to: date | None
    warehouse_id: UUID | None
    rows: list[InventoryBreakdownRowOut]
    total_in_qty: Decimal
    total_out_qty: Decimal
    total_in_value: Decimal | None
    total_out_value: Decimal | None
    stale_count: int
