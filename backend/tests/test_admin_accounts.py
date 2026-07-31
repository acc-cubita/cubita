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
