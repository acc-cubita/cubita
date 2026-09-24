"""آپدیتِ «کوبیتا سازمانی» — سرور از ابر می‌گیرد، کلاینت‌ها از سرور (ENTERPRISE_PLAN.md، M5).

**کلاینت هرگز از سرورش جلو نمی‌زند.** کلاینتی که از API سرور تازه‌تر باشد، مسیرهایی را صدا
می‌زند که هنوز نیستند. پس ترتیب همیشه این است:

1. مدیر روی سرور «بررسیِ نسخه‌ی تازه» می‌زند: `latest.yml` و امضایش از کانالِ سازمانیِ ابر
   گرفته، امضا سنجیده، نصاب دانلود و هشِ sha512 اش با همان `latest.yml`ِ امضاشده سنجیده
   می‌شود (`check_and_download`). پوشه: `<home>/updates/<version>/`.
2. مدیر نصاب را **روی خودِ سرور** اجرا می‌کند (از داخلِ برنامه). نصاب پیش از مهاجرت از
   دیتابیس پشتیبان می‌گیرد (`provision`).
3. سرور با نسخه‌ی تازه بالا می‌آید و از آن لحظه `/updates/*` همان نسخه را به کلاینت‌ها می‌دهد
   (`feed_dir`): پوشه‌ی **هم‌نسخه‌ی سرورِ در حالِ اجرا**، نه تازه‌ترین پوشه‌ی دانلودشده.

**امضا روی `latest.yml` است، نه روی نصاب:** `latest.yml` هشِ sha512ِ نصاب را دارد، پس امضای
آن همه‌چیز را می‌بندد. پیشوندِ `cubita-update-v1` نمی‌گذارد امضای یک توکنِ مجوز به‌جای امضای
آپدیت (یا برعکس) پذیرفته شود، با اینکه کلید یکی است.
"""

from __future__ import annotations

import base64
import hashlib
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from app.licensing import keys
from app.licensing.token import b64u_decode, b64u_encode
from app.version import app_version, parse_version

SIGNING_CONTEXT = b"cubita-update-v1\n"
MANIFEST = "latest.yml"
SIGNATURE = "latest.yml.sig"
CHANNEL_PATH = "/updates/enterprise/"


class UpdateError(RuntimeError):
    """پیامِ فارسی برای مدیرِ سرور."""


@dataclass(frozen=True)
class Manifest:
    version: str
    path: str
    sha512: str
    size: int | None


def parse_manifest(text: str) -> Manifest:
    """فقط کلیدهای سطحِ اولِ `latest.yml`ِ electron-builder — بدونِ وابستگی به PyYAML."""
    top: dict[str, str] = {}
    for line in text.splitlines():
        m = re.match(r"^([A-Za-z0-9_]+):\s*(.*)$", line)
        if m:
            top[m.group(1)] = m.group(2).strip().strip("'\"")
    #: electron-builder اندازه را فقط زیرِ `files:` می‌نویسد (تورفته)، نه در سطحِ اول.
    if "size" not in top:
        size = re.search(r"^\s+size:\s*(\d+)\s*$", text, re.MULTILINE)
        if size:
            top["size"] = size.group(1)
    try:
        manifest = Manifest(
            version=top["version"],
            path=top["path"],
            sha512=top["sha512"],
            size=int(top["size"]) if top.get("size", "").isdigit() else None,
        )
    except KeyError as exc:
        raise UpdateError(f"فایلِ latest.yml ناقص است ({exc.args[0]}).") from exc
    #: نامِ فایل از بیرون می‌آید و در مسیرِ دیسک و URL می‌نشیند — فقط نامِ ساده.
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*\.exe", manifest.path):
        raise UpdateError("نامِ فایلِ نصاب در latest.yml مجاز نیست.")
    return manifest


def sign_manifest(data: bytes, private_key: Ed25519PrivateKey) -> str:
    return b64u_encode(private_key.sign(SIGNING_CONTEXT + data))


def verify_manifest(data: bytes, signature: str, trusted: dict[str, str] | None = None) -> None:
    sig = b64u_decode(signature.strip())
    for public in (keys.TRUSTED_PUBLIC_KEYS if trusted is None else trusted).values():
        try:
            Ed25519PublicKey.from_public_bytes(b64u_decode(public)).verify(sig, SIGNING_CONTEXT + data)
            return
        except (InvalidSignature, ValueError):
            continue
    raise UpdateError("امضای بسته‌ی آپدیت معتبر نیست؛ چیزی دانلود نشد.")


def sha512_b64(path: Path) -> str:
    h = hashlib.sha512()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return base64.b64encode(h.digest()).decode("ascii")


# --- روی دیسکِ سرور -----------------------------------------------------------


def updates_root(home: Path) -> Path:
    return home / "updates"


def feed_dir(home: Path, version: str | None = None) -> Path:
    """پوشه‌ای که به کلاینت‌ها داده می‌شود: هم‌نسخه‌ی سرورِ در حالِ اجرا."""
    return updates_root(home) / (version or app_version())


def feed_files(folder: Path) -> set[str]:
    """نام‌هایی که `/updates/*` مجاز است بدهد — فقط آنچه در manifestِ سنجیده‌شده آمده."""
    manifest_file = folder / MANIFEST
    if not manifest_file.exists() or not (folder / SIGNATURE).exists():
        return set()
    try:
        m = parse_manifest(manifest_file.read_text(encoding="utf-8"))
    except UpdateError:
        return set()
    return {MANIFEST, SIGNATURE, m.path, f"{m.path}.blockmap"}


@dataclass
class UpdateStatus:
    running: str
    latest_available: str | None
    installer_path: str | None
    serving_clients: bool


def status(home: Path) -> UpdateStatus:
    running = app_version()
    newest: tuple[tuple[int, int, int], str, Path] | None = None
    root = updates_root(home)
    if root.exists():
        for d in root.iterdir():
            if d.is_dir() and feed_files(d) and parse_version(d.name) > parse_version(running):
                if newest is None or parse_version(d.name) > newest[0]:
                    newest = (parse_version(d.name), d.name, d)
    installer = None
    if newest:
        m = parse_manifest((newest[2] / MANIFEST).read_text(encoding="utf-8"))
        installer = str(newest[2] / m.path)
    return UpdateStatus(
        running=running,
        latest_available=newest[1] if newest else None,
        installer_path=installer,
        serving_clients=bool(feed_files(feed_dir(home, running))),
    )


def check_and_download(
    home: Path,
    server_url: str,
    *,
    timeout: float = 30.0,
    log=lambda m: None,
    transport: httpx.BaseTransport | None = None,
) -> UpdateStatus:
    """نسخه‌ی تازه را از کانالِ سازمانیِ ابر می‌گیرد، می‌سنجد و کنار می‌گذارد.

    چیزی نصب نمی‌کند. فایلِ نیمه‌کاره یا هشِ نادرست هرگز در پوشه‌ی نهایی نمی‌نشیند
    (دانلود در `.part` و جابه‌جاییِ اتمی بعد از سنجش).
    """
    base = server_url.rstrip("/") + CHANNEL_PATH
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, transport=transport) as client:
            raw = client.get(base + MANIFEST)
            raw.raise_for_status()
            sig = client.get(base + SIGNATURE)
            sig.raise_for_status()
            verify_manifest(raw.content, sig.text)
            manifest = parse_manifest(raw.content.decode("utf-8"))
            newer = parse_version(manifest.version) > parse_version(app_version())
            same = parse_version(manifest.version) == parse_version(app_version())
            #: هم‌نسخه‌ی سرور هم گرفته می‌شود اگر خوراکِ کلاینت‌ها خالی است — سروری که با
            #: نصابِ دستی (از پشتیبانی) نصب شده، وگرنه هرگز چیزی به کلاینت‌ها نمی‌داد.
            if not newer and not (same and not feed_files(feed_dir(home))):
                log("نسخه‌ی تازه‌تری نیست.")
                return status(home)

            target = updates_root(home) / manifest.version
            if feed_files(target):
                log("این نسخه قبلاً دانلود شده است.")
                return status(home)
            target.mkdir(parents=True, exist_ok=True)
            part = target / f"{manifest.path}.part"
            log(f"دانلودِ نسخه‌ی {manifest.version}…")
            with client.stream("GET", base + manifest.path) as resp:
                resp.raise_for_status()
                with open(part, "wb") as fh:
                    for chunk in resp.iter_bytes(1 << 20):
                        fh.write(chunk)
    except httpx.HTTPError as exc:
        raise UpdateError(
            "به کانالِ آپدیتِ کوبیتا دسترسی نیست. اتصالِ اینترنتِ سرور را بررسی کنید؛ "
            "یا نصابِ تازه را از پشتیبانی بگیرید و دستی روی سرور اجرا کنید."
        ) from exc

    if manifest.size is not None and part.stat().st_size != manifest.size:
        part.unlink(missing_ok=True)
        raise UpdateError("اندازه‌ی نصابِ دانلودشده با latest.yml نمی‌خواند؛ دوباره امتحان کنید.")
    if sha512_b64(part) != manifest.sha512:
        part.unlink(missing_ok=True)
        raise UpdateError("هشِ نصابِ دانلودشده با latest.yml نمی‌خواند؛ فایل رد شد.")
    part.replace(target / manifest.path)
    (target / MANIFEST).write_bytes(raw.content)
    (target / SIGNATURE).write_text(sig.text.strip(), encoding="utf-8")
    log(f"نسخه‌ی {manifest.version} آماده‌ی نصب روی سرور است.")
    return status(home)


def prune(home: Path, keep: int = 2) -> None:
    """پوشه‌های نسخه‌ی قدیمی — نسخه‌ی در حالِ اجرا و تازه‌ترها همیشه می‌مانند."""
    root = updates_root(home)
    if not root.exists():
        return
    running = parse_version(app_version())
    old = sorted(
        (d for d in root.iterdir() if d.is_dir() and parse_version(d.name) < running),
        key=lambda d: parse_version(d.name),
    )
    for d in old[: max(0, len(old) - keep)]:
        shutil.rmtree(d, ignore_errors=True)
