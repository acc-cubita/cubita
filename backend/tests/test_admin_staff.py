"""مدیریتِ کاربرانِ ستاد — و قاعده‌ی ضدِقفلی که پنل را باز نگه می‌دارد."""
import pytest

from app.models.staff_audit import StaffAuditLog
from app.models.tenant import PlatformAdmin
from app.models.user import User


@pytest.fixture
def owner_client(staff_client):
    return staff_client(role="owner")


def _create(client, email="new@staff.cubita.ir", role="support"):
    return client.post(
        "/api/admin/staff",
        json={
            "name": "کارمندِ تازه",
            "email": email,
            "password": "AnotherStaffPass!2026",
            "role": role,
        },
    )


# ── فقط مالک ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("role", ["admin", "finance", "support"])
def test_only_the_owner_can_manage_staff(staff_client, role):
    """حتی `admin` هم نمی‌تواند.

    اگر با مجوز گیت می‌شد، یک `admin` می‌توانست به خودش مجوزِ `staff` بدهد و
    بعد خودش را `owner` کند — یعنی گاردِ نقش تزئینی می‌شد.
    """
    c = staff_client(role=role, email=f"{role}@staff.cubita.ir")
    assert c.get("/api/admin/staff").status_code == 403
    assert _create(c).status_code == 403


def test_owner_sees_the_roster(owner_client):
    rows = owner_client.get("/api/admin/staff").json()
    assert len(rows) >= 1
    assert rows[0]["role_label"]


# ── ساخت ────────────────────────────────────────────────────────────────────


def test_creating_a_staff_user(owner_client, db):
    r = _create(owner_client, role="finance")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["role"] == "finance"
    assert body["role_label"] == "مالی"
    assert body["is_active"] is True

    #: کاربرِ تازه **هیچ عضویتی** نمی‌گیرد — نکته‌ی اصلیِ هویتِ ستاد.
    from app.models.tenant import Membership

    assert db.query(Membership).filter(Membership.user_id == body["user_id"]).count() == 0


def test_an_existing_user_can_become_staff(owner_client, db):
    """یک نفر می‌تواند هم مالکِ کسب‌وکارِ خودش باشد و هم کارمندِ ستاد.

    (مالکِ seed دامنه‌ی `.invalid` دارد و از اعتبارسنجیِ ایمیل رد نمی‌شود، پس
    این تست کاربرِ خودش را می‌سازد.)
    """
    from app.security import hash_password

    existing = User(
        name="حسابدارِ مستقل",
        email="both@shop.cubita.ir",
        hashed_password=hash_password("TheirOwnPassword!2026"),
        active=True,
    )
    db.add(existing)
    db.flush()

    r = owner_client.post(
        "/api/admin/staff",
        json={
            "name": existing.name,
            "email": existing.email,
            "password": "IgnoredBecauseUserExists!1",
            "role": "support",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["user_id"] == str(existing.id)


def test_cannot_add_the_same_person_twice(owner_client):
    _create(owner_client, email="dup@staff.cubita.ir")
    assert _create(owner_client, email="dup@staff.cubita.ir").status_code == 409


def test_unknown_role_is_rejected(owner_client):
    r = owner_client.post(
        "/api/admin/staff",
        json={
            "name": "نقشِ خیالی",
            "email": "ghost@staff.cubita.ir",
            "password": "AnotherStaffPass!2026",
            "role": "superuser",
        },
    )
    assert r.status_code == 422


# ── قاعده‌ی ضدِقفل ───────────────────────────────────────────────────────────


def test_the_last_active_owner_cannot_be_disabled(owner_client, db):
    """**مهم‌ترین گاردِ این فایل.**

    بازیابیِ رمزِ ستاد در فازِ ۱ خودکار نیست؛ اگر آخرین مالک برداشته شود، راهِ
    برگشت فقط SSH است. پس سرور اجازه نمی‌دهد.
    """
    me = owner_client.get("/api/admin/auth/me").json()
    mine = next(r for r in owner_client.get("/api/admin/staff").json() if r["id"] == me["id"])
    r = owner_client.patch(f"/api/admin/staff/{mine['id']}/status", json={"active": False})
    assert r.status_code == 409
    assert "تنها مالکِ فعال" in r.json()["detail"]


def test_the_last_active_owner_cannot_be_demoted(owner_client):
    me = owner_client.get("/api/admin/auth/me").json()
    r = owner_client.patch(f"/api/admin/staff/{me['id']}/role", json={"role": "support"})
    assert r.status_code == 409


def test_with_a_second_owner_the_first_can_step_down(owner_client, db):
    second = _create(owner_client, email="owner2@staff.cubita.ir", role="owner").json()
    assert second["role"] == "owner"

    me = owner_client.get("/api/admin/auth/me").json()
    r = owner_client.patch(f"/api/admin/staff/{me['id']}/role", json={"role": "admin"})
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "admin"


# ── نقش و رمز ───────────────────────────────────────────────────────────────


def test_changing_the_role_clears_a_custom_permission_override(owner_client, db):
    """وگرنه نقشِ تازه بی‌اثر می‌ماند و کسی نمی‌فهمد چرا."""
    row = _create(owner_client, email="override@staff.cubita.ir").json()
    admin = db.get(PlatformAdmin, row["id"])
    admin.permissions = {"accounts": ["view", "create", "delete"]}
    db.flush()

    owner_client.patch(f"/api/admin/staff/{row['id']}/role", json={"role": "support"})
    db.refresh(admin)
    assert admin.permissions is None


def test_resetting_a_staff_password_invalidates_their_sessions(owner_client, db):
    row = _create(owner_client, email="reset@staff.cubita.ir").json()
    before = db.get(User, row["user_id"]).token_version or 0

    r = owner_client.post(
        f"/api/admin/staff/{row['id']}/reset-password", json={"password": "FreshStaffPass!2026"}
    )
    assert r.status_code == 200, r.text
    db.expire_all()
    assert (db.get(User, row["user_id"]).token_version or 0) == before + 1


def test_a_disabled_staff_user_is_rejected_on_the_next_request(owner_client, db, staff_client):
    from app.security import create_staff_token
    from fastapi.testclient import TestClient
    from app.main import app

    row = _create(owner_client, email="revoked@staff.cubita.ir", role="admin").json()
    token = create_staff_token(db.get(User, row["user_id"]))

    victim = TestClient(app)
    victim.headers.update({"Authorization": f"Bearer {token}"})
    assert victim.get("/api/admin/auth/me").status_code == 200

    owner_client.patch(f"/api/admin/staff/{row['id']}/status", json={"active": False})
    assert victim.get("/api/admin/auth/me").status_code == 401


# ── ردگیری ──────────────────────────────────────────────────────────────────


def test_staff_changes_are_recorded(owner_client, db):
    row = _create(owner_client, email="traced@staff.cubita.ir").json()
    owner_client.patch(f"/api/admin/staff/{row['id']}/role", json={"role": "finance"})
    owner_client.patch(f"/api/admin/staff/{row['id']}/status", json={"active": False})

    actions = {r.action for r in db.query(StaffAuditLog).all()}
    assert {"staff_create", "staff_role_change", "staff_disable"} <= actions


def test_the_new_password_value_is_never_recorded(owner_client, db):
    secret = "NeverInTheLog!2026"
    row = _create(owner_client, email="secret@staff.cubita.ir").json()
    owner_client.post(f"/api/admin/staff/{row['id']}/reset-password", json={"password": secret})
    blob = "".join(
        f"{r.summary}{r.details}" for r in db.query(StaffAuditLog).all()
    )
    assert secret not in blob
