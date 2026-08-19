"""قراردادِ اپ موبایل ↔ بک‌اند — «آیا اپ به حسابی که با برنامه ساخته شده وصل می‌شود؟»

این تست دقیقاً مسیرِ واقعیِ اپ را می‌رود: یک حساب مثلِ ثبت‌نامِ برنامه ساخته می‌شود،
با اندپوینتِ واقعیِ login یک **توکنِ Bearerِ واقعی** گرفته می‌شود (بدونِ override احراز)،
و همه‌ی اندپوینت‌هایی که صفحه‌های اپ صدا می‌زنند با همان توکن زده می‌شوند. اگر این سبز
باشد، یعنی ورود + همه‌ی تب‌ها روی یک حسابِ استانداردِ واقعی کار می‌کنند.

فهرستِ اندپوینت‌ها از `mobile/src/api/{auth,reports,contacts,marketplace}.ts` گرفته شده.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.services.provisioning import signup_new_business

PASSWORD = "AStrongPassword2026"


@pytest.fixture(autouse=True)
def _clean_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def anon(db):
    # فقط get_db را به sessionِ تست گره می‌زنیم؛ get_principal override نمی‌شود تا
    # احراز هویتِ واقعی (توکن → کاربر → RLS) دقیقاً مثلِ اپ اجرا شود.
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


@pytest.fixture
def account(db):
    """حسابی که با «برنامه» ساخته شده — همان مسیرِ ثبت‌نامِ خودسرویس (تنانتِ استاندارد، آزمایشی)."""
    tenant, user = signup_new_business(
        db,
        business_name="کسب‌وکار موبایل",
        owner_name="مالک",
        email=f"mobile-{uuid.uuid4().hex[:8]}@cubita-test.ir",
        password=PASSWORD,
    )
    db.flush()
    return tenant, user


def _token(anon, user) -> str:
    resp = anon.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_app_logs_into_a_program_created_account(anon, account):
    """ورودِ واقعی + /me — قلبِ «اتصالِ اپ به حسابِ برنامه»."""
    _, user = account
    body = anon.post("/api/auth/login", json={"email": user.email, "password": PASSWORD}).json()
    assert body["access_token"]
    assert body["refresh_token"]  # «همیشه‌واردمانده»ی اپ

    me = anon.get("/api/auth/me", headers=_auth(body["access_token"]))
    assert me.status_code == 200, me.text
    data = me.json()
    assert data["email"] == user.email
    assert data["tenant_kind"] == "standard"  # حسابِ عادیِ برنامه
    assert data["role_key"] == "owner"
    assert data["permissions"].get("*")  # مالک → دسترسیِ کامل


def test_home_and_report_tabs_load_for_a_real_account(anon, account):
    """همه‌ی اندپوینت‌های تبِ خانه و گزارش‌ها روی یک حسابِ واقعیِ (خالی) ۲۰۰ می‌دهند."""
    _, user = account
    h = _auth(_token(anon, user))

    endpoints = [
        "/api/sales-invoices/summary",          # KPIهای خانه
        "/api/reports/dashboard?months=12",     # نمودارِ روند + پرفروش‌ها
        "/api/alerts",                          # کارتِ هشدارها
        "/api/reports/income-statement",        # گزارشِ سود و زیان
        "/api/reports/balance-sheet",           # ترازنامه
        "/api/reports/aging?kind=receivable",   # مطالبات
        "/api/reports/aging?kind=payable",      # بدهی‌ها
        "/api/reports/inventory",               # موجودی
    ]
    for path in endpoints:
        r = anon.get(path, headers=h)
        assert r.status_code == 200, f"{path} → {r.status_code}: {r.text}"


def test_contacts_tab_loads_and_detail_endpoints_work(anon, account):
    """تبِ اشخاص: فهرستِ keyset + کارتِ حساب + وضعیتِ اعتبارِ یک شخصِ واقعی."""
    _, user = account
    h = _auth(_token(anon, user))

    # فهرست (اپ apiGetAll با limit می‌زند) — شکلِ Page.
    lst = anon.get("/api/contacts?limit=200", headers=h)
    assert lst.status_code == 200, lst.text
    page = lst.json()
    assert "items" in page and "next_cursor" in page

    # یک شخص بساز تا صفحه‌های جزئیاتِ اپ هم سنجیده شوند.
    created = anon.post("/api/contacts", json={"name": "مشتریِ آزمایشی", "type": "customer"}, headers=h)
    assert created.status_code == 201, created.text
    cid = created.json()["id"]

    stmt = anon.get(f"/api/reports/contact-statement/{cid}", headers=h)
    assert stmt.status_code == 200, stmt.text
    assert stmt.json()["contact_id"] == cid

    credit = anon.get(f"/api/contacts/{cid}/credit", headers=h)
    assert credit.status_code == 200, credit.text


def test_market_tab_is_graceful_for_a_standard_account(anon, account):
    """حسابِ استاندارد ماژولِ بازار ندارد؛ نشانِ خوانده‌نشده باید ۰ باشد، نه خطا."""
    _, user = account
    r = anon.get("/api/marketplace/unread", headers=_auth(_token(anon, user)))
    assert r.status_code == 200, r.text
    assert r.json() == 0


def test_unauthenticated_requests_are_rejected(anon):
    """بدونِ توکن، اندپوینت‌های اپ ۴۰۱ می‌دهند (نه ۲۰۰ و نه ۵۰۰)."""
    assert anon.get("/api/auth/me").status_code == 401
    assert anon.get("/api/reports/dashboard?months=12").status_code == 401
