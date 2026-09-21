"""ورودِ کارمندِ ستاد — و مرزهایی که توکنش نباید رد کند.

قلبِ این پرونده یک ناوردا است: **کارمندِ ستاد به هیچ کسب‌وکاری عضویت ندارد.**
تا پیش از این کوچ، `get_principal` عضویتِ فعال را اجباری می‌کرد و همین باعث
می‌شد حسابِ مدیریتی مجبور باشد یک کسب‌وکارِ واقعی داشته باشد.
"""
import pytest

from app.models.tenant import Membership
from app.security import (
    TOKEN_TYPE_STAFF,
    create_access_token,
    create_staff_token,
    decode_access_token,
)


def test_staff_token_carries_no_tenant(db, staff_user):
    """نبودِ `tid` تزئینی نیست — خودِ سازوکارِ بسته‌ماندنِ RLS است."""
    admin = staff_user()
    claims = decode_access_token(create_staff_token(admin.user))
    assert claims is not None
    assert claims.typ == TOKEN_TYPE_STAFF
    assert claims.tenant_id is None


def test_staff_user_has_no_membership(db, staff_user):
    admin = staff_user()
    assert db.query(Membership).filter(Membership.user_id == admin.user_id).count() == 0


def test_login_returns_a_staff_token(db, staff_client, staff_user):
    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.main import app

    staff_user(email="login@staff.cubita.ir", role="admin")
    app.dependency_overrides[get_db] = lambda: db
    c = TestClient(app)
    r = c.post(
        "/api/admin/auth/login",
        json={"email": "login@staff.cubita.ir", "password": "StaffPassword!2026"},
    )
    assert r.status_code == 200, r.text
    claims = decode_access_token(r.json()["access_token"])
    assert claims.typ == TOKEN_TYPE_STAFF and claims.tenant_id is None


@pytest.mark.parametrize(
    "email,password",
    [
        ("login@staff.cubita.ir", "WrongPassword!1"),      # رمزِ غلط
        ("nobody@staff.cubita.ir", "StaffPassword!2026"),  # کاربر وجود ندارد
        ("client@shop.cubita.ir", "ClientPassword!2026"),  # کاربر هست، کارمندِ ستاد نیست
    ],
)
def test_every_login_failure_looks_identical(db, staff_user, email, password):
    """پیامِ متفاوت یعنی فهرستِ کارمندانِ ستاد قابلِ استخراج است.

    آن فهرست هیچ‌جای دیگری در دسترس نیست، پس تفکیکِ «رمزِ غلط» از «کارمند نیست»
    چیزی لو می‌دهد که خودِ سامانه هرگز منتشر نمی‌کند.
    """
    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.main import app

    from app.models.user import User
    from app.security import hash_password

    staff_user(email="login@staff.cubita.ir")
    db.add(
        User(
            name="مشتریِ عادی",
            email="client@shop.cubita.ir",
            hashed_password=hash_password("ClientPassword!2026"),
            active=True,
        )
    )
    db.flush()
    app.dependency_overrides[get_db] = lambda: db
    try:
        r = TestClient(app).post(
            "/api/admin/auth/login", json={"email": email, "password": password}
        )
        assert r.status_code == 401
        assert r.json()["detail"] == "ایمیل یا رمز عبور نادرست است"
    finally:
        app.dependency_overrides.clear()


def test_inactive_staff_row_cannot_log_in(db, staff_user):
    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.main import app

    admin = staff_user(email="gone@staff.cubita.ir")
    admin.is_active = False
    db.flush()
    app.dependency_overrides[get_db] = lambda: db
    try:
        r = TestClient(app).post(
            "/api/admin/auth/login",
            json={"email": "gone@staff.cubita.ir", "password": "StaffPassword!2026"},
        )
        assert r.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_password_change_kills_outstanding_staff_tokens(db, staff_client):
    c = staff_client()
    assert c.get("/api/admin/auth/me").status_code == 200

    stale = dict(c.headers)
    r = c.post(
        "/api/admin/auth/change-password",
        json={"current_password": "StaffPassword!2026", "new_password": "BrandNew!2026"},
    )
    assert r.status_code == 200, r.text

    from fastapi.testclient import TestClient

    from app.main import app

    other = TestClient(app)
    other.headers.update({"Authorization": stale["authorization"]})
    assert other.get("/api/admin/auth/me").status_code == 401


def test_change_password_needs_the_current_one(db, staff_client):
    c = staff_client()
    r = c.post(
        "/api/admin/auth/change-password",
        json={"current_password": "NotIt!2026", "new_password": "BrandNew!2026"},
    )
    assert r.status_code == 400


def test_me_reports_role_and_permissions(db, staff_client):
    body = staff_client(role="finance", email="fin@staff.cubita.ir").get(
        "/api/admin/auth/me"
    ).json()
    assert body["role"] == "finance"
    assert body["role_label"] == "مالی"
    assert body["via"] == "staff"
    #: `finance` فقط می‌بیند — ساختِ اکانت کارِ او نیست.
    assert "create" not in body["permissions"]["accounts"]


def test_login_rate_limit_trips(db, staff_user):
    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.main import app

    staff_user(email="rl@staff.cubita.ir")
    app.dependency_overrides[get_db] = lambda: db
    try:
        c = TestClient(app)
        codes = [
            c.post(
                "/api/admin/auth/login",
                json={"email": "rl@staff.cubita.ir", "password": "nope"},
            ).status_code
            for _ in range(7)
        ]
        assert 429 in codes, codes
    finally:
        app.dependency_overrides.clear()


def test_diagnostics_names_the_database(db, staff_client):
    """کاوشی که استقرارِ اشتباهِ دمو لازم داشت: `/api/health` دو بک‌اند را از هم جدا نمی‌کند."""
    body = staff_client().get("/api/admin/diagnostics").json()
    assert body["database_name"]
    assert body["staff_count"] >= 1


def test_tenant_token_is_not_a_staff_token(db, user):
    claims = decode_access_token(create_access_token(user))
    assert claims.typ == "tenant"
