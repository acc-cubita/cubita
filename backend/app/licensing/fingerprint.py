"""اثرانگشتِ دستگاهِ سرور — سه جزء، تطبیقِ ۲ از ۳.

**چرا سه جزء و ۲ از ۳.** تعویضِ یک دیسک یا نصبِ دوباره‌ی ویندوز نباید نصبِ مشتری را
بی‌خبر قفل کند؛ ولی کپی‌کردنِ کلِ سرور روی رایانه‌ی دیگری باید دست‌کم دو جزء را عوض
کند. **هرگز MAC:** داک، VPN و کارتِ شبکه‌ی مجازی عوضش می‌کنند.

| جزء | ویندوز | دیگر (فقط توسعه/تست) |
|---|---|---|
| `machine_guid` | رجیستری `Cryptography\\MachineGuid` | `/etc/machine-id` |
| `smbios_uuid` | `Win32_ComputerSystemProduct.UUID` | `/sys/class/dmi/id/product_uuid` |
| `volume_serial` | سریالِ ولومِ درایوِ سیستم | نامِ میزبان |

فقط **هشِ نمک‌خورده** از سرور بیرون می‌رود (در کدِ درخواست)، نه خودِ شناسه‌ها.
"""

import hashlib
import os
import platform
import subprocess
from functools import lru_cache

COMPONENTS = ("machine_guid", "smbios_uuid", "volume_serial")
MIN_MATCH = 2

#: شناسه‌های ساختگیِ SMBIOS که سازنده‌ها گاهی به‌جای شناسه‌ی واقعی می‌گذارند —
#: یکی بودنشان روی هزاران دستگاه یعنی هیچ چیزی را شناسایی نمی‌کنند.
_BOGUS_UUIDS = {
    "00000000-0000-0000-0000-000000000000",
    "FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF",
    "03000200-0400-0500-0006-000700080009",
}


def _read(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read().strip() or None
    except OSError:
        return None


def _windows_machine_guid() -> str | None:
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
            0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
        ) as key:
            return str(winreg.QueryValueEx(key, "MachineGuid")[0]).strip() or None
    except OSError:
        return None


def _windows_smbios_uuid() -> str | None:
    try:
        out = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "(Get-CimInstance -ClassName Win32_ComputerSystemProduct).UUID",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    return out.upper() if out and out.upper() not in _BOGUS_UUIDS else None


def _windows_volume_serial() -> str | None:
    try:
        import ctypes

        root = os.environ.get("SystemDrive", "C:") + "\\"
        serial = ctypes.c_uint32()
        ok = ctypes.windll.kernel32.GetVolumeInformationW(  # type: ignore[attr-defined]
            ctypes.c_wchar_p(root), None, 0, ctypes.byref(serial), None, None, None, 0
        )
        return f"{serial.value:08X}" if ok else None
    except (OSError, AttributeError):
        return None


@lru_cache(maxsize=1)
def collect() -> dict[str, str | None]:
    """شناسه‌های خامِ همین دستگاه. یک‌بار در عمرِ پردازه (فراخوانِ PowerShell کند است)."""
    if platform.system() == "Windows":
        return {
            "machine_guid": _windows_machine_guid(),
            "smbios_uuid": _windows_smbios_uuid(),
            "volume_serial": _windows_volume_serial(),
        }
    product = _read("/sys/class/dmi/id/product_uuid")
    return {
        "machine_guid": _read("/etc/machine-id"),
        "smbios_uuid": product.upper() if product and product.upper() not in _BOGUS_UUIDS else None,
        "volume_serial": platform.node() or None,
    }


def hashed(raw: dict[str, str | None]) -> dict[str, str]:
    """هشِ نمک‌خورده‌ی هر جزء؛ جزءِ خوانده‌نشده حذف می‌شود (و در تطبیق نمی‌شمارد)."""
    return {
        name: hashlib.sha256(f"cubita-fp-v1:{name}:{value}".encode()).hexdigest()[:32]
        for name, value in raw.items()
        if name in COMPONENTS and value
    }


def current() -> dict[str, str]:
    return hashed(collect())


def matches(expected: dict[str, str], actual: dict[str, str]) -> bool:
    """دست‌کم دو جزء یکی باشند. جزئی که یک طرف ندارد به نفعِ تطبیق نمی‌شمارد."""
    same = sum(1 for name in COMPONENTS if name in expected and expected[name] == actual.get(name))
    return same >= MIN_MATCH
