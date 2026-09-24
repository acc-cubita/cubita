"""ساختِ کلید و صدورِ مجوزِ کوبیتا سازمانی — فقط روی ابر، کنارِ کلیدِ خصوصی.

    python -m app.licensing.cli keygen --out /opt/hesabdari/secrets/license-signing.pem
    python -m app.licensing.cli issue --key PEM --request CUBREQ1.… --seats 5 --days 365 [--org …]
    python -m app.licensing.cli inspect CUB1.… | CUBREQ1.…

تا پنلِ ستاد (M3) ساخته شود، صدور با همین ابزار است. **کلیدِ خصوصی هرگز چاپ، کامیت یا
کنارِ پشتیبانِ دیتابیس نگه داشته نمی‌شود** — همان قاعده‌ی `SECRETS_KEY`.
"""

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    load_pem_private_key,
)

from app.licensing.state import decode_request
from app.licensing.token import (
    FORMAT_VERSION,
    PREFIX,
    LicenseError,
    decode_unverified,
    key_id,
    public_key_b64,
    sign,
)


def _keygen(args: argparse.Namespace) -> int:
    out = Path(args.out)
    if out.exists():
        print(f"{out} از قبل هست؛ رونویسی نمی‌شود (مجوزهای صادرشده با آن باطل می‌شدند).", file=sys.stderr)
        return 1
    key = Ed25519PrivateKey.generate()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()))
    try:
        os.chmod(out, 0o600)
    except OSError:
        pass
    public = public_key_b64(key.public_key())
    print("کلیدِ خصوصی ذخیره شد:", out)
    print("این خط را به TRUSTED_PUBLIC_KEYS در app/licensing/keys.py اضافه و کامیت کنید:")
    print(f'    "{key_id(public)}": "{public}",')
    return 0


def _load_key(path: str) -> Ed25519PrivateKey:
    key = load_pem_private_key(Path(path).read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise SystemExit("این فایل کلیدِ Ed25519 نیست.")
    return key


def _decode_request(code: str) -> dict:
    try:
        return decode_request(code)
    except LicenseError as exc:
        raise SystemExit(str(exc)) from exc


def _issue(args: argparse.Namespace) -> int:
    request = _decode_request(args.request)
    fp = request["fp"]
    now = int(time.time())
    payload = {
        "v": FORMAT_VERSION,
        "lic": args.lic or uuid.uuid4().hex[:12],
        "edition": "enterprise",
        "org": args.org or request.get("org"),
        "iat": now,
        "install": request.get("install"),
        "fp": fp,
        "grace": args.grace,
    }
    if args.days:
        payload["exp"] = now + args.days * 86400
    if args.seats is not None:
        payload["seats"] = args.seats
    if args.mods:
        payload["mods"] = sorted({m.strip() for m in args.mods.split(",") if m.strip()})
    if args.feat is not None:
        payload["feat"] = sorted({f.strip() for f in args.feat.split(",") if f.strip()})
    print(sign(payload, _load_key(args.key)))
    return 0


def _inspect(args: argparse.Namespace) -> int:
    text = "".join(args.code.split())
    data = decode_unverified(text) if text.startswith(PREFIX + ".") else _decode_request(text)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    #: کنسولِ ویندوز پیش‌فرض cp1252 است و پیامِ فارسی را نمی‌تواند چاپ کند — `keygen` کلید
    #: را می‌نوشت و بعد موقعِ چاپِ کلیدِ عمومی می‌افتاد، یعنی کلیدی بی‌کلیدِ عمومی.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="python -m app.licensing.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("keygen", help="ساختِ کلیدِ امضا (یک‌بار)")
    p.add_argument("--out", required=True)
    p.set_defaults(fn=_keygen)

    p = sub.add_parser("issue", help="صدورِ مجوز از روی کدِ درخواست")
    p.add_argument("--key", required=True, help="فایلِ PEMِ کلیدِ خصوصی")
    p.add_argument("--request", required=True, help="کدِ CUBREQ1 از سرورِ مشتری")
    p.add_argument("--seats", type=int, help="سقفِ حسابِ کاربری؛ خالی = بی‌سقف")
    p.add_argument("--days", type=int, help="مدت به روز؛ خالی = دائمی")
    p.add_argument("--grace", type=int, default=14, help="مهلت پس از انقضا (روز)")
    p.add_argument("--mods", help="ماژول‌های مجاز با کاما؛ خالی = همه")
    p.add_argument("--feat", help="قابلیت‌های پولی با کاما (مثلِ moadian)؛ خالی = همه")
    p.add_argument("--org", help="نامِ سازمان؛ خالی = همان که در درخواست آمده")
    p.add_argument("--lic", help="شناسه‌ی مجوز؛ خالی = تصادفی")
    p.set_defaults(fn=_issue)

    p = sub.add_parser("inspect", help="نمایشِ محتوای کدِ مجوز یا درخواست (بدونِ راستی‌آزمایی)")
    p.add_argument("code")
    p.set_defaults(fn=_inspect)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
