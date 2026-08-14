"""فعال‌سازیِ شماره‌ی موبایل با کدِ پیامکی.

کدِ ۶رقمی برخلافِ توکنِ ۲۵۶بیتیِ بازیابیِ رمز حدس‌زدنی است، پس این تست‌ها بیش از آنکه
کارکردی باشند امنیتی‌اند:

- `test_code_locks_after_too_many_wrong_attempts` — بدونِ سقفِ تلاش، یک‌میلیون حالتِ
  کد با چند صد درخواست شکسته می‌شود.
- `test_only_the_hash_of_the_code_is_stored` — و نمک‌خورده با کاربر، وگرنه یک جدولِ
  آماده‌ی یک‌میلیون کد کلِ hashها را برمی‌گرداند.
- `test_changing_phone_via_profile_drops_verification` — نشانِ «تأییدشده» نباید روی
  شماره‌ی تازه‌ی اثبات‌نشده بماند، وگرنه بازیابیِ رمز با پیامک به شماره‌ی غریبه می‌رود.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models.auth_token import PURPOSE_PHONE_VERIFY, AuthToken
from app.security import create_access_token
from app.services import tokens
from app.services.provisioning import signup_new_business

PASSWORD = "AStrongPassword2026"
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
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


@pytest.fixture
def account(db):
    tenant, user = signup_new_business(
        db,
        business_name="کسب‌وکار تأیید",
        owner_name="مالک",
        email=f"phone-{uuid.uuid4().hex[:8]}@cubita-test.ir",
        password=PASSWORD,
    )
    db.flush()
    return tenant, user


@pytest.fixture
def authed(client, account):
    tenant, user = account
    client.headers.update({"Authorization": f"Bearer {create_access_token(user, tenant.id)}"})
    return client, user


# --- چرخه‌ی موفق ---------------------------------------------------------------------


def test_send_then_verify_marks_phone_verified(authed, sent_codes):
    client, user = authed

    res = client.post("/api/auth/phone/send-code", json={"phone": PHONE})
    assert res.status_code == 200, res.text[:300]
    assert res.json()["sent"] is True
    assert "*" in res.json()["phone"], "شماره در پاسخ ماسک نشده"
    assert len(sent_codes) == 1 and sent_codes[0]["to"] == PHONE

    # پیش از تأیید، phone_verified باید false باشد
    assert client.get("/api/auth/me").json()["phone_verified"] is False

    verify = client.post("/api/auth/phone/verify", json={"code": sent_codes[0]["code"]})
    assert verify.status_code == 200, verify.text[:300]
    body = verify.json()
    assert body["phone"] == PHONE
    assert body["phone_verified"] is True


def test_send_accepts_messy_input_and_normalizes(authed, sent_codes):
    """شماره با +۹۸ و فاصله هم باید به ۰۹... یکدست شود."""
    client, _ = authed
    res = client.post("/api/auth/phone/send-code", json={"phone": "+98 912 123 4567"})
    assert res.status_code == 200
    assert sent_codes[0]["to"] == PHONE


def test_invalid_phone_is_rejected(authed, sent_codes):
    client, _ = authed
    res = client.post("/api/auth/phone/send-code", json={"phone": "12345"})
    assert res.status_code == 400
    assert len(sent_codes) == 0


# --- امنیت ---------------------------------------------------------------------------


def test_wrong_code_is_rejected(authed, sent_codes):
    client, _ = authed
    client.post("/api/auth/phone/send-code", json={"phone": PHONE})

    res = client.post("/api/auth/phone/verify", json={"code": "000000"})
    assert res.status_code == 400
    assert client.get("/api/auth/me").json()["phone_verified"] is False


def test_code_locks_after_too_many_wrong_attempts(authed, sent_codes):
    """مهم‌ترین تست: بعد از سقفِ تلاش، حتی کدِ درست هم باید رد شود."""
    client, _ = authed
    client.post("/api/auth/phone/send-code", json={"phone": PHONE})
    real = sent_codes[0]["code"]

    for _ in range(tokens.MAX_CODE_ATTEMPTS):
        assert client.post("/api/auth/phone/verify", json={"code": "111111"}).status_code == 400

    locked = client.post("/api/auth/phone/verify", json={"code": real})
    assert locked.status_code == 400, "کدِ درست بعد از سقفِ تلاش هنوز پذیرفته شد — حمله‌ی حدس باز است"
    assert client.get("/api/auth/me").json()["phone_verified"] is False


def test_code_works_only_once(authed, sent_codes):
    client, _ = authed
    client.post("/api/auth/phone/send-code", json={"phone": PHONE})
    code = sent_codes[0]["code"]

    assert client.post("/api/auth/phone/verify", json={"code": code}).status_code == 200
    second = client.post("/api/auth/phone/verify", json={"code": code})
    assert second.status_code == 400, "کد بارِ دوم هم کار کرد"


def test_a_new_code_invalidates_the_previous_one(authed, sent_codes):
    client, _ = authed
    client.post("/api/auth/phone/send-code", json={"phone": PHONE})
    client.post("/api/auth/phone/send-code", json={"phone": PHONE})
    assert len(sent_codes) == 2

    stale = client.post("/api/auth/phone/verify", json={"code": sent_codes[0]["code"]})
    assert stale.status_code == 400, "کدِ قبلی بعد از صدورِ کدِ تازه هنوز کار می‌کند"
    fresh = client.post("/api/auth/phone/verify", json={"code": sent_codes[1]["code"]})
    assert fresh.status_code == 200, fresh.text[:200]


def test_an_expired_code_is_rejected(authed, sent_codes, db):
    client, user = authed
    client.post("/api/auth/phone/send-code", json={"phone": PHONE})

    row = db.query(AuthToken).filter(
        AuthToken.user_id == user.id, AuthToken.purpose == PURPOSE_PHONE_VERIFY
    ).one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.flush()

    res = client.post("/api/auth/phone/verify", json={"code": sent_codes[0]["code"]})
    assert res.status_code == 400, "کدِ منقضی پذیرفته شد"


def test_only_the_hash_of_the_code_is_stored(authed, sent_codes, db):
    client, user = authed
    client.post("/api/auth/phone/send-code", json={"phone": PHONE})
    code = sent_codes[0]["code"]

    row = db.query(AuthToken).filter(
        AuthToken.user_id == user.id, AuthToken.purpose == PURPOSE_PHONE_VERIFY
    ).one()
    assert row.token_hash != code, "کدِ خام در دیتابیس ذخیره شده"
    assert len(row.token_hash) == 64
    # نمک‌خورده با کاربر: hashِ خامِ کد نباید بخورد، ولی نمک‌خورده باید
    assert row.token_hash != tokens.hash_token(code)
    assert row.token_hash == tokens.hash_token(f"{user.id}:{PURPOSE_PHONE_VERIFY}:{code}")


def test_verify_requires_authentication(client, sent_codes):
    assert client.post("/api/auth/phone/verify", json={"code": "123456"}).status_code == 401


# --- تعاملِ با پروفایل ---------------------------------------------------------------


def test_changing_phone_via_profile_drops_verification(authed, sent_codes):
    client, _ = authed
    client.post("/api/auth/phone/send-code", json={"phone": PHONE})
    client.post("/api/auth/phone/verify", json={"code": sent_codes[0]["code"]})
    assert client.get("/api/auth/me").json()["phone_verified"] is True

    patched = client.patch("/api/auth/me", json={"phone": "09350001122"})
    assert patched.status_code == 200
    assert patched.json()["phone_verified"] is False, "شماره‌ی تازه هنوز تأییدشده نشان داده می‌شود"
