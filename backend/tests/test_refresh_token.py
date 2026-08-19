"""رفرش‌توکنِ نشستِ موبایل — چرخش، ابطالِ با تغییرِ رمز، انقضا، خروج.

مسیرهای login/refresh/logout به get_principal وابسته نیستند، پس روی یک TestClientِ
گره‌خورده به sessionِ تست (بدونِ override احراز) منطقِ واقعی اجرا می‌شود. حساب با ایمیلِ
معتبر ساخته می‌شود چون LoginIn.email از نوعِ EmailStr است و ایمیلِ seed رزروشده است.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models.refresh_token import RefreshToken
from app.security import set_password
from app.services.provisioning import signup_new_business
from app.services.tokens import hash_token

PASSWORD = "AStrongPassword2026"


@pytest.fixture(autouse=True)
def _clean_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def anon(db):
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


@pytest.fixture
def account(db):
    _, user = signup_new_business(
        db,
        business_name="کسب‌وکار رفرش",
        owner_name="مالک",
        email=f"refresh-{uuid.uuid4().hex[:8]}@cubita-test.ir",
        password=PASSWORD,
    )
    db.flush()
    return user


def _login(anon, user) -> dict:
    resp = anon.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_login_issues_access_and_refresh(anon, account):
    body = _login(anon, account)
    assert body["access_token"]
    assert body["refresh_token"]


def test_refresh_rotates_old_dies_new_works(anon, account):
    old = _login(anon, account)["refresh_token"]

    r = anon.post("/api/auth/refresh", json={"refresh_token": old})
    assert r.status_code == 200, r.text
    new = r.json()["refresh_token"]
    assert new and new != old
    assert r.json()["access_token"]

    # توکنِ چرخیده دیگر کار نمی‌کند (یک‌بارمصرفِ عملی).
    assert anon.post("/api/auth/refresh", json={"refresh_token": old}).status_code == 401
    # ولی تازه کار می‌کند.
    assert anon.post("/api/auth/refresh", json={"refresh_token": new}).status_code == 200


def test_change_password_invalidates_refresh(anon, account, db):
    old = _login(anon, account)["refresh_token"]
    set_password(account, "AnotherStrongPassword!2026")  # نسلِ توکن جلو می‌رود
    db.flush()
    assert anon.post("/api/auth/refresh", json={"refresh_token": old}).status_code == 401


def test_expired_refresh_is_rejected(anon, account, db):
    from app.services import refresh as refresh_svc

    membership = account.memberships[0]
    raw = refresh_svc.issue_refresh(db, user=account, tenant_id=membership.tenant_id)
    row = db.query(RefreshToken).filter(RefreshToken.token_hash == hash_token(raw)).one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.flush()
    assert anon.post("/api/auth/refresh", json={"refresh_token": raw}).status_code == 401


def test_logout_revokes_refresh(anon, account):
    old = _login(anon, account)["refresh_token"]
    assert anon.post("/api/auth/logout", json={"refresh_token": old}).status_code == 204
    assert anon.post("/api/auth/refresh", json={"refresh_token": old}).status_code == 401


def test_garbage_refresh_is_rejected(anon, account):
    assert anon.post("/api/auth/refresh", json={"refresh_token": "not-a-real-token"}).status_code == 401
