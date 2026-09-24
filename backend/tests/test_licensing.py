"""مجوزِ «کوبیتا سازمانی» (ENTERPRISE_PLAN.md، M2).

قاعده‌ای که این تست‌ها بیش از همه نگهش می‌دارند: **هیچ حالتی خواندن را نمی‌بندد.**
انقضای مجوز یا آزمایشی فقط ثبتِ تازه را می‌بندد؛ دفتر، گزارش و پشتیبان‌گیری باز می‌ماند.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.config import get_settings
from app.licensing import cli, fingerprint, keys
from app.licensing import state as license_state
from app.licensing.token import LicenseError, key_id, public_key_b64, sign, verify
from app.models.enterprise_license import EnterpriseLicense
from app.models.tenant import Tenant

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)
FP = {"machine_guid": "a" * 32, "smbios_uuid": "b" * 32, "volume_serial": "c" * 32}
OTHER_FP = {"machine_guid": "x" * 32, "smbios_uuid": "y" * 32, "volume_serial": "c" * 32}


@pytest.fixture
def signing_key(monkeypatch):
    key = Ed25519PrivateKey.generate()
    public = public_key_b64(key.public_key())
    monkeypatch.setattr(keys, "TRUSTED_PUBLIC_KEYS", {key_id(public): public})
    return key


@pytest.fixture
def enterprise(monkeypatch, tmp_path):
    settings = get_settings()
    monkeypatch.setattr(settings, "edition", "enterprise")
    monkeypatch.setattr(settings, "license_dir", str(tmp_path))
    monkeypatch.setattr(fingerprint, "current", lambda: dict(FP))
    monkeypatch.setattr(license_state, "_now", lambda: NOW)
    license_state.reset_cache()
    yield settings
    license_state.reset_cache()


def _payload(**extra):
    base = {"v": 1, "lic": "L1", "edition": "enterprise", "org": "شرکت آزمون", "iat": 0, "fp": FP}
    base.update(extra)
    return base


def _row(installed_days_ago=0, token=None, last_seen=NOW):
    return EnterpriseLicense(
        id=1,
        installed_at=NOW - timedelta(days=installed_days_ago),
        token=token,
        last_seen_at=last_seen,
    )


def _eval(row, fp=FP, trusted=None):
    return license_state.evaluate(row, NOW, fp, trusted if trusted is not None else keys.TRUSTED_PUBLIC_KEYS, 30)


# --- توکن -------------------------------------------------------------------


def test_token_roundtrip(signing_key):
    assert verify(sign(_payload(), signing_key), keys.TRUSTED_PUBLIC_KEYS)["lic"] == "L1"


def test_tampered_token_rejected(signing_key):
    token = sign(_payload(seats=2), signing_key)
    prefix, body, sig = token.split(".")
    forged = sign(_payload(seats=500), Ed25519PrivateKey.generate()).split(".")[1]
    with pytest.raises(LicenseError):
        verify(f"{prefix}.{forged}.{sig}", keys.TRUSTED_PUBLIC_KEYS)


def test_untrusted_key_rejected(signing_key):
    with pytest.raises(LicenseError):
        verify(sign(_payload(), Ed25519PrivateKey.generate()), keys.TRUSTED_PUBLIC_KEYS)


def test_cloud_edition_token_rejected(signing_key):
    with pytest.raises(LicenseError):
        verify(sign(_payload(edition="cloud"), signing_key), keys.TRUSTED_PUBLIC_KEYS)


def test_token_survives_pasted_line_breaks(signing_key):
    token = sign(_payload(), signing_key)
    wrapped = "\n".join(token[i : i + 40] for i in range(0, len(token), 40))
    assert verify(wrapped, keys.TRUSTED_PUBLIC_KEYS)["lic"] == "L1"


# --- اثرانگشت ---------------------------------------------------------------


def test_fingerprint_two_of_three():
    assert fingerprint.matches(FP, {**FP, "volume_serial": "z" * 32})
    assert not fingerprint.matches(FP, OTHER_FP)
    # جزئی که یک طرف ندارد به نفعِ تطبیق نمی‌شمارد.
    assert not fingerprint.matches({"machine_guid": FP["machine_guid"]}, FP)


def test_fingerprint_hash_hides_raw_ids():
    hashed = fingerprint.hashed({"machine_guid": "1234", "smbios_uuid": None, "volume_serial": "9"})
    assert set(hashed) == {"machine_guid", "volume_serial"}
    assert "1234" not in hashed["machine_guid"]


# --- محاسبه‌ی وضعیت ----------------------------------------------------------


def test_trial_then_trial_expired():
    s = _eval(_row(installed_days_ago=10))
    assert (s.mode, s.writable, s.days_left) == ("trial", True, 20)
    s = _eval(_row(installed_days_ago=31))
    assert (s.mode, s.writable) == ("trial_expired", False)
    assert "آزمایشی" in s.message


def test_active_grace_expired(signing_key):
    def at(exp_days, grace=14):
        exp = int((NOW + timedelta(days=exp_days)).timestamp())
        return _eval(_row(token=sign(_payload(exp=exp, grace=grace, seats=5), signing_key)))

    s = at(100)
    assert (s.mode, s.writable, s.seats) == ("active", True, 5)
    s = at(-3)
    assert (s.mode, s.writable) == ("grace", True)
    assert s.days_left == 11
    s = at(-30)
    assert (s.mode, s.writable) == ("expired", False)


def test_perpetual_license(signing_key):
    s = _eval(_row(token=sign(_payload(), signing_key)))
    assert (s.mode, s.writable, s.expires_at) == ("active", True, None)


def test_clock_rollback_blocks_writes():
    s = _eval(_row(last_seen=NOW + timedelta(days=3)))
    assert (s.mode, s.writable) == ("clock", False)
    # چند ساعت اختلاف (منطقه‌ی زمانی، همگام‌سازیِ ساعت) قفل نمی‌کند.
    assert _eval(_row(last_seen=NOW + timedelta(hours=5))).writable


def test_license_on_other_machine(signing_key):
    s = _eval(_row(token=sign(_payload(), signing_key)), fp=OTHER_FP)
    assert (s.mode, s.writable) == ("mismatch", False)


def test_license_from_revoked_key_is_invalid(signing_key):
    token = sign(_payload(), signing_key)
    s = _eval(_row(token=token), trusted={})
    assert (s.mode, s.writable) == ("invalid", False)


# --- پایداری: دیتابیس و فایل --------------------------------------------------


def test_deleting_the_row_does_not_reset_trial(db, enterprise):
    license_state.current(db)
    row = db.get(EnterpriseLicense, 1)
    row.installed_at = NOW - timedelta(days=40)
    db.flush()
    license_state._write_file(row)

    db.delete(row)
    db.flush()
    license_state.reset_cache()
    assert license_state.current(db).mode == "trial_expired"


def test_deleting_the_file_does_not_reset_trial(db, enterprise):
    license_state.current(db)
    row = db.get(EnterpriseLicense, 1)
    row.installed_at = NOW - timedelta(days=40)
    db.flush()
    license_state.license_file().unlink()
    license_state.reset_cache()
    assert license_state.current(db).mode == "trial_expired"
    # و فایل دوباره ساخته شد.
    assert license_state.license_file().exists()


# --- نصب ---------------------------------------------------------------------


def test_install_applies_seats(db, enterprise, signing_key, tenant_id):
    status_ = license_state.install(db, sign(_payload(seats=7), signing_key))
    assert (status_.mode, status_.writable) == ("active", True)
    assert db.get(Tenant, tenant_id).max_users == 7


def test_install_refuses_other_machine(db, enterprise, signing_key):
    with pytest.raises(LicenseError, match="رایانه‌ی دیگری"):
        license_state.install(db, sign(_payload(fp=OTHER_FP), signing_key))


def test_install_refuses_expired(db, enterprise, signing_key):
    exp = int((NOW - timedelta(days=40)).timestamp())
    with pytest.raises(LicenseError, match="منقضی"):
        license_state.install(db, sign(_payload(exp=exp, grace=14), signing_key))


def test_cli_issue_from_request_code(db, enterprise, signing_key, tmp_path, capsys):
    pem = tmp_path / "k.pem"
    from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat

    pem.write_bytes(signing_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()))
    code = license_state.request_code(db, "شرکت آزمون")
    assert code.startswith("CUBREQ1.")

    assert cli.main(["issue", "--key", str(pem), "--request", code, "--seats", "4", "--days", "365"]) == 0
    token = capsys.readouterr().out.strip()
    status_ = license_state.install(db, token)
    assert (status_.mode, status_.seats, status_.org) == ("active", 4, "شرکت آزمون")


def test_cli_keygen_never_prints_private_key(tmp_path, capsys):
    out = tmp_path / "signing.pem"
    assert cli.main(["keygen", "--out", str(out)]) == 0
    printed = capsys.readouterr().out
    assert "PRIVATE KEY" in out.read_text()
    assert "PRIVATE KEY" not in printed
    # رونویسیِ کلیدِ موجود همه‌ی مجوزهای صادرشده را باطل می‌کرد.
    assert cli.main(["keygen", "--out", str(out)]) == 1


# --- گلوگاه: نوشتن بسته، خواندن باز ------------------------------------------


def _expire_trial(db):
    license_state.current(db)
    db.get(EnterpriseLicense, 1).installed_at = NOW - timedelta(days=45)
    db.flush()
    license_state.reset_cache()


def test_expired_trial_blocks_writes_not_reads(client, db, enterprise):
    _expire_trial(db)
    r = client.post("/api/cost-centers", json={"name": "مرکز آزمون", "kind": "branch"})
    assert r.status_code == 402
    assert "آزمایشی" in r.json()["detail"]
    assert client.get("/api/cost-centers").status_code == 200
    # پشتیبان‌گیری هرگز پشتِ مجوز نمی‌ماند.
    assert client.get("/api/backup/export").status_code == 200


def test_active_trial_allows_writes(client, db, enterprise):
    r = client.post("/api/cost-centers", json={"name": "مرکز آزمون", "kind": "branch"})
    assert r.status_code == 201, r.text


def test_cloud_ignores_enterprise_license(client, db):
    """در ابر جدولِ مجوز حتی خوانده نمی‌شود."""
    r = client.post("/api/cost-centers", json={"name": "مرکز ابری", "kind": "branch"})
    assert r.status_code == 201, r.text
    assert db.get(EnterpriseLicense, 1) is None
    assert client.get("/api/auth/me").json()["license"] is None


def test_me_carries_license(client, enterprise):
    lic = client.get("/api/auth/me").json()["license"]
    assert (lic["mode"], lic["writable"], lic["days_left"]) == ("trial", True, 30)


def test_license_mods_restrict_modules(db, enterprise, signing_key):
    from app.services import modules as modules_service

    license_state.install(db, sign(_payload(mods=["sales", "inventory"]), signing_key))
    allowed = modules_service.allowed_modules(SimpleNamespace(granted_modules=[]))
    assert {"sales", "inventory"} <= allowed
    assert "manufacturing" not in allowed
    # ماژولِ پایه را هیچ مجوزی نمی‌گیرد.
    assert set(modules_service.CORE_MODULES) <= allowed


def test_license_feat_gates_premium_feature(client, db, enterprise, signing_key):
    license_state.install(db, sign(_payload(feat=[]), signing_key))
    me = client.get("/api/auth/me").json()
    assert "moadian" in me["locked_features"]


# --- روترِ مجوز ---------------------------------------------------------------


@pytest.fixture
def license_client(client):
    """روترِ مجوز فقط در بیلدِ سازمانی سوار است؛ اینجا روی همان اپِ تست سوارش می‌کنیم."""
    from app.main import app
    from app.routers import enterprise_license

    before = len(app.router.routes)
    app.include_router(enterprise_license.router)
    try:
        yield client
    finally:
        del app.router.routes[before:]


def test_owner_gets_request_code_and_bad_token_is_400(license_client, enterprise):
    assert license_client.get("/api/license/request").json()["code"].startswith("CUBREQ1.")
    r = license_client.post("/api/license", json={"token": "CUB1.not.valid-token"})
    assert r.status_code == 400
    body = license_client.get("/api/license").json()
    assert body["mode"] == "trial" and body["seats_used"] >= 1


def test_trial_shows_the_enforced_seat_limit(license_client, db, enterprise, tenant_id):
    db.get(Tenant, tenant_id).max_users = 3
    db.flush()
    assert license_client.get("/api/license").json()["seats"] == 3


def test_install_via_api(license_client, enterprise, signing_key):
    r = license_client.post("/api/license", json={"token": sign(_payload(seats=9), signing_key)})
    assert r.status_code == 200, r.text
    assert (r.json()["mode"], r.json()["seats"]) == ("active", 9)
