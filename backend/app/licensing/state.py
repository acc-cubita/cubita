"""وضعیتِ مجوزِ همین نصب — تنها جایی که «آیا این سرور حقِ ثبتِ سند دارد» تصمیم گرفته می‌شود.

**وضعیت ذخیره نمی‌شود، محاسبه می‌شود** — همان اصلِ `models/subscription.py`: تاریخ‌ها و
توکنِ امضاشده منبعِ حقیقت‌اند، و هر حالت (آزمایشی، فعال، مهلت، منقضی) از آن‌ها مشتق
می‌شود. هیچ کرونی لازم نیست که به‌موقع اجرا شود.

**هیچ حالتی خواندن را نمی‌بندد.** `writable=False` فقط ثبتِ تازه را می‌بندد
(`services/entitlements.py`)؛ دفترها، گزارش‌ها و پشتیبان‌گیری باز می‌مانند. داده روی
ماشینِ خودِ مشتری است و گروگان‌گرفتنش پشتِ مجوز، همان کاری است که `deps.py` صریحاً رد
کرده. به همین دلیل آزمایشیِ منقضی هم، برخلافِ ابر، فقط نوشتن را می‌بندد.

**دو نسخه از مجوز:** ردیفِ `enterprise_license` و فایلِ `license.lic`. هرکدام گم شود
از دیگری ساخته می‌شود و زودترین `installed_at` برنده است — پس نه پاک‌کردنِ فایل
آزمایشی را ریست می‌کند، نه بازگرداندنِ پشتیبانِ قدیمیِ دیتابیس فعال‌سازی را می‌بَرد.

**ساعتِ عقب‌رفته:** `last_seen_at` فقط جلو می‌رود. اگر ساعتِ سرور بیش از یک روز از آن
عقب‌تر باشد، کسی ساعت را برای دور زدنِ انقضا عقب برده (یا باتریِ مادربورد تمام شده) —
در هر دو حالت نوشتن تا درست‌شدنِ ساعت بسته می‌ماند، چون تاریخِ سندها هم غلط می‌شد.

**کش:** وضعیت برای چند دقیقه در حافظه‌ی پردازه می‌ماند تا هر درخواستِ نوشتن یک
راستی‌آزماییِ امضا و یک کوئری نباشد. نصبِ مجوز کش را خالی می‌کند.
"""

import json
import logging
import os
import platform
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.config import get_settings
from app.licensing import fingerprint, keys
from app.licensing.token import LicenseError, b64u_encode, verify
from app.models.enterprise_license import EnterpriseLicense
from app.models.tenant import Tenant

log = logging.getLogger("cubita.license")

CLOCK_TOLERANCE = timedelta(days=1)
CACHE_SECONDS = 300
REQUEST_PREFIX = "CUBREQ1"
_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def _fa(n: int) -> str:
    return str(n).translate(_FA_DIGITS)


@dataclass(frozen=True)
class LicenseStatus:
    #: trial | trial_expired | active | grace | expired | clock | mismatch | invalid
    mode: str
    writable: bool
    #: پیامِ فارسی برای کاربر وقتی چیزی کم است؛ برای آزمایشی/فعالِ عادی خالی.
    message: str | None = None
    days_left: int | None = None
    expires_at: datetime | None = None
    org: str | None = None
    seats: int | None = None
    #: None = بی‌محدودیت (آزمایشی، یا مجوزی که فهرست ندارد).
    mods: frozenset[str] | None = None
    feat: frozenset[str] | None = None
    license_id: str | None = None


_cache: tuple[float, LicenseStatus] | None = None


def reset_cache() -> None:
    global _cache
    _cache = None


def peek() -> LicenseStatus | None:
    """آخرین وضعیتِ محاسبه‌شده، بدونِ دیتابیس — برای توابعِ خالص مثلِ `allowed_modules`.

    هر مسیری که به آن‌ها می‌رسد اول `current(db)` را صدا می‌زند؛ اگر هنوز هیچ وضعیتی
    محاسبه نشده، فراخوان باید مثلِ آزمایشی (بی‌محدودیت) رفتار کند.
    """
    return _cache[1] if _cache else None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _days_until(end: datetime, now: datetime) -> int:
    # «۰ روز مانده» وقتی هنوز چند ساعت باقی است گمراه‌کننده است؛ رو به بالا گرد می‌شود.
    return max(0, -(-int((end - now).total_seconds()) // 86400))


# --- فایلِ license.lic -------------------------------------------------------


def license_file() -> Path:
    configured = get_settings().license_dir
    if configured:
        base = Path(configured)
    elif platform.system() == "Windows":
        base = Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "Cubita"
    else:
        base = Path(__file__).resolve().parents[2] / "var"
    return base / "license.lic"


def _read_file() -> dict | None:
    try:
        data = json.loads(license_file().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _write_file(row: EnterpriseLicense) -> None:
    data = {
        "install_id": str(row.install_id),
        "installed_at": row.installed_at.isoformat(),
        "token": row.token,
    }
    path = license_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        # نسخه‌ی دوم است، نه منبعِ اصلی؛ نبودنش نباید سرور را از کار بیندازد.
        log.warning("فایلِ مجوز نوشته نشد: %s", path)


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _load_row(db: Session, now: datetime) -> EnterpriseLicense:
    """ردیفِ مجوز، ساخته یا ترمیم‌شده از روی فایل."""
    saved = _read_file() or {}
    file_installed = _parse_time(saved.get("installed_at"))
    file_token = saved.get("token") if isinstance(saved.get("token"), str) else None
    try:
        file_install_id = uuid.UUID(str(saved.get("install_id")))
    except ValueError:
        file_install_id = None

    row = db.get(EnterpriseLicense, 1)
    if row is None:
        # دو درخواستِ همزمانِ اول نباید هر دو ردیف بسازند.
        db.execute(
            pg_insert(EnterpriseLicense)
            .values(
                id=1,
                install_id=file_install_id or uuid.uuid4(),
                installed_at=file_installed or now,
                token=file_token,
                last_seen_at=now,
            )
            .on_conflict_do_nothing(index_elements=["id"])
        )
        db.flush()
        row = db.get(EnterpriseLicense, 1)
        assert row is not None
    else:
        if file_installed and file_installed < row.installed_at:
            row.installed_at = file_installed
        if not row.token and file_token:
            row.token = file_token

    if (
        file_installed != row.installed_at
        or file_token != row.token
        or file_install_id != row.install_id
    ):
        _write_file(row)
    return row


# --- محاسبه‌ی وضعیت ---------------------------------------------------------


def evaluate(
    row: EnterpriseLicense,
    now: datetime,
    current_fp: dict[str, str],
    trusted: dict[str, str],
    trial_days: int,
) -> LicenseStatus:
    """خالص: از ردیف، ساعت و اثرانگشت یک وضعیت می‌سازد."""
    if now + CLOCK_TOLERANCE < row.last_seen_at:
        return LicenseStatus(
            mode="clock",
            writable=False,
            message=(
                "ساعتِ رایانه‌ی سرور از آخرین باری که کوبیتا اجرا شده عقب‌تر است. تاریخ و "
                "ساعتِ ویندوزِ سرور را درست کنید؛ تا آن موقع ثبتِ سندِ تازه بسته است."
            ),
        )

    if not row.token:
        end = row.installed_at + timedelta(days=trial_days)
        if now < end:
            return LicenseStatus(mode="trial", writable=True, days_left=_days_until(end, now), expires_at=end)
        return LicenseStatus(
            mode="trial_expired",
            writable=False,
            expires_at=end,
            days_left=0,
            message=(
                f"دوره‌ی آزمایشیِ {_fa(trial_days)}روزه تمام شده است. دفترها و گزارش‌ها در دسترس‌اند، "
                "ولی برای ثبتِ سندِ تازه باید نرم‌افزار را فعال کنید."
            ),
        )

    try:
        payload = verify(row.token, trusted)
    except LicenseError:
        return LicenseStatus(
            mode="invalid",
            writable=False,
            message="مجوزِ نصب‌شده دیگر معتبر نیست. برای کدِ تازه با پشتیبانیِ کوبیتا تماس بگیرید.",
        )

    common = dict(
        org=payload.get("org"),
        seats=payload.get("seats"),
        mods=frozenset(payload["mods"]) if isinstance(payload.get("mods"), list) else None,
        feat=frozenset(payload["feat"]) if isinstance(payload.get("feat"), list) else None,
        license_id=payload.get("lic"),
    )

    expected_fp = payload.get("fp")
    if isinstance(expected_fp, dict) and expected_fp and not fingerprint.matches(expected_fp, current_fp):
        return LicenseStatus(
            mode="mismatch",
            writable=False,
            message=(
                "این مجوز برای رایانه‌ی دیگری صادر شده است. اگر سرور را عوض کرده‌اید، برای "
                "انتقالِ مجوز با پشتیبانیِ کوبیتا تماس بگیرید."
            ),
            **common,
        )

    exp = payload.get("exp")
    if exp is None:
        return LicenseStatus(mode="active", writable=True, **common)
    end = datetime.fromtimestamp(int(exp), tz=timezone.utc)
    if now < end:
        return LicenseStatus(mode="active", writable=True, days_left=_days_until(end, now), expires_at=end, **common)
    grace_end = end + timedelta(days=int(payload.get("grace") or 0))
    if now < grace_end:
        left = _days_until(grace_end, now)
        return LicenseStatus(
            mode="grace",
            writable=True,
            days_left=left,
            expires_at=end,
            message=f"مجوز منقضی شده است؛ {_fa(left)} روز مهلت تا بسته‌شدنِ ثبتِ سند مانده. برای تمدید اقدام کنید.",
            **common,
        )
    return LicenseStatus(
        mode="expired",
        writable=False,
        days_left=0,
        expires_at=end,
        message=(
            "مجوزِ کوبیتا سازمانی منقضی شده است. دفترها و گزارش‌ها در دسترس‌اند، ولی برای "
            "ثبتِ سندِ تازه باید مجوز را تمدید کنید."
        ),
        **common,
    )


def current(db: Session) -> LicenseStatus:
    global _cache
    if _cache and time.monotonic() - _cache[0] < CACHE_SECONDS:
        return _cache[1]

    now = _now()
    row = _load_row(db, now)
    status = evaluate(
        row, now, fingerprint.current(), keys.TRUSTED_PUBLIC_KEYS, get_settings().enterprise_trial_days
    )
    if status.mode != "clock" and now > row.last_seen_at:
        row.last_seen_at = now
    db.flush()
    _cache = (time.monotonic(), status)
    return status


# --- فعال‌سازی --------------------------------------------------------------


def request_code(db: Session, org: str | None) -> str:
    """«کدِ درخواست» — کاربر آن را برای ستاد می‌فرستد و مجوزِ امضاشده پس می‌گیرد.

    فقط هشِ اثرانگشت در آن است، نه شناسه‌های خام. امضا ندارد: چیزی که در آن است را
    ستاد باید با فروش تطبیق بدهد، نه باور کند.
    """
    row = _load_row(db, _now())
    body = {
        "v": 1,
        "install": str(row.install_id),
        "fp": fingerprint.current(),
        "org": org,
    }
    return f"{REQUEST_PREFIX}.{b64u_encode(json.dumps(body, ensure_ascii=False, separators=(',', ':')).encode())}"


def install(db: Session, token: str) -> LicenseStatus:
    """توکن را می‌سنجد و نصب می‌کند؛ خطا را با `LicenseError` (پیامِ فارسی) می‌دهد."""
    payload = verify(token, keys.TRUSTED_PUBLIC_KEYS)
    now = _now()

    expected_fp = payload.get("fp")
    if isinstance(expected_fp, dict) and expected_fp and not fingerprint.matches(expected_fp, fingerprint.current()):
        raise LicenseError(
            "این مجوز برای رایانه‌ی دیگری صادر شده است. «کدِ درخواست» را از همین سرور بگیرید و بفرستید."
        )
    exp = payload.get("exp")
    if exp is not None:
        grace_end = datetime.fromtimestamp(int(exp), tz=timezone.utc) + timedelta(days=int(payload.get("grace") or 0))
        if now >= grace_end:
            raise LicenseError("این مجوز منقضی شده است؛ برای کدِ تازه با پشتیبانی تماس بگیرید.")

    row = _load_row(db, now)
    row.token = "".join(token.split())
    row.activated_at = now
    db.flush()
    _write_file(row)

    #: سقفِ کاربران از مجوز می‌آید؛ دعوتِ عضوِ تازه همین ستون را می‌سنجد
    #: (`services/members.py`). اعضای فعلی حتی اگر بیش از سقف باشند می‌مانند.
    seats = payload.get("seats")
    for tenant in db.query(Tenant).all():
        tenant.max_users = int(seats) if seats is not None else None
    db.flush()

    reset_cache()
    return current(db)
