"""لاگ ساختاریافته، شناسه‌ی درخواست، و مدیریت خطای سراسری.

این پرونده بعد از یک حادثه‌ی واقعی نوشته شد: استقرار شکست، production خراب شد، و
تنها راه فهمیدن علت SSH زدن و خواندن journalctl بود. با یک مشتری جواب می‌دهد، با
پنجاه مشتری نه.

مهم‌ترین تست اینجا `test_the_exception_message_never_reaches_the_client` است.
تا امروز هیچ handler سراسری‌ای وجود نداشت، یعنی هر استثنای پیش‌بینی‌نشده متن خودش
را به کاربر می‌رساند — و آن متن می‌تواند نام جدول، بخشی از کوئری یا مقادیر داده
داشته باشد. این نشت اطلاعات است، نه فقط تجربه‌ی کاربری بد.
"""
import json
import logging

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.observability import (
    REQUEST_ID_HEADER,
    JsonFormatter,
    request_id_var,
    tenant_id_var,
)

SECRET_IN_EXCEPTION = "raz-e-dakheli-table-users-column-hashed-password"


@pytest.fixture
def app_with_boom():
    """اپ واقعی، به‌علاوه‌ی یک مسیر که عمداً می‌ترکد."""
    from app.main import app

    router = APIRouter()

    @router.get("/api/__boom")
    def boom():
        raise RuntimeError(SECRET_IN_EXCEPTION)

    app.include_router(router)
    try:
        # raise_server_exceptions=False یعنی TestClient مثل production رفتار کند و
        # استثنا را بالا نیندازد؛ وگرنه handler سراسری اصلاً سنجیده نمی‌شود.
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        app.router.routes = [r for r in app.router.routes if getattr(r, "path", "") != "/api/__boom"]


# --- شناسه‌ی درخواست -------------------------------------------------------------------


def test_every_response_carries_a_request_id(app_with_boom):
    res = app_with_boom.get("/api/health")
    assert res.headers.get(REQUEST_ID_HEADER), "پاسخ شناسه‌ی درخواست ندارد"


def test_an_incoming_request_id_is_kept(app_with_boom):
    """اگر پراکسی یا کلاینت شناسه بدهد، همان باید ادامه پیدا کند.

    بدون این، ردیابی یک درخواست بین سرویس‌ها می‌شکند و هر لایه شناسه‌ی خودش را
    می‌سازد — یعنی همان چیزی که شناسه برای حلش هست، حل نمی‌شود.
    """
    res = app_with_boom.get("/api/health", headers={REQUEST_ID_HEADER: "abc123"})
    assert res.headers[REQUEST_ID_HEADER] == "abc123"


def test_each_request_gets_its_own_id(app_with_boom):
    a = app_with_boom.get("/api/health").headers[REQUEST_ID_HEADER]
    b = app_with_boom.get("/api/health").headers[REQUEST_ID_HEADER]
    assert a != b


# --- مدیریت خطا -----------------------------------------------------------------------


def test_the_exception_message_never_reaches_the_client(app_with_boom):
    """مهم‌ترین تست این پرونده.

    متن استثنا می‌تواند نام جدول، بخشی از کوئری یا مقادیر داده داشته باشد.
    فرستادنش به کلاینت یعنی دادن نقشه‌ی داخلی سیستم به هر کسی که بتواند خطا
    تولید کند.
    """
    res = app_with_boom.get("/api/__boom")

    assert res.status_code == 500
    body = res.text
    assert SECRET_IN_EXCEPTION not in body, "متن استثنا به کلاینت رسید"
    assert "RuntimeError" not in body
    assert "Traceback" not in body and "File \"" not in body


def test_the_error_response_gives_a_tracking_code(app_with_boom):
    """بدون کد پیگیری، کاربر می‌گوید «خطا خوردم» و ما نمی‌دانیم کدام درخواست."""
    res = app_with_boom.get("/api/__boom")
    rid = res.headers.get(REQUEST_ID_HEADER)

    assert rid
    assert rid in res.json()["detail"], "کد پیگیری در پیام خطا نیست"


def test_a_normal_http_error_keeps_its_message(app_with_boom):
    """handler سراسری نباید خطاهای عمدی و مفید را هم بی‌صدا کند."""
    res = app_with_boom.post("/api/auth/login", json={"email": "a@b.co", "password": "x"})
    assert res.status_code in (401, 422)
    assert "detail" in res.json()


# --- قالب لاگ ------------------------------------------------------------------------


def _format(record_kwargs=None, **context) -> dict:
    token_r = request_id_var.set(context.get("request_id"))
    token_t = tenant_id_var.set(context.get("tenant_id"))
    try:
        record = logging.LogRecord(
            name="cubita.test", level=logging.INFO, pathname=__file__, lineno=1,
            msg="پیام آزمایشی", args=(), exc_info=None,
        )
        for key, value in (record_kwargs or {}).items():
            setattr(record, key, value)
        return json.loads(JsonFormatter().format(record))
    finally:
        request_id_var.reset(token_r)
        tenant_id_var.reset(token_t)


def test_log_lines_are_valid_json():
    """لاگ متنی را باید با regex خواند و هر تغییر قالب ابزار تحلیل را می‌شکند."""
    entry = _format()
    assert entry["level"] == "INFO"
    assert entry["msg"] == "پیام آزمایشی"
    assert entry["logger"] == "cubita.test"


def test_tenant_id_appears_in_the_log_line():
    """در سیستم چندمستأجری، لاگی که نگوید کدام کسب‌وکار عملاً بی‌فایده است."""
    entry = _format(tenant_id="11111111-1111-1111-1111-111111111111")
    assert entry["tenant_id"] == "11111111-1111-1111-1111-111111111111"


def test_request_id_appears_in_the_log_line():
    entry = _format(request_id="deadbeef")
    assert entry["request_id"] == "deadbeef"


def test_context_is_absent_rather_than_null_when_unset():
    """کلیدِ null در لاگ فقط نویز است و کوئری‌ها را پیچیده می‌کند."""
    entry = _format()
    assert "tenant_id" not in entry
    assert "request_id" not in entry


def test_extra_fields_are_merged_into_the_line():
    entry = _format({"extra_fields": {"path": "/api/x", "status": 500, "duration_ms": 12.3}})
    assert entry["path"] == "/api/x"
    assert entry["status"] == 500
    assert entry["duration_ms"] == 12.3


def test_persian_is_not_escaped():
    """با ensure_ascii پیش‌فرض، فارسی در لاگ به کدهای یونیکد تبدیل و ناخوانا می‌شود.

    اینجا عمداً *رشته‌ی خام* خروجی formatter سنجیده می‌شود و نه نتیجه‌ی json.loads.
    نسخه‌ی اول این تست دیکشنریِ پارس‌شده را دوباره سریالایز می‌کرد و برای همین
    هر تنظیمی که formatter داشت سبز می‌ماند — یعنی چیزی را که ادعا می‌کرد
    نمی‌سنجید. با جهش‌آزمایی معلوم شد.
    """
    record = logging.LogRecord(
        name="cubita.test", level=logging.INFO, pathname=__file__, lineno=1,
        msg="پیام آزمایشی", args=(), exc_info=None,
    )
    raw = JsonFormatter().format(record)
    assert "پیام آزمایشی" in raw, f"فارسی در لاگ escape شده و ناخوانا است: {raw}"
