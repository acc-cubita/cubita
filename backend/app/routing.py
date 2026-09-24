"""سوارکردنِ روترها — تنها جایی که فرقِ دو نسخه در سطحِ مسیرها تعریف می‌شود.

**چرا فهرستِ سیاه و نه یک `if` کنارِ هر روتر.** مسیری که در نسخه‌ی سازمانی نباید
باشد (فروشگاه، بازار، پرداخت، ستاد) روی سرورِ خودِ مشتری یا کار نمی‌کند یا بدتر،
درِ بازی است که کسی مراقبش نیست. یک فهرستِ نام‌دار یعنی تستِ ساختاری
(`tests/test_editions.py`) می‌تواند اثبات کند هیچ‌کدام از آن پیشوندها سوار نشده، و
روترِ تازه‌ی ابری که کسی فراموش کند اینجا بنویسد، آن تست را قرمز می‌کند.

ترتیبِ `include_router` حفظ شده است: FastAPI اولین مسیرِ منطبق را برمی‌دارد.
"""

from fastapi import APIRouter, FastAPI

from app.routers import (
    accounting_ops,
    accounts,
    admin_accounts,
    admin_assurance,
    admin_auth,
    admin_billing,
    admin_commissions,
    admin_errors,
    admin_staff,
    advanced_inventory,
    alerts,
    assets,
    assurance,
    audit,
    auth,
    backup,
    banking,
    benefits,
    billing,
    budgeting,
    calendar,
    cashbox,
    check_ops,
    client_errors,
    company,
    contracting,
    cost_centers,
    crm,
    currencies,
    dashboard,
    devices,
    enterprise_license,
    enterprise_setup,
    fiscal_year,
    installments,
    integration,
    inventory,
    inventory_valuation,
    invoices,
    issue_returns,
    journal,
    manufacturing,
    marketplace,
    members,
    moadian,
    modules,
    numbering,
    onboarding,
    owner_transactions,
    payroll,
    period_close,
    pos_settlements,
    pos_terminals,
    purchase_deductions,
    quotations,
    receipts,
    recurring,
    reports,
    returns,
    sales_ops,
    settlements,
    shop,
    stock_taking,
    storefront,
    subscription,
    trades,
    transfers,
    treasury,
    warehouse_issues,
)

#: روترهایی که فقط در ابر معنا دارند. هر کدام دلیلی دارد که روی سرورِ شرکت نباشد:
#: - ستاد (`admin_*`): مدیریتِ پلتفرمِ ما؛ روی سرورِ مشتری ستادی وجود ندارد.
#: - پرداخت (`billing`): خریدِ پلن با زرین‌پال؛ نسخه‌ی سازمانی با مجوز کار می‌کند.
#: - فروشگاه/بازار (`integration`، `shop`، `storefront`، `marketplace`): تصمیمِ صاحبِ
#:   محصول — این نسخه مخصوصِ شرکت‌ها و سازمان‌هاست و بازارِ عمده‌فروشی ندارد.
#: - پوش (`devices`): توکنِ FCM برای اپِ موبایل؛ نسخه‌ی سازمانی موبایل ندارد.
CLOUD_ONLY: tuple[APIRouter, ...] = (
    admin_auth.router,
    admin_auth.diagnostics_router,
    admin_accounts.router,
    admin_billing.router,
    admin_commissions.router,
    admin_errors.router,
    admin_staff.router,
    admin_assurance.router,
    billing.router,
    integration.router,
    shop.router,
    storefront.router,
    marketplace.router,
    devices.router,
)

#: روترهایی که فقط روی سرورِ سازمانی معنا دارند.
ENTERPRISE_ONLY: tuple[APIRouter, ...] = (enterprise_setup.router, enterprise_license.router)

#: همه‌ی روترها به ترتیبِ سوارشدن.
ALL_ROUTERS: tuple[APIRouter, ...] = (
    auth.router,
    fiscal_year.router,
    cashbox.router,
    numbering.router,
    admin_auth.router,
    admin_auth.diagnostics_router,
    admin_accounts.router,
    admin_billing.router,
    admin_commissions.router,
    admin_errors.router,
    admin_staff.router,
    members.router,
    modules.router,
    accounts.router,
    journal.router,
    accounting_ops.router,
    inventory.router,
    invoices.router,
    quotations.router,
    returns.router,
    owner_transactions.router,
    transfers.router,
    warehouse_issues.router,
    issue_returns.router,
    inventory_valuation.router,
    purchase_deductions.router,
    reports.router,
    banking.router,
    check_ops.router,
    payroll.router,
    benefits.router,
    period_close.router,
    integration.router,
    billing.router,
    receipts.router,
    treasury.router,
    pos_settlements.router,
    pos_terminals.router,
    settlements.router,
    audit.router,
    backup.router,
    subscription.router,
    calendar.router,
    assets.router,
    budgeting.router,
    company.router,
    cost_centers.router,
    moadian.router,
    stock_taking.router,
    recurring.router,
    alerts.router,
    currencies.router,
    crm.router,
    manufacturing.router,
    contracting.router,
    advanced_inventory.router,
    onboarding.router,
    installments.router,
    shop.router,
    storefront.router,
    marketplace.router,
    #: عمومی — صفحه‌ی ثبت‌نام پیش از داشتنِ توکن صنف را می‌پرسد.
    trades.router,
    devices.router,
    sales_ops.router,
    client_errors.router,
    dashboard.router,
    assurance.router,
    #: روترِ کاری پشتِ گیتِ ماژولِ مشتق — هر اندپوینتِ تازه‌اش خودکار گیت می‌خورد.
    assurance.work_router,
    admin_assurance.router,
    enterprise_setup.router,
    enterprise_license.router,
)


def routers_for(edition: str) -> list[APIRouter]:
    """روترهای یک نسخه، به ترتیبِ سوارشدن."""
    skip = ENTERPRISE_ONLY if edition == "cloud" else CLOUD_ONLY
    return [r for r in ALL_ROUTERS if not any(r is s for s in skip)]


def include_routers(app: FastAPI, edition: str) -> None:
    for router in routers_for(edition):
        app.include_router(router)
