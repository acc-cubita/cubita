"""لاگ ساختاریافته، شناسه‌ی درخواست، و مدیریت خطای سراسری.

**چرا این لازم شد:** وقتی امروز استقرار شکست و production خراب شد، تنها راه فهمیدنِ
علت، SSH زدن و خواندن `journalctl` بود. با یک مشتری این جواب می‌دهد؛ با پنجاه
مشتری نه. و مهم‌تر: تا امروز هیچ handler سراسری‌ای وجود نداشت، یعنی هر استثنای
پیش‌بینی‌نشده به‌شکل ۵۰۰ خام به کاربر می‌رسید و **متن خطا و traceback** می‌توانست
جزئیات داخلی را لو بدهد.

**`tenant_id` در هر خط لاگ حیاتی است.** در سیستم چندمستأجری، لاگی که نگوید کدام
کسب‌وکار، عملاً غیرقابل استفاده است: نمی‌شود فهمید مشکل یک مشتری است یا همه.

**چرا JSON و نه متن:** لاگ متنی را باید با regex خواند و هر تغییر قالب، ابزار
تحلیل را می‌شکند. JSON مستقیم قابل کوئری است — و اگر روزی Sentry یا Loki اضافه شد،
بدون تغییر کد کار می‌کند.

هیچ وابستگی بیرونی اضافه نشد (نه structlog نه loguru): کتابخانه‌ی استاندارد این کار
را می‌کند و هر وابستگی تازه یعنی یک گام pip install در استقرار.
"""
import json
import logging
import time
import traceback
import uuid
from contextvars import ContextVar

from fastapi import Request, status
from fastapi.responses import JSONResponse

#: شناسه‌ی درخواست جاری. در لاگ می‌نشیند و در هدر پاسخ هم برمی‌گردد، تا وقتی کاربر
#: می‌گوید «خطا خوردم»، بشود دقیقاً همان درخواست را در لاگ پیدا کرد.
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
tenant_id_var: ContextVar[str | None] = ContextVar("log_tenant_id", default=None)

REQUEST_ID_HEADER = "X-Request-ID"

#: مسیرهایی که لاگ نمی‌شوند — health check هر چند ثانیه صدا زده می‌شود و لاگ را
#: پر می‌کند تا جایی که چیز مهمی در آن پیدا نشود.
QUIET_PATHS = frozenset({"/api/health"})


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if (rid := request_id_var.get()) is not None:
            payload["request_id"] = rid
        if (tid := tenant_id_var.get()) is not None:
            payload["tenant_id"] = tid

        for key, value in getattr(record, "extra_fields", {}).items():
            payload[key] = value

        if record.exc_info:
            payload["exception"] = "".join(traceback.format_exception(*record.exc_info)).strip()

        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # uvicorn لاگ دسترسی خودش را دارد که تکراری و بدون زمینه‌ی مستأجر است؛
    # middleware پایین همان اطلاعات را با زمینه‌ی کامل می‌دهد.
    logging.getLogger("uvicorn.access").disabled = True


def log_with(logger: logging.Logger, level: int, message: str, **fields) -> None:
    logger.log(level, message, extra={"extra_fields": fields})


async def request_context_middleware(request: Request, call_next):
    """شناسه به هر درخواست می‌دهد، مدت اجرا را می‌سنجد، و نتیجه را لاگ می‌کند."""
    incoming = request.headers.get(REQUEST_ID_HEADER)
    rid = incoming or uuid.uuid4().hex[:16]
    token = request_id_var.set(rid)
    tenant_token = tenant_id_var.set(None)

    started = time.perf_counter()
    logger = logging.getLogger("cubita.request")
    try:
        response = await call_next(request)
    except Exception:
        # استثنای فرارکرده از handlerها. اینجا فقط لاگ می‌شود و دوباره پرتاب
        # می‌گردد تا exception handler سراسری پاسخ تمیز بسازد.
        elapsed = (time.perf_counter() - started) * 1000
        log_with(
            logger,
            logging.ERROR,
            "درخواست با استثنای مدیریت‌نشده شکست",
            method=request.method,
            path=request.url.path,
            duration_ms=round(elapsed, 1),
        )
        raise
    finally:
        request_id_var.reset(token)
        tenant_id_var.reset(tenant_token)

    elapsed = (time.perf_counter() - started) * 1000
    response.headers[REQUEST_ID_HEADER] = rid

    if request.url.path not in QUIET_PATHS:
        log_with(
            logger,
            logging.WARNING if response.status_code >= 500 else logging.INFO,
            "درخواست",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round(elapsed, 1),
        )
    return response


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """هر استثنایی که به اینجا برسد یک باگ است، نه یک حالت مورد انتظار.

    **متن خطا عمداً به کاربر نمی‌رسد.** پیام استثنا می‌تواند نام جدول، بخشی از
    کوئری یا مقادیر داده را داشته باشد؛ فرستادنش به کلاینت یعنی دادن نقشه‌ی داخلی
    سیستم به هر کسی که بتواند خطا تولید کند. به‌جایش شناسه‌ی درخواست برمی‌گردد تا
    کاربر بتواند بگوید «این کد» و ما دقیقاً همان را در لاگ پیدا کنیم.
    """
    rid = request_id_var.get() or "-"
    logging.getLogger("cubita.error").error(
        "استثنای مدیریت‌نشده",
        exc_info=exc,
        extra={"extra_fields": {"method": request.method, "path": request.url.path}},
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": f"خطای داخلی سرور. کد پیگیری: {rid}"},
        headers={REQUEST_ID_HEADER: rid},
    )
