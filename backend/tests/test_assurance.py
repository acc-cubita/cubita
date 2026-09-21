"""حسابرسی — چرخه‌ی قرارداد، گیتِ زیرمنوها، اجرا و کارتابلِ ستاد.

قیدهایی که این فایل نگه می‌دارد:

* پیش از تأییدِ ما، هیچ مسیرِ کاری‌ای باز نیست — **و پنهان‌بودنِ منو اثباتش
  نمی‌کند**، فقط ۴۰۳ِ سرور اثباتش می‌کند.
* جابه‌جاکردنِ گرنتِ یک ماژولِ دیگر (که فهرست را یک‌جا جایگزین می‌کند) نباید
  دسترسیِ حسابرسی را ببرد.
* قرارداد جدولی **سراسری** است، پس هر مشتری فقط قراردادِ خودش را می‌بیند.
"""
import uuid
from datetime import date, datetime, timezone

import pytest

from app.config import get_settings
from app.models.assurance import AssuranceEngagement
from app.models.tenant import Tenant
from app.models.user import User
from app.security import hash_password

OWNER = "test-owner@example.invalid"  # = SEED_OWNER_EMAIL

#: همه‌ی مسیرهایی که باید پشتِ گیت باشند. پارامتری‌اند تا مسیرِ تازه‌ای که کسی
#: فردا اضافه کند و یادش برود گیت بگذارد، این‌جا دیده شود.
WORK_PATHS = [
    "/api/assurance/runs",
    "/api/assurance/runs/latest",
    f"/api/assurance/runs/{uuid.uuid4()}",
    f"/api/assurance/runs/{uuid.uuid4()}/findings",
]

AUDITOR_EMAIL = "auditor@cubita.invalid"


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


def _seed_foreign_engagement(db, name: str, *, status: str) -> Tenant:
    """قراردادی برای مستأجرِ دیگر، **درونِ زمینه‌ی همان مستأجر**.

    بیرونِ زمینه‌اش، هوکِ ردِ حسابرسی ردیفی با `tenant_id`ِ دیگری می‌نویسد و
    سیاستِ `WITH CHECK`ِ `audit_log` ردش می‌کند — همان تله‌ای که روترِ ستاد با
    `tenant_scope` از آن عبور می‌کند. اگر فیکسچر همان کار را نکند، تست به‌جای
    سنجیدنِ نشتی، روی ستون‌بندی می‌شکند.
    """
    from app.models.user import User
    from app.tenant_context import (
        apply_tenant_to_transaction,
        bind_session_tenant,
        session_tenant,
        tenant_scope,
    )

    other = Tenant(name=name, slug=f"other-{uuid.uuid4().hex[:8]}")
    db.add(other)
    db.flush()
    owner = db.query(User).filter(User.email == OWNER).one()
    #: `tenant_scope` هنگامِ خروج فقط ContextVar را برمی‌گرداند، نه زمینه‌ی خودِ
    #: تراکنش — به همین دلیل روترِ ستاد هم دستی بازمی‌گرداند. بدونِ این، بقیه‌ی
    #: تست در زمینه‌ی مستأجرِ دوم اجرا می‌شد.
    home = session_tenant(db)
    try:
        with tenant_scope(db, other.id):
            db.add(
                AssuranceEngagement(
                    tenant_id=other.id,
                    status=status,
                    requested_at=datetime.now(timezone.utc),
                    requested_by_id=owner.id,
                )
            )
            db.flush()
    finally:
        bind_session_tenant(db, home)
        apply_tenant_to_transaction(db, home)
    return other


def _request(client, **kwargs):
    body = {"period_from": "2026-01-01", "period_to": "2026-06-31"[:10], "contact_phone": "09120000000"}
    body.update(kwargs)
    body.setdefault("period_to", "2026-06-30")
    return client.post("/api/assurance/request", json=body)


# ── چرخه‌ی قرارداد ───────────────────────────────────────────────────────────


def test_request_creates_engagement_in_requested_status(client):
    r = _request(client, period_to="2026-06-30")
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "requested"
    assert client.get("/api/assurance/engagement").json()["status"] == "requested"


def test_engagement_is_null_before_any_request(client):
    """نبودنِ قرارداد حالتِ عادیِ هر حسابِ تازه است، نه خطا."""
    r = client.get("/api/assurance/engagement")
    assert r.status_code == 200
    assert r.json() is None


def test_second_open_request_is_conflict(client):
    _request(client, period_to="2026-06-30")
    r = _request(client, period_to="2026-06-30")
    assert r.status_code == 409, r.text


def test_reversed_period_is_rejected(client):
    r = _request(client, period_from="2026-06-30", period_to="2026-01-01")
    assert r.status_code == 400, r.text


def test_request_after_rejection_creates_a_new_row(client, super_client, db):
    first = _request(client, period_to="2026-06-30").json()
    super_client.post(f"/api/admin/assurance/{first['id']}/reject", json={"reason": "مدارک ناقص"})

    second = _request(client, period_to="2026-06-30")
    assert second.status_code == 201, second.text
    assert second.json()["id"] != first["id"]
    #: تاریخچه‌ی «یک بار رد شدیم» باید بماند — بازگشت به requested نداریم.
    assert db.query(AssuranceEngagement).count() == 2


def test_illegal_transition_is_conflict(client, super_client, auditor_user):
    engagement = _request(client, period_to="2026-06-30").json()
    super_client.post(f"/api/admin/assurance/{engagement['id']}/reject", json={"reason": "نه"})
    r = super_client.post(
        f"/api/admin/assurance/{engagement['id']}/approve",
        json={"auditor_email": AUDITOR_EMAIL, "days": 30},
    )
    assert r.status_code == 409, r.text


def test_close_is_terminal(client, super_client, auditor_user):
    engagement = _request(client, period_to="2026-06-30").json()
    super_client.post(
        f"/api/admin/assurance/{engagement['id']}/approve",
        json={"auditor_email": AUDITOR_EMAIL, "days": 30},
    )
    assert super_client.post(
        f"/api/admin/assurance/{engagement['id']}/close", json={"note": "تمام"}
    ).status_code == 200
    r = super_client.post(f"/api/admin/assurance/{engagement['id']}/close", json={"note": "دوباره"})
    assert r.status_code == 409


# ── گیتِ زیرمنوها ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("path", WORK_PATHS)
def test_work_endpoints_forbidden_before_approval(client, path):
    """**هسته‌ی این ماژول.** پیش از تأیید، سرور بسته است — نه فقط منو."""
    _request(client, period_to="2026-06-30")
    r = client.get(path)
    assert r.status_code == 403, f"{path} → {r.status_code}"
    assert "فعال نیست" in r.json()["detail"]


def test_request_endpoints_stay_open_before_approval(client):
    assert client.get("/api/assurance/engagement").status_code == 200
    assert _request(client, period_to="2026-06-30").status_code == 201


def test_work_endpoints_open_after_approval(client, super_client, auditor_user):
    engagement = _request(client, period_to="2026-06-30").json()
    super_client.post(
        f"/api/admin/assurance/{engagement['id']}/approve",
        json={"auditor_email": AUDITOR_EMAIL, "days": 30},
    )
    assert client.get("/api/assurance/runs").status_code == 200
    assert client.get("/api/assurance/runs/latest").status_code == 200


def test_work_endpoints_close_again_after_engagement_closed(client, super_client, auditor_user):
    engagement = _request(client, period_to="2026-06-30").json()
    super_client.post(
        f"/api/admin/assurance/{engagement['id']}/approve",
        json={"auditor_email": AUDITOR_EMAIL, "days": 30},
    )
    super_client.post(f"/api/admin/assurance/{engagement['id']}/close", json={"note": ""})
    assert client.get("/api/assurance/runs").status_code == 403


def test_me_reports_assurance_work_only_when_active(client, super_client, auditor_user):
    before = client.get("/api/auth/me").json()
    assert "assurance" in before["allowed_modules"]
    assert "assurance_work" not in before["allowed_modules"]

    engagement = _request(client, period_to="2026-06-30").json()
    super_client.post(
        f"/api/admin/assurance/{engagement['id']}/approve",
        json={"auditor_email": AUDITOR_EMAIL, "days": 30},
    )
    after = client.get("/api/auth/me").json()
    assert "assurance_work" in after["allowed_modules"]
    assert "assurance_work" in after["enabled_modules"]


def test_super_admin_toggling_another_module_does_not_revoke_assurance(
    client, super_client, auditor_user, db, tenant_id
):
    """رگرسیونِ اصلیِ طراحی.

    `set_grants` کلِ فهرست را جایگزین می‌کند. اگر دسترسیِ حسابرسی هم گرنت بود،
    همین یک فراخوان پاکش می‌کرد و هیچ‌کس نمی‌فهمید تا وقتی مشتری زنگ بزند.
    """
    engagement = _request(client, period_to="2026-06-30").json()
    super_client.post(
        f"/api/admin/assurance/{engagement['id']}/approve",
        json={"auditor_email": AUDITOR_EMAIL, "days": 30},
    )
    assert client.get("/api/assurance/runs").status_code == 200

    super_client.post(f"/api/admin/accounts/{tenant_id}/modules", json={"granted": ["manufacturing"]})

    assert client.get("/api/assurance/runs").status_code == 200
    assert "assurance_work" in client.get("/api/auth/me").json()["allowed_modules"]


def test_industry_change_keeps_assurance_visible(client, super_client, tenant_id):
    """`set_industry` نمایش را بازنشانی می‌کند؛ «حسابرسی» باید در هر پنج قالب باشد."""
    for industry in ("general", "manufacturing", "retail", "services", "distribution"):
        super_client.post(f"/api/admin/accounts/{tenant_id}/industry", json={"industry": industry})
        assert "assurance" in client.get("/api/auth/me").json()["enabled_modules"], industry


# ── نشتیِ جدولِ سراسری ───────────────────────────────────────────────────────


def test_client_reads_only_own_engagement(client, db, tenant_id):
    """`assurance_engagements` سیاستِ RLS ندارد؛ فیلتر دستِ روتر است.

    اگر آن فیلتر یک روز جا بیفتد، قرارداد و نامِ حسابرس و نمره‌ی مشتریِ دیگری
    لو می‌رود. این تست همان را می‌پاید.
    """
    _seed_foreign_engagement(db, "کسب‌وکار دیگر", status="active")

    assert client.get("/api/assurance/engagement").json() is None
    #: و پس از ساختِ قراردادِ خودش، همچنان فقط مالِ خودش.
    mine = _request(client, period_to="2026-06-30").json()
    seen = client.get("/api/assurance/engagement").json()
    assert seen["id"] == mine["id"]
    assert seen["tenant_id"] == str(tenant_id)


# ── کارتابلِ ستاد ────────────────────────────────────────────────────────────


def test_admin_gate_blocks_everyone_but_staff(client, db, user):
    """کارتابل فقط با هویتِ ستاد باز می‌شود.

    دو مسیرِ شکست جداست و هر دو باید بسته باشند: بی‌توکن ۴۰۱، و با توکنِ
    مستأجریِ یک کاربرِ عادی ۴۰۱/۴۰۳ (پلِ سازگاری فقط ایمیل‌های روی allowlist را
    رد می‌کند، نه هر توکنِ معتبری).
    """
    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.main import app
    from app.security import create_access_token

    assert client.get("/api/admin/assurance").status_code == 401

    app.dependency_overrides[get_db] = lambda: db
    raw = TestClient(app)
    raw.headers.update({"Authorization": f"Bearer {create_access_token(user)}"})
    assert raw.get("/api/admin/assurance").status_code in (401, 403)


def test_admin_list_spans_tenants(client, super_client, db):
    _request(client, period_to="2026-06-30")
    _seed_foreign_engagement(db, "کسب‌وکار سوم", status="requested")

    rows = super_client.get("/api/admin/assurance").json()
    assert len({row["tenant_id"] for row in rows}) == 2


def test_approve_requires_an_existing_auditor_user(client, super_client):
    engagement = _request(client, period_to="2026-06-30").json()
    r = super_client.post(
        f"/api/admin/assurance/{engagement['id']}/approve",
        json={"auditor_email": "nobody@nowhere.invalid", "days": 30},
    )
    assert r.status_code == 404, r.text


def test_same_auditor_can_take_the_next_years_engagement(client, super_client, auditor_user, db):
    """بستنِ پرونده عضویت را **غیرفعال** می‌کند نه حذف؛ پرونده‌ی سالِ بعد نباید
    به همین دلیل رد شود."""
    first = _request(client, period_to="2026-06-30").json()
    super_client.post(
        f"/api/admin/assurance/{first['id']}/approve",
        json={"auditor_email": AUDITOR_EMAIL, "days": 30},
    )
    super_client.post(f"/api/admin/assurance/{first['id']}/close", json={"note": ""})

    second = _request(client, period_from="2027-01-01", period_to="2027-06-30").json()
    r = super_client.post(
        f"/api/admin/assurance/{second['id']}/approve",
        json={"auditor_email": AUDITOR_EMAIL, "days": 30},
    )
    assert r.status_code == 200, r.text

    from app.models.tenant import Membership

    row = db.get(AssuranceEngagement, uuid.UUID(second["id"]))
    assert db.get(Membership, row.auditor_membership_id).status == "active"


def test_approve_rejects_an_existing_member_of_the_same_tenant(client, super_client):
    """تبدیلِ بی‌صدای حسابدارِ خودِ مشتری به «حسابرس» هم دروغ است هم قطعِ دسترسی."""
    engagement = _request(client, period_to="2026-06-30").json()
    r = super_client.post(
        f"/api/admin/assurance/{engagement['id']}/approve",
        json={"auditor_email": OWNER, "days": 30},
    )
    assert r.status_code == 409, r.text


# ── اجرا ─────────────────────────────────────────────────────────────────────


def test_approval_creates_the_first_run(client, super_client, auditor_user):
    engagement = _request(client, period_from="2026-01-01", period_to="2026-06-30").json()
    approved = super_client.post(
        f"/api/admin/assurance/{engagement['id']}/approve",
        json={"auditor_email": AUDITOR_EMAIL, "days": 30},
    ).json()

    assert approved["status"] == "active", "اولین اجرا باید پرونده را به «در جریان» ببرد"
    assert approved["last_run_at"] is not None
    latest = client.get("/api/assurance/runs/latest").json()
    assert latest["trigger"] == "approval"
    assert latest["number"] == 1
    assert latest["summary"], "جدولِ توضیحِ نمره نباید خالی باشد"


def test_refresh_cooldown_is_conflict(client, super_client, auditor_user):
    engagement = _request(client, period_to="2026-06-30").json()
    super_client.post(
        f"/api/admin/assurance/{engagement['id']}/approve",
        json={"auditor_email": AUDITOR_EMAIL, "days": 30},
    )
    r = client.post("/api/assurance/runs")
    assert r.status_code == 409, r.text
    assert "دقیقه" in r.json()["detail"]


def test_snapshot_is_immutable_when_the_ledger_changes_afterwards(
    client, super_client, auditor_user, db
):
    """کلِ دلیلِ ذخیره‌کردنِ اجرا.

    گزارشِ حسابرس به وضعیتِ دفتر **در تاریخِ بررسی** استناد می‌کند. اگر مشتری
    فردا سند را عوض کند، آن گزارش نباید بی‌صدا عوض شود.
    """
    engagement = _request(client, period_from="2026-01-01", period_to="2026-12-29").json()
    super_client.post(
        f"/api/admin/assurance/{engagement['id']}/approve",
        json={"auditor_email": AUDITOR_EMAIL, "days": 30},
    )
    before = client.get("/api/assurance/runs/latest").json()

    from app.models.invoices import PurchaseInvoice
    owner = db.query(User).filter(User.email == OWNER).one()
    for offset in range(2):
        db.add(
            PurchaseInvoice(
                number=90_000 + offset,
                invoice_date=date(2026, 3, 1),
                supplier_invoice_number="DUP-1",
                total_amount=1_000_000,
                created_by_id=owner.id,
            )
        )
    db.flush()

    #: همان اجرا، بعد از تغییرِ دفتر — عددها باید همان باشند.
    again = client.get(f"/api/assurance/runs/{before['id']}").json()
    assert again["finding_count"] == before["finding_count"]
    assert again["score"] == before["score"]


def test_staff_run_lands_in_the_client_tenant_and_restores_context(
    client, super_client, auditor_user, db, tenant_id
):
    engagement = _request(client, period_to="2026-06-30").json()
    super_client.post(
        f"/api/admin/assurance/{engagement['id']}/approve",
        json={"auditor_email": AUDITOR_EMAIL, "days": 30},
    )
    r = super_client.post(f"/api/admin/assurance/{engagement['id']}/run")
    assert r.status_code == 200, r.text

    from app.models.assurance import AssuranceRun

    runs = db.query(AssuranceRun).all()
    assert len(runs) == 2
    assert {run.tenant_id for run in runs} == {tenant_id}
    #: زمینه باید به مستأجرِ ادمین برگشته باشد، وگرنه درخواستِ بعدی در زمینه‌ی
    #: مشتری اجرا می‌شد.
    assert client.get("/api/auth/me").json()["tenant_id"] == str(tenant_id)


def test_extend_updates_both_engagement_and_membership(client, super_client, auditor_user, db):
    engagement = _request(client, period_to="2026-06-30").json()
    approved = super_client.post(
        f"/api/admin/assurance/{engagement['id']}/approve",
        json={"auditor_email": AUDITOR_EMAIL, "days": 10},
    ).json()
    extended = super_client.post(
        f"/api/admin/assurance/{engagement['id']}/extend", json={"days": 30}
    ).json()
    assert extended["access_expires_at"] > approved["access_expires_at"]

    from app.models.tenant import Membership

    row = db.get(AssuranceEngagement, uuid.UUID(engagement["id"]))
    membership = db.get(Membership, row.auditor_membership_id)
    assert membership.expires_at == row.access_expires_at
