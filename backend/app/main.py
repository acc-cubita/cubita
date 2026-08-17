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
    admin_accounts,
    alerts,
    assets,
    audit,
    auth,
    backup,
    banking,
    benefits,
    billing,
    budgeting,
    calendar,
    cost_centers,
    crm,
    currencies,
    installments,
    integration,
    manufacturing,
    inventory,
    invoices,
    journal,
    marketplace,
    members,
    moadian,
    onboarding,
    payroll,
    period_close,
    pos_terminals,
    quotations,
    recurring,
    reports,
    returns,
    shop,
    stock_taking,
    storefront,
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

# CORS سطحِ عمومیِ فروشگاه (`/api/shop/*`) عمداً *باز* است (`*`): این سطح روی دامنه‌ی
# هاستِ خودِ هر مستأجر اجرا می‌شود (cross-origin) و هیچ کوکی/اعتبارنامه‌ی ambient ندارد —
# احراز فقط با هدرِ کلیدِ publishable است، پس نه CSRF معنا دارد و نه محدودکردنِ origin
# مرزِ امنیتی است (خودِ کلید است). CORالسراسریِ بالا فقط دامنه‌های اپ را می‌شناسد، پس
# این میدل‌ور جدا هدرهای درست را برای مسیرهای فروشگاه می‌گذارد و preflight را پاسخ می‌دهد.
_SHOP_CORS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "X-Shop-Slug, X-Shop-Key, Content-Type",
    "Access-Control-Max-Age": "600",
}


@app.middleware("http")
async def shop_public_cors(request, call_next):
    is_shop = request.url.path.startswith("/api/shop")
    if is_shop and request.method == "OPTIONS":
        from starlette.responses import Response as _Resp

        return _Resp(status_code=204, headers=_SHOP_CORS)
    response = await call_next(request)
    if is_shop:
        for key, value in _SHOP_CORS.items():
            response.headers[key] = value
    return response

app.include_router(auth.router)
app.include_router(admin_accounts.router)
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
app.include_router(pos_terminals.router)
app.include_router(audit.router)
app.include_router(backup.router)
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
app.include_router(installments.router)
app.include_router(shop.router)
app.include_router(storefront.router)
app.include_router(marketplace.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
