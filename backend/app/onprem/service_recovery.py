"""شروعِ محدودِ سرویسِ محلی؛ نه نصب، تغییر شبکه، توقف یا دسترسی به رازهای دفتر.

نصاب فقط QUERY_STATUS/START را یک‌بار به کاربران محلی می‌دهد. Mutex مشترک با
نصاب و نشانِ ماندگار HKLM نمی‌گذارند نسخهٔ نیمه‌کپی‌شده خودکار روشن شود.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes as wt
from contextlib import contextmanager
import os
import time

from app.onprem.services import API_SERVICE, PG_SERVICE, _wait_api_ready
from app.onprem.provision import ProvisionError

REG_KEY = r"Software\Cubita Enterprise"
MUTEX_NAME = r"Global\CubitaEnterpriseServiceOperation"
MUTEX_SDDL = "D:(A;;GA;;;SY)(A;;GA;;;BA)(A;;0x00100001;;;BU)"


class RecoveryError(Exception):
    def __init__(self, code: str):
        self.code = code


def installed_config() -> tuple[str, bool, int]:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, REG_KEY, 0,
                            winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
            role = winreg.QueryValueEx(key, "Role")[0]
            try:
                blocked = bool(winreg.QueryValueEx(key, "AutomaticStartBlocked")[0])
            except FileNotFoundError:
                blocked = False
            try:
                port = winreg.QueryValueEx(key, "ApiPort")[0]
            except FileNotFoundError:
                port = 8420
            if not isinstance(port, int) or not 1 <= port <= 65535:
                raise RecoveryError("repair")
            return role, blocked, port
    except FileNotFoundError:
        return "client", False, 8420


def _api():
    # Pointer-width declarations matter on x64; default int truncates handles.
    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    adv.OpenSCManagerW.argtypes = [wt.LPCWSTR, wt.LPCWSTR, wt.DWORD]
    adv.OpenSCManagerW.restype = wt.HANDLE
    adv.OpenServiceW.argtypes = [wt.HANDLE, wt.LPCWSTR, wt.DWORD]
    adv.OpenServiceW.restype = wt.HANDLE
    adv.CloseServiceHandle.argtypes = [wt.HANDLE]
    adv.CloseServiceHandle.restype = wt.BOOL
    adv.StartServiceW.argtypes = [wt.HANDLE, wt.DWORD, ctypes.c_void_p]
    adv.StartServiceW.restype = wt.BOOL
    adv.QueryServiceStatusEx.argtypes = [wt.HANDLE, ctypes.c_int, ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.DWORD)]
    adv.QueryServiceStatusEx.restype = wt.BOOL
    adv.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [wt.LPCWSTR, wt.DWORD, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p]
    adv.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = wt.BOOL
    kernel.CreateMutexExW.argtypes = [ctypes.c_void_p, wt.LPCWSTR, wt.DWORD, wt.DWORD]
    kernel.CreateMutexExW.restype = wt.HANDLE
    kernel.WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]
    kernel.WaitForSingleObject.restype = wt.DWORD
    kernel.ReleaseMutex.argtypes = [wt.HANDLE]
    kernel.ReleaseMutex.restype = wt.BOOL
    kernel.CloseHandle.argtypes = [wt.HANDLE]
    kernel.CloseHandle.restype = wt.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    return adv, kernel


def _os_error():
    code = ctypes.get_last_error()
    raise RecoveryError("permission" if code == 5 else "missing" if code == 1060 else "repair")


@contextmanager
def operation_lock():
    adv, kernel = _api()
    sd = ctypes.c_void_p()
    if not adv.ConvertStringSecurityDescriptorToSecurityDescriptorW(MUTEX_SDDL, 1, ctypes.byref(sd), None):
        _os_error()

    class Attributes(ctypes.Structure):
        _fields_ = [("length", wt.DWORD), ("descriptor", ctypes.c_void_p), ("inherit", wt.BOOL)]

    attr = Attributes(ctypes.sizeof(Attributes), sd, False)
    handle = kernel.CreateMutexExW(ctypes.byref(attr), MUTEX_NAME, 0, 0x00100001)
    kernel.LocalFree(sd)
    if not handle:
        _os_error()
    acquired = False
    try:
        result = kernel.WaitForSingleObject(handle, 0)
        if result not in (0, 0x80):  # acquired / abandoned owner
            raise RecoveryError("maintenance")
        acquired = True
        yield
    finally:
        if acquired:
            kernel.ReleaseMutex(handle)
        kernel.CloseHandle(handle)


class WindowsServices:
    def __init__(self):
        self.adv, _ = _api()

    @contextmanager
    def handle(self, name: str, access: int):
        if name not in (PG_SERVICE, API_SERVICE):
            raise RecoveryError("repair")
        manager = self.adv.OpenSCManagerW(None, None, 1)  # local SCM_CONNECT
        if not manager:
            _os_error()
        service = None
        try:
            service = self.adv.OpenServiceW(manager, name, access)
            if not service:
                _os_error()
            yield service
        finally:
            if service:
                self.adv.CloseServiceHandle(service)
            self.adv.CloseServiceHandle(manager)

    def state(self, name: str) -> int:
        class Status(ctypes.Structure):
            _fields_ = [(f"field{i}", wt.DWORD) for i in range(9)]

        with self.handle(name, 4) as handle:  # QUERY_STATUS
            status, needed = Status(), wt.DWORD()
            if not self.adv.QueryServiceStatusEx(handle, 0, ctypes.byref(status), ctypes.sizeof(status), ctypes.byref(needed)):
                _os_error()
            return status.field1

    def start(self, name: str):
        with self.handle(name, 0x10) as handle:  # START, never STOP/change-config
            if not self.adv.StartServiceW(handle, 0, None):
                if ctypes.get_last_error() != 1056:  # already running race
                    _os_error()


MESSAGES = {
    "ready": "سرور آماده است؛ اتصال خودکار برقرار شد.",
    "client": "این رایانه کلاینت است؛ اتصال به سرور ذخیره‌شده دوباره بررسی می‌شود.",
    "maintenance": "سرور در حال نصب یا تعمیر است؛ بازیابی خودکار تا پایان نصب متوقف می‌ماند.",
    "permission": "مجوز شروع خودکار هنوز نصب نشده؛ نصاب کامل سازمانی را یک‌بار با نقش سرور و مسیر قبلی اجرا کنید.",
    "missing": "نصب سرویس سرور کامل نیست؛ نصاب کامل سازمانی را با نقش سرور و مسیر قبلی اجرا کنید. داده‌ها را حذف نکنید.",
    "repair": "سرور آماده نشد؛ نصاب سازمانی را با نقش سرور و مسیر قبلی برای تعمیر اجرا کنید. داده‌ها و صف محفوظ‌اند.",
}


def recover_local_services(*, config=installed_config, lock=operation_lock, controller=None,
                           ready=_wait_api_ready, now=time.monotonic, sleep=time.sleep) -> dict:
    if os.name != "nt" and controller is None:
        return {"state": "client", "message": MESSAGES["client"]}
    try:
        with lock():
            # Read role/maintenance inside the same lock as installer begin.
            role, blocked, port = config()
            if blocked:
                raise RecoveryError("maintenance")
            if role != "server":
                return {"state": "client", "message": MESSAGES["client"]}
            ctl = controller or WindowsServices()
            deadline = now() + 55
            for name in (PG_SERVICE, API_SERVICE):
                state = ctl.state(name)
                if state not in (1, 2, 4):
                    raise RecoveryError("repair")
                if state == 1:
                    ctl.start(name)
                while ctl.state(name) != 4:
                    if now() >= deadline:
                        raise RecoveryError("repair")
                    sleep(0.5)
            ready(port, timeout=max(1, min(20, deadline - now())))
        return {"state": "ready", "message": MESSAGES["ready"]}
    except RecoveryError as exc:
        code = exc.code
    except ProvisionError:
        code = "repair"
    except OSError:
        code = "permission"
    return {"state": code, "message": MESSAGES[code]}
