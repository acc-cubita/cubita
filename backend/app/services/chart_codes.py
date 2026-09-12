"""نقش‌های معنایی حساب — منبع مشترک همه‌ی سرویس‌هایی که سند خودکار می‌سازند.

**این‌ها دیگر کد حساب نیستند، نقش‌اند.** قبلاً مقدارشان رشته‌ی کد بود (`"1101"`) و
`get_account` با همان کد جست‌وجو می‌کرد. مشکلش این بود که کد حساب متعلق به مشتری
است، نه به ما: حسابداران چارت را بازشماره‌گذاری می‌کنند تا با رویه‌ی خودشان یا با
الزامات گزارش‌گیری جور شود. لحظه‌ای که مشتری «صندوق» را از ۱۱۰۱ به چیز دیگری
می‌برد، هر ثبت خودکاری در سیستم می‌شکست.

حالا حسابِ نقش‌دار با ستون `system_role` علامت‌گذاری می‌شود و منطق ثبت هرگز
نمی‌داند مشتری چه شماره‌ای رویش گذاشته. نام ثابت‌ها عمداً دست‌نخورده ماند تا هر ۳۹
فراخوانی موجود بدون تغییر کار کند.
"""

CASH = "cash"
BANK = "bank"
PETTY_CASH = "petty_cash"
ACCOUNTS_RECEIVABLE = "accounts_receivable"
INVENTORY = "inventory"
CHECKS_RECEIVABLE = "checks_receivable"
ACCOUNTS_PAYABLE = "accounts_payable"
CHECKS_PAYABLE = "checks_payable"
INSURANCE_TAX_PAYABLE = "insurance_tax_payable"
PAYROLL_PAYABLE = "payroll_payable"
SALES_REVENUE = "sales_revenue"
COGS = "cogs"
PAYROLL_EXPENSE = "payroll_expense"
#: وام و مساعده‌ی کارکنان — **دارایی** است نه هزینه: پولی که به کارمند داده‌ایم و
#: قسط‌به‌قسط از حقوقش برمی‌گردد. حسابِ نقش‌دارِ تازه است، پس با
#: `get_or_create_account` ساخته می‌شود تا چارتِ مشتریانِ موجود هم نشکند.
EMPLOYEE_LOAN = "employee_loan"
INVENTORY_ADJUSTMENT = "inventory_adjustment"
RETAINED_EARNINGS = "retained_earnings"
VAT_PAYABLE = "vat_payable"  # مالیات بر ارزش افزوده‌ی فروش (بدهی — به دارایی پرداختنی)
VAT_RECEIVABLE = "vat_receivable"  # مالیات بر ارزش افزوده‌ی خرید (اعتبار مالیاتی — دارایی)
FIXED_ASSETS = "fixed_assets"  # بهای تمام‌شده‌ی دارایی‌های ثابت (دارایی)
ACCUMULATED_DEPRECIATION = "accumulated_depreciation"  # استهلاک انباشته (کاهنده‌ی دارایی)
DEPRECIATION_EXPENSE = "depreciation_expense"  # هزینه‌ی استهلاک دوره (هزینه)
SALES_ROUNDING = "sales_rounding"  # تعدیلِ گِرد کردنِ مبلغِ فاکتور فروش (کاهنده/افزاینده‌ی درآمد)
SALES_ADDITIONS = "sales_additions"
SALES_DISCOUNT = "sales_discount"
FX_GAIN = "fx_gain"  # سودِ تسعیرِ ارز (درآمد)
FX_LOSS = "fx_loss"  # زیانِ تسعیرِ ارز (هزینه)
BANK_FEE = "bank_fee"  # کارمزد و هزینه‌های بانکی (هزینه) — کارمزدِ تسویه‌ی کارتخوان هم اینجا می‌نشیند
#: وجوهِ در راهِ کارت‌خوان — حسابِ واسط بینِ «کارت کشیده شد» و «پول به بانک رسید».
#:
#: **چرا لازم است:** کارت‌کشیدنِ مشتری و رسیدنِ پول به بانک یک رویداد نیستند؛ شرکتِ
#: پرداخت چند روز بعد جمعِ چند تراکنش را واریز می‌کند. تا پیش از این، رسیدِ کارتی
#: همان لحظه معینِ *بانک* را بدهکار می‌کرد — یعنی مانده‌ی بانک دقیقاً به اندازه‌ی
#: پولِ تسویه‌نشده باد کرده بود و مغایرت‌گیری با صورت‌حسابِ بانک از پایه نمی‌خواند.
#: حالا مرحله‌ی اول اینجا می‌نشیند و تسویه آن را به بانک منتقل می‌کند.
POS_CLEARING = "pos_clearing"
#: چک‌های واگذارشده به بانک — حسابِ واسط بینِ «چک نزدِ ماست» و «پول به حساب نشست».
#:
#: **چرا لازم است:** واگذاری به بانک وصول نیست. تا امروز واگذاری هیچ سندی نمی‌زد،
#: پس مبلغِ چک تا لحظه‌ی وصول روی «چک‌های دریافتنی» می‌ماند و دفتر نمی‌توانست
#: بگوید چقدر از آن هنوز نزدِ ماست و چقدر دستِ بانک. واگذاری حالا طبقه‌بندیِ
#: دوباره است: دارایی از بین نرفته، فقط محلش عوض شده.
CHECKS_IN_COLLECTION = "checks_in_collection"
#: دو حسابِ واسطِ پایانِ سال. اختتامیه همه‌ی حساب‌های دائمی را در پایانِ سال صفر
#: می‌کند و افتتاحیه در ابتدای سالِ بعد دوباره بازشان می‌گرداند؛ جمعِ این دو در
#: هر دو سند صفر است، پس هیچ‌کدام مانده‌ی واقعی نمی‌سازند.
CLOSING_ACCOUNT = "closing_account"  # حسابِ اختتامیه
OPENING_ACCOUNT = "opening_account"  # حسابِ افتتاحیه

#: نگاشت نقش به کد پیش‌فرض چارت. فقط هنگام provisioning و backfill مهاجرت استفاده
#: می‌شود؛ منطق ثبت هرگز از این عبور نمی‌کند.
DEFAULT_CODE_BY_ROLE = {
    CASH: "1101",
    BANK: "1102",
    PETTY_CASH: "1103",
    ACCOUNTS_RECEIVABLE: "1104",
    INVENTORY: "1105",
    CHECKS_RECEIVABLE: "1106",
    ACCOUNTS_PAYABLE: "2101",
    CHECKS_PAYABLE: "2102",
    INSURANCE_TAX_PAYABLE: "2103",
    PAYROLL_PAYABLE: "2104",
    VAT_PAYABLE: "2105",
    VAT_RECEIVABLE: "1107",
    FIXED_ASSETS: "1201",
    ACCUMULATED_DEPRECIATION: "1202",
    RETAINED_EARNINGS: "3102",
    SALES_REVENUE: "4101",
    SALES_ROUNDING: "4102",
    SALES_ADDITIONS: "4198",
    SALES_DISCOUNT: "4199",
    COGS: "5101",
    PAYROLL_EXPENSE: "5102",
    EMPLOYEE_LOAN: "1111",
    INVENTORY_ADJUSTMENT: "5105",
    DEPRECIATION_EXPENSE: "5106",
    FX_GAIN: "4106",
    FX_LOSS: "5116",
    BANK_FEE: "5111",
    POS_CLEARING: "1112",
    CHECKS_IN_COLLECTION: "1113",
    CLOSING_ACCOUNT: "3901",
    OPENING_ACCOUNT: "3902",
}

ROLE_BY_DEFAULT_CODE = {code: role for role, code in DEFAULT_CODE_BY_ROLE.items()}
