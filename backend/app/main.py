from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.observability import (
    REQUEST_ID_HEADER,
    configure_logging,
    request_context_middleware,
    unhandled_exception_handler,
)
from app.routers import (
    accounts,
    advanced_inventory,
    alerts,
    assets,
    audit,
    auth,
    banking,
    benefits,
    billing,
    budgeting,
    calendar,
    cost_centers,
    crm,
    currencies,
    integration,
    manufacturing,
    inventory,
    invoices,
    journal,
    members,
    moadian,
    onboarding,
    payroll,
    period_close,
    quotations,
    recurring,
    reports,
    returns,
    stock_taking,
    subscription,
    transfers,
    treasury,
)

settings = get_settings()
configure_logging()

app = FastAPI(title="Cubita API", docs_url=None if settings.is_production else "/api/docs")

# ترتیب مهم است: middleware زمینه باید بیرونی‌ترین باشد تا شناسه‌ی درخواست برای
# هر چیزی که داخلش لاگ می‌شود در دسترس باشد.
app.middleware("http")(request_context_middleware)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # بدون این، کلاینت در مرورگر شناسه‌ی درخواست را نمی‌بیند و کاربر نمی‌تواند
    # کد پیگیری را به ما بدهد.
    expose_headers=[REQUEST_ID_HEADER],
)

app.include_router(auth.router)
app.include_router(members.router)
app.include_router(accounts.router)
app.include_router(journal.router)
app.include_router(inventory.router)
app.include_router(invoices.router)
app.include_router(quotations.router)
app.include_router(returns.router)
app.include_router(transfers.router)
app.include_router(reports.router)
app.include_router(banking.router)
app.include_router(payroll.router)
app.include_router(benefits.router)
app.include_router(period_close.router)
app.include_router(integration.router)
app.include_router(billing.router)
app.include_router(treasury.router)
app.include_router(audit.router)
app.include_router(subscription.router)
app.include_router(calendar.router)
app.include_router(assets.router)
app.include_router(budgeting.router)
app.include_router(cost_centers.router)
app.include_router(moadian.router)
app.include_router(stock_taking.router)
app.include_router(recurring.router)
app.include_router(alerts.router)
app.include_router(currencies.router)
app.include_router(crm.router)
app.include_router(manufacturing.router)
app.include_router(advanced_inventory.router)
app.include_router(onboarding.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
