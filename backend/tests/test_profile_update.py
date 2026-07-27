"""ویرایشِ پروفایل و نامِ کسب‌وکار (PATCH /api/auth/me و /api/auth/business)."""
from app.models.user import User
from app.security import set_password
from tests.conftest import SEED_OWNER_PASSWORD


def test_update_name_and_phone(db, user, client):
    res = client.patch("/api/auth/me", json={"name": "نامِ تازه", "phone": "09120000000"})

    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "نامِ تازه"
    assert body["phone"] == "09120000000"
    db.refresh(user)
    assert user.name == "نامِ تازه"


def test_partial_update_keeps_email(db, user, client):
    original_email = user.email
    client.patch("/api/auth/me", json={"name": "فقط نام"})
    db.refresh(user)
    assert user.email == original_email  # ایمیل دست نخورد


def test_email_change_needs_current_password(db, user, client):
    res = client.patch("/api/auth/me", json={"email": "new.owner@gmail.com"})

    assert res.status_code == 400
    db.refresh(user)
    assert user.email != "new.owner@gmail.com"


def test_email_change_with_correct_password(db, user, client):
    res = client.patch(
        "/api/auth/me",
        json={"email": "changed.owner@gmail.com", "current_password": SEED_OWNER_PASSWORD},
    )

    assert res.status_code == 200
    assert res.json()["email"] == "changed.owner@gmail.com"
    db.refresh(user)
    assert user.email == "changed.owner@gmail.com"


def test_email_duplicate_is_rejected(db, user, client):
    other = User(name="کاربرِ دیگر", email="taken@gmail.com")
    set_password(other, "AnotherPassword!2026")
    db.add(other)
    db.flush()

    res = client.patch(
        "/api/auth/me",
        json={"email": "taken@gmail.com", "current_password": SEED_OWNER_PASSWORD},
    )

    assert res.status_code == 409


def test_owner_can_rename_business(db, user, client):
    res = client.patch("/api/auth/business", json={"name": "کسب‌وکارِ تازه"})

    assert res.status_code == 200
    assert res.json()["tenant_name"] == "کسب‌وکارِ تازه"


def test_blank_name_rejected(db, user, client):
    res = client.patch("/api/auth/me", json={"name": "   "})
    assert res.status_code == 422
