"""بازیابیِ رمز با پیامک (کدِ ۶رقمی به شماره‌ی تأییدشده).

قرینه‌ی امنیتیِ بازیابیِ ایمیلی، ولی چون کد کوتاه و حدس‌زدنی است، این تست‌ها بیش از
هر چیز مرزهای امنیتی را می‌سنجند:

- **ضدِ enumeration:** شماره‌ی ناموجود/تأییدنشده همان ۲۰۲/۴۰۰ِ یکسان را می‌گیرد؛ از
  تفاوتِ پاسخ نباید بشود فهمید کدام شماره در سیستم هست.
- **فقط شماره‌ی تأییدشده:** شماره‌ی اثبات‌نشده اثباتِ مالکیت نیست، پس نباید کدِ بازیابی
  بگیرد — وگرنه هرکس با دانستنِ شماره‌ی قربانی حسابش را می‌رباید.
- **سقفِ تلاش و یک‌بارمصرفی:** کدِ ۶رقمی بدونِ این‌ها با چند صد حدس شکستنی است.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models.auth_token import PURPOSE_SMS_PASSWORD_RESET, AuthToken
from app.models.user import User
from app.services import tokens
from app.services.provisioning import signup_new_business

OLD_PASSWORD = "OldPassword2026!"
NEW_PASSWORD = "BrandNewPassword2026!"
PHONE = "09121234567"


@pytest.fixture(autouse=True)
def _clean_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def sent_codes(monkeypatch):
    """کدِ ارسالی را می‌گیرد — اندپوینت خودِ کد را برنمی‌گرداند، فقط پیامکش می‌کند."""
    captured: list[dict] = []

    def fake_send(to, code):
        captured.append({"to": to, "code": code})
        return True

    monkeypatch.setattr("app.routers.auth.sms.send_verification_code", fake_send)
    return captured


@pytest.fixture
def client(db):
    """کلاینتِ ناشناس (بدونِ احراز) — این اندپوینت‌ها پیش از ورود صدا زده می‌شوند."""
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _make_account(db, *, phone: str | None, verified: bool):
    email = f"smsreset-{uuid.uuid4().hex[:8]}@cubita-test.ir"
    tenant, user = signup_new_business(
        db,
        business_name="کسب‌وکار بازیابی",
        owner_name="مالک",
        email=email,
        password=OLD_PASSWORD,
    )
    if phone is not None:
        user.phone = phone
        user.phone_verified_at = datetime.now(timezone.utc) if verified else None
    db.flush()
    return tenant, user, email


@pytest.fixture
def verified_account(db):
    """حسابی با شماره‌ی موبایلِ تأییدشده — تنها حالتی که بازیابیِ پیامکی مجاز است."""
    return _make_account(db, phone=PHONE, verified=True)


# --- چرخه‌ی موفق --------------------------------------------------------------------


def test_full_flow_resets_password_and_logs_in(client, verified_account, sent_codes):
    _, _, email = verified_account

    req = client.post("/api/auth/forgot-password/sms", json={"phone": PHONE})
    assert req.status_code == 202, req.text[:300]
    assert len(sent_codes) == 1 and sent_codes[0]["to"] == PHONE
    code = sent_codes[0]["code"]

    reset = client.post(
        "/api/auth/reset-password/sms",
        json={"phone": PHONE, "code": code, "password": NEW_PASSWORD},
    )
    assert reset.status_code == 200, reset.text[:300]
    assert reset.json()["access_token"]

    # رمزِ تازه کار می‌کند و رمزِ قدیمی دیگر نه — یعنی رمز واقعاً عوض شد.
    assert client.post("/api/auth/login", json={"email": email, "password": NEW_PASSWORD}).status_code == 200
    assert client.post("/api/auth/login", json={"email": email, "password": OLD_PASSWORD}).status_code == 401


def test_messy_phone_is_normalized(client, verified_account, sent_codes):
    """شماره با +۹۸ و فاصله باید همان کاربر را پیدا کند."""
    client.post("/api/auth/forgot-password/sms", json={"phone": "+98 912 123 4567"})
    assert len(sent_codes) == 1 and sent_codes[0]["to"] == PHONE


# --- ضدِ enumeration / شماره‌ی تأییدنشده ---------------------------------------------


def test_unknown_phone_returns_202_and_sends_nothing(client, sent_codes):
    res = client.post("/api/auth/forgot-password/sms", json={"phone": "09350009988"})
    assert res.status_code == 202, "پاسخِ شماره‌ی ناموجود باید با شماره‌ی موجود یکسان باشد"
    assert len(sent_codes) == 0


def test_unverified_phone_gets_no_code(client, db, sent_codes):
    """شماره‌ی اثبات‌نشده اثباتِ مالکیت نیست؛ نباید کدِ بازیابی بگیرد."""
    _make_account(db, phone="09120001122", verified=False)
    res = client.post("/api/auth/forgot-password/sms", json={"phone": "09120001122"})
    assert res.status_code == 202
    assert len(sent_codes) == 0, "شماره‌ی تأییدنشده نباید کدِ بازیابی بگیرد"


def test_ambiguous_phone_two_accounts_gets_no_code(client, db, sent_codes):
    """اگر دو حساب یک شماره‌ی تأییدشده داشته باشند، نمی‌دانیم کد برای کدام است → هیچ‌کدام."""
    _make_account(db, phone="09121110000", verified=True)
    _make_account(db, phone="09121110000", verified=True)
    res = client.post("/api/auth/forgot-password/sms", json={"phone": "09121110000"})
    assert res.status_code == 202
    assert len(sent_codes) == 0


def test_reset_with_unknown_phone_is_generic_400(client, sent_codes):
    """گامِ دوم برای شماره‌ی ناموجود همان ۴۰۰ِ «کد نادرست» را می‌دهد، نه ۴۰۴/نشتِ وجود."""
    res = client.post(
        "/api/auth/reset-password/sms",
        json={"phone": "09350009988", "code": "123456", "password": NEW_PASSWORD},
    )
    assert res.status_code == 400


# --- امنیتِ کد ----------------------------------------------------------------------


def test_wrong_code_is_rejected_and_password_unchanged(client, verified_account, sent_codes):
    _, _, email = verified_account
    client.post("/api/auth/forgot-password/sms", json={"phone": PHONE})

    res = client.post(
        "/api/auth/reset-password/sms",
        json={"phone": PHONE, "code": "000000", "password": NEW_PASSWORD},
    )
    assert res.status_code == 400
    # رمزِ قدیمی هنوز باید کار کند
    assert client.post("/api/auth/login", json={"email": email, "password": OLD_PASSWORD}).status_code == 200


def test_code_locks_after_too_many_wrong_attempts(client, verified_account, sent_codes):
    """مهم‌ترین تست: بعد از سقفِ تلاش، حتی کدِ درست هم باید رد شود."""
    client.post("/api/auth/forgot-password/sms", json={"phone": PHONE})
    real = sent_codes[0]["code"]

    for _ in range(tokens.MAX_CODE_ATTEMPTS):
        bad = client.post(
            "/api/auth/reset-password/sms",
            json={"phone": PHONE, "code": "111111", "password": NEW_PASSWORD},
        )
        assert bad.status_code == 400

    locked = client.post(
        "/api/auth/reset-password/sms",
        json={"phone": PHONE, "code": real, "password": NEW_PASSWORD},
    )
    assert locked.status_code == 400, "کدِ درست بعد از سقفِ تلاش هنوز پذیرفته شد — حمله‌ی حدس باز است"


def test_code_is_single_use(client, verified_account, sent_codes):
    _, _, email = verified_account
    client.post("/api/auth/forgot-password/sms", json={"phone": PHONE})
    code = sent_codes[0]["code"]

    first = client.post(
        "/api/auth/reset-password/sms",
        json={"phone": PHONE, "code": code, "password": NEW_PASSWORD},
    )
    assert first.status_code == 200
    second = client.post(
        "/api/auth/reset-password/sms",
        json={"phone": PHONE, "code": code, "password": "AnotherPassword2026!"},
    )
    assert second.status_code == 400, "کد بارِ دوم هم کار کرد"


def test_new_code_invalidates_the_previous_one(client, verified_account, sent_codes):
    client.post("/api/auth/forgot-password/sms", json={"phone": PHONE})
    client.post("/api/auth/forgot-password/sms", json={"phone": PHONE})
    assert len(sent_codes) == 2

    stale = client.post(
        "/api/auth/reset-password/sms",
        json={"phone": PHONE, "code": sent_codes[0]["code"], "password": NEW_PASSWORD},
    )
    assert stale.status_code == 400, "کدِ قبلی بعد از صدورِ کدِ تازه هنوز کار می‌کند"
    fresh = client.post(
        "/api/auth/reset-password/sms",
        json={"phone": PHONE, "code": sent_codes[1]["code"], "password": NEW_PASSWORD},
    )
    assert fresh.status_code == 200, fresh.text[:200]


def test_expired_code_is_rejected(client, verified_account, sent_codes, db):
    _, user, _ = verified_account
    client.post("/api/auth/forgot-password/sms", json={"phone": PHONE})

    row = db.query(AuthToken).filter(
        AuthToken.user_id == user.id, AuthToken.purpose == PURPOSE_SMS_PASSWORD_RESET
    ).one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.flush()

    res = client.post(
        "/api/auth/reset-password/sms",
        json={"phone": PHONE, "code": sent_codes[0]["code"], "password": NEW_PASSWORD},
    )
    assert res.status_code == 400, "کدِ منقضی پذیرفته شد"


def test_only_salted_hash_of_code_is_stored(client, verified_account, sent_codes, db):
    _, user, _ = verified_account
    client.post("/api/auth/forgot-password/sms", json={"phone": PHONE})
    code = sent_codes[0]["code"]

    row = db.query(AuthToken).filter(
        AuthToken.user_id == user.id, AuthToken.purpose == PURPOSE_SMS_PASSWORD_RESET
    ).one()
    assert row.token_hash != code, "کدِ خام در دیتابیس ذخیره شده"
    # نمک‌خورده با کاربر و هدف: hashِ خامِ کد نباید بخورد
    assert row.token_hash != tokens.hash_token(code)
    assert row.token_hash == tokens.hash_token(f"{user.id}:{PURPOSE_SMS_PASSWORD_RESET}:{code}")
