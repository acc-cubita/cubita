from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.observability import (
    REQUEST_ID_HEADER,
    configure_logging,
    request_context_middleware,
    unhandled_exception_handler,
)
from app.routers.journal import JournalLineInputError, journal_line_error_handler
from app.routing import include_routers

settings = get_settings()
configure_logging()

app = FastAPI(title="Cubita API", docs_url=None if settings.is_production else "/api/docs")

# ترتیب مهم است: middleware زمینه باید بیرونی‌ترین باشد تا شناسه‌ی درخواست برای
# هر چیزی که داخلش لاگ می‌شود در دسترس باشد.
app.middleware("http")(request_context_middleware)
app.add_exception_handler(Exception, unhandled_exception_handler)
#: خطای ردیفیِ سند (`line_errors`) — raise می‌شود تا تراکنش rollback شود، و این‌جا
#: همان پاسخِ `{detail, line_errors}` را می‌گیرد. بی این، FastAPI فقط `detail` را می‌نوشت.
app.add_exception_handler(JournalLineInputError, journal_line_error_handler)

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

include_routers(app, settings.edition)


@app.get("/api/health")
def health():
    #: `edition` برای جادوگرِ اولین اجرای کلاینتِ سازمانی است: «آزمایش اتصال» باید
    #: بفهمد آدرسی که کاربر داده واقعاً سرورِ کوبیتا سازمانی است، نه هر چیزی که روی
    #: آن پورت جواب می‌دهد (یا سرورِ ابری).
    out = {"status": "ok", "edition": settings.edition}
    if settings.is_enterprise:
        #: کلاینت با این می‌فهمد از سرورش عقب است یا نه (آپدیت از `/updates/*`ِ همین سرور).
        from app.version import app_version

        out["version"] = app_version()
    return out
