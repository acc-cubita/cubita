"""صدور و مدیریتِ مجوزهای «کوبیتا سازمانی» — سمتِ ابر.

هر مجوز از دو راه به دستِ مشتری می‌رسد و **هر دو از `bind_and_issue` می‌گذرند**:
- آنلاین: سرورِ مشتری کدِ فعال‌سازی + کدِ درخواست را به `/api/enterprise/activate` می‌فرستد.
- آفلاین: مشتری کدِ درخواست را برای پشتیبانی می‌فرستد و کارمند در پنل صادر می‌کند.

یک مسیرِ مشترک یعنی قاعده‌ی «هر مجوز یک دستگاه» در هر دو یکسان اجرا می‌شود؛ اگر
صدورِ آفلاین قاعده‌ی خودش را داشت، دیر یا زود راهِ دور زدنِ دیگری می‌شد.
"""

import hashlib
import secrets
import time
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.licensing import fingerprint
from app.licensing.state import decode_request
from app.licensing.token import FORMAT_VERSION, LicenseError, sign
from app.models.enterprise_license_registry import EnterpriseLicenseEvent, EnterpriseLicenseRecord

#: الفبای Crockford بدونِ I/L/O/U — نویسه‌هایی که پشتِ تلفن با ۱ و ۰ اشتباه می‌شوند نیستند.
_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_CODE_GROUPS = 4
_GROUP_LEN = 4  # ۱۶ نویسه = ۸۰ بیت


def new_code() -> str:
    raw = "".join(secrets.choice(_ALPHABET) for _ in range(_CODE_GROUPS * _GROUP_LEN))
    return "-".join(raw[i : i + _GROUP_LEN] for i in range(0, len(raw), _GROUP_LEN))


def normalize_code(code: str) -> str:
    """فاصله، خط‌تیره و حروفِ کوچک بی‌اثرند؛ O/I/L به ۰/۱ برمی‌گردند (خطای رایجِ تایپ)."""
    cleaned = "".join(ch for ch in code.upper() if ch.isalnum())
    return cleaned.translate(str.maketrans({"O": "0", "I": "1", "L": "1"}))


def hash_code(code: str) -> str:
    return hashlib.sha256(f"cubita-activation-v1:{normalize_code(code)}".encode()).hexdigest()


def _lic_id() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(10))


@lru_cache(maxsize=1)
def _signing_key(path: str) -> Ed25519PrivateKey:
    key = load_pem_private_key(Path(path).read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("not an Ed25519 key")
    return key


def signing_key() -> Ed25519PrivateKey:
    path = get_settings().license_signing_key_file
    try:
        if not path:
            raise FileNotFoundError(path)
        return _signing_key(path)
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "صدورِ مجوز روی این سرور پیکربندی نشده است (کلیدِ امضا در دسترس نیست).",
        ) from exc


def _event(db: Session, record: EnterpriseLicenseRecord, kind: str, actor: str, detail: dict | None = None) -> None:
    db.add(EnterpriseLicenseEvent(license_id=record.id, kind=kind, actor=actor, detail=detail))


def create(
    db: Session,
    *,
    org_name: str,
    contact: str | None,
    seats: int | None,
    days: int | None,
    grace_days: int,
    mods: list[str] | None,
    feat: list[str] | None,
    note: str | None,
    actor: str,
) -> tuple[EnterpriseLicenseRecord, str]:
    """مجوزِ تازه + کدِ فعال‌سازی. **کد فقط همین‌جا برمی‌گردد** — در دیتابیس فقط هشش هست."""
    code = new_code()
    record = EnterpriseLicenseRecord(
        lic_id=_lic_id(),
        org_name=org_name.strip(),
        contact=(contact or "").strip() or None,
        seats=seats,
        mods=mods,
        feat=feat,
        expires_at=datetime.now(timezone.utc) + timedelta(days=days) if days else None,
        grace_days=grace_days,
        code_hash=hash_code(code),
        code_hint=normalize_code(code)[-4:],
        note=(note or "").strip() or None,
        created_by_email=actor,
    )
    db.add(record)
    db.flush()
    _event(db, record, "create", actor, {"seats": seats, "days": days})
    return record, code


def regenerate_code(db: Session, record: EnterpriseLicenseRecord, actor: str) -> str:
    code = new_code()
    record.code_hash = hash_code(code)
    record.code_hint = normalize_code(code)[-4:]
    _event(db, record, "code", actor)
    db.flush()
    return code


def _issue_token(record: EnterpriseLicenseRecord, install: str, fp: dict) -> str:
    payload: dict = {
        "v": FORMAT_VERSION,
        "lic": record.lic_id,
        "edition": "enterprise",
        "org": record.org_name,
        "iat": int(time.time()),
        "install": install,
        "fp": fp,
        "grace": record.grace_days,
    }
    if record.expires_at is not None:
        payload["exp"] = int(record.expires_at.timestamp())
    if record.seats is not None:
        payload["seats"] = record.seats
    if record.mods is not None:
        payload["mods"] = list(record.mods)
    if record.feat is not None:
        payload["feat"] = list(record.feat)
    return sign(payload, signing_key())


def bind_and_issue(db: Session, record: EnterpriseLicenseRecord, request_code: str, actor: str) -> str:
    """کدِ درخواست را به این مجوز گره می‌زند و توکنِ امضاشده برمی‌گرداند.

    دستگاهِ همان مجوز می‌تواند هر چند بار بخواهد دوباره بگیرد (نصبِ دوباره، تمدید)؛
    دستگاهِ **دیگر** نه — آن کارِ «انتقال» در پنل است. خطاها `LicenseError` با پیامِ
    فارسی‌اند؛ فراخوان تصمیم می‌گیرد کدِ HTTP چه باشد.
    """
    request = decode_request(request_code)
    if record.status != "active":
        _event(db, record, "refuse", actor, {"reason": "revoked"})
        raise LicenseError("این مجوز باطل شده است؛ با پشتیبانیِ کوبیتا تماس بگیرید.")
    if record.expires_at is not None:
        if datetime.now(timezone.utc) >= record.expires_at + timedelta(days=record.grace_days):
            _event(db, record, "refuse", actor, {"reason": "expired"})
            raise LicenseError("این مجوز منقضی شده است؛ برای تمدید با پشتیبانی تماس بگیرید.")
    if record.fp and not fingerprint.matches(record.fp, request["fp"]):
        _event(db, record, "refuse", actor, {"reason": "other_machine", "install": request["install"]})
        raise LicenseError(
            "این مجوز روی رایانه‌ی دیگری فعال شده است. اگر سرور را عوض کرده‌اید، برای انتقالِ "
            "مجوز با پشتیبانیِ کوبیتا تماس بگیرید."
        )

    now = datetime.now(timezone.utc)
    first = not record.fp
    if first:
        record.bound_at = now
    #: اثرانگشتِ تازه ذخیره می‌شود (نه اولی): اگر یک جزء عوض شده و ۲ از ۳ هنوز جور است،
    #: از این به بعد با وضعیتِ فعلیِ دستگاه مقایسه شود، نه با وضعیتِ روزِ نصب.
    record.fp = request["fp"]
    record.install_id = request["install"] or record.install_id
    record.last_issued_at = now
    record.issue_count = (record.issue_count or 0) + 1
    token = _issue_token(record, record.install_id or "", request["fp"])
    _event(db, record, "activate" if actor == "online" else "issue", actor, {"install": request["install"], "first": first})
    db.flush()
    return token


def activate_online(db: Session, code: str, request_code: str) -> str:
    record = (
        db.query(EnterpriseLicenseRecord).filter(EnterpriseLicenseRecord.code_hash == hash_code(code)).one_or_none()
    )
    if record is None:
        raise LicenseError("کدِ فعال‌سازی درست نیست؛ آن را همان‌طور که دریافت کرده‌اید وارد کنید.")
    return bind_and_issue(db, record, request_code, "online")


def transfer(db: Session, record: EnterpriseLicenseRecord, actor: str) -> None:
    """گره را باز می‌کند تا دستگاهِ تازه فعال شود. توکنِ دستگاهِ قبلی خودکفاست و تا انقضا
    کار می‌کند — برای همین انتقال با تماس و توافق است، نه با یک دکمه‌ی سلف‌سرویس."""
    _event(db, record, "transfer", actor, {"install": record.install_id})
    record.fp = None
    record.install_id = None
    record.bound_at = None
    db.flush()


def revoke(db: Session, record: EnterpriseLicenseRecord, actor: str) -> None:
    record.status = "revoked"
    record.revoked_at = datetime.now(timezone.utc)
    _event(db, record, "revoke", actor)
    db.flush()
