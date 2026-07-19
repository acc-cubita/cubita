"""ثبت‌نام self-serve و جابه‌جایی بین کسب‌وکارها.

مهم‌ترین تست این پرونده آن نیست که جابه‌جایی کار می‌کند، بلکه این است که
جابه‌جایی به کسب‌وکاری که کاربر عضوش نیست **کار نمی‌کند**. اگر آن بررسی نبود،
شناسه‌ی مستأجر داخل توکن چیزی جز یک مقدار تأمین‌شده توسط کلاینت نبود و کل
ایزوله‌سازی RLS بی‌اثر می‌شد — چون RLS به همان مقدار اعتماد می‌کند.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models.tenant import Membership, Tenant
from app.models.user import Role, User
from app.security import create_access_token
from app.services.provisioning import make_slug, signup_new_business


@pytest.fixture
def anon_client(db):
    """کلاینت بدون احراز هویت — برای مسیرهای عمومی مثل ثبت‌نام."""
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def authed(db, user, tenant_id) -> TestClient:
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {create_access_token(user.id, tenant_id)}"})
    return client


# --- ثبت‌نام --------------------------------------------------------------------


def test_signup_creates_a_working_business(anon_client, db):
    email = f"new-{uuid.uuid4().hex[:8]}@cubita-test.ir"
    res = anon_client.post(
        "/api/auth/signup",
        json={
            "business_name": "کسب‌وکار تازه",
            "owner_name": "مالک تازه",
            "email": email,
            "password": "AStrongPassword2026",
        },
    )
    assert res.status_code == 201, res.text[:300]
    token = res.json()["access_token"]

    # توکن باید بلافاصله قابل استفاده باشد — ثبت‌نامی که بعدش باید جدا لاگین کنی نصفه است
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {token}"})
    me = client.get("/api/auth/me")
    assert me.status_code == 200, me.text[:300]
    assert me.json()["role_key"] == "owner"
    assert me.json()["tenant_name"] == "کسب‌وکار تازه"


def test_signup_provisions_everything_needed_to_post(anon_client, db):
    """کسب‌وکار نیمه‌ساخته سالم به‌نظر می‌رسد و اولین فاکتور می‌شکند.

    شمارنده‌ی سند رایج‌ترین چیزی است که جا می‌ماند، چون تا لحظه‌ی ثبت لازم نمی‌شود.
    """
    from app.models.accounting import Account
    from app.models.counters import DOC_TYPES, DocumentCounter
    from app.models.inventory import Warehouse

    email = f"full-{uuid.uuid4().hex[:8]}@cubita-test.ir"
    tenant, _ = signup_new_business(
        db,
        business_name="کسب‌وکار کامل",
        owner_name="مالک",
        email=email,
        password="AStrongPassword2026",
    )
    db.flush()

    assert db.query(Account).filter(Account.tenant_id == tenant.id).count() > 20
    assert db.query(Warehouse).filter(Warehouse.tenant_id == tenant.id).count() == 2
    assert db.query(Role).filter(Role.tenant_id == tenant.id).count() == 6
    counters = db.query(DocumentCounter).filter(DocumentCounter.tenant_id == tenant.id).count()
    assert counters == len(DOC_TYPES), f"شمارنده‌ها ناقص‌اند: {counters} از {len(DOC_TYPES)}"


def test_duplicate_email_is_rejected_without_confirming_it_exists(anon_client, db):
    email = f"dup-{uuid.uuid4().hex[:8]}@cubita-test.ir"
    payload = {
        "business_name": "اولی",
        "owner_name": "مالک",
        "email": email,
        "password": "AStrongPassword2026",
    }
    assert anon_client.post("/api/auth/signup", json=payload).status_code == 201

    second = anon_client.post("/api/auth/signup", json={**payload, "business_name": "دومی"})
    assert second.status_code == 409
    # پیام نباید تأیید کند که ایمیل وجود دارد — وگرنه فهرست کاربران قابل استخراج است
    assert "وجود دارد" not in second.json()["detail"]


@pytest.mark.parametrize("password", ["short", "123456789"])
def test_weak_password_is_rejected(anon_client, password):
    res = anon_client.post(
        "/api/auth/signup",
        json={
            "business_name": "کسب‌وکار",
            "owner_name": "مالک",
            "email": f"weak-{uuid.uuid4().hex[:8]}@cubita-test.ir",
            "password": password,
        },
    )
    assert res.status_code == 422


def test_persian_business_name_still_produces_a_usable_slug(db):
    """نام‌ها فارسی‌اند و اسلاگ لاتین از آن‌ها درنمی‌آید — نباید خالی بماند."""
    slug = make_slug("فروشگاه لوازم خانگی پارس")
    assert slug, "اسلاگ خالی شد"
    assert len(slug) <= 60


def test_two_businesses_with_the_same_name_both_work(anon_client, db):
    name = "فروشگاه تکراری"
    for i in range(2):
        res = anon_client.post(
            "/api/auth/signup",
            json={
                "business_name": name,
                "owner_name": "مالک",
                "email": f"same-{i}-{uuid.uuid4().hex[:6]}@cubita-test.ir",
                "password": "AStrongPassword2026",
            },
        )
        assert res.status_code == 201, f"ثبت‌نام {i} شکست خورد: {res.text[:200]}"


# --- جابه‌جایی بین کسب‌وکارها ------------------------------------------------------


@pytest.fixture
def accountant_with_two_businesses(db):
    """حسابدار مستقلی که دفتر دو کسب‌وکار را می‌برد — الگوی رایج این بازار."""
    email = f"acc-{uuid.uuid4().hex[:8]}@cubita-test.ir"
    tenant_a, user = signup_new_business(
        db, business_name="مشتری الف", owner_name="حسابدار", email=email, password="AStrongPassword2026"
    )
    tenant_b = signup_new_business(
        db,
        business_name="مشتری ب",
        owner_name="مالک ب",
        email=f"other-{uuid.uuid4().hex[:6]}@cubita-test.ir",
        password="AStrongPassword2026",
    )[0]
    # حسابدار به کسب‌وکار دوم هم دعوت می‌شود
    role_b = db.query(Role).filter(Role.tenant_id == tenant_b.id, Role.key == "accountant").one()
    db.add(Membership(user_id=user.id, tenant_id=tenant_b.id, role_id=role_b.id, status="active"))
    db.flush()
    return user, tenant_a, tenant_b


def test_listing_shows_both_businesses(accountant_with_two_businesses, db):
    user, tenant_a, tenant_b = accountant_with_two_businesses
    res = authed(db, user, tenant_a.id).get("/api/auth/tenants")
    assert res.status_code == 200, res.text[:300]
    ids = {row["tenant_id"] for row in res.json()}
    assert {str(tenant_a.id), str(tenant_b.id)} <= ids
    current = [r for r in res.json() if r["is_current"]]
    assert len(current) == 1 and current[0]["tenant_id"] == str(tenant_a.id)


def test_switching_changes_which_ledger_is_visible(accountant_with_two_businesses, db):
    user, tenant_a, tenant_b = accountant_with_two_businesses
    client = authed(db, user, tenant_a.id)

    res = client.post("/api/auth/switch-tenant", json={"tenant_id": str(tenant_b.id)})
    assert res.status_code == 200, res.text[:300]

    switched = TestClient(app)
    switched.headers.update({"Authorization": f"Bearer {res.json()['access_token']}"})
    me = switched.get("/api/auth/me").json()
    assert me["tenant_id"] == str(tenant_b.id)
    assert me["role_key"] == "accountant", "نقش باید مالِ همان کسب‌وکار باشد، نه نقش کسب‌وکار قبلی"


def test_cannot_switch_into_a_business_you_do_not_belong_to(db, user, tenant_id):
    """مهم‌ترین تست این پرونده.

    اگر این بررسی نبود، هر کاربری می‌توانست شناسه‌ی هر مستأجری را بفرستد و توکنی
    بگیرد که RLS بی‌چون‌وچرا به آن اعتماد می‌کند — یعنی دسترسی کامل به دفتر یک
    کسب‌وکار بیگانه.
    """
    stranger = signup_new_business(
        db,
        business_name="کسب‌وکار بیگانه",
        owner_name="غریبه",
        email=f"stranger-{uuid.uuid4().hex[:6]}@cubita-test.ir",
        password="AStrongPassword2026",
    )[0]
    db.flush()

    res = authed(db, user, tenant_id).post("/api/auth/switch-tenant", json={"tenant_id": str(stranger.id)})
    assert res.status_code == 403, f"جابه‌جایی به کسب‌وکار بیگانه مجاز شد: {res.status_code}"


def test_cannot_switch_to_a_nonexistent_tenant(db, user, tenant_id):
    res = authed(db, user, tenant_id).post(
        "/api/auth/switch-tenant", json={"tenant_id": str(uuid.uuid4())}
    )
    assert res.status_code == 403


def test_a_forged_tenant_claim_in_the_token_is_rejected(db, user):
    """توکن دست‌ساز با tid دلخواه — همان حمله، از مسیر دیگر.

    ادعای مستأجر داخل JWT امضاشده است ولی محتوایش را ما تعیین می‌کنیم؛ اگر سرور
    آن را در برابر عضویت نسنجد، هر کسی که یک توکن معتبر دارد می‌تواند tid را عوض
    کند. اینجا با کلید واقعی توکن می‌سازیم تا دقیقاً همان حالت شبیه‌سازی شود.
    """
    foreign = signup_new_business(
        db,
        business_name="کسب‌وکار دیگر",
        owner_name="مالک",
        email=f"forge-{uuid.uuid4().hex[:6]}@cubita-test.ir",
        password="AStrongPassword2026",
    )[0]
    db.flush()

    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        client.headers.update({"Authorization": f"Bearer {create_access_token(user.id, foreign.id)}"})
        res = client.get("/api/auth/me")
        assert res.status_code == 403, f"توکن با مستأجر جعلی پذیرفته شد: {res.status_code}"
    finally:
        app.dependency_overrides.clear()
