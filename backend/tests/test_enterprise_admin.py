"""دفترِ مجوزهای کوبیتا سازمانی در ابر، پنلِ ستاد و فعال‌سازیِ آنلاین (ENTERPRISE_PLAN.md، M3).

قاعده‌ای که بیش از همه نگه داشته می‌شود: **هر مجوز یک دستگاه**، هم در فعال‌سازیِ آنلاین و
هم در صدورِ آفلاینِ ستاد — و تنها راهِ دستگاهِ دوم «انتقال» در پنل است.
"""

import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat

from app.config import get_settings
from app.licensing import fingerprint, keys
from app.licensing import state as license_state
from app.licensing.token import b64u_encode, key_id, public_key_b64, verify
from app.models.enterprise_license_registry import EnterpriseLicenseEvent, EnterpriseLicenseRecord
from app.models.staff_audit import StaffAuditLog
from app.services import enterprise_licenses as svc

FP_A = {"machine_guid": "a" * 32, "smbios_uuid": "b" * 32, "volume_serial": "c" * 32}
FP_B = {"machine_guid": "x" * 32, "smbios_uuid": "y" * 32, "volume_serial": "c" * 32}


def request_code(fp: dict, install: str = "inst-1", org: str = "شرکت آزمون") -> str:
    body = json.dumps({"v": 1, "install": install, "fp": fp, "org": org}).encode()
    return f"CUBREQ1.{b64u_encode(body)}"


@pytest.fixture
def signing(monkeypatch, tmp_path):
    key = Ed25519PrivateKey.generate()
    pem = tmp_path / "signing.pem"
    pem.write_bytes(key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()))
    monkeypatch.setattr(get_settings(), "license_signing_key_file", str(pem))
    public = public_key_b64(key.public_key())
    monkeypatch.setattr(keys, "TRUSTED_PUBLIC_KEYS", {key_id(public): public})
    svc._signing_key.cache_clear()
    yield key
    svc._signing_key.cache_clear()


def _create(db, **kw):
    args = dict(
        org_name="شرکت آزمون", contact=None, seats=5, days=365, grace_days=14, mods=None, feat=None,
        note=None, actor="staff@staff.cubita.ir",
    )
    args.update(kw)
    return svc.create(db, **args)


# --- کد ---------------------------------------------------------------------


def test_code_is_stored_hashed_and_forgiving_to_typos(db):
    record, code = _create(db)
    assert code not in (record.code_hash, record.code_hint)
    assert len(code.replace("-", "")) == 16
    # حروفِ کوچک، فاصله و O به‌جای ۰ همان کد است.
    messy = code.lower().replace("-", " ").replace("0", "o")
    assert svc.hash_code(messy) == record.code_hash


# --- یک مجوز، یک دستگاه ------------------------------------------------------


def test_online_activation_binds_first_machine_only(db, signing):
    record, code = _create(db)
    token = svc.activate_online(db, code, request_code(FP_A))
    payload = verify(token, keys.TRUSTED_PUBLIC_KEYS)
    assert (payload["lic"], payload["seats"], payload["fp"]) == (record.lic_id, 5, FP_A)
    assert record.bound_at is not None

    # همان دستگاه دوباره می‌گیرد (نصبِ دوباره) — حتی با یک جزءِ عوض‌شده.
    svc.activate_online(db, code, request_code({**FP_A, "volume_serial": "z" * 32}))
    # دستگاهِ دیگر نه.
    with pytest.raises(Exception, match="رایانه‌ی دیگری"):
        svc.activate_online(db, code, request_code(FP_B))


def test_transfer_frees_the_license(db, signing):
    record, code = _create(db)
    svc.activate_online(db, code, request_code(FP_A))
    svc.transfer(db, record, "staff@staff.cubita.ir")
    token = svc.activate_online(db, code, request_code(FP_B))
    assert verify(token, keys.TRUSTED_PUBLIC_KEYS)["fp"] == FP_B


def test_revoked_and_expired_refuse(db, signing):
    record, code = _create(db)
    svc.revoke(db, record, "staff@staff.cubita.ir")
    with pytest.raises(Exception, match="باطل"):
        svc.activate_online(db, code, request_code(FP_A))

    old, old_code = _create(db)
    old.expires_at = datetime.now(timezone.utc) - timedelta(days=30)
    with pytest.raises(Exception, match="منقضی"):
        svc.activate_online(db, old_code, request_code(FP_A))


def test_unknown_code_refused(db, signing):
    with pytest.raises(Exception, match="درست نیست"):
        svc.activate_online(db, "AAAA-BBBB-CCCC-DDDD", request_code(FP_A))


def test_missing_signing_key_is_503(db, monkeypatch):
    from fastapi import HTTPException

    monkeypatch.setattr(get_settings(), "license_signing_key_file", "")
    svc._signing_key.cache_clear()
    record, code = _create(db)
    with pytest.raises(HTTPException) as exc:
        svc.activate_online(db, code, request_code(FP_A))
    assert exc.value.status_code == 503


# --- مسیرِ عمومیِ فعال‌سازی --------------------------------------------------


@pytest.fixture
def public_client(db):
    from fastapi.testclient import TestClient

    from app.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_public_activate_and_refusal_is_recorded(public_client, db, signing):
    record, code = _create(db)
    r = public_client.post("/api/enterprise/activate", json={"code": code, "request_code": request_code(FP_A)})
    assert r.status_code == 200, r.text
    assert r.json()["token"].startswith("CUB1.")

    r = public_client.post("/api/enterprise/activate", json={"code": code, "request_code": request_code(FP_B)})
    assert r.status_code == 400
    kinds = [e.kind for e in db.query(EnterpriseLicenseEvent).filter_by(license_id=record.id)]
    # «رد» باید در تاریخچه بماند — سؤالِ اولِ پشتیبانی.
    assert "refuse" in kinds and "activate" in kinds


# --- پنلِ ستاد ---------------------------------------------------------------


def test_admin_create_issue_transfer_revoke(staff_client, db, signing):
    c = staff_client("owner")
    r = c.post("/api/admin/licenses", json={"org_name": "شرکت پارس", "seats": 8, "days": 365, "feat": ["moadian"]})
    assert r.status_code == 201, r.text
    lic_id = r.json()["license"]["id"]
    assert r.json()["activation_code"]
    assert "activation_code" not in c.get(f"/api/admin/licenses/{lic_id}").json()

    r = c.post(f"/api/admin/licenses/{lic_id}/issue", json={"request_code": request_code(FP_A)})
    assert r.status_code == 200, r.text
    assert verify(r.json()["token"], keys.TRUSTED_PUBLIC_KEYS)["feat"] == ["moadian"]

    r = c.post(f"/api/admin/licenses/{lic_id}/issue", json={"request_code": request_code(FP_B)})
    assert r.status_code == 400

    assert c.post(f"/api/admin/licenses/{lic_id}/transfer").json()["bound"] is False
    r = c.patch(f"/api/admin/licenses/{lic_id}", json={"seats": 12, "extend_days": 30})
    assert r.json()["seats"] == 12
    assert c.post(f"/api/admin/licenses/{lic_id}/revoke").json()["status"] == "revoked"

    actions = {a for (a,) in db.query(StaffAuditLog.action).all()}
    assert {"license_create", "license_issue", "license_transfer", "license_update", "license_revoke"} <= actions
    assert len(c.get("/api/admin/licenses", params={"q": "پارس"}).json()) == 1


def test_support_can_issue_but_not_create(staff_client, db, signing):
    record, _ = _create(db)
    c = staff_client("support", email="support@staff.cubita.ir")
    assert c.post("/api/admin/licenses", json={"org_name": "x شرکت"}).status_code == 403
    r = c.post(f"/api/admin/licenses/{record.id}/issue", json={"request_code": request_code(FP_A)})
    assert r.status_code == 200, r.text
    assert c.post(f"/api/admin/licenses/{record.id}/revoke").status_code == 403


def test_tenant_token_cannot_reach_admin(client):
    assert client.get("/api/admin/licenses").status_code in (401, 403)


# --- سمتِ سرورِ سازمانی: فعال‌سازیِ آنلاین از ابر ----------------------------


@pytest.fixture
def enterprise(monkeypatch, tmp_path):
    settings = get_settings()
    monkeypatch.setattr(settings, "edition", "enterprise")
    monkeypatch.setattr(settings, "license_dir", str(tmp_path / "lic"))
    monkeypatch.setattr(fingerprint, "current", lambda: dict(FP_A))
    license_state.reset_cache()
    yield settings
    license_state.reset_cache()


@pytest.fixture
def license_client(client):
    from app.main import app
    from app.routers import enterprise_license

    before = len(app.router.routes)
    app.include_router(enterprise_license.router)
    try:
        yield client
    finally:
        del app.router.routes[before:]


def test_enterprise_server_activates_through_cloud(license_client, db, enterprise, signing, monkeypatch):
    record, code = _create(db, seats=6)

    def fake_post(url, json, timeout):
        assert url.endswith("/api/enterprise/activate")
        token = svc.activate_online(db, json["code"], json["request_code"])
        return httpx.Response(200, json={"token": token})

    monkeypatch.setattr(httpx, "post", fake_post)
    r = license_client.post("/api/license/activate", json={"code": code})
    assert r.status_code == 200, r.text
    assert (r.json()["mode"], r.json()["seats"]) == ("active", 6)


def test_enterprise_server_offline_gets_clear_message(license_client, enterprise, monkeypatch):
    def down(*_a, **_k):
        raise httpx.ConnectError("no route")

    monkeypatch.setattr(httpx, "post", down)
    r = license_client.post("/api/license/activate", json={"code": "AAAA-BBBB-CCCC-DDDD"})
    assert r.status_code == 503
    assert "کدِ درخواست" in r.json()["detail"]


def test_enterprise_server_relays_cloud_refusal(license_client, enterprise, monkeypatch):
    monkeypatch.setattr(
        httpx, "post", lambda *a, **k: httpx.Response(400, json={"detail": "کدِ فعال‌سازی درست نیست."})
    )
    r = license_client.post("/api/license/activate", json={"code": "AAAA-BBBB-CCCC-DDDD"})
    assert r.status_code == 400
    assert r.json()["detail"] == "کدِ فعال‌سازی درست نیست."
