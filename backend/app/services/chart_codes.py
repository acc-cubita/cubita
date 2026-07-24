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
INVENTORY_ADJUSTMENT = "inventory_adjustment"
RETAINED_EARNINGS = "retained_earnings"
VAT_PAYABLE = "vat_payable"  # مالیات بر ارزش افزوده‌ی فروش (بدهی — به دارایی پرداختنی)
VAT_RECEIVABLE = "vat_receivable"  # مالیات بر ارزش افزوده‌ی خرید (اعتبار مالیاتی — دارایی)
FIXED_ASSETS = "fixed_assets"  # بهای تمام‌شده‌ی دارایی‌های ثابت (دارایی)
ACCUMULATED_DEPRECIATION = "accumulated_depreciation"  # استهلاک انباشته (کاهنده‌ی دارایی)
DEPRECIATION_EXPENSE = "depreciation_expense"  # هزینه‌ی استهلاک دوره (هزینه)

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
    COGS: "5101",
    PAYROLL_EXPENSE: "5102",
    INVENTORY_ADJUSTMENT: "5105",
    DEPRECIATION_EXPENSE: "5106",
}

ROLE_BY_DEFAULT_CODE = {code: role for role, code in DEFAULT_CODE_BY_ROLE.items()}
