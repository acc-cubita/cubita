"""دو نسخه، یک کد — مرزِ «کوبیتا سازمانی» و ابر (ENTERPRISE_PLAN.md، M1).

تست‌های ساختاری اینجا جلوی خطایی را می‌گیرند که خطا نمی‌دهد: روترِ ابریِ تازه‌ای
که کسی یادش برود در `routing.CLOUD_ONLY` بنویسد، بی‌صدا روی سرورِ شرکت هم سوار
می‌شد — مثلاً یک مسیرِ `/api/admin/*` روی شبکه‌ی داخلیِ مشتری.
"""

import importlib
import pkgutil
from types import SimpleNamespace

import pytest
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.testclient import TestClient

import app.routers as routers_pkg
from app import routing
from app.config import Settings, _validate, get_settings
from app.database import get_db
from app.models.subscription import Subscription
from app.models.tenant import Tenant
from app.routers import enterprise_setup
from app.services import entitlements

#: پیشوندهایی که هرگز نباید روی سرورِ سازمانی جواب بدهند.
CLOUD_ONLY_PREFIXES = (
    "/api/admin",
    "/api/plans",
    "/api/purchases",
    "/api/shop",
    "/api/storefront",
    "/api/marketplace",
    "/api/integration",
    "/api/devices",
    "/api/enterprise",
)


def _paths(edition: str) -> set[str]:
    app = FastAPI()
    routing.include_routers(app, edition)
    return {r.path for r in app.routes if hasattr(r, "methods")}


def test_enterprise_mounts_no_cloud_only_path():
    leaked = sorted(p for p in _paths("enterprise") if p.startswith(CLOUD_ONLY_PREFIXES))
    assert leaked == []


def test_cloud_keeps_its_paths_and_hides_setup():
    paths = _paths("cloud")
    for prefix in CLOUD_ONLY_PREFIXES:
        assert any(p.startswith(prefix) for p in paths), prefix
    assert not any(p.startswith("/api/setup") for p in paths)


def test_enterprise_has_setup():
    assert "/api/setup" in _paths("enterprise")


def test_every_router_is_registered():
    """هر APIRouterِ سطحِ ماژول در app/routers باید در ALL_ROUTERS باشد — وگرنه در هیچ نسخه‌ای سوار نمی‌شود."""
    missing = []
    for info in pkgutil.iter_modules(routers_pkg.__path__):
        mod = importlib.import_module(f"app.routers.{info.name}")
        for name, obj in vars(mod).items():
            if isinstance(obj, APIRouter) and not any(obj is r for r in routing.ALL_ROUTERS):
                missing.append(f"{info.name}.{name}")
    assert missing == []


def test_admin_routers_are_cloud_only():
    for r in routing.ALL_ROUTERS:
        if r.prefix.startswith("/api/admin"):
            assert any(r is c for c in routing.CLOUD_ONLY), r.prefix


def test_unknown_edition_rejected():
    with pytest.raises(RuntimeError, match="EDITION"):
        _validate(Settings(edition="onprem", zarinpal_sandbox=True))


def test_enterprise_ignores_zarinpal_guard():
    # سرورِ سازمانی پولی جابه‌جا نمی‌کند؛ ZARINPAL_SANDBOX=false نباید بوتش را بشکند.
    _validate(Settings(edition="enterprise", zarinpal_sandbox=False))


@pytest.fixture
def enterprise(monkeypatch):
    monkeypatch.setattr(get_settings(), "edition", "enterprise")


def test_cloud_signup_is_404_on_enterprise(client, enterprise):
    for path in ("/api/auth/signup/request-code", "/api/auth/forgot-password"):
        assert client.post(path, json={"email": "a@example.com"}).status_code == 404, path


def test_me_reports_edition(client, enterprise):
    body = client.get("/api/auth/me").json()
    assert body["edition"] == "enterprise"
    assert body["is_platform_admin"] is False


def _expired_subscription_state(*_a, **_k):
    return SimpleNamespace(can_write=False)


def test_enterprise_write_not_gated_by_cloud_subscription(monkeypatch, db, enterprise):
    """سرورِ شرکت اشتراکِ ابری ندارد؛ نبودِ/انقضای آن نباید نوشتن را ببندد."""
    monkeypatch.setattr(entitlements, "subscription_state", _expired_subscription_state)
    tenant = SimpleNamespace(is_trial=False, id=None)
    entitlements.enforce(db, tenant, ("create",))


def test_cloud_write_gated_by_subscription(monkeypatch, db):
    monkeypatch.setattr(entitlements, "subscription_state", _expired_subscription_state)
    tenant = SimpleNamespace(is_trial=False, id=None)
    with pytest.raises(HTTPException) as exc:
        entitlements.enforce(db, tenant, ("create",))
    assert exc.value.status_code == 402
    # خواندن هرگز قفل نمی‌شود.
    entitlements.enforce(db, tenant, ("read",))


@pytest.fixture
def setup_client(db):
    app = FastAPI()
    app.include_router(enterprise_setup.router)
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


SETUP_BODY = {
    "business_name": "شرکت آزمون",
    "owner_name": "مالک آزمون",
    "email": "owner-setup@setup-test.cubita.ir",
    "password": "SetupPassword!2026",
}


def test_setup_refused_once_a_business_exists(setup_client):
    assert setup_client.get("/api/setup/status").json() == {"needs_setup": False}
    r = setup_client.post("/api/setup", json=SETUP_BODY)
    assert r.status_code == 409


def test_setup_creates_non_trial_business(setup_client, db, monkeypatch):
    monkeypatch.setattr(enterprise_setup, "_has_business", lambda _db: False)
    r = setup_client.post("/api/setup", json=SETUP_BODY)
    assert r.status_code == 201, r.text
    assert r.json()["access_token"]
    tenant = (
        db.query(Tenant).filter(Tenant.name == SETUP_BODY["business_name"]).one()
    )
    # آزمایشیِ ابری نیست: نه بنرِ تریال، نه کرونِ حذف، نه اشتراکِ زماندار.
    assert tenant.is_trial is False
    assert db.query(Subscription).filter(Subscription.tenant_id == tenant.id).count() == 0


def test_enterprise_modules_without_superadmin_grant(enterprise):
    """سرورِ سازمانی سوپرادمین ندارد: ماژولِ محدود (تولید) باز، «اتصال فروشگاه» حذف."""
    from app.services import modules as modules_service

    tenant = SimpleNamespace(granted_modules=[])
    allowed = modules_service.allowed_modules(tenant)
    assert "manufacturing" in allowed
    assert "integration" not in allowed


def test_cloud_restricted_modules_need_grant():
    from app.services import modules as modules_service

    allowed = modules_service.allowed_modules(SimpleNamespace(granted_modules=[]))
    assert "manufacturing" not in allowed


def test_enterprise_allows_electron_file_origin():
    assert "file://" in Settings(edition="enterprise", allowed_origins="").allowed_origins_list
    assert "file://" not in Settings(edition="cloud", allowed_origins="").allowed_origins_list
