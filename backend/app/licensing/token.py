"""توکنِ مجوز: `CUB1.<b64url(payload)>.<b64url(sig)>`.

امضا روی **همان بایت‌هایی** است که base64 شده‌اند (مثلِ JWS)، نه روی JSONی که
دوباره ساخته شود — پس کانونیک‌سازیِ JSON در راستی‌آزمایی نقشی ندارد و ترتیبِ کلیدها
یا فاصله‌ها نمی‌تواند امضای درست را نادرست کند.

**محتوای payload** (همه به‌جز `v`/`lic`/`iat` اختیاری‌اند):

| کلید | معنا |
|---|---|
| `v` | نسخه‌ی قالب (۱) |
| `lic` | شناسه‌ی مجوز در ستاد |
| `edition` | باید `enterprise` باشد |
| `org` | نامِ سازمان — فقط نمایش |
| `iat` / `exp` | صدور / انقضا (ثانیه‌ی یونیکس)؛ بی‌`exp` = دائمی |
| `grace` | روزهای مهلت پس از انقضا که نوشتن هنوز باز است |
| `seats` | سقفِ حسابِ کاربری؛ بی‌آن = بی‌سقف |
| `mods` | ماژول‌های مجاز؛ بی‌آن = همه |
| `feat` | قابلیت‌های پولی (مثلِ `moadian`)؛ بی‌آن = همه |
| `fp` | اثرانگشتِ هش‌شده‌ی دستگاه (`fingerprint.hashed`) |
| `install` | شناسه‌ی نصب — برای ردگیری در ستاد |
"""

import base64
import hashlib
import json

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

PREFIX = "CUB1"
FORMAT_VERSION = 1


class LicenseError(ValueError):
    """توکنِ نامعتبر. پیام فارسی است و مستقیم به کاربر نشان داده می‌شود."""


def b64u_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64u_decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def public_key_b64(public_key: Ed25519PublicKey) -> str:
    return b64u_encode(public_key.public_bytes(Encoding.Raw, PublicFormat.Raw))


def key_id(public_key_b64u: str) -> str:
    """شناسه‌ی کوتاهِ کلید — برای نام‌بردن در کد و گزارش، نه برای امنیت."""
    return hashlib.sha256(b64u_decode(public_key_b64u)).hexdigest()[:8]


def sign(payload: dict, private_key: Ed25519PrivateKey) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return f"{PREFIX}.{b64u_encode(body)}.{b64u_encode(private_key.sign(body))}"


def decode_unverified(token: str) -> dict:
    """فقط برای پشتیبانی (`cli inspect`) — هرگز برای تصمیم‌گیری."""
    parts = token.strip().split(".")
    if len(parts) != 3 or parts[0] != PREFIX:
        raise LicenseError("قالبِ کدِ مجوز درست نیست.")
    try:
        return json.loads(b64u_decode(parts[1]))
    except ValueError as exc:
        raise LicenseError("کدِ مجوز خراب است.") from exc


def verify(token: str, trusted: dict[str, str]) -> dict:
    """payload را برمی‌گرداند اگر یکی از کلیدهای مورد اعتماد امضایش کرده باشد."""
    parts = "".join(token.split()).split(".")
    if len(parts) != 3 or parts[0] != PREFIX:
        raise LicenseError("قالبِ کدِ مجوز درست نیست؛ کلِ متن را بی‌کم‌وکاست کپی کنید.")
    try:
        body = b64u_decode(parts[1])
        signature = b64u_decode(parts[2])
    except ValueError as exc:
        raise LicenseError("کدِ مجوز خراب است؛ کلِ متن را دوباره کپی کنید.") from exc

    for public in trusted.values():
        try:
            Ed25519PublicKey.from_public_bytes(b64u_decode(public)).verify(signature, body)
        except (InvalidSignature, ValueError):
            continue
        break
    else:
        raise LicenseError("امضای این کدِ مجوز معتبر نیست.")

    try:
        payload = json.loads(body)
    except ValueError as exc:
        raise LicenseError("کدِ مجوز خراب است.") from exc
    if not isinstance(payload, dict) or payload.get("v") != FORMAT_VERSION:
        raise LicenseError("این کدِ مجوز برای نسخه‌ی دیگری از کوبیتا صادر شده است.")
    if payload.get("edition") != "enterprise":
        raise LicenseError("این کد مجوزِ کوبیتا سازمانی نیست.")
    return payload
