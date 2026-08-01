"""حسابِ آزمایشیِ رایگانِ ۱۴روزه.

مدلِ یکپارچه: آزمایشی یک مستأجرِ عادی است با «اشتراکِ ۱۴روزه‌ی بدونِ پلن» و پرچمِ
`is_trial`. سه رفتار از این پرچم مشتق می‌شود و هر سه اینجا تست می‌شوند:

- مودیان و اتصال‌فروشگاه قفل‌اند (۴۰۲) — تا فرانت باکسِ «خرید پلن» را نشان دهد.
- بعد از انقضا کلِ دفتر قفل می‌شود (خواندن هم)، نه فقط‌خواندنی — سخت‌گیرانه‌تر از
  مشتریِ واقعی، چون داده‌ی آزمایشی سندِ قانونیِ کسی نیست.
- خرید همان مستأجر را سرِ جا به واقعی تبدیل می‌کند و دیتا حفظ می‌شود.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models.subscription import Subscription
from app.models.tenant import Tenant
from app.security import create_access_token
from app.services.provisioning import provision_for_purchase, signup_new_business

PASSWORD = "AStrongPassword2026"


@pytest.fixture(autouse=True)
def _clean_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def trial(db):
    tenant, user = signup_new_business(
        db,
        business_name="کسب‌وکار آزمایشی",
        owner_name="مالک",
        email=f"trial-{uuid.uuid4().hex[:8]}@cubita-test.ir",
        password=PASSWORD,
    )
    db.flush()
    return tenant, user


@pytest.fixture
def tclient(db, trial):
    tenant, user = trial
    app.dependency_overrides[get_db] = lambda: db
    c = TestClient(app)
    c.headers.update({"Authorization": f"Bearer {create_access_token(user, tenant.id)}"})
    return c


def _expire_trial(db, tenant_id):
    from datetime import datetime, timedelta, timezone

    sub = db.query(Subscription).filter(Subscription.tenant_id == tenant_id).one()
    sub.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    db.flush()


# --- ساختِ آزمایشی -------------------------------------------------------------------


def test_signup_creates_a_14_day_trial(trial, db):
    tenant, _ = trial
    assert tenant.is_trial is True
    sub = db.query(Subscription).filter(Subscription.tenant_id == tenant.id).one()
    assert sub.source == "trial"
    assert sub.plan_id is None, "آزمایشی نباید پلنی داشته باشد"
    days = (sub.expires_at.replace(tzinfo=sub.expires_at.tzinfo) - sub.starts_at.replace(tzinfo=sub.starts_at.tzinfo)).days
    assert days == 14


def test_me_exposes_trial_state(tclient):
    me = tclient.get("/api/auth/me").json()
    assert me["is_trial"] is True
    assert me["trial_expired"] is False
    assert 12 <= me["trial_days_left"] <= 14
    assert set(me["locked_features"]) == {"moadian", "storefront"}


# --- گیتِ قابلیت‌های فقط-پلن ----------------------------------------------------------


def test_trial_is_locked_out_of_moadian_and_storefront(tclient):
    for path in ("/api/moadian/settings", "/api/integration/settings"):
        res = tclient.get(path)
        assert res.status_code == 402, f"{path} برای آزمایشی باید ۴۰۲ بدهد، {res.status_code} داد"
        assert "آزمایشی" in res.json()["detail"]


def test_trial_can_use_normal_modules(tclient):
    # خواندن باز است
    assert tclient.get("/api/accounts").status_code == 200
    # و نوشتن هم (آزمایشیِ فعال) — یک انبارِ تازه
    res = tclient.post("/api/warehouses", json={"code": "TRIALWH", "name": "انبار آزمایشی"})
    assert res.status_code in (200, 201), f"نوشتن در آزمایشیِ فعال باید کار کند، {res.status_code} آمد"


# --- انقضا: قفلِ کامل ----------------------------------------------------------------


def test_expired_trial_is_fully_locked_even_for_reads(tclient, db, trial):
    tenant, _ = trial
    _expire_trial(db, tenant.id)
    # حتی خواندنِ دفتر بسته می‌شود — برخلافِ مشتریِ واقعیِ منقضی
    res = tclient.get("/api/accounts")
    assert res.status_code == 402, f"آزمایشیِ منقضی باید کاملاً قفل شود، {res.status_code} آمد"


def test_expired_trial_can_still_reach_the_buy_flow(tclient, db, trial):
    """/me و /subscription نباید قفل شوند، وگرنه کاربر حتی نمی‌تواند صفحه‌ی خرید را ببیند."""
    tenant, _ = trial
    _expire_trial(db, tenant.id)

    me = tclient.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["trial_expired"] is True

    assert tclient.get("/api/subscription").status_code == 200


# --- خرید = تبدیل به واقعی، دیتا حفظ می‌شود -------------------------------------------


def test_buying_exits_trial_unlocks_features_and_keeps_data(tclient, db, trial):
    tenant, user = trial

    # یک ردیفِ داده در آزمایشی می‌سازیم تا حفظ‌شدنش را بسنجیم
    tclient.post("/api/warehouses", json={"code": "KEEPME", "name": "بماند"})

    # شبیه‌سازیِ خریدِ تأییدشده با ایمیلِ همین مالک
    from app.models.billing import Plan, Purchase

    plan = db.query(Plan).filter(Plan.billing_period == "yearly").first()
    assert plan is not None, "پلن سالانه‌ای در seed نیست"
    purchase = Purchase(
        plan_id=plan.id, customer_name="مالک", customer_email=user.email,
        amount_toman=plan.price_toman, status="paid",
    )
    db.add(purchase)
    db.flush()
    provision_for_purchase(db, purchase)
    db.flush()

    # دیگر آزمایشی نیست
    assert db.get(Tenant, tenant.id).is_trial is False
    me = tclient.get("/api/auth/me").json()
    assert me["is_trial"] is False
    assert me["locked_features"] == []

    # قابلیتِ قفل‌شده حالا باز است (۴۰۲ نمی‌دهد)
    assert tclient.get("/api/moadian/settings").status_code != 402

    # و دیتای آزمایشی حفظ شده — همان انبار هنوز هست
    codes = [w["code"] for w in tclient.get("/api/warehouses").json()]
    assert "KEEPME" in codes, "دیتای آزمایشی بعد از خرید باید حفظ شود"
