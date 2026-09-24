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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pg-dir", required=True, help="ریشه‌ی نصبِ PostgreSQL (حاویِ bin/lib/share)")
    parser.add_argument("--winsw", help="WinSW-x64.exe محلی (وگرنه دانلود با هشِ پین‌شده)")
    parser.add_argument("--skip-pyinstaller", action="store_true", help="از dist/cubita-server موجود استفاده کن")
    args = parser.parse_args()

    if not args.skip_pyinstaller:
        print("PyInstaller…")
        subprocess.run(
            [sys.executable, "-m", "PyInstaller", "--noconfirm", "--distpath", str(DIST),
             "--workpath", str(BACKEND / "build"), str(BACKEND / "packaging" / "cubita-server.spec")],
            cwd=BACKEND,
            check=True,
        )

    frozen = DIST / "cubita-server"
    if not (frozen / "cubita-server.exe").exists():
        raise SystemExit("dist/cubita-server/cubita-server.exe نیست؛ PyInstaller اجرا نشده.")

    print("چیدنِ بسته…")
    shutil.rmtree(BUNDLE, ignore_errors=True)
    shutil.copytree(frozen, BUNDLE)
    copy_postgres(Path(args.pg_dir), BUNDLE / "pgsql")
    #: نسخه‌ی سرور = نسخه‌ی دسکتاپ (یک انتشار). سرور با این تعیین می‌کند کدام نصاب را به
    #: کلاینت‌ها بدهد (`app/version.py`).
    version = json.loads((BACKEND.parent / "desktop" / "package.json").read_text(encoding="utf-8"))["version"]
    (BUNDLE / "version.txt").write_text(version, encoding="utf-8")
    fetch_winsw(BUNDLE / "winsw" / "WinSW-x64.exe", args.winsw)

    print("selftest…")
    subprocess.run([str(BUNDLE / "cubita-server.exe"), "selftest"], check=True)

    size = sum(p.stat().st_size for p in BUNDLE.rglob("*") if p.is_file())
    print(f"بسته‌ی سرور آماده است: {BUNDLE} ({size / 1_048_576:.0f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
