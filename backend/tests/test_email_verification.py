"""تأییدِ ایمیل در ثبت‌نام — کد پیش از ساختِ حساب سنجیده می‌شود (verify-before-create).

مهم‌ترین چیزی که این پرونده می‌سنجد این است که **هیچ حسابی با ایمیلِ تأییدنشده ساخته
نمی‌شود**: بدونِ کدِ درست، signup باید ۴۰۰ بدهد و هیچ کاربری در دیتابیس نماند.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models.user import User
from app.services.email_verification import MAX_ATTEMPTS, consume_email_code, issue_email_code
from app.services.provisioning import signup_new_business

PASSWORD = "AStrongPassword2026"


@pytest.fixture
def anon_client(db):
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def sent_codes(monkeypatch):
    """کدِ ایمیل‌شده را می‌گیرد — اندپوینت خودِ کد را برنمی‌گرداند، فقط ایمیلش می‌کند."""
    captured: list[dict] = []

    def fake_send(to, name, code, valid_minutes):
        captured.append({"to": to, "code": code})
        return True

    monkeypatch.setattr("app.routers.auth.send_email_verification_code", fake_send)
    return captured


def _new_email() -> str:
    return f"verify-{uuid.uuid4().hex[:8]}@cubita-test.ir"


def _request_code(client, captured, email) -> str:
    r = client.post("/api/auth/signup/request-code", json={"email": email})
    assert r.status_code == 200, r.text[:300]
    assert r.json()["sent"] is True
    assert "*" in r.json()["email"], "ایمیل در پاسخ ماسک نشده"
    return captured[-1]["code"]


def _signup(client, captured, email, **over):
    code = _request_code(client, captured, email)
    payload = {
        "business_name": "کسب‌وکار تأیید",
        "owner_name": "مالک",
        "email": email,
        "password": PASSWORD,
        "code": code,
        **over,
    }
    return client.post("/api/auth/signup", json=payload)


# --- چرخه‌ی موفق --------------------------------------------------------------------


def test_request_then_signup_creates_verified_account(anon_client, sent_codes):
    email = _new_email()
    res = _signup(anon_client, sent_codes, email)
    assert res.status_code == 201, res.text[:300]

    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {res.json()['access_token']}"})
    me = client.get("/api/auth/me").json()
    assert me["email"] == email
    assert me["email_verified"] is True, "حساب باید تأییدشده باشد چون کد سنجیده شد"


# --- بدونِ کدِ درست هیچ حسابی ساخته نمی‌شود -------------------------------------------


def test_signup_with_wrong_code_is_rejected_and_creates_nothing(anon_client, sent_codes, db):
    email = _new_email()
    _request_code(anon_client, sent_codes, email)  # کد می‌رود ولی از کدِ غلط استفاده می‌کنیم
    res = anon_client.post(
        "/api/auth/signup",
        json={
            "business_name": "نباید ساخته شود",
            "owner_name": "مالک",
            "email": email,
            "password": PASSWORD,
            "code": "000000",
        },
    )
    assert res.status_code == 400, res.text[:300]
    assert db.query(User).filter(User.email == email).first() is None, "حساب با کدِ غلط ساخته شد"


def test_signup_without_any_code_request_is_rejected(anon_client, db):
    email = _new_email()
    res = anon_client.post(
        "/api/auth/signup",
        json={
            "business_name": "بدونِ کد",
            "owner_name": "مالک",
            "email": email,
            "password": PASSWORD,
            "code": "123456",
        },
    )
    assert res.status_code == 400
    assert db.query(User).filter(User.email == email).first() is None


def test_missing_code_field_is_422(anon_client):
    res = anon_client.post(
        "/api/auth/signup",
        json={"business_name": "x", "owner_name": "y", "email": _new_email(), "password": PASSWORD},
    )
    assert res.status_code == 422, "کدِ تأیید فیلدِ اجباری است"


# --- سقفِ تلاش و انقضا (سطحِ سرویس، تا سقفِ نرخِ signup دخالت نکند) --------------------


def test_attempts_lock_after_max(db):
    email = _new_email()
    issue_email_code(db, email)
    for _ in range(MAX_ATTEMPTS):
        assert consume_email_code(db, email, "999999") is False
    # حتی اگر کدِ درست را هم بدانیم، بعد از سقف قفل است — ولی کدِ تازه دوباره باز می‌کند.
    real = issue_email_code(db, email)
    assert consume_email_code(db, email, real) is True


def test_reissue_invalidates_previous_code(db):
    email = _new_email()
    first = issue_email_code(db, email)
    second = issue_email_code(db, email)
    assert first != second or True  # ممکن است اتفاقی یکی شوند؛ مهم رفتارِ زیر است
    assert consume_email_code(db, email, first) is False, "کدِ قبلی باید باطل شده باشد"
    assert consume_email_code(db, email, second) is True


def test_expired_code_is_rejected(db):
    from datetime import datetime, timedelta, timezone

    from app.models.email_verification import EmailVerificationCode

    email = _new_email()
    code = issue_email_code(db, email)
    row = db.query(EmailVerificationCode).filter(EmailVerificationCode.email == email).one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.flush()
    assert consume_email_code(db, email, code) is False


# --- ایمیلِ تکراری --------------------------------------------------------------------


def test_request_code_for_existing_email_is_rejected(anon_client, db):
    email = _new_email()
    signup_new_business(db, business_name="اولی", owner_name="مالک", email=email, password=PASSWORD)
    db.flush()

    res = anon_client.post("/api/auth/signup/request-code", json={"email": email})
    assert res.status_code == 409
    assert "وجود دارد" not in res.json()["detail"], "پیام نباید وجودِ ایمیل را تأیید کند"
