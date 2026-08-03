"""ماژولِ «مدیریت اکانت‌ها» — گیتِ سوپرادمین، فهرست، ساخت، تمدید، تعلیق، رمز، حذف."""
import pytest

from app.config import get_settings

OWNER = "test-owner@example.invalid"  # = SEED_OWNER_EMAIL


@pytest.fixture
def super_client(client, monkeypatch):
    """همان کلاینتِ تست، ولی کاربرش را سوپرادمین می‌کند (به‌جای acc.cubita پیش‌فرض)."""
    monkeypatch.setattr(get_settings(), "super_admin_emails", OWNER)
    return client


def _create(super_client, email="new-cust@example.com", days=365):
    return super_client.post(
        "/api/admin/accounts",
        json={
            "business_name": "مشتری تازه",
            "owner_name": "علی رضایی",
            "email": email,
            "password": "verylongpassword",
            "days": days,
        },
    )


# --- گیت --------------------------------------------------------------------

def test_gate_blocks_non_super_admin(client):
    # بدونِ سوپرادمین‌کردن، کاربرِ عادیِ تست دسترسی ندارد
    assert client.get("/api/admin/accounts").status_code == 403
    assert client.post("/api/admin/accounts", json={}).status_code == 403


def test_super_admin_can_list(super_client):
    r = super_client.get("/api/admin/accounts")
    assert r.status_code == 200, r.text
    rows = r.json()
    assert any(row["owner_email"] == OWNER for row in rows)


# --- ساخت -------------------------------------------------------------------

def test_create_account_with_subscription(super_client):
    r = _create(super_client, days=365)
    assert r.status_code == 201, r.text
    row = r.json()
    assert row["owner_email"] == "new-cust@example.com"
    assert row["name"] == "مشتری تازه"
    assert row["subscription_status"] == "active"
    assert row["days_left"] is not None and row["days_left"] > 300
    assert row["status"] == "active"


def test_create_without_days_has_no_subscription(super_client):
    r = _create(super_client, email="no-sub@example.com", days=0)
    assert r.status_code == 201, r.text
    assert r.json()["subscription_status"] == "none"


# --- دیدِ آزمایشیِ رایگان -----------------------------------------------------

def test_manual_account_is_not_trial(super_client):
    """اکانتِ دستیِ مدیر آزمایشی نیست — پرچمِ trial باید خاموش بماند."""
    row = _create(super_client, email="manual@example.com", days=365).json()
    assert row["is_trial"] is False
    assert row["trial_days_left"] is None
    assert row["trial_expired"] is False


def test_self_serve_signup_shows_as_trial(super_client):
    """ثبت‌نامِ «۱۴ روز رایگان» در فهرستِ مدیریت با پرچمِ آزمایشی و ~۱۴ روز دیده می‌شود."""
    r = super_client.post(
        "/api/auth/signup",
        json={
            "business_name": "کسب‌وکارِ آزمایشی",
            "owner_name": "مریم احمدی",
            "email": "trialbiz@example.com",
            "password": "verylongpassword",
        },
    )
    assert r.status_code == 201, r.text

    rows = super_client.get("/api/admin/accounts").json()
    row = next(x for x in rows if x["owner_email"] == "trialbiz@example.com")
    assert row["is_trial"] is True
    assert row["trial_expired"] is False
    assert row["trial_days_left"] == 14  # ceil در لحظه‌ی ثبت‌نام = ۱۴
    # فیلترِ فرانت روی همین is_trial کار می‌کند؛ اکانتِ آزمایشی پلن ندارد.
    assert row["plan_name"] == ""


def test_duplicate_email_rejected(super_client):
    assert _create(super_client, email="dup@example.com").status_code == 201
    assert _create(super_client, email="dup@example.com").status_code == 409


def test_short_password_rejected(super_client):
    r = super_client.post(
        "/api/admin/accounts",
        json={"business_name": "x", "owner_name": "y", "email": "z@example.com", "password": "short"},
    )
    assert r.status_code == 422


# --- تمدید ------------------------------------------------------------------

def test_extend_adds_days(super_client):
    tid = _create(super_client, email="ext@example.com", days=10).json()["tenant_id"]
    r = super_client.post(f"/api/admin/accounts/{tid}/extend", json={"days": 30})
    assert r.status_code == 200, r.text
    assert r.json()["days_left"] > 30  # ۱۰ + ۳۰


def test_set_expiry_date(super_client):
    tid = _create(super_client, email="exp@example.com", days=0).json()["tenant_id"]
    r = super_client.post(f"/api/admin/accounts/{tid}/extend", json={"expires_at": "2030-01-01"})
    assert r.status_code == 200, r.text
    assert r.json()["subscription_status"] == "active"


def test_extend_clears_trial_flag(super_client):
    """تمدیدِ دستیِ یک اکانتِ آزمایشی، پرچمِ trial را پاک می‌کند (دیگر آزمایشی نیست)."""
    super_client.post(
        "/api/auth/signup",
        json={
            "business_name": "آزمایشیِ تمدیدی",
            "owner_name": "رضا",
            "email": "trial-extend@example.com",
            "password": "verylongpassword",
        },
    )
    tid = next(r["tenant_id"] for r in super_client.get("/api/admin/accounts").json() if r["owner_email"] == "trial-extend@example.com")
    r = super_client.post(f"/api/admin/accounts/{tid}/extend", json={"days": 365})
    assert r.status_code == 200, r.text
    row = r.json()
    assert row["is_trial"] is False
    assert row["trial_days_left"] is None


# --- تعلیق/فعال‌سازی ---------------------------------------------------------

def test_suspend_and_activate(super_client):
    tid = _create(super_client, email="susp@example.com").json()["tenant_id"]
    assert super_client.post(f"/api/admin/accounts/{tid}/status", json={"status": "suspended"}).json()["status"] == "suspended"
    assert super_client.post(f"/api/admin/accounts/{tid}/status", json={"status": "active"}).json()["status"] == "active"


def test_cannot_suspend_own_account(super_client):
    rows = super_client.get("/api/admin/accounts").json()
    own = next(r for r in rows if r["owner_email"] == OWNER)
    r = super_client.post(f"/api/admin/accounts/{own['tenant_id']}/status", json={"status": "suspended"})
    assert r.status_code == 400


# --- بازنشانی رمز -----------------------------------------------------------

def test_reset_owner_password(super_client):
    tid = _create(super_client, email="pw@example.com").json()["tenant_id"]
    r = super_client.post(f"/api/admin/accounts/{tid}/reset-password", json={"password": "anotherlongpassword"})
    assert r.status_code == 200, r.text


# --- حذف --------------------------------------------------------------------

def test_delete_account(super_client):
    tid = _create(super_client, email="del@example.com").json()["tenant_id"]
    assert super_client.delete(f"/api/admin/accounts/{tid}").status_code == 200
    rows = super_client.get("/api/admin/accounts").json()
    assert all(row["tenant_id"] != tid for row in rows)


def test_cannot_delete_own_account(super_client):
    rows = super_client.get("/api/admin/accounts").json()
    own = next(r for r in rows if r["owner_email"] == OWNER)
    assert super_client.delete(f"/api/admin/accounts/{own['tenant_id']}").status_code == 400


# --- فعالیتِ کاربران --------------------------------------------------------

def test_new_account_has_users_but_no_activity(super_client):
    row = _create(super_client, email="act@example.com").json()
    # اکانتِ تازه یک کاربرِ مالک دارد که هنوز وارد نشده
    assert row["owner_last_login_at"] is None
    assert row["last_activity_at"] is None
    assert len(row["users"]) == 1
    owner = row["users"][0]
    assert owner["is_owner"] is True
    assert owner["email"] == "act@example.com"
    assert owner["last_login_at"] is None


def test_login_updates_last_activity(super_client):
    # اکانتی با ایمیلِ معتبر می‌سازیم تا بتوانیم واقعاً با /login وارد شویم
    # (ایمیلِ seed پسوندِ رزروِ .invalid دارد و EmailStr ردش می‌کند).
    email, pw = "login@example.com", "verylongpassword"
    tid = _create(super_client, email=email).json()["tenant_id"]

    before = next(r for r in super_client.get("/api/admin/accounts").json() if r["tenant_id"] == tid)
    assert before["owner_last_login_at"] is None
    assert before["last_activity_at"] is None

    # ورودِ واقعی (این اندپوینت auth را override نمی‌کند)
    r = super_client.post("/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text

    after = next(r for r in super_client.get("/api/admin/accounts").json() if r["tenant_id"] == tid)
    assert after["owner_last_login_at"] is not None
    assert after["last_activity_at"] is not None
    assert any(u["is_owner"] and u["last_login_at"] is not None for u in after["users"])
