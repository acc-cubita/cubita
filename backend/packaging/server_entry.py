"""`cubita-server.exe` — تنها باینریِ سمتِ سرورِ «کوبیتا سازمانی» (ENTERPRISE_PLAN.md، M4).

    cubita-server install    [--home DIR] [--pg-port 5433] [--api-port 8420]   # نصاب (مدیر)
    cubita-server setup      [--home DIR] ...     # فقط دیتابیس و .env، بدونِ سرویس (آزمون/تعمیر)
    cubita-server serve      [--home DIR]         # سرویسِ API (WinSW این را اجرا می‌کند)
    cubita-server migrate    [--home DIR]         # مهاجرت‌ها با نقشِ مالک (آپدیت)
    cubita-server uninstall-services [--home DIR] # حذفِ برنامه؛ داده می‌ماند
    cubita-server status     [--home DIR]
    cubita-server selftest

چیدمانِ بسته (کنارِ این exe):

    server/cubita-server.exe  + _internal/   (PyInstaller onedir)
    server/pgsql/bin|lib|share               (PostgreSQLِ همراه)
    server/winsw/WinSW-x64.exe

**همه‌ی منطق در `app/onprem/` است** (تست‌پذیر، بدونِ PyInstaller)؛ این فایل فقط مسیرها را
پیدا می‌کند و آرگومان‌ها را می‌خواند.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _bundle_dir() -> Path:
    """پوشه‌ی exe در حالتِ بسته‌بندی؛ در توسعه، پوشه‌ی `backend/`."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def _resource_dir() -> Path:
    """جایی که PyInstaller داده‌ها (`alembic/`) را گذاشته."""
    return Path(getattr(sys, "_MEIPASS", _bundle_dir()))


def _default_home() -> Path:
    return Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "Cubita"


def _pg_bin(args) -> Path:
    if args.pg_bin:
        return Path(args.pg_bin)
    return _bundle_dir() / "pgsql" / "bin"


def _enter_home(home: Path) -> None:
    """`Settings` فایلِ `.env` را از پوشه‌ی جاری می‌خواند — پیش از هر import از `app`."""
    if not (home / ".env").exists():
        raise SystemExit(f"{home} راه‌اندازی نشده است؛ اول «cubita-server install» را اجرا کنید.")
    os.chdir(home)


def cmd_setup(args, *, services: bool) -> int:
    from app.onprem.provision import Layout, ProvisionError, provision

    layout = Layout(Path(args.home))
    try:
        provision(
            layout=layout,
            pg_bin=_pg_bin(args),
            alembic_dir=_resource_dir() / "alembic",
            pg_port=args.pg_port,
            api_port=args.api_port,
        )
        if services:
            from app.onprem.services import install_services

            install_services(
                layout=layout,
                pg_bin=_pg_bin(args),
                server_exe=Path(sys.executable).resolve(),
                winsw_exe=_bundle_dir() / "winsw" / "WinSW-x64.exe",
                api_port=args.api_port,
            )
    except ProvisionError as exc:
        print(f"خطا: {exc}", file=sys.stderr)
        return 1
    print("نصبِ سرور کامل شد.")
    return 0


def cmd_serve(args) -> int:
    home = Path(args.home)
    _enter_home(home)
    from app.onprem.provision import Layout, read_env

    env = read_env(Layout(home))
    import uvicorn

    from app.main import app

    uvicorn.run(
        app,
        host=env.get("API_HOST", "0.0.0.0"),
        port=int(env.get("API_PORT", "8420")),
        log_level="info",
        #: پشتِ هیچ پراکسی‌ای نیست؛ هدرهای X-Forwarded را باور نکن.
        proxy_headers=False,
    )
    return 0


def cmd_migrate(args) -> int:
    home = Path(args.home)
    _enter_home(home)
    from app.onprem.provision import Layout, read_env, run_migrations, verify_isolation

    env = read_env(Layout(home))
    version = run_migrations(env["MIGRATION_DATABASE_URL"], _resource_dir() / "alembic")
    verify_isolation(env["DATABASE_URL"])
    print(f"دیتابیس در نسخه‌ی {version}.")
    return 0


def cmd_uninstall(args) -> int:
    from app.onprem.provision import Layout
    from app.onprem.services import uninstall_services

    uninstall_services(layout=Layout(Path(args.home)), pg_bin=_pg_bin(args))
    print("سرویس‌ها برداشته شدند. داده‌ها در پوشه‌ی داده باقی ماندند.")
    return 0


def cmd_status(args) -> int:
    import subprocess

    import httpx

    from app.onprem.provision import Layout, read_env
    from app.onprem.services import API_SERVICE, PG_SERVICE

    for name in (PG_SERVICE, API_SERVICE):
        out = subprocess.run(["sc", "query", name], capture_output=True, text=True).stdout
        state = next((ln.split(":", 1)[1].strip() for ln in out.splitlines() if "STATE" in ln), "نصب نشده")
        print(f"{name}: {state}")
    port = read_env(Layout(Path(args.home))).get("API_PORT", "8420")
    try:
        print("API:", httpx.get(f"http://127.0.0.1:{port}/api/health", timeout=5).json())
    except httpx.HTTPError as exc:
        print("API: پاسخ نداد —", exc)
    return 0


def cmd_selftest(_args) -> int:
    os.environ.setdefault("EDITION", "enterprise")
    os.environ.setdefault("ZARINPAL_SANDBOX", "true")
    from app.main import app

    routes = sum(1 for r in app.routes if hasattr(r, "methods"))
    alembic_versions = len(list((_resource_dir() / "alembic" / "versions").glob("*.py")))
    print(f"routes={routes} migrations={alembic_versions} bundle={_bundle_dir()}")
    return 0 if routes and alembic_versions else 1


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(prog="cubita-server")
    sub = parser.add_subparsers(dest="cmd", required=True)

    def common(p, *, ports: bool = False):
        p.add_argument("--home", default=str(_default_home()))
        p.add_argument("--pg-bin", default=None, help="پوشه‌ی bin ِ PostgreSQL (پیش‌فرض: همراهِ بسته)")
        if ports:
            p.add_argument("--pg-port", type=int, default=5433)
            p.add_argument("--api-port", type=int, default=8420)

    common(sub.add_parser("install"), ports=True)
    common(sub.add_parser("setup"), ports=True)
    common(sub.add_parser("serve"))
    common(sub.add_parser("migrate"))
    common(sub.add_parser("uninstall-services"))
    common(sub.add_parser("status"))
    sub.add_parser("selftest")

    args = parser.parse_args(argv)
    return {
        "install": lambda: cmd_setup(args, services=True),
        "setup": lambda: cmd_setup(args, services=False),
        "serve": lambda: cmd_serve(args),
        "migrate": lambda: cmd_migrate(args),
        "uninstall-services": lambda: cmd_uninstall(args),
        "status": lambda: cmd_status(args),
        "selftest": lambda: cmd_selftest(args),
    }[args.cmd]()


if __name__ == "__main__":
    raise SystemExit(main())
