"""دسترسیِ حسابرس — عضویتِ موقت، انقضا، و مرزهایی که نباید رد کند.

این فایل جوابِ سؤالی است که مشتری حق دارد بپرسد: «کسی که به دفترم دسترسی دادید
دقیقاً چه کاری می‌تواند بکند؟» هر سطرش یک «نمی‌تواند» است.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.config import get_settings
from app.deps import Principal, get_principal
from app.models.assurance import AssuranceEngagement
from app.models.tenant import Membership
from app.models.user import Role, User
from app.security import hash_password
from app.services import members as members_service

OWNER = "test-owner@example.invalid"
AUDITOR_EMAIL = "auditor2@cubita.invalid"

#: نمونه‌ای از مسیرهای نوشتن در ماژول‌های مختلف. حسابرس نباید هیچ‌کدام را بتواند.
WRITE_PATHS = [
    ("POST", "/api/journal-entries", {"entry_date": "2026-03-01", "description": "x", "lines": []}),
    ("POST", "/api/accounts", {"code": "9999", "name": "حسابِ نفوذی", "type": "expense"}),
    ("POST", "/api/members/invite", {"email": "x@y.z", "role_key": "accountant"}),
    ("PUT", "/api/modules", {"enabled": []}),
]


@pytest.fixture
def super_client(client, staff_client):
    """کارتابلِ ستاد با توکنِ ستادی.

    `client` هم گرفته می‌شود چون همه‌ی تست‌های این پرونده سمتِ مستأجر را هم لمس
    می‌کنند و ترتیبِ ساختِ فیکسچرها باید ثابت بماند (هر دو `get_db` را به همان
    session می‌بندند).
    """
    return staff_client(role="owner")


@pytest.fixture
def auditor_user(db) -> User:
    """کاربرِ حسابرسِ کوبیتا.

    عمداً **مستأجر کامل provision نمی‌شود**: حسابرس فقط باید یک کاربرِ موجود
    باشد. ساختنِ یک مستأجرِ واقعی هم اسکیمای مشترکِ تست‌ها را آلوده می‌کرد (چون
    `provision_tenant` واقعاً commit می‌کند) و هم پاک‌کردنش روی قفلِ تراکنشِ بازِ
    همین تست می‌ماند — کاربرِ تازه از داخلِ همان تراکنش، هر دو مشکل را ندارد.
    """
    user = User(
        name="حسابرسِ کوبیتا",
        email=AUDITOR_EMAIL,
        hashed_password=hash_password("AuditorPassword!2026"),
        active=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def engaged(client, super_client, auditor_user, db):
    """قراردادِ تأییدشده + عضویتِ حسابرس."""
    created = client.post(
        "/api/assurance/request",
        json={"period_from": "2026-01-01", "period_to": "2026-06-30", "contact_phone": ""},
    ).json()
    super_client.post(
        f"/api/admin/assurance/{created['id']}/approve",
        json={"auditor_email": AUDITOR_EMAIL, "days": 30},
    )
    return db.get(AssuranceEngagement, uuid.UUID(created["id"]))


def _membership(db, engagement) -> Membership:
    return db.get(Membership, engagement.auditor_membership_id)


def _as_auditor(client, db, auditor_user, engagement):
    """کلاینتِ تست را با هویتِ حسابرس در کسب‌وکارِ مشتری اجرا می‌کند.

    `get_principal` در تست override شده، پس جابه‌جایی هویت همان‌جا انجام می‌شود —
    همان کاری که فیکسچرِ `client` برای مالک می‌کند.
    """
    from app.main import app

    membership = _membership(db, engagement)
    app.dependency_overrides[get_principal] = lambda: Principal(auditor_user, membership)
    return client


# ── عضویتِ موقت ─────────────────────────────────────────────────────────────


def test_approve_creates_a_time_boxed_readonly_membership(engaged, db):
    membership = _membership(db, engaged)
    assert membership is not None
    assert membership.status == "active"
    assert membership.role.key == "auditor"
    assert membership.expires_at is not None
    assert membership.expires_at == engaged.access_expires_at
    #: نقش فقط مشاهده دارد، و «مدیریت کاربران» اصلاً در آن نیست.
    assert membership.role.permissions["accounting"] == ["view"]
    assert "users" not in membership.role.permissions
    assert "*" not in membership.role.permissions


def test_auditor_does_not_consume_a_plan_seat(engaged, db, tenant_id):
    """حسابرسِ ما مهمانِ موقت است؛ نباید مشتری را وادار به خریدِ صندلی کند."""
    seats = members_service.seats_used(db, tenant_id)
    others = (
        db.query(Membership)
        .join(Role, Role.id == Membership.role_id)
        .filter(Membership.tenant_id == tenant_id, Role.key != "auditor")
        .filter(Membership.status.in_(members_service.SEAT_STATUSES))
        .count()
    )
    assert seats == others


@pytest.mark.parametrize("method,path,body", WRITE_PATHS)
def test_auditor_cannot_write_anywhere(engaged, client, db, auditor_user, method, path, body):
    as_auditor = _as_auditor(client, db, auditor_user, engaged)
    response = as_auditor.request(method, path, json=body)
    #: دقیقاً ۴۰۳ — ۴۰۴ یعنی مسیر اصلاً وجود ندارد و تست هیچ چیزی را اثبات نمی‌کند.
    assert response.status_code == 403, f"{path} → {response.status_code}: {response.text[:200]}"


def test_auditor_cannot_export_or_backup(engaged, client, db, auditor_user):
    as_auditor = _as_auditor(client, db, auditor_user, engaged)
    assert as_auditor.get("/api/backup/export").status_code == 403


def test_auditor_can_read_the_ledger_and_the_score(engaged, client, db, auditor_user):
    as_auditor = _as_auditor(client, db, auditor_user, engaged)
    assert as_auditor.get("/api/assurance/runs/latest").status_code == 200
    assert as_auditor.get("/api/reports/integrity").status_code == 200


def test_auditor_can_refresh_the_run(engaged, client, db, auditor_user):
    """کنشِ `refresh` تنها کارِ «نوشتنی»ای است که حسابرس دارد — و چیزی در دفتر نمی‌نویسد."""
    engaged.last_run_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db.flush()
    as_auditor = _as_auditor(client, db, auditor_user, engaged)
    assert as_auditor.post("/api/assurance/runs").status_code == 201


# ── انقضا و ابطال ───────────────────────────────────────────────────────────


def test_expired_membership_is_rejected_by_get_principal(engaged, db, auditor_user, tenant_id):
    """گاردِ انقضا در `get_principal` است — تنها نقطه‌ای که هر درخواست از آن رد می‌شود.

    این‌جا **خودِ** تابع صدا زده می‌شود، نه از راهِ کلاینتِ تست: فیکسچرِ کلاینت
    `get_principal` را override می‌کند، پس تستِ HTTP اصلاً به این گارد نمی‌رسید و
    سبز می‌ماند حتی اگر گارد را برداریم.
    """
    from fastapi import HTTPException
    from fastapi.security import HTTPAuthorizationCredentials

    from app.deps import get_principal as real_get_principal
    from app.security import create_access_token

    membership = _membership(db, engaged)
    token = create_access_token(auditor_user, membership.tenant_id)
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    #: پیش از انقضا کار می‌کند…
    principal = real_get_principal(credentials=creds, db=db)
    assert principal.tenant_id == membership.tenant_id

    membership.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.flush()

    with pytest.raises(HTTPException) as err:
        real_get_principal(credentials=creds, db=db)
    assert err.value.status_code == 403
    assert "مهلت" in err.value.detail


def test_expired_membership_disappears_from_the_switcher(engaged, db, auditor_user):
    from app.routers.auth import _active_memberships

    membership = _membership(db, engaged)
    assert any(m.id == membership.id for m in _active_memberships(db, auditor_user))

    membership.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.flush()
    assert not any(m.id == membership.id for m in _active_memberships(db, auditor_user))


def test_close_engagement_disables_the_membership(engaged, super_client, db):
    super_client.post(f"/api/admin/assurance/{engaged.id}/close", json={"note": "تمام"})
    db.refresh(engaged)
    assert _membership(db, engaged).status == "disabled"


def test_assign_disables_the_previous_auditor(engaged, super_client, db):
    second = User(
        name="حسابرسِ دوم",
        email="second-auditor@cubita.invalid",
        hashed_password=hash_password("SecondAuditor!2026"),
        active=True,
    )
    db.add(second)
    db.flush()

    first_membership_id = engaged.auditor_membership_id
    r = super_client.post(
        f"/api/admin/assurance/{engaged.id}/assign",
        json={"auditor_email": second.email},
    )
    assert r.status_code == 200, r.text
    db.refresh(engaged)
    assert engaged.auditor_membership_id != first_membership_id
    assert db.get(Membership, first_membership_id).status == "disabled"


# ── مالکِ مشتری نمی‌تواند دامنه‌ی حسابرس را عوض کند ───────────────────────────


def test_owner_cannot_widen_auditor_permissions(engaged, client, db):
    membership = _membership(db, engaged)
    r = client.patch(
        f"/api/members/{membership.id}/permissions",
        json={"permissions": {"accounting": ["view", "create", "update", "delete"]}},
    )
    assert r.status_code == 409, r.text


def test_owner_cannot_change_the_auditor_role(engaged, client, db):
    membership = _membership(db, engaged)
    r = client.patch(f"/api/members/{membership.id}/role", json={"role_key": "owner"})
    assert r.status_code == 409, r.text


def test_owner_can_still_disable_the_auditor(engaged, client, db):
    """دفتر مالِ مشتری است؛ باید بتواند هر کسی — از جمله ما — را بیرون بگذارد."""
    membership = _membership(db, engaged)
    r = client.patch(f"/api/members/{membership.id}/status", json={"active": False})
    assert r.status_code == 200, r.text
    db.refresh(membership)
    assert membership.status == "disabled"
