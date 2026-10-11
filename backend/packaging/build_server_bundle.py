"""ساختِ «بسته‌ی سرور»ِ کوبیتا سازمانی — ورودیِ نصابِ `npm run dist:enterprise`.

    cd backend
    ZARINPAL_SANDBOX=true venv/Scripts/python.exe packaging/build_server_bundle.py \\
        --pg-dir "C:/Program Files/PostgreSQL/17"

خروجی `backend/dist/server-bundle/`:

    cubita-server.exe  _internal/         (PyInstaller، از packaging/cubita-server.spec)
    pgsql/bin lib share  LICENSE.txt      (PostgreSQL — فقط آنچه سرور لازم دارد)
    winsw/WinSW-x64.exe                   (هشِ پین‌شده)

**نسخه‌ی PostgreSQL:** همان که `--pg-dir` می‌دهد (امروز ۱۷ — هم‌نسخه‌ی محیطِ توسعه). داخلِ
یک کانالِ آپدیت هرگز عوض نشود: پوشه‌ی دادهِ ساخته‌شده با یک نسخه‌ی اصلی با نسخه‌ی دیگر
بالا نمی‌آید (ریسکِ ۵ در ENTERPRISE_PLAN.md).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
DIST = BACKEND / "dist"
BUNDLE = DIST / "server-bundle"

#: WinSW امضای دیجیتال ندارد (انتشارهای رسمی‌اش همین‌طورند)، پس هش پین می‌شود — نسخه‌ی
#: دست‌کاری‌شده‌ای که از میانه‌ی راه برسد، بیلد را می‌شکند نه نصبِ مشتری را.
WINSW_URL = "https://github.com/winsw/winsw/releases/download/v2.12.0/WinSW-x64.exe"
WINSW_SHA256 = "05b82d46ad331cc16bdc00de5c6332c1ef818df8ceefcd49c726553209b3a0da"

PG_PARTS = ("bin", "lib", "share")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_winsw(dest: Path, local: str | None) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if local:
        shutil.copyfile(local, dest)
    else:
        print("دریافتِ WinSW…")
        urllib.request.urlretrieve(WINSW_URL, dest)  # noqa: S310 — نشانیِ ثابت و هشِ پین‌شده
    got = sha256(dest)
    if got != WINSW_SHA256:
        dest.unlink(missing_ok=True)
        raise SystemExit(f"هشِ WinSW نمی‌خواند ({got}); فایل رد شد.")


def copy_postgres(pg_dir: Path, dest: Path) -> None:
    for part in PG_PARTS:
        src = pg_dir / part
        if not src.is_dir():
            raise SystemExit(f"{src} نیست؛ --pg-dir باید ریشه‌ی نصبِ PostgreSQL باشد.")
        shutil.copytree(src, dest / part, ignore=shutil.ignore_patterns("*.pdb", "pgAdmin*", "stackbuilder*"))
    for name in ("server_license.txt", "LICENSE", "COPYRIGHT"):
        if (pg_dir / name).exists():
            shutil.copyfile(pg_dir / name, dest / "LICENSE.txt")
            break
    for exe in ("initdb", "pg_ctl", "postgres", "pg_dump", "pg_restore", "psql"):
        if not (dest / "bin" / f"{exe}.exe").exists():
            raise SystemExit(f"{exe}.exe در بسته‌ی PostgreSQL نیست.")


def validate_compatibility(profile: str, python_version: tuple[int, ...], pg_version: str) -> int:
    """Do not confuse a working build host with the intended Windows runtime."""
    import re
    match = re.search(r"PostgreSQL\)?\s+(\d+)", pg_version)
    if not match:
        raise SystemExit("PostgreSQL version could not be verified.")
    major = int(match.group(1))
    if profile == "windows81":
        if python_version[:2] != (3, 12):
            raise SystemExit("Windows 8.1 server must be frozen with Python 3.12; do not reuse the modern server.")
        if major != 17:
            raise SystemExit("Windows 8.1 profile must preserve PostgreSQL 17; changing the data engine requires a separate migration.")
    return major


def main() -> int:
    #: خروجیِ هدایت‌شده به فایل روی ویندوز cp1252 است و پیامِ فارسی را نمی‌تواند چاپ کند —
    #: بیلد وسطِ کار با UnicodeEncodeError می‌افتاد و بسته‌ی کهنه سرِ جایش می‌ماند (۱۴۰۵/۰۷/۰۳).
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser()
    parser.add_argument("--pg-dir", required=True, help="ریشه‌ی نصبِ PostgreSQL (حاویِ bin/lib/share)")
    parser.add_argument("--winsw", help="WinSW-x64.exe محلی (وگرنه دانلود با هشِ پین‌شده)")
    parser.add_argument("--skip-pyinstaller", action="store_true", help="از dist/cubita-server موجود استفاده کن")
    parser.add_argument("--profile", choices=("modern", "windows81"), default="modern")
    parser.add_argument("--version", help="نسخهٔ انتشار؛ پیش‌فرض نسخهٔ desktop")
    args = parser.parse_args()

    pg_dir = Path(args.pg_dir).resolve()
    pg_version = subprocess.check_output([str(pg_dir / "bin" / "postgres.exe"), "--version"], text=True).strip()
    pg_major = validate_compatibility(args.profile, tuple(sys.version_info), pg_version)
    frozen_dist = DIST if args.profile == "modern" else DIST / "windows81"
    bundle = BUNDLE if args.profile == "modern" else DIST / "server-bundle-windows81"

    if not args.skip_pyinstaller:
        print("PyInstaller…")
        subprocess.run(
            [sys.executable, "-m", "PyInstaller", "--noconfirm", "--distpath", str(frozen_dist),
             "--workpath", str(BACKEND / "build" / args.profile), str(BACKEND / "packaging" / "cubita-server.spec")],
            cwd=BACKEND,
            check=True,
        )

    frozen = frozen_dist / "cubita-server"
    if not (frozen / "cubita-server.exe").exists():
        raise SystemExit("dist/cubita-server/cubita-server.exe نیست؛ PyInstaller اجرا نشده.")
    if args.profile == "windows81" and not (frozen / "_internal" / "python312.dll").exists():
        raise SystemExit("Frozen Windows 8.1 server does not contain Python 3.12.")

    print("چیدنِ بسته…")
    if bundle.resolve().parent != DIST.resolve():
        raise SystemExit("Bundle destination escaped the packaging directory.")
    shutil.rmtree(bundle, ignore_errors=True)
    shutil.copytree(frozen, bundle)
    copy_postgres(pg_dir, bundle / "pgsql")
    #: نسخه‌ی سرور = نسخه‌ی دسکتاپ (یک انتشار). سرور با این تعیین می‌کند کدام نصاب را به
    #: کلاینت‌ها بدهد (`app/version.py`).
    version = args.version or json.loads((BACKEND.parent / "desktop" / "package.json").read_text(encoding="utf-8"))["version"]
    (bundle / "version.txt").write_text(version, encoding="utf-8")
    fetch_winsw(bundle / "winsw" / "WinSW-x64.exe", args.winsw)

    print("selftest…")
    subprocess.run([str(bundle / "cubita-server.exe"), "selftest"], check=True)
    (bundle / "compatibility.json").write_text(json.dumps({
        "profile": args.profile, "python": sys.version.split()[0],
        "postgresMajor": pg_major, "postgresVersion": pg_version, "version": version,
        "serverSha256": sha256(bundle / "cubita-server.exe"),
        "targetOsVerified": False,
    }, indent=2), encoding="utf-8")

    size = sum(p.stat().st_size for p in bundle.rglob("*") if p.is_file())
    print(f"بسته‌ی سرور آماده است: {bundle} ({size / 1_048_576:.0f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
