"""نسخه‌ی برنامه — یک عدد برای بک‌اند و دسکتاپ، چون در نسخه‌ی سازمانی با هم منتشر می‌شوند.

منبعِ حقیقت `desktop/package.json` است. بسته‌ی سرور (`packaging/build_server_bundle.py`)
آن را در `version.txt` کنارِ `cubita-server.exe` می‌نویسد؛ در توسعه مستقیم از خودِ
package.json خوانده می‌شود. `CUBITA_VERSION` هر دو را برای آزمون کنار می‌زند.

در نسخه‌ی سازمانی این عدد تعیین می‌کند سرور کدام نصاب را به کلاینت‌ها بدهد
(`app/onprem/updates.py`): کلاینت هرگز از سرورش جلوتر نمی‌رود.
"""

import json
import os
import sys
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def app_version() -> str:
    if os.environ.get("CUBITA_VERSION"):
        return os.environ["CUBITA_VERSION"].strip()
    if getattr(sys, "frozen", False):
        path = Path(sys.executable).resolve().parent / "version.txt"
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError:
            return "0.0.0"
    pkg = Path(__file__).resolve().parents[2] / "desktop" / "package.json"
    try:
        return str(json.loads(pkg.read_text(encoding="utf-8"))["version"])
    except (OSError, ValueError, KeyError):
        return "0.0.0"


def parse_version(v: str) -> tuple[int, int, int]:
    """`1.7.0` → (1, 7, 0). پسوندِ پیش‌انتشار نادیده گرفته می‌شود؛ ناخوانا = صفر."""
    core = v.strip().lstrip("v").split("-", 1)[0].split("+", 1)[0]
    parts = (core.split(".") + ["0", "0", "0"])[:3]
    try:
        return tuple(int(p) for p in parts)  # type: ignore[return-value]
    except ValueError:
        return (0, 0, 0)
