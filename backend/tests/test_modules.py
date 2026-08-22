"""شخصی‌سازیِ پنل — حقِ دسترسی (entitlement) + نمایش (preference) + گیتِ بک‌اند."""
import pytest

from app.models.tenant import Membership, Tenant
from app.models.user import Role
from app.services import modules as svc


def _tenant(db, tenant_id) -> Tenant:
    return db.get(Tenant, tenant_id)


def test_default_state_hides_restricted_until_granted(client):
    """حسابِ تازه (enabled=NULL): همه‌ی اختیاری‌ها روشن، ولی «تولید» مجاز نیست → نمایش نمی‌شود."""
    r = client.get("/api/modules")
    assert r.status_code == 200, r.text
    s = r.json()
    assert s["industry"] == "general"
    # core همیشه روشن و مجاز
    for k in ("overview", "contacts", "reports"):
        assert k in s["enabled"] and k in s["allowed"]
    # تولید در رجیستری هست، اختیاری و محدود است
    assert "manufacturing" in s["optional"] and "manufacturing" in s["restricted"]
    # ترجیحِ پیش‌فرض روشنش می‌بیند، ولی «حقِ دسترسی» ندارد → نمایشِ نهایی خاموش
    assert "manufacturing" in s["enabled"]
    assert "manufacturing" not in s["allowed"]


def test_owner_can_toggle_visible_modules(client):
    r = client.put("/api/modules", json={"enabled": ["sales", "pos"]})
    assert r.status_code == 200, r.text
    s = r.json()
    assert "sales" in s["enabled"] and "pos" in s["enabled"]
    assert "crm" not in s["enabled"] and "banking" not in s["enabled"]
    # core جدا نگه داشته می‌شود
    assert "overview" in s["enabled"]
    # GET بعدی همان را می‌دهد (روی tenant ماندگار است)
    assert set(client.get("/api/modules").json()["enabled"]) == set(s["enabled"])


def test_owner_cannot_self_enable_restricted(client):
    """مالک نمی‌تواند از مسیرِ ترجیح، ماژولِ محدودِ گرنت‌نشده را روشن کند (fail-safe)."""
    r = client.put("/api/modules", json={"enabled": ["sales", "manufacturing"]})
    assert r.status_code == 200, r.text
    assert "manufacturing" not in r.json()["enabled"]


def test_non_owner_cannot_toggle(db, user):
    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.deps import Principal, get_current_user, get_principal
    from app.main import app

    membership = db.query(Membership).filter(Membership.user_id == user.id).one()
    non_owner = db.query(Role).filter(Role.key != "owner").first()
    membership.role = non_owner  # فقط برای همین تست؛ تراکنش در پایان برمی‌گردد
    principal = Principal(user, membership)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_principal] = lambda: principal
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        c = TestClient(app)
        assert c.put("/api/modules", json={"enabled": ["sales"]}).status_code == 403
        # ولی خواندنش برای هر عضو باز است
        assert c.get("/api/modules").status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_manufacturing_backend_gated_without_grant(client):
    """گیتِ سطحِ روتر: بدونِ گرنت، خودِ API هم بسته است (خواسته‌ی «ترکیبی»)."""
    assert client.post("/api/boms", json={}).status_code == 403
    assert client.get("/api/boms").status_code == 403


def test_grant_opens_manufacturing_backend(client, db, tenant_id):
    _tenant(db, tenant_id).granted_modules = ["manufacturing"]
    db.flush()
    # حالا گیت باز است (۴۰۳ نیست؛ ممکن است ۲۰۰/۴۲۲ بسته به بدنه باشد)
    assert client.get("/api/boms").status_code != 403


def test_set_industry_applies_template_and_grants(db, tenant_id):
    tenant = _tenant(db, tenant_id)
    svc.set_industry(tenant, "manufacturing")
    assert tenant.industry == "manufacturing"
    # قالبِ تولیدی → «تولید» هم روشن و هم گرنت‌شده (مجاز)
    assert "manufacturing" in tenant.enabled_modules
    assert "manufacturing" in svc.allowed_modules(tenant)
    # قالبِ تولیدی صندوق ندارد
    assert "pos" not in tenant.enabled_modules


def test_set_grants_only_restricted(db, tenant_id):
    tenant = _tenant(db, tenant_id)
    svc.set_grants(tenant, ["manufacturing", "sales", "nope"])
    # فقط کلیدهای محدودِ معتبر می‌مانند
    assert tenant.granted_modules == ["manufacturing"]


def test_invalid_industry_rejected():
    with pytest.raises(ValueError):
        svc.set_industry(object_with_defaults(), "not-a-real-industry")


class _FakeTenant:
    industry = "general"
    enabled_modules = None
    granted_modules: list = []


def object_with_defaults() -> _FakeTenant:
    return _FakeTenant()
