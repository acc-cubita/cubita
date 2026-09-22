"""بازیابی و تغییر رمز عبور.

تا امروز هیچ مسیر بازیابی وجود نداشت: مشتری‌ای که رمزش را فراموش می‌کرد برای همیشه
بیرون می‌ماند و فقط با UPDATE دستی روی دیتابیس قابل نجات بود. حالا که ثبت‌نام
عمومی است، این دیگر یک ناراحتی نیست — یک مسیر شکستِ قطعی است.

سه تست اینجا امنیتی‌اند و نه کارکردی:

- `test_forgot_password_never_reveals_whether_the_email_exists` — اگر پاسخ برای
  ایمیل موجود و ناموجود فرق کند، این اندپوینت به ابزار فهرست‌برداری مشتریان کوبیتا
  تبدیل می‌شود.
- `test_changing_password_kills_existing_sessions` — کاری که کاربر دقیقاً برای
  بیرون کردن مهاجم انجام می‌دهد باید واقعاً کار کند.
- `test_only_the_hash_of_the_token_is_stored` — وگرنه یک نشتِ خواندنی از دیتابیس
  (یا یک پشتیبان گم‌شده) به تصاحب همه‌ی حساب‌ها تبدیل می‌شود.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models.auth_token import PURPOSE_INVITE, PURPOSE_PASSWORD_RESET, AuthToken
from app.security import create_access_token
from app.services import tokens
from app.services.provisioning import signup_new_business

PASSWORD = "AStrongPassword2026"
NEW_PASSWORD = "ADifferentPassword2027"


@pytest.fixture(autouse=True)
def _clean_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def anon(db):
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


@pytest.fixture
def sent_resets(monkeypatch):
    captured: list[dict] = []

    def fake_send(*, to, name, token, valid_hours):
        captured.append({"to": to, "token": token})
        return True

    monkeypatch.setattr("app.routers.auth.send_password_reset", fake_send)
    return captured


@pytest.fixture
def account(db):
    tenant, user = signup_new_business(
        db,
        business_name="کسب‌وکار بازیابی",
        owner_name="مالک",
        email=f"reset-{uuid.uuid4().hex[:8]}@cubita-test.ir",
        password=PASSWORD,
    )
    db.flush()
    return tenant, user


# --- عدم افشای وجود کاربر --------------------------------------------------------------


def test_forgot_password_never_reveals_whether_the_email_exists(anon, account, sent_resets):
    _, user = account

    known = anon.post("/api/auth/forgot-password", json={"email": user.email})
    unknown = anon.post(
        "/api/auth/forgot-password", json={"email": f"ghost-{uuid.uuid4().hex[:8]}@cubita-test.ir"}
    )

    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json(), "پاسخ برای ایمیل موجود و ناموجود فرق داشت — فهرست کاربران قابل استخراج است"
    # ولی ایمیل فقط برای حساب واقعی رفته باشد
    assert len(sent_resets) == 1 and sent_resets[0]["to"] == user.email


def test_hitting_the_per_email_cap_still_looks_identical(anon, account, sent_resets):
    """سقفِ مبتنی بر ایمیل نباید با ۴۲۹ خودش را لو بدهد.

    اگر ایمیل موجود بعد از چند تلاش ۴۲۹ بدهد و ایمیل ناموجود همچنان ۲۰۲، همان
    نشتِ شمارش کاربران از در پشتی برمی‌گردد.
    """
    _, user = account
    statuses = [
        anon.post("/api/auth/forgot-password", json={"email": user.email}).status_code for _ in range(5)
    ]
    assert set(statuses) == {202}, f"سقف ایمیلی خودش را با کد وضعیت لو داد: {statuses}"
    # ولی واقعاً جلوی ارسال را گرفته باشد
    assert len(sent_resets) < 5, "سقف مبتنی بر ایمیل اصلاً اعمال نشد"


# --- خودِ چرخه ---------------------------------------------------------------------


def test_reset_link_sets_a_new_password_and_kills_the_old_one(anon, account, sent_resets):
    _, user = account
    anon.post("/api/auth/forgot-password", json={"email": user.email})

    res = anon.post(
        "/api/auth/reset-password", json={"token": sent_resets[0]["token"], "password": NEW_PASSWORD}
    )
    assert res.status_code == 200, res.text[:300]

    assert anon.post("/api/auth/login", json={"email": user.email, "password": NEW_PASSWORD}).status_code == 200
    old = anon.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
    assert old.status_code == 401, "رمز قدیمی بعد از بازیابی هنوز کار می‌کند"


def test_the_token_returned_by_reset_works_immediately(anon, account, sent_resets):
    """توکنِ بازگشتی نباید قربانی همان بررسی‌ای شود که نشست‌های قدیمی را می‌کشد.

    اگر توکن قبل از `set_password` صادر شود نسل قدیمی را دارد و بلافاصله باطل
    می‌شود — یعنی کاربر درست بعد از بازیابی موفق رمز، باز هم بیرون می‌ماند.
    """
    _, user = account
    anon.post("/api/auth/forgot-password", json={"email": user.email})
    token = anon.post(
        "/api/auth/reset-password", json={"token": sent_resets[0]["token"], "password": NEW_PASSWORD}
    ).json()["access_token"]

    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {token}"})
    assert client.get("/api/auth/me").status_code == 200, "توکنِ صادرشده توسط خودِ بازیابی رد شد"


def test_reset_link_works_only_once(anon, account, sent_resets):
    _, user = account
    anon.post("/api/auth/forgot-password", json={"email": user.email})
    token = sent_resets[0]["token"]

    assert anon.post("/api/auth/reset-password", json={"token": token, "password": NEW_PASSWORD}).status_code == 200
    second = anon.post("/api/auth/reset-password", json={"token": token, "password": "YetAnotherPass2028"})
    assert second.status_code == 400, "لینک بازیابی بار دوم هم کار کرد"


def test_a_new_request_invalidates_the_previous_link(anon, account, sent_resets):
    """لینک قدیمیِ رهاشده در صندوق ایمیل نباید تا ابد یک در باز بماند."""
    _, user = account
    anon.post("/api/auth/forgot-password", json={"email": user.email})
    anon.post("/api/auth/forgot-password", json={"email": user.email})
    assert len(sent_resets) == 2

    stale = anon.post(
        "/api/auth/reset-password", json={"token": sent_resets[0]["token"], "password": NEW_PASSWORD}
    )
    assert stale.status_code == 400, "لینک اولِ باطل‌شده هنوز کار می‌کند"
    fresh = anon.post(
        "/api/auth/reset-password", json={"token": sent_resets[1]["token"], "password": NEW_PASSWORD}
    )
    assert fresh.status_code == 200, fresh.text[:200]


def test_an_expired_link_is_rejected(anon, db, account, sent_resets):
    _, user = account
    anon.post("/api/auth/forgot-password", json={"email": user.email})

    row = db.query(AuthToken).filter(AuthToken.user_id == user.id).one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.flush()

    res = anon.post(
        "/api/auth/reset-password", json={"token": sent_resets[0]["token"], "password": NEW_PASSWORD}
    )
    assert res.status_code == 400, "لینک منقضی پذیرفته شد"


def test_an_invite_token_cannot_be_spent_as_a_password_reset(anon, db, account):
    """دو جریان با عمر و سطح اعتماد متفاوت نباید به هم وصل شوند.

    توکن دعوت ۷ روز معتبر است و توکن بازیابی یک ساعت؛ اگر `purpose` سنجیده نشود،
    عمرِ بلندِ یکی به دیگری قرض داده می‌شود.
    """
    tenant, user = account
    raw = tokens.issue_invite(db, user.id, tenant.id)

    res = anon.post("/api/auth/reset-password", json={"token": raw, "password": NEW_PASSWORD})
    assert res.status_code == 400, "توکن دعوت به‌عنوان توکن بازیابی رمز خرج شد"


def test_a_garbage_token_is_rejected(anon):
    res = anon.post("/api/auth/reset-password", json={"token": "not-a-real-token", "password": NEW_PASSWORD})
    assert res.status_code == 400


# --- ذخیره‌سازی راز ------------------------------------------------------------------


def test_only_the_hash_of_the_token_is_stored(anon, db, account, sent_resets):
    _, user = account
    anon.post("/api/auth/forgot-password", json={"email": user.email})
    raw = sent_resets[0]["token"]

    row = db.query(AuthToken).filter(AuthToken.user_id == user.id).one()
    assert row.token_hash != raw, "توکن خام در دیتابیس ذخیره شده"
    assert row.token_hash == tokens.hash_token(raw)
    assert len(row.token_hash) == 64

    # و راز واقعاً غیرقابل حدس باشد
    assert len(raw) >= 40, f"توکن کوتاه است ({len(raw)} کاراکتر)"


# --- باطل شدن نشست‌ها ----------------------------------------------------------------


def test_changing_password_kills_existing_sessions(db, account, sent_resets):
    """مهم‌ترین تست این پرونده.

    توکن‌های ما stateless‌اند؛ بدون بررسی `password_changed_at`، کسی که توکن دزدیده
    تا ۸ ساعت دسترسی دارد حتی بعد از اینکه قربانی رمزش را عوض کند. یعنی تنها کاری
    که کاربر برای بیرون کردن مهاجم بلد است، هیچ اثری ندارد.
    """
    tenant, user = account
    app.dependency_overrides[get_db] = lambda: db

    stolen = TestClient(app)
    stolen.headers.update({"Authorization": f"Bearer {create_access_token(user, tenant.id)}"})
    assert stolen.get("/api/auth/me").status_code == 200, "توکن اولیه از همان اول کار نکرد"

    victim = TestClient(app)
    victim.headers.update({"Authorization": f"Bearer {create_access_token(user, tenant.id)}"})
    changed = victim.post(
        "/api/auth/change-password",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert changed.status_code == 200, changed.text[:300]

    after = stolen.get("/api/auth/me")
    assert after.status_code == 401, f"نشست قدیمی بعد از تغییر رمز هنوز زنده است: {after.status_code}"

    # و توکن تازه‌ای که خودِ تغییر رمز داد باید کار کند
    fresh = TestClient(app)
    fresh.headers.update({"Authorization": f"Bearer {changed.json()['access_token']}"})
    assert fresh.get("/api/auth/me").status_code == 200


def test_change_password_issues_a_fresh_refresh_too(db, account):
    """نشستِ آفلاینِ دسکتاپ نباید با تغییرِ رمزِ خودِ کاربر بشکند.

    set_password نسلِ توکن را جلو می‌برد و رفرشِ نسلِ قدیم را باطل می‌کند
    (services/refresh.py) — پس اگر change-password رفرشِ تازه ندهد، کاربری که
    رمزش را از داخلِ اپ عوض می‌کند، نشستِ آفلاینش را هم از دست می‌دهد.
    """
    tenant, user = account
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {create_access_token(user, tenant.id)}"})

    res = client.post(
        "/api/auth/change-password",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert res.status_code == 200, res.text[:300]
    new_refresh = res.json().get("refresh_token")
    assert new_refresh

    # app.dependency_overrides از بالای همین تست ست شده؛ کلاینتِ تازه هم آن را
    # به ارث می‌برد چون هر دو همان app را می‌سازند.
    anon = TestClient(app)
    refreshed = anon.post("/api/auth/refresh", json={"refresh_token": new_refresh})
    assert refreshed.status_code == 200, refreshed.text[:300]


def test_change_password_requires_the_current_one(db, account):
    """بدون این، لپ‌تاپِ بازِ رهاشده یا توکنِ دزدیده‌شده به تصاحب دائمی حساب می‌رسد."""
    tenant, user = account
    app.dependency_overrides[get_db] = lambda: db

    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {create_access_token(user, tenant.id)}"})
    res = client.post(
        "/api/auth/change-password",
        json={"current_password": "WrongCurrentPassword", "new_password": NEW_PASSWORD},
    )
    assert res.status_code == 400


def test_a_weak_new_password_is_rejected(db, account):
    tenant, user = account
    app.dependency_overrides[get_db] = lambda: db

    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {create_access_token(user, tenant.id)}"})
    res = client.post(
        "/api/auth/change-password", json={"current_password": PASSWORD, "new_password": "short"}
    )
    assert res.status_code == 422
