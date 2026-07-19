"""مدیریت کاربران یک کسب‌وکار: دعوت، پذیرش، نقش، غیرفعال‌سازی.

دو تست این پرونده از بقیه مهم‌ترند و هیچ‌کدام درباره‌ی «کار کردن» قابلیت نیستند:

- `test_member_list_never_shows_another_business` — چون `memberships` و `users`
  جدول سراسری‌اند و RLS ندارند، تنها چیزی که فهرست کاربران را به یک کسب‌وکار محدود
  می‌کند یک فیلتر دستی در کد است. حذف آن فیلتر هیچ تستی جز این یکی را قرمز نمی‌کند،
  و نتیجه‌اش همان شکل نشتی است که قبلاً در پنل صورتحساب رخ داد.

- `test_last_active_owner_cannot_be_*` — کسب‌وکاری که مالک فعال ندارد فقط با
  دسترسی مستقیم به دیتابیس قابل نجات است.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models.tenant import Membership, Tenant
from app.models.user import Role, User
from app.security import create_access_token
from app.services.provisioning import signup_new_business

PASSWORD = "AStrongPassword2026"


def new_business(db, name="کسب‌وکار تست", max_users=None):
    tenant, owner = signup_new_business(
        db,
        business_name=name,
        owner_name="مالک",
        email=f"own-{uuid.uuid4().hex[:8]}@cubita-test.ir",
        password=PASSWORD,
    )
    if max_users is not None:
        tenant.max_users = max_users
    db.flush()
    return tenant, owner


def authed(db, user, tenant_id) -> TestClient:
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {create_access_token(user, tenant_id)}"})
    return client


@pytest.fixture(autouse=True)
def _clean_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def sent_invites(monkeypatch):
    """توکن دعوت را می‌قاپد — تنها لحظه‌ای که مقدار خام وجود دارد."""
    captured: list[dict] = []

    def fake_send(*, to, tenant_name, inviter_name, token, valid_days):
        captured.append({"to": to, "token": token, "tenant_name": tenant_name})
        return True

    monkeypatch.setattr("app.routers.members.send_invitation", fake_send)
    return captured


@pytest.fixture
def business(db):
    return new_business(db, "شرکت الف")


# --- مجوز -------------------------------------------------------------------------


def test_owner_can_list_members(db, business):
    tenant, owner = business
    res = authed(db, owner, tenant.id).get("/api/members")
    assert res.status_code == 200, res.text[:300]
    assert len(res.json()["members"]) == 1
    assert res.json()["members"][0]["is_me"] is True


def test_accountant_cannot_manage_members(db, business, sent_invites):
    """مدیریت کاربر یعنی دادن دسترسی به دفتر مالی — نباید به نقش‌های عملیاتی برسد."""
    tenant, owner = business
    accountant_role = db.query(Role).filter(Role.tenant_id == tenant.id, Role.key == "accountant").one()
    other = User(
        name="حسابدار", email=f"acc-{uuid.uuid4().hex[:8]}@cubita-test.ir", hashed_password="x"
    )
    db.add(other)
    db.flush()
    db.add(Membership(user_id=other.id, tenant_id=tenant.id, role_id=accountant_role.id, status="active"))
    db.flush()

    client = authed(db, other, tenant.id)
    assert client.get("/api/members").status_code == 403
    assert (
        client.post(
            "/api/members/invite",
            json={"email": "x@cubita-test.ir", "name": "کسی", "role_key": "salesperson"},
        ).status_code
        == 403
    )


# --- نشتی بین کسب‌وکارها ------------------------------------------------------------


def test_member_list_never_shows_another_business(db, business):
    """`memberships` سراسری است و RLS ندارد — فیلتر مستأجر فقط در کد وجود دارد.

    اگر آن فیلتر برداشته شود هیچ تست دیگری قرمز نمی‌شود، ولی مالک هر کسب‌وکار
    فهرست نام و ایمیل کاربران همه‌ی مشتری‌ها را می‌بیند.
    """
    tenant_a, owner_a = business
    tenant_b, owner_b = new_business(db, "شرکت ب")

    res = authed(db, owner_a, tenant_a.id).get("/api/members")
    assert res.status_code == 200, res.text[:300]

    emails = {m["email"] for m in res.json()["members"]}
    assert owner_a.email in emails
    assert owner_b.email not in emails, "کاربر کسب‌وکار دیگر در فهرست ظاهر شد — نشت بین مستأجرها"


def test_cannot_touch_a_membership_of_another_business(db, business):
    tenant_a, owner_a = business
    tenant_b, owner_b = new_business(db, "شرکت ب")
    foreign = db.query(Membership).filter(Membership.tenant_id == tenant_b.id).first()

    client = authed(db, owner_a, tenant_a.id)
    res = client.patch(f"/api/members/{foreign.id}/role", json={"role_key": "salesperson"})
    # ۴۰۴ و نه ۴۰۳: تفکیک این دو به مهاجم می‌گوید کدام شناسه‌ها واقعی‌اند
    assert res.status_code == 404, f"عضویت کسب‌وکار دیگر قابل تغییر بود: {res.status_code}"


# --- دعوت و پذیرش -------------------------------------------------------------------


def test_invite_then_accept_gives_a_working_second_user(db, business, sent_invites):
    """چرخه‌ی کامل — همان چیزی که تا امروز اصلاً وجود نداشت."""
    tenant, owner = business
    email = f"invitee-{uuid.uuid4().hex[:8]}@cubita-test.ir"

    res = authed(db, owner, tenant.id).post(
        "/api/members/invite",
        json={"email": email, "name": "همکار تازه", "role_key": "accountant"},
    )
    assert res.status_code == 201, res.text[:300]
    assert res.json()["member"]["status"] == "invited"
    assert res.json()["email_sent"] is True
    assert len(sent_invites) == 1 and sent_invites[0]["to"] == email

    anon = TestClient(app)
    accepted = anon.post(
        "/api/auth/accept-invite",
        json={"token": sent_invites[0]["token"], "password": PASSWORD},
    )
    assert accepted.status_code == 200, accepted.text[:300]

    invited = TestClient(app)
    invited.headers.update({"Authorization": f"Bearer {accepted.json()['access_token']}"})
    me = invited.get("/api/auth/me")
    assert me.status_code == 200, me.text[:300]
    assert me.json()["role_key"] == "accountant"
    assert me.json()["tenant_id"] == str(tenant.id)


def test_invited_user_has_no_access_before_accepting(db, business, sent_invites):
    """عضویت «invited» نباید دسترسی بدهد، وگرنه دعوت خودش یک در باز است."""
    tenant, owner = business
    email = f"pending-{uuid.uuid4().hex[:8]}@cubita-test.ir"
    authed(db, owner, tenant.id).post(
        "/api/members/invite", json={"email": email, "name": "منتظر", "role_key": "accountant"}
    )

    pending = db.query(User).filter(User.email == email).one()
    res = authed(db, pending, tenant.id).get("/api/auth/me")
    assert res.status_code == 403, f"کاربر دعوت‌شده قبل از پذیرش دسترسی گرفت: {res.status_code}"


def test_invite_link_works_only_once(db, business, sent_invites):
    tenant, owner = business
    authed(db, owner, tenant.id).post(
        "/api/members/invite",
        json={"email": f"once-{uuid.uuid4().hex[:8]}@cubita-test.ir", "name": "یکبار", "role_key": "accountant"},
    )
    token = sent_invites[0]["token"]

    anon = TestClient(app)
    assert anon.post("/api/auth/accept-invite", json={"token": token, "password": PASSWORD}).status_code == 200
    second = anon.post("/api/auth/accept-invite", json={"token": token, "password": "AnotherPassword2026"})
    assert second.status_code == 400, "لینک دعوت بار دوم هم کار کرد"


def test_inviting_an_existing_user_does_not_touch_their_account(db, business, sent_invites):
    """حسابدار مستقلی که عضو کسب‌وکار دیگری است.

    دعوت کردن کسی نباید به دعوت‌کننده اجازه دهد نام یا رمز حساب او را — که در
    کسب‌وکارهای دیگر هم استفاده می‌شود — عوض کند.
    """
    tenant_a, owner_a = business
    tenant_b, owner_b = new_business(db, "شرکت ب")
    original_name, original_hash = owner_b.name, owner_b.hashed_password

    res = authed(db, owner_a, tenant_a.id).post(
        "/api/members/invite",
        json={"email": owner_b.email, "name": "نام تحمیلی", "role_key": "accountant"},
    )
    assert res.status_code == 201, res.text[:300]

    db.refresh(owner_b)
    assert owner_b.name == original_name, "نام کاربر موجود توسط دعوت‌کننده عوض شد"
    assert owner_b.hashed_password == original_hash, "رمز کاربر موجود توسط دعوت‌کننده عوض شد"


def test_inviting_an_existing_member_is_rejected(db, business, sent_invites):
    tenant, owner = business
    res = authed(db, owner, tenant.id).post(
        "/api/members/invite", json={"email": owner.email, "name": "خودش", "role_key": "accountant"}
    )
    assert res.status_code == 409


def test_unknown_role_is_rejected(db, business, sent_invites):
    tenant, owner = business
    res = authed(db, owner, tenant.id).post(
        "/api/members/invite",
        json={"email": f"r-{uuid.uuid4().hex[:6]}@cubita-test.ir", "name": "کسی", "role_key": "superadmin"},
    )
    assert res.status_code == 400


# --- سقف کاربران ---------------------------------------------------------------------


def test_seat_limit_is_enforced(db, sent_invites):
    """`Plan.max_users` تعریف شده بود ولی هیچ‌جا خوانده نمی‌شد.

    یعنی پلن «پایه» با یک کاربر فروخته می‌شد و خریدارش می‌توانست بی‌نهایت کاربر
    اضافه کند.
    """
    tenant, owner = new_business(db, "شرکت محدود", max_users=2)
    client = authed(db, owner, tenant.id)

    first = client.post(
        "/api/members/invite",
        json={"email": f"s1-{uuid.uuid4().hex[:6]}@cubita-test.ir", "name": "یک", "role_key": "accountant"},
    )
    assert first.status_code == 201, first.text[:300]

    second = client.post(
        "/api/members/invite",
        json={"email": f"s2-{uuid.uuid4().hex[:6]}@cubita-test.ir", "name": "دو", "role_key": "accountant"},
    )
    assert second.status_code == 409, "سقف کاربران اعمال نشد"
    assert "سقف" in second.json()["detail"]


def test_disabling_a_member_frees_a_seat(db, sent_invites):
    """کاربر غیرفعال نباید صندلی اشغال کند — ردیفش فقط برای تاریخچه می‌ماند."""
    tenant, owner = new_business(db, "شرکت محدود", max_users=2)
    client = authed(db, owner, tenant.id)

    invited = client.post(
        "/api/members/invite",
        json={"email": f"f1-{uuid.uuid4().hex[:6]}@cubita-test.ir", "name": "یک", "role_key": "accountant"},
    ).json()["member"]

    assert client.patch(f"/api/members/{invited['id']}/status", json={"active": False}).status_code == 200

    again = client.post(
        "/api/members/invite",
        json={"email": f"f2-{uuid.uuid4().hex[:6]}@cubita-test.ir", "name": "دو", "role_key": "accountant"},
    )
    assert again.status_code == 201, f"صندلی بعد از غیرفعال‌سازی آزاد نشد: {again.text[:200]}"


def test_unlimited_plan_has_no_seat_limit(db, sent_invites):
    tenant, owner = new_business(db, "شرکت سازمانی")
    tenant.max_users = None
    db.flush()
    client = authed(db, owner, tenant.id)

    for i in range(4):
        res = client.post(
            "/api/members/invite",
            json={"email": f"u{i}-{uuid.uuid4().hex[:6]}@cubita-test.ir", "name": f"کاربر {i}", "role_key": "salesperson"},
        )
        assert res.status_code == 201, f"دعوت {i} روی پلن نامحدود رد شد: {res.text[:200]}"


# --- محافظت در برابر قفل شدن ----------------------------------------------------------


def test_last_active_owner_cannot_be_demoted(db, business):
    tenant, owner = business
    membership = db.query(Membership).filter(
        Membership.tenant_id == tenant.id, Membership.user_id == owner.id
    ).one()

    res = authed(db, owner, tenant.id).patch(
        f"/api/members/{membership.id}/role", json={"role_key": "salesperson"}
    )
    assert res.status_code == 409, "آخرین مالک تنزل داده شد — کسب‌وکار بدون مدیر می‌ماند"


def test_a_second_owner_can_be_disabled(db, business, sent_invites):
    """گارد نباید بیش از لازم سخت‌گیر باشد: تا وقتی مالک دیگری فعال است، مجاز است."""
    tenant, owner = business
    client = authed(db, owner, tenant.id)
    second = client.post(
        "/api/members/invite",
        json={"email": f"co-{uuid.uuid4().hex[:8]}@cubita-test.ir", "name": "مالک دوم", "role_key": "owner"},
    ).json()["member"]
    TestClient(app).post(
        "/api/auth/accept-invite", json={"token": sent_invites[0]["token"], "password": PASSWORD}
    )

    res = client.patch(f"/api/members/{second['id']}/status", json={"active": False})
    assert res.status_code == 200, f"غیرفعال کردن مالک دوم رد شد: {res.text[:200]}"


def test_a_non_owner_manager_cannot_disable_the_last_owner(db, business):
    """گاردِ آخرین مالک روی مسیر غیرفعال‌سازی، دفاع در برابر نقش‌های *آینده* است.

    امروز فقط «مالک» مجوز `users` دارد، و مالکی که بخواهد تنها مالکِ فعال را
    غیرفعال کند خودش است — یعنی اول به گاردِ «خودتان را قطع نکنید» می‌خورد. پس این
    گارد با نقش‌های پیش‌فرض غیرقابل‌دسترس است.

    ولی `permissions` یک JSONB آزاد است و اولین نقش سفارشی‌ای که `users` بگیرد این
    مسیر را باز می‌کند: یک «مدیر دفتر» می‌تواند تنها مالک را غیرفعال کند و کسب‌وکار
    را بدون هیچ‌کسی بگذارد که بتواند برش گرداند. تست همان نقش را می‌سازد تا گارد
    واقعاً سنجیده شود و به‌عنوان کد مرده حذف نشود.
    """
    tenant, owner = business
    manager_role = Role(
        tenant_id=tenant.id,
        key="office_manager",
        name="مدیر دفتر",
        permissions={"users": ["view", "update"]},
    )
    db.add(manager_role)
    db.flush()

    manager = User(
        name="مدیر دفتر", email=f"mgr-{uuid.uuid4().hex[:8]}@cubita-test.ir", hashed_password="x"
    )
    db.add(manager)
    db.flush()
    db.add(Membership(user_id=manager.id, tenant_id=tenant.id, role_id=manager_role.id, status="active"))
    db.flush()

    owner_membership = db.query(Membership).filter(
        Membership.tenant_id == tenant.id, Membership.user_id == owner.id
    ).one()

    res = authed(db, manager, tenant.id).patch(
        f"/api/members/{owner_membership.id}/status", json={"active": False}
    )
    assert res.status_code == 409, "آخرین مالکِ فعال غیرفعال شد — کسب‌وکار بدون مدیر ماند"


def test_you_cannot_disable_yourself(db, business):
    tenant, owner = business
    membership = db.query(Membership).filter(
        Membership.tenant_id == tenant.id, Membership.user_id == owner.id
    ).one()

    res = authed(db, owner, tenant.id).patch(
        f"/api/members/{membership.id}/status", json={"active": False}
    )
    assert res.status_code == 409


def test_a_disabled_member_loses_access_immediately(db, business, sent_invites):
    """غیرفعال‌سازی باید فوری اثر کند، نه بعد از انقضای توکن.

    عضویت در هر درخواست از دیتابیس خوانده می‌شود؛ اگر روزی کسی برای «بهینه‌سازی»
    آن را داخل توکن کش کند، اخراج کارمند تا ۸ ساعت بی‌اثر می‌شود.
    """
    tenant, owner = business
    email = f"fired-{uuid.uuid4().hex[:8]}@cubita-test.ir"
    client = authed(db, owner, tenant.id)
    member = client.post(
        "/api/members/invite", json={"email": email, "name": "کارمند", "role_key": "salesperson"}
    ).json()["member"]
    TestClient(app).post(
        "/api/auth/accept-invite", json={"token": sent_invites[0]["token"], "password": PASSWORD}
    )

    fired_user = db.query(User).filter(User.email == email).one()
    assert authed(db, fired_user, tenant.id).get("/api/auth/me").status_code == 200

    assert client.patch(f"/api/members/{member['id']}/status", json={"active": False}).status_code == 200
    after = authed(db, fired_user, tenant.id).get("/api/auth/me")
    assert after.status_code == 403, f"کاربر غیرفعال‌شده هنوز دسترسی دارد: {after.status_code}"
