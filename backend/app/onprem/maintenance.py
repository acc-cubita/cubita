"""نگهداریِ سرورِ سازمانی (ENTERPRISE_PLAN.md، M6): پشتیبانِ شبانه، زیپِ عیب‌یابی، و
برگرداندنِ دسترسیِ مالکی که رمزش را فراموش کرده.

**پشتیبانِ شبانه اختیاری نیست.** روی ابر پشتیبان کارِ ماست؛ روی سرورِ شرکت کسی نیست که
یادش باشد، و از‌دست‌رفتنِ دفترِ حسابداری روی دیسکِ خودشان برای ما هم فاجعه است. پس
سرویسِ API خودش هر ۲۴ ساعت یک `pg_dump` می‌گیرد (`BackupScheduler`، از `cubita-server serve`
روشن می‌شود — نه در توسعه و تست)، ۱۴ تای آخر را نگه می‌دارد، و اگر آخرین پشتیبان از
۴۸ ساعت کهنه‌تر شد مالک نوارِ قرمز می‌بیند. شکستِ پشتیبان در `last-error.txt` می‌ماند تا
همان نوار دلیلش را بگوید، نه فقط «کهنه است».

این نسخه‌ها روی **همان دیسکِ** سرورند و از خرابیِ دیسک نجات نمی‌دهند؛ نسخه‌ی دوم را
اسنپ‌شاتِ خودکارِ اپِ دسکتاپ روی رایانه‌ی مالک نگه می‌دارد (`electron/backup.ts`).

**زیپِ عیب‌یابی هیچ رازی ندارد:** `.env` و `secrets.json` و خودِ دیتابیس داخلش نمی‌روند، و
رمزِ داخلِ آدرسِ اتصال و توکن‌های JWT از لاگ‌ها پاک می‌شوند. مشتری این فایل را برای
پشتیبانی می‌فرستد؛ نباید کلیدِ خانه‌اش را هم همراهش بفرستد.
"""

from __future__ import annotations

import io
import json
import logging
import os
import platform
import re
import shutil
import sys
import threading
import time
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.onprem.provision import Layout, ProvisionError, dump

log = logging.getLogger("cubita.maintenance")

NIGHTLY_PREFIX = "nightly-"
#: دو هفته: هم خطای دیرفهمیده‌شده (سندی که سه روز پیش اشتباه پاک شد) را پوشش می‌دهد، هم
#: دیسکِ یک رایانه‌ی اداری را پر نمی‌کند.
KEEP_NIGHTLY = 14
DUE_HOURS = 24
#: یک شبِ ازدست‌رفته (سرورِ خاموش در تعطیلی) هنوز هشدار نیست؛ دو شب هست.
STALE_HOURS = 48
ERROR_FILE = "last-error.txt"

#: پشتیبانِ دستی و زمان‌بند نباید هم‌زمان دو pg_dump روی یک دیسک بزنند.
_backup_lock = threading.Lock()


class BackupBusy(RuntimeError):
    pass


def resolve_pg_bin() -> Path | None:
    """`pgsql/bin`ِ همراهِ بسته، کنارِ `cubita-server.exe`. در توسعه `PG_BIN` یا هیچ."""
    if os.environ.get("PG_BIN"):
        return Path(os.environ["PG_BIN"])
    if getattr(sys, "frozen", False):
        candidate = Path(sys.executable).resolve().parent / "pgsql" / "bin"
        if candidate.exists():
            return candidate
    return None


# --- پشتیبان ------------------------------------------------------------------


@dataclass
class BackupStatus:
    #: آخرین پشتیبانِ کامل (شبانه، دستی یا پیش از ارتقا) به ISOِ UTC.
    last_at: str | None
    age_hours: float | None
    count: int
    total_bytes: int
    folder: str
    last_error: str | None
    stale: bool


def _dumps(layout: Layout) -> list[Path]:
    if not layout.backups.exists():
        return []
    return sorted(layout.backups.glob("*.dump"), key=lambda p: p.stat().st_mtime)


def status(layout: Layout, *, now: float | None = None) -> BackupStatus:
    now = time.time() if now is None else now
    dumps = _dumps(layout)
    last = dumps[-1] if dumps else None
    age = (now - last.stat().st_mtime) / 3600 if last else None
    error_file = layout.backups / ERROR_FILE
    error = error_file.read_text(encoding="utf-8").strip() if error_file.exists() else None
    return BackupStatus(
        last_at=(
            datetime.fromtimestamp(last.stat().st_mtime, tz=timezone.utc).isoformat() if last else None
        ),
        age_hours=round(age, 1) if age is not None else None,
        count=len(dumps),
        total_bytes=sum(p.stat().st_size for p in dumps),
        folder=str(layout.backups),
        last_error=error or None,
        stale=age is None or age > STALE_HOURS or bool(error),
    )


def is_due(layout: Layout, *, now: float | None = None) -> bool:
    age = status(layout, now=now).age_hours
    return age is None or age >= DUE_HOURS


def prune(layout: Layout, keep: int = KEEP_NIGHTLY) -> int:
    """فقط پشتیبان‌های شبانه/دستی دور ریخته می‌شوند؛ دامپِ پیش از ارتقا دست‌نخورده می‌ماند."""
    nightly = [p for p in _dumps(layout) if p.name.startswith(NIGHTLY_PREFIX)]
    doomed = nightly[:-keep] if keep > 0 else nightly
    for path in doomed:
        path.unlink(missing_ok=True)
    return len(doomed)


def run_backup(layout: Layout, pg_bin: Path, migration_url: str) -> Path:
    """یک پشتیبانِ کامل؛ خطا در `last-error.txt` می‌ماند تا نوارِ هشدار دلیلش را بگوید."""
    if not _backup_lock.acquire(blocking=False):
        raise BackupBusy("پشتیبان‌گیری همین حالا در جریان است.")
    try:
        name = f"{NIGHTLY_PREFIX}{time.strftime('%Y%m%d-%H%M%S')}.dump"
        try:
            target = dump(pg_bin, layout, migration_url, name)
        except ProvisionError as exc:
            layout.backups.mkdir(parents=True, exist_ok=True)
            (layout.backups / ERROR_FILE).write_text(
                f"{datetime.now(timezone.utc).isoformat()}\n{exc}", encoding="utf-8"
            )
            raise
        (layout.backups / ERROR_FILE).unlink(missing_ok=True)
        prune(layout)
        return target
    finally:
        _backup_lock.release()


class BackupScheduler(threading.Thread):
    """هر نیم ساعت نگاه می‌کند؛ اگر ۲۴ ساعت از آخرین پشتیبان گذشته، یکی می‌گیرد.

    «هر ۲۴ ساعت از آخری» به‌جای «ساعتِ ۲ بامداد»: سرورِ شرکت شب‌ها معمولاً خاموش است و
    زمان‌بندِ ساعت‌ثابت آن‌وقت هرگز اجرا نمی‌شد. `pg_dump` قفل نمی‌گیرد و کارِ کاربران را
    در طولِ روز نمی‌خواباند.
    """

    def __init__(
        self,
        layout: Layout,
        pg_bin: Path,
        migration_url: str,
        *,
        initial_delay: float = 300,
        interval: float = 1800,
    ):
        super().__init__(name="cubita-backup", daemon=True)
        self.layout = layout
        self.pg_bin = pg_bin
        self.migration_url = migration_url
        self.initial_delay = initial_delay
        self.interval = interval
        self.stop_event = threading.Event()

    def tick(self) -> Path | None:
        if not is_due(self.layout):
            return None
        try:
            return run_backup(self.layout, self.pg_bin, self.migration_url)
        except (ProvisionError, BackupBusy, OSError) as exc:
            log.error("پشتیبانِ خودکار شکست خورد: %s", exc)
            return None

    def run(self) -> None:
        if self.stop_event.wait(self.initial_delay):
            return
        while True:
            self.tick()
            if self.stop_event.wait(self.interval):
                return


# --- زیپِ عیب‌یابی --------------------------------------------------------------

#: هرگز داخلِ زیپ نمی‌روند، حتی اگر روزی کسی آن‌ها را به پوشه‌ی لاگ ببرد.
_NEVER = {".env", "secrets.json", "license.lic"}
_LOG_TAIL_BYTES = 1_000_000

_URL_PASSWORD = re.compile(r"(://[^:/@\s]+):[^@\s]+@")
_JWT = re.compile(r"eyJ[\w-]+\.[\w-]+\.[\w-]+")
_SECRET_LINE = re.compile(r"(?im)^(\s*[\w.]*(?:PASSWORD|SECRET|TOKEN|KEY)\w*\s*[=:]\s*).+$")


def redact(text: str) -> str:
    text = _URL_PASSWORD.sub(r"\1:***@", text)
    text = _JWT.sub("eyJ***", text)
    return _SECRET_LINE.sub(r"\1***", text)


def _tail(path: Path, limit: int = _LOG_TAIL_BYTES) -> str:
    size = path.stat().st_size
    with path.open("rb") as fh:
        if size > limit:
            fh.seek(size - limit)
        data = fh.read()
    return data.decode("utf-8", errors="replace")


def _log_files(layout: Layout) -> list[tuple[str, Path]]:
    found: list[tuple[str, Path]] = []
    if layout.logs.exists():
        found += [(f"logs/{p.name}", p) for p in layout.logs.iterdir() if p.is_file()]
    pg_logs = layout.pgdata / "log"
    if pg_logs.exists():
        newest = sorted((p for p in pg_logs.iterdir() if p.is_file()), key=lambda p: p.stat().st_mtime)[-3:]
        found += [(f"pg-log/{p.name}", p) for p in newest]
    return [(arc, p) for arc, p in found if p.name not in _NEVER]


def base_info(layout: Layout) -> dict:
    """آنچه بدونِ دیتابیس و بدونِ API هم به دست می‌آید — CLI وقتی سرویس بالا نیست همین را دارد."""
    from app.version import app_version

    info: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "version": app_version(),
        "python": sys.version.split()[0],
        "os": platform.platform(),
        "machine": platform.node(),
        "home": str(layout.home),
        "backups": asdict(status(layout)),
    }
    try:
        usage = shutil.disk_usage(layout.home if layout.home.exists() else Path.cwd())
        info["disk"] = {"free_gb": round(usage.free / 1e9, 1), "total_gb": round(usage.total / 1e9, 1)}
    except OSError as exc:
        info["disk"] = str(exc)
    if layout.updates.exists():
        info["updates"] = sorted(str(p.relative_to(layout.updates)) for p in layout.updates.rglob("*") if p.is_file())
    return info


def diagnostics_zip(layout: Layout, info: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("info.json", redact(json.dumps(info, ensure_ascii=False, indent=2, default=str)))
        for arc, path in _log_files(layout):
            try:
                zf.writestr(arc, redact(_tail(path)))
            except OSError as exc:
                zf.writestr(arc + ".error.txt", str(exc))
    return buf.getvalue()


# --- مالکِ رمزفراموش‌کرده ----------------------------------------------------------

#: کسی که پشتِ خودِ سرور نشسته همان لحظه کد را وارد می‌کند.
OWNER_RESET_HOURS = 1


def issue_owner_reset(migration_url: str, email: str | None = None) -> list[tuple[str, str, str]]:
    """کدِ بازنشانیِ رمز برای مالک(های) فعال — `(email, name, code)`.

    **ریشه‌ی اعتماد دسترسیِ فیزیکی به سرور است:** این فقط از `cubita-server` روی خودِ
    رایانه‌ی سرور و با اجازه‌ی مدیرِ ویندوز اجرا می‌شود (`.env` جز برای مدیر و سرویس
    خواندنی نیست). سرورِ آفلاین راهِ دیگری ندارد — ایمیل و پیامکی در کار نیست. کار در
    دفترِ حسابرسیِ همان کسب‌وکار ثبت می‌شود.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    import app.models  # noqa: F401 — همه‌ی مدل‌ها برای رابطه‌ها

    engine = create_engine(migration_url)
    try:
        with Session(engine) as db:
            out = owner_reset_codes(db, email)
            db.commit()
            return out
    finally:
        engine.dispose()


def owner_reset_codes(db, email: str | None = None) -> list[tuple[str, str, str]]:
    from app.models.tenant import Membership
    from app.models.user import Role, User
    from app.services import tokens
    from app.services.members import OWNER_ROLE_KEY, audit_member

    query = (
        db.query(Membership)
        .join(Role, Role.id == Membership.role_id)
        .join(User, User.id == Membership.user_id)
        .filter(Role.key == OWNER_ROLE_KEY, Membership.status == "active", User.active.is_(True))
    )
    if email:
        query = query.filter(User.email == email.strip().lower())
    out: list[tuple[str, str, str]] = []
    for membership in query.all():
        code = tokens.issue_password_reset(db, membership.user_id, short=True, hours=OWNER_RESET_HOURS)
        audit_member(db, membership, None, "صدورِ کدِ بازنشانیِ رمزِ مالک روی خودِ سرور (cubita-server)")
        out.append((membership.user.email, membership.user.name, code))
    return out
