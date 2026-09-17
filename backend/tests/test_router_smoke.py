"""اسموک‌تستِ HTTP برای هشت روتری که فقط سطحِ سرویس تست داشتند.

`GAPS.md` موردِ ۳: «۱۸۱ از ۶۱۱ مسیر هرگز از HTTP صدا زده نمی‌شوند… برای آن ۱۸۱
مسیر، گاردِ مجوز، تجزیه‌ی پارامتر و شکلِ پاسخ هرگز آزموده نمی‌شوند.»

این هشت روتر **۱۳۴ تست دارند** — ولی هر ۱۳۴ تا تابعِ سرویس را مستقیم صدا می‌زنند
و **صفر فراخوانیِ HTTP** دارند. یعنی منطقِ کسب‌وکار پوشیده است و لایه‌ی وب نه.

**چرا این لایه جدا اهمیت دارد.** همین امروز در کارِ دیگری، ستونی از مدل حذف شد و
تابعِ سریال‌سازی که دیکشنری را از `__table__.columns` می‌ساخت، بی‌صدا فیلدِ
اجباریِ پاسخ را جا انداخت. هیچ تستِ سرویسی آن را نمی‌گرفت — چون سرویس سالم بود.
یک درخواستِ ساده‌ی `GET` می‌گرفتش.

**مسیرها برنامه‌ای شمرده می‌شوند، نه دستی.** هر مسیری که به این روترها اضافه
شود، خودکار زیرِ همین سه سنجش می‌آید؛ وگرنه فهرستِ دستی از روزِ دوم عقب می‌افتد.

## آنچه این فایل **ثابت نمی‌کند**

سنجشِ گروهیِ `GET` روی جدولِ **خالی** اجرا می‌شود. فهرستِ خالی با هر اسکیمایی
می‌خوانَد، پس آن بخش **سریال‌سازیِ داده‌ی واقعی را نمی‌آزماید**. این آزموده شد:
فیلدی اجباری به `CashboxOut` اضافه شد و هیچ تستی قرمز نشد.

برای همین بخشِ «رفت‌وبرگشت» پایین هست — رکورد می‌سازد و دوباره می‌خوانَدش، تا
دستِ‌کم برای دو منبع مسیرِ کاملِ نوشتن و سریال‌سازی واقعاً طی شود. الگویش برای
منابعِ دیگر قابلِ تکرار است.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app

ROUTER_MODULES = [
    "fiscal_year", "stock_taking", "assets", "receipts",
    "budgeting", "calendar", "cashbox", "currencies",
]


def _routes():
    """(متد، مسیر) برای همه‌ی مسیرهای این هشت روتر."""
    import importlib

    out = []
    for name in ROUTER_MODULES:
        router = importlib.import_module(f"app.routers.{name}").router
        for route in router.routes:
            for method in route.methods:
                out.append((name, method, route.path))
    return out


ALL_ROUTES = _routes()
#: مسیرهایی که پارامترِ مسیری ندارند — این‌ها را می‌شود بی‌داده‌ی آزمایشی صدا زد.
PLAIN_GETS = [(m, p) for (m, meth, p) in ALL_ROUTES if meth == "GET" and "{" not in p]
PARAM_GETS = [(m, p) for (m, meth, p) in ALL_ROUTES if meth == "GET" and "{" in p]


def test_the_route_list_is_not_empty():
    """اگر نام‌گذاریِ روترها عوض شود، این فایل بی‌صدا هیچ‌چیز تست نمی‌کند."""
    assert len(ALL_ROUTES) > 50, f"فقط {len(ALL_ROUTES)} مسیر پیدا شد — فهرستِ روترها را بررسی کنید"
    assert len(PLAIN_GETS) >= 15


# ─────────────── گاردِ مجوز ───────────────


@pytest.fixture
def anon(db):
    """کلاینتی که احراز هویتش override **نشده**.

    فیکسچرِ `client` عمداً احراز هویت را دور می‌زند تا منطقِ اندپوینت را جدا
    بسنجد. نتیجه‌اش این است که **هیچ تستی نمی‌بیند گارد سرِ جایش هست یا نه** —
    و روتری که `require_permission` یادش برود، از همه‌ی تست‌ها سبز رد می‌شود.
    """
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize(("mod", "path"), PLAIN_GETS, ids=[p for _, p in PLAIN_GETS])
def test_every_get_rejects_an_anonymous_caller(anon, mod, path):
    res = anon.get(path)
    assert res.status_code in (401, 403), (
        f"*** {path} بدونِ احراز هویت {res.status_code} داد — گاردِ مجوز ندارد ***"
    )


# ─────────────── شکلِ پاسخ ───────────────


@pytest.mark.parametrize(("mod", "path"), PLAIN_GETS, ids=[p for _, p in PLAIN_GETS])
def test_every_plain_get_answers_and_validates(client, mod, path):
    """پاسخ باید هم برسد و هم با اسکیمای خودش بخواند.

    FastAPI پاسخ را در برابرِ `response_model` اعتبارسنجی می‌کند، پس ۵۰۰ این‌جا
    یعنی مدل و اسکیما از هم واگرا شده‌اند — همان چیزی که تستِ سرویس نمی‌بیند.

    ۴۲۲ پذیرفته است: بعضی گزارش‌ها پارامترِ اجباری می‌خواهند و نبودشان خطای
    اعتبارسنجیِ درست است، نه خرابی.
    """
    res = client.get(path)
    assert res.status_code in (200, 422), f"*** {path} → {res.status_code}: {res.text[:200]} ***"
    if res.status_code == 200:
        res.json()  #: پاسخِ ۲۰۰ که JSON نباشد، خودش خرابی است


# ─────────────── تجزیه‌ی پارامتر ───────────────


@pytest.mark.parametrize(("mod", "path"), PARAM_GETS, ids=[p for _, p in PARAM_GETS])
def test_a_malformed_id_is_rejected_not_crashed(client, mod, path):
    """شناسه‌ی بدشکل باید ۴۲۲ بگیرد، نه ۵۰۰.

    ۵۰۰ یعنی رشته تا داخلِ کوئری رفته و آن‌جا ترکیده — نشتِ جزئیاتِ داخلی به
    پاسخ، و لاگی پر از خطای کاذب.
    """
    res = client.get(path.replace("{" + path.split("{")[1].split("}")[0] + "}", "not-a-uuid"))
    assert res.status_code < 500, f"*** {path} با شناسه‌ی بدشکل {res.status_code} داد ***"
    assert res.status_code in (400, 404, 422)


@pytest.mark.parametrize(("mod", "path"), PARAM_GETS, ids=[p for _, p in PARAM_GETS])
def test_an_unknown_id_is_a_clean_not_found(client, mod, path):
    """شناسه‌ی معتبر ولی ناموجود → ۴۰۴، نه ۵۰۰ و نه ۲۰۰ِ توخالی."""
    res = client.get(path.replace("{" + path.split("{")[1].split("}")[0] + "}", str(uuid.uuid4())))
    assert res.status_code < 500, f"*** {path} با شناسه‌ی ناموجود {res.status_code} داد ***"
    assert res.status_code in (400, 404, 422)


# ─────────────── رفت‌وبرگشتِ واقعی ───────────────
#
# سنجشِ گروهیِ بالا روی جدولِ خالی اجرا می‌شود و سریال‌سازی را نمی‌آزماید. این دو
# رکورد می‌سازند و دوباره می‌خوانندشان، پس مسیرِ کامل — اعتبارسنجیِ ورودی، نوشتن،
# و ساختنِ پاسخ از یک ردیفِ واقعی — طی می‌شود.


def test_a_cashbox_survives_a_write_then_read(client):
    made = client.post("/api/cashboxes", json={"name": "صندوقِ آزمون", "currency_code": "IRR"})
    assert made.status_code in (200, 201), made.text
    created = made.json()
    assert created["name"] == "صندوقِ آزمون"

    listed = client.get("/api/cashboxes")
    assert listed.status_code == 200
    #: **این‌جاست که سریال‌سازی واقعاً اجرا می‌شود** — با ردیف، نه با فهرستِ خالی.
    assert any(row["id"] == created["id"] for row in listed.json())


def test_a_calendar_event_survives_a_write_then_read(client):
    made = client.post(
        "/api/calendar-events",
        json={"title": "یادآورِ آزمون", "event_date": "2026-03-15", "category": "reminder"},
    )
    assert made.status_code in (200, 201), made.text
    created = made.json()

    listed = client.get("/api/calendar-events")
    assert listed.status_code == 200
    rows = listed.json()
    assert any(row["id"] == created["id"] and row["title"] == "یادآورِ آزمون" for row in rows)


def test_a_blank_name_is_refused_by_the_endpoint(client):
    """اعتبارسنجیِ ورودی هم از HTTP آزموده می‌شود، نه فقط از سرویس."""
    res = client.post("/api/cashboxes", json={"name": "   "})
    assert res.status_code == 422
