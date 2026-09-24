"""آپدیتِ «کوبیتا سازمانی» (ENTERPRISE_PLAN.md، M5).

دو قاعده بیش از همه: **هیچ فایلی بی‌امضا و بی‌هشِ درست کنار گذاشته نمی‌شود**، و **سرور فقط
نسخه‌ی خودش را به کلاینت‌ها می‌دهد** (کلاینت هرگز از API سرورش جلو نمی‌زند).
"""

import base64
import hashlib

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import version as version_mod
from app.config import get_settings
from app.licensing import keys
from app.licensing.token import key_id, public_key_b64, sign
from app.onprem import updates as upd

INSTALLER = b"MZ" + b"\x00" * 4096 + b"cubita-installer"


def manifest_for(version: str, blob: bytes = INSTALLER, name: str | None = None) -> bytes:
    name = name or f"Cubita-Enterprise-Setup-{version}.exe"
    sha = base64.b64encode(hashlib.sha512(blob).digest()).decode()
    return (
        f"version: {version}\nfiles:\n  - url: {name}\n    sha512: {sha}\n    size: {len(blob)}\n"
        f"path: {name}\nsha512: {sha}\nreleaseDate: '2026-09-24T00:00:00.000Z'\n"
    ).encode()


@pytest.fixture
def key(monkeypatch):
    k = Ed25519PrivateKey.generate()
    pub = public_key_b64(k.public_key())
    monkeypatch.setattr(keys, "TRUSTED_PUBLIC_KEYS", {key_id(pub): pub})
    return k


@pytest.fixture
def running(monkeypatch):
    def _set(v: str):
        monkeypatch.setenv("CUBITA_VERSION", v)
        version_mod.app_version.cache_clear()

    _set("1.7.0")
    yield _set
    version_mod.app_version.cache_clear()


def channel(files: dict[str, bytes]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        name = request.url.path.rsplit("/", 1)[-1]
        assert request.url.path.startswith(upd.CHANNEL_PATH)
        return httpx.Response(200, content=files[name]) if name in files else httpx.Response(404)

    return httpx.MockTransport(handler)


def published(k, version: str, blob: bytes = INSTALLER, tamper_after_sign: bytes | None = None) -> dict[str, bytes]:
    m = manifest_for(version, blob)
    sig = upd.sign_manifest(m, k).encode()
    return {
        "latest.yml": tamper_after_sign or m,
        "latest.yml.sig": sig,
        f"Cubita-Enterprise-Setup-{version}.exe": blob,
    }


# --- manifest و امضا -----------------------------------------------------------


def test_manifest_parse_and_unsafe_name_rejected():
    m = upd.parse_manifest(manifest_for("1.8.0").decode())
    assert (m.version, m.path, m.size) == ("1.8.0", "Cubita-Enterprise-Setup-1.8.0.exe", len(INSTALLER))
    with pytest.raises(upd.UpdateError):
        upd.parse_manifest(manifest_for("1.8.0", name="../../evil.exe").decode())


def test_license_signature_is_not_an_update_signature(key):
    """کلید یکی است ولی زمینه فرق دارد — توکنِ مجوزِ امضاشده نباید آپدیتِ معتبر حساب شود."""
    data = manifest_for("1.8.0")
    forged = sign({"v": 1}, key).split(".")[2]  # امضای بدونِ پیشوندِ زمینه
    with pytest.raises(upd.UpdateError):
        upd.verify_manifest(data, forged)
    upd.verify_manifest(data, upd.sign_manifest(data, key))


# --- دانلود از ابر --------------------------------------------------------------


def test_newer_version_is_downloaded_and_verified(tmp_path, key, running):
    st = upd.check_and_download(tmp_path, "https://acc.cubita.ir", transport=channel(published(key, "1.8.0")))
    assert st.latest_available == "1.8.0"
    assert st.installer_path and st.installer_path.endswith("Cubita-Enterprise-Setup-1.8.0.exe")
    folder = tmp_path / "updates" / "1.8.0"
    assert (folder / "latest.yml.sig").exists()
    assert not list(folder.glob("*.part"))


def test_tampered_manifest_rejected(tmp_path, key, running):
    evil = manifest_for("1.8.0", b"MZ-evil")
    with pytest.raises(upd.UpdateError, match="امضا"):
        upd.check_and_download(tmp_path, "https://x", transport=channel(published(key, "1.8.0", tamper_after_sign=evil)))
    assert not (tmp_path / "updates" / "1.8.0").exists()


def test_installer_hash_mismatch_rejected(tmp_path, key, running):
    files = published(key, "1.8.0")
    files["Cubita-Enterprise-Setup-1.8.0.exe"] = INSTALLER[:-1] + b"X"  # همان اندازه، محتوای دیگر
    with pytest.raises(upd.UpdateError, match="هش"):
        upd.check_and_download(tmp_path, "https://x", transport=channel(files))
    folder = tmp_path / "updates" / "1.8.0"
    assert not list(folder.glob("*.exe")) and not list(folder.glob("*.part"))


def test_older_version_is_ignored(tmp_path, key, running):
    st = upd.check_and_download(tmp_path, "https://x", transport=channel(published(key, "1.6.0")))
    assert st.latest_available is None and not st.serving_clients
    assert not (tmp_path / "updates").exists() or not any((tmp_path / "updates").iterdir())


def test_same_version_seeds_the_client_feed(tmp_path, key, running):
    """سروری که با نصابِ دستی نصب شده: همان نسخه برای کلاینت‌ها گرفته می‌شود، ولی «تازه» نیست."""
    st = upd.check_and_download(tmp_path, "https://x", transport=channel(published(key, "1.7.0")))
    assert st.latest_available is None and st.serving_clients


def test_offline_server_gets_clear_message(tmp_path, key, running):
    def down(_request):
        raise httpx.ConnectError("no route")

    with pytest.raises(upd.UpdateError, match="دسترسی نیست"):
        upd.check_and_download(tmp_path, "https://x", transport=httpx.MockTransport(down))


# --- خوراکِ کلاینت‌ها -------------------------------------------------------------


def _stage(home, k, version: str) -> None:
    folder = home / "updates" / version
    folder.mkdir(parents=True)
    for name, data in published(k, version).items():
        (folder / name).write_bytes(data)


@pytest.fixture
def feed_client(tmp_path, monkeypatch):
    from app.routers import enterprise_updates

    monkeypatch.setattr(get_settings(), "license_dir", str(tmp_path))
    app = FastAPI()
    app.include_router(enterprise_updates.router)
    return TestClient(app)


def test_feed_serves_only_the_running_version(tmp_path, key, running, feed_client):
    _stage(tmp_path, key, "1.7.0")
    _stage(tmp_path, key, "1.8.0")  # دانلود شده ولی سرور هنوز نصبش نکرده
    r = feed_client.get("/updates/latest.yml")
    assert r.status_code == 200 and b"version: 1.7.0" in r.content
    assert feed_client.get("/updates/Cubita-Enterprise-Setup-1.7.0.exe").content == INSTALLER
    # کلاینت نباید از سرورش جلو بزند.
    assert feed_client.get("/updates/Cubita-Enterprise-Setup-1.8.0.exe").status_code == 404

    running("1.8.0")
    assert b"version: 1.8.0" in feed_client.get("/updates/latest.yml").content


def test_feed_refuses_unlisted_files(tmp_path, key, running, feed_client):
    _stage(tmp_path, key, "1.7.0")
    (tmp_path / "updates" / "1.7.0" / "secrets.json").write_text("{}")
    assert feed_client.get("/updates/secrets.json").status_code == 404
    assert feed_client.get("/updates/..%2F..%2Fsecrets.json").status_code == 404


def test_feed_is_empty_without_a_signed_manifest(tmp_path, key, running, feed_client):
    folder = tmp_path / "updates" / "1.7.0"
    folder.mkdir(parents=True)
    (folder / "latest.yml").write_bytes(manifest_for("1.7.0"))  # بی‌امضا
    assert feed_client.get("/updates/latest.yml").status_code == 404


def test_version_parse():
    assert version_mod.parse_version("1.10.0") > version_mod.parse_version("1.9.9")
    assert version_mod.parse_version("v2.0.0-beta.1") == (2, 0, 0)
    assert version_mod.parse_version("garbage") == (0, 0, 0)


def test_client_and_server_keys_match():
    """کلاینت همان کلیدهایی را باور کند که سرور — وگرنه یا آپدیتِ درست رد می‌شد یا کلیدِ
    باطل‌شده در یکی جا می‌ماند."""
    import re
    from pathlib import Path

    ts = (Path(__file__).resolve().parents[2] / "desktop" / "electron" / "updateKeys.ts").read_text(encoding="utf-8")
    body = ts[ts.index("TRUSTED_UPDATE_KEYS") :]
    client = dict(re.findall(r'["\']([0-9a-f]{8})["\']\s*:\s*["\']([A-Za-z0-9_-]+)["\']', body))
    from app.licensing.keys import TRUSTED_PUBLIC_KEYS

    assert client == TRUSTED_PUBLIC_KEYS
