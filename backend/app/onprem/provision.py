"""راه‌اندازیِ سرورِ سازمانی: Postgresِ همراه، نقش‌ها، `.env`، مهاجرت، و سنجشِ RLS.

**بی‌خطر برای اجرای دوباره.** نصابِ نسخه‌ی تازه، تعمیر، یا اجرای دستیِ دوباره همین را
صدا می‌زنند: پوشه‌ی دادهِ موجود دوباره initdb نمی‌شود، رازهای موجود عوض نمی‌شوند (وگرنه
کلیدِ رمزگذاریِ مؤدیان و همه‌ی نشست‌ها از دست می‌رفت)، و نقش‌ها فقط تنظیم می‌شوند.

**دو نقش، همان تفکیکِ `scripts/setup_db_roles.sql`:**
- `cubita_migrate` مالکِ دیتابیس و جدول‌هاست و `BYPASSRLS` دارد — برای مهاجرت‌های داده و
  `pg_dump` (بدونِ آن پشتیبان بی‌صدا ناقص بود).
- `cubita_app` برنامه با آن کار می‌کند؛ نه مالک است نه `BYPASSRLS`. دسترسی‌اش روی جدول‌های
  آینده با `ALTER DEFAULT PRIVILEGES FOR ROLE cubita_migrate` داده می‌شود — بدونِ `FOR ROLE`
  پیش‌فرض‌ها روی جدول‌هایی می‌نشست که superuser می‌سازد، نه مهاجرت.

**آخرین قدم سنجشِ RLS است، نه تزئین:** اتصال با `cubita_app` بدونِ `app.tenant_id` باید
صفر ردیف ببیند. اگر نصاب نقش‌ها را اشتباه بسازد (مثلاً برنامه با superuser وصل شود)،
جداسازی بی‌صدا خاموش است و هیچ خطایی آن را نشان نمی‌دهد — جز همین.
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

APP_ROLE = "cubita_app"
MIGRATE_ROLE = "cubita_migrate"
DB_NAME = "cubita"
SUPERUSER = "postgres"
DEFAULT_PG_PORT = 5433
DEFAULT_API_PORT = 8420

#: جدولی که حتماً مستأجرمحور و FORCE RLS است — پروبِ سنجشِ ایزوله‌سازی.
RLS_PROBE_TABLE = "accounts"


class ProvisionError(RuntimeError):
    """پیامِ فارسیِ قابلِ نمایش به کسی که نصاب را اجرا کرده."""


@dataclass(frozen=True)
class Layout:
    """چیدمانِ پوشه‌ی داده (پیش‌فرض `C:\\ProgramData\\Cubita`)."""

    home: Path

    @property
    def pgdata(self) -> Path:
        return self.home / "pgdata"

    @property
    def logs(self) -> Path:
        return self.home / "logs"

    @property
    def env_file(self) -> Path:
        #: `Settings` فایلِ `.env` را از پوشه‌ی جاری می‌خواند؛ سرویس با همین پوشه اجرا می‌شود.
        return self.home / ".env"

    @property
    def secrets_file(self) -> Path:
        return self.home / "secrets.json"

    @property
    def backups(self) -> Path:
        return self.home / "backups"

    @property
    def updates(self) -> Path:
        return self.home / "updates"


# --- رازها و .env -------------------------------------------------------------


def _token(n: int = 48) -> str:
    return secrets.token_urlsafe(n)


def load_or_create_secrets(layout: Layout) -> dict:
    """رازهای این نصب. **فقط یک‌بار ساخته می‌شوند** — عوض‌کردنِ `SECRETS_KEY` یعنی کلیدِ
    امضای مؤدیانِ رمزشده دیگر باز نمی‌شود، و عوض‌کردنِ `JWT_SECRET` همه را بیرون می‌اندازد."""
    if layout.secrets_file.exists():
        data = json.loads(layout.secrets_file.read_text(encoding="utf-8"))
        missing = {"superuser_password", "app_password", "migrate_password", "jwt_secret", "secrets_key"} - set(data)
        if missing:
            raise ProvisionError(f"فایلِ رازها ناقص است ({', '.join(sorted(missing))}); آن را دستی پاک نکنید.")
        return data
    data = {
        "superuser_password": _token(24),
        "app_password": _token(24),
        "migrate_password": _token(24),
        "jwt_secret": _token(48),
        "secrets_key": _token(48),
    }
    layout.home.mkdir(parents=True, exist_ok=True)
    layout.secrets_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def db_url(user: str, password: str, port: int) -> str:
    return f"postgresql+psycopg://{user}:{quote(password, safe='')}@127.0.0.1:{port}/{DB_NAME}"


def render_env(secrets_: dict, pg_port: int, api_port: int, license_dir: Path | None = None) -> str:
    """`.env`ِ سرورِ سازمانی. برنامه با `cubita_app` وصل می‌شود، نه با مالک یا superuser."""
    lines = [
        "# ساخته‌شده به دستِ نصابِ کوبیتا سازمانی — دستی ویرایش نکنید؛ «cubita-server setup» دوباره می‌سازدش.",
        "EDITION=enterprise",
        "ENV=production",
        "ZARINPAL_SANDBOX=true",
        f"DATABASE_URL={db_url(APP_ROLE, secrets_['app_password'], pg_port)}",
        f"MIGRATION_DATABASE_URL={db_url(MIGRATE_ROLE, secrets_['migrate_password'], pg_port)}",
        f"JWT_SECRET={secrets_['jwt_secret']}",
        f"SECRETS_KEY={secrets_['secrets_key']}",
        "API_HOST=0.0.0.0",
        f"API_PORT={api_port}",
        #: نسخه‌ی دومِ مجوز کنارِ همین داده — نه جای پیش‌فرض، اگر پوشه‌ی داده جابه‌جا شده باشد.
        *([f"LICENSE_DIR={license_dir}"] if license_dir else []),
        "",
    ]
    return "\n".join(lines)


def read_env(layout: Layout) -> dict[str, str]:
    out: dict[str, str] = {}
    if not layout.env_file.exists():
        return out
    for line in layout.env_file.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            out[key.strip()] = value.strip()
    return out


# --- Postgres ----------------------------------------------------------------


def _run(args: list[str], *, env: dict | None = None, timeout: int = 180) -> subprocess.CompletedProcess:
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, **(env or {})},
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProvisionError(f"اجرای {Path(args[0]).name} ممکن نشد: {exc}") from exc
    if proc.returncode != 0:
        raise ProvisionError(f"{Path(args[0]).name} شکست خورد:\n{(proc.stderr or proc.stdout).strip()[-2000:]}")
    return proc


def _exe(pg_bin: Path, name: str) -> str:
    for candidate in (pg_bin / f"{name}.exe", pg_bin / name):
        if candidate.exists():
            return str(candidate)
    raise ProvisionError(f"{name} در {pg_bin} پیدا نشد؛ بسته‌ی PostgreSQL ناقص است.")


def init_cluster(pg_bin: Path, layout: Layout, superuser_password: str, port: int) -> bool:
    """initdb، فقط اگر پوشه‌ی داده هنوز نیست. برمی‌گرداند که کلاستر تازه ساخته شد یا نه."""
    if (layout.pgdata / "PG_VERSION").exists():
        return False
    if layout.pgdata.exists() and any(layout.pgdata.iterdir()):
        raise ProvisionError(f"پوشه‌ی {layout.pgdata} خالی نیست ولی کلاسترِ PostgreSQL هم نیست؛ دست نمی‌زنم.")
    layout.pgdata.mkdir(parents=True, exist_ok=True)
    pwfile = layout.home / ".pwfile"
    pwfile.write_text(superuser_password, encoding="utf-8")
    try:
        _run(
            [
                _exe(pg_bin, "initdb"),
                "-D", str(layout.pgdata),
                "-U", SUPERUSER,
                f"--pwfile={pwfile}",
                "--auth-local=scram-sha-256",
                "--auth-host=scram-sha-256",
                "--encoding=UTF8",
                "--locale=C",
            ]
        )
    finally:
        pwfile.unlink(missing_ok=True)

    #: فقط localhost: کلاینت‌ها هرگز مستقیم به Postgres وصل نمی‌شوند، فقط به API.
    with open(layout.pgdata / "postgresql.conf", "a", encoding="utf-8") as fh:
        fh.write(
            "\n# کوبیتا سازمانی\n"
            "listen_addresses = 'localhost'\n"
            f"port = {port}\n"
            "max_connections = 100\n"
        )
    return True


def pg_ctl(pg_bin: Path, layout: Layout, action: str) -> None:
    """شروع/توقفِ دستیِ Postgres در طولِ راه‌اندازی.

    **خروجی به DEVNULL می‌رود، نه pipe:** پردازه‌ی postgres که `pg_ctl start` می‌سازد
    دسته‌های خروجیِ ما را به ارث می‌برد و هرگز نمی‌بندد، پس `capture_output` تا ابد منتظرِ
    EOF می‌ماند (در اولین اجرای واقعی همین‌طور گیر کرد). خطاها در لاگِ فایلی (`-l`) هستند.
    """
    layout.logs.mkdir(parents=True, exist_ok=True)
    log_file = layout.logs / "postgres-setup.log"
    args = [_exe(pg_bin, "pg_ctl"), "-D", str(layout.pgdata), "-w", "-t", "60"]
    if action == "start":
        args += ["-l", str(log_file), "start"]
    else:
        args += ["-m", "fast", "stop"]
    try:
        code = subprocess.run(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=90,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).returncode
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProvisionError(f"pg_ctl {action} اجرا نشد: {exc}") from exc
    if code != 0:
        tail = log_file.read_text(encoding="utf-8", errors="replace")[-1500:] if log_file.exists() else ""
        raise ProvisionError(f"pg_ctl {action} شکست خورد (کد {code}).\n{tail}")


def is_running(pg_bin: Path, layout: Layout) -> bool:
    proc = subprocess.run(
        [_exe(pg_bin, "pg_ctl"), "-D", str(layout.pgdata), "status"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return proc.returncode == 0


def _connect(user: str, password: str, port: int, dbname: str):
    import psycopg

    last: Exception | None = None
    for _ in range(20):
        try:
            return psycopg.connect(
                host="127.0.0.1", port=port, user=user, password=password, dbname=dbname, autocommit=True
            )
        except psycopg.OperationalError as exc:
            last = exc
            time.sleep(0.5)
    raise ProvisionError(f"اتصال به PostgreSQL ممکن نشد: {last}")


def bootstrap_database(secrets_: dict, port: int) -> None:
    """نقش‌ها، دیتابیس و پیش‌فرض‌های دسترسی. بی‌خطر برای اجرای دوباره."""
    from psycopg import sql

    with _connect(SUPERUSER, secrets_["superuser_password"], port, "postgres") as conn:
        for role in (APP_ROLE, MIGRATE_ROLE):
            exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,)).fetchone()
            if not exists:
                conn.execute(sql.SQL("CREATE ROLE {} LOGIN").format(sql.Identifier(role)))
        conn.execute(
            sql.SQL("ALTER ROLE {} PASSWORD {} NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE").format(
                sql.Identifier(APP_ROLE), sql.Literal(secrets_["app_password"])
            )
        )
        conn.execute(
            sql.SQL("ALTER ROLE {} PASSWORD {} NOSUPERUSER BYPASSRLS NOCREATEDB NOCREATEROLE").format(
                sql.Identifier(MIGRATE_ROLE), sql.Literal(secrets_["migrate_password"])
            )
        )
        if not conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,)).fetchone():
            conn.execute(
                sql.SQL("CREATE DATABASE {} OWNER {} ENCODING 'UTF8' TEMPLATE template0").format(
                    sql.Identifier(DB_NAME), sql.Identifier(MIGRATE_ROLE)
                )
            )

    with _connect(SUPERUSER, secrets_["superuser_password"], port, DB_NAME) as conn:
        app, mig = sql.Identifier(APP_ROLE), sql.Identifier(MIGRATE_ROLE)
        for stmt in (
            "REVOKE ALL ON DATABASE {db} FROM PUBLIC",
            "GRANT CONNECT ON DATABASE {db} TO {app}, {mig}",
            "ALTER SCHEMA public OWNER TO {mig}",
            "REVOKE CREATE ON SCHEMA public FROM PUBLIC",
            "GRANT USAGE ON SCHEMA public TO {app}",
            "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {app}",
            "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {app}",
            "ALTER DEFAULT PRIVILEGES FOR ROLE {mig} IN SCHEMA public "
            "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {app}",
            "ALTER DEFAULT PRIVILEGES FOR ROLE {mig} IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {app}",
            "ALTER DEFAULT PRIVILEGES FOR ROLE {mig} IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO {app}",
        ):
            conn.execute(sql.SQL(stmt).format(db=sql.Identifier(DB_NAME), app=app, mig=mig))


def run_migrations(migration_url: str, alembic_dir: Path) -> str:
    """`alembic upgrade head` با نقشِ مالک. `DATABASE_URL` برای همین پردازه به نقشِ مهاجرت
    اشاره می‌کند، چون `alembic/env.py` نشانی را از `Settings` می‌خواند."""
    from alembic import command
    from alembic.config import Config

    from app.config import get_settings

    os.environ["DATABASE_URL"] = migration_url
    get_settings.cache_clear()
    cfg = Config()
    cfg.set_main_option("script_location", str(alembic_dir))
    command.upgrade(cfg, "head")

    import psycopg

    raw = migration_url.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(raw) as conn:
        row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
    return row[0] if row else ""


def current_revision(migration_url: str) -> str | None:
    """نسخه‌ی فعلیِ دیتابیس؛ None یعنی هنوز هیچ مهاجرتی اجرا نشده (نصبِ تازه)."""
    import psycopg

    raw = migration_url.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(raw) as conn:
        exists = conn.execute("SELECT to_regclass('public.alembic_version')").fetchone()[0]
        if not exists:
            return None
        row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
        return row[0] if row else None


def head_revision(alembic_dir: Path) -> str:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config()
    cfg.set_main_option("script_location", str(alembic_dir))
    return ScriptDirectory.from_config(cfg).get_current_head() or ""


def dump(pg_bin: Path, layout: Layout, migration_url: str, name: str) -> Path:
    """`pg_dump -Fc` با نقشِ مالک (BYPASSRLS — بی‌آن پشتیبان بی‌صدا فقط ردیف‌های قابل‌دیدن را
    می‌گرفت). اول در `.partial` نوشته می‌شود و بعد جابه‌جا، تا دامپِ نیمه‌کاره (قطعِ برق،
    پرشدنِ دیسک) هرگز به‌جای پشتیبانِ سالم شمرده نشود."""
    from sqlalchemy.engine import make_url

    url = make_url(migration_url)
    layout.backups.mkdir(parents=True, exist_ok=True)
    target = layout.backups / name
    partial = target.with_name(target.name + ".partial")
    _run(
        [
            _exe(pg_bin, "pg_dump"),
            "-h", url.host or "127.0.0.1",
            "-p", str(url.port or DEFAULT_PG_PORT),
            "-U", url.username or MIGRATE_ROLE,
            "-Fc",
            "-f", str(partial),
            url.database or DB_NAME,
        ],
        env={"PGPASSWORD": url.password or ""},
        timeout=3600,
    )
    partial.replace(target)
    return target


def backup_before_upgrade(pg_bin: Path, layout: Layout, secrets_: dict, port: int, revision: str) -> Path:
    """پیش از مهاجرتِ ارتقا. **اگر شکست بخورد مهاجرت اجرا نمی‌شود**: ارتقایی که پشتیبان
    ندارد، ریسکی است که دفترِ حسابداریِ شرکت نباید بپردازد."""
    stamp = time.strftime("%Y%m%d-%H%M%S")
    url = db_url(MIGRATE_ROLE, secrets_["migrate_password"], port)
    return dump(pg_bin, layout, url, f"pre-upgrade-{revision}-{stamp}.dump")


def verify_isolation(app_url: str) -> int:
    """جداسازیِ داده زنده است؟ با همان نقشی که برنامه وصل می‌شود.

    روی دیتابیسِ تازه شمردنِ ردیف به‌تنهایی چیزی ثابت نمی‌کند (جدول خالی است)، پس سه
    شرطِ ساختاری سنجیده می‌شود که هرکدام به‌تنهایی جداسازی را بی‌صدا خاموش می‌کند: نقشِ
    دورزن، نبودِ FORCE، نبودِ سیاست. روی دیتابیسِ پُر (نصبِ دوباره، ارتقا) شمارش هم معنا
    دارد: بدونِ زمینه‌ی مستأجر باید صفر باشد. تعدادِ جدول‌های سنجیده‌شده را برمی‌گرداند.
    """
    import psycopg

    raw = app_url.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(raw) as conn:
        bypass, is_super = conn.execute(
            "SELECT rolbypassrls, rolsuper FROM pg_roles WHERE rolname = current_user"
        ).fetchone()
        if bypass or is_super:
            raise ProvisionError("نقشِ برنامه RLS را دور می‌زند؛ جداسازیِ داده خاموش است. نصب متوقف شد.")

        rows = conn.execute(
            """
            SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity,
                   EXISTS (SELECT 1 FROM pg_policies p WHERE p.tablename = c.relname
                           AND p.schemaname = n.nspname AND p.qual LIKE '%%app.tenant_id%%')
            FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relkind = 'r'
              AND EXISTS (SELECT 1 FROM information_schema.columns col
                          WHERE col.table_schema = 'public' AND col.table_name = c.relname
                          AND col.column_name = 'tenant_id')
            """
        ).fetchall()
        from app.tenancy import GLOBAL_TABLES

        checked = [r for r in rows if r[0] not in GLOBAL_TABLES]
        broken = sorted(name for name, enabled, forced, policy in checked if not (enabled and forced and policy))
        if not checked or RLS_PROBE_TABLE not in {r[0] for r in checked}:
            raise ProvisionError("جدول‌های مستأجرمحور پیدا نشدند؛ مهاجرت‌ها کامل اجرا نشده‌اند.")
        if broken:
            raise ProvisionError(f"این جدول‌ها RLSِ کامل ندارند و جداسازیِ داده رویشان خاموش است: {', '.join(broken[:10])}")

        if conn.execute("SELECT current_setting('app.tenant_id', true)").fetchone()[0]:
            raise ProvisionError("اتصالِ تازه زمینه‌ی مستأجر دارد؛ این نباید ممکن باشد.")
        seen = conn.execute(f"SELECT count(*) FROM {RLS_PROBE_TABLE}").fetchone()[0]  # noqa: S608 — نامِ ثابت
        if seen:
            raise ProvisionError(
                f"نقشِ برنامه بدونِ زمینه‌ی مستأجر {seen} ردیف دید؛ جداسازیِ داده کار نمی‌کند. نصب متوقف شد."
            )
    return len(checked)


# --- کلِ راه‌اندازی ----------------------------------------------------------------


@dataclass
class ProvisionResult:
    cluster_created: bool
    alembic_version: str
    env_file: Path


def provision(
    *,
    layout: Layout,
    pg_bin: Path,
    alembic_dir: Path,
    pg_port: int = DEFAULT_PG_PORT,
    api_port: int = DEFAULT_API_PORT,
    keep_running: bool = False,
    log=print,
) -> ProvisionResult:
    """همه‌ی قدم‌ها به ترتیب. Postgres برای مدتِ راه‌اندازی دستی بالا می‌آید و بعد خاموش
    می‌شود — از آن به بعد سرویسِ ویندوز صاحبش است (مگر `keep_running`)."""
    layout.home.mkdir(parents=True, exist_ok=True)
    for sub in (layout.logs, layout.backups, layout.updates):
        sub.mkdir(parents=True, exist_ok=True)

    log("رازهای نصب…")
    secrets_ = load_or_create_secrets(layout)

    log("پوشه‌ی دادهِ PostgreSQL…")
    created = init_cluster(pg_bin, layout, secrets_["superuser_password"], pg_port)

    started_here = False
    if not is_running(pg_bin, layout):
        log("راه‌اندازیِ موقتِ PostgreSQL…")
        pg_ctl(pg_bin, layout, "start")
        started_here = True
    try:
        log("نقش‌ها و دیتابیس…")
        bootstrap_database(secrets_, pg_port)

        layout.env_file.write_text(render_env(secrets_, pg_port, api_port, layout.home), encoding="utf-8")
        env = read_env(layout)

        current = current_revision(env["MIGRATION_DATABASE_URL"])
        if current and current != head_revision(alembic_dir):
            log(f"پشتیبان پیش از ارتقا (نسخه‌ی {current})…")
            dump = backup_before_upgrade(pg_bin, layout, secrets_, pg_port, current)
            log(f"  {dump.name}")

        log("مهاجرت‌ها…")
        version = run_migrations(env["MIGRATION_DATABASE_URL"], alembic_dir)

        log("سنجشِ جداسازیِ داده (RLS)…")
        tables = verify_isolation(env["DATABASE_URL"])
        log(f"  {tables} جدولِ مستأجرمحور با RLSِ کامل.")
    finally:
        if started_here and not keep_running:
            pg_ctl(pg_bin, layout, "stop")

    log(f"آماده است — نسخه‌ی دیتابیس {version}.")
    return ProvisionResult(cluster_created=created, alembic_version=version, env_file=layout.env_file)


def remove_data(layout: Layout) -> None:
    """فقط برای آزمون و حذفِ کامل با تأییدِ صریح — نصابِ عادی هرگز این را صدا نمی‌زند."""
    shutil.rmtree(layout.home, ignore_errors=True)
