"""Pure recovery QA; OS/SCM/registry/health are all injected, no real DB/service."""
import base64
import ctypes
from ctypes import wintypes as wt
from contextlib import contextmanager
from types import SimpleNamespace
import sys

import pytest

from app.onprem import service_recovery as recovery
from app.onprem import services
from app.onprem.provision import ProvisionError


class FakeServices:
    def __init__(self, states=None, failure=None):
        self.states = states or {services.PG_SERVICE: 1, services.API_SERVICE: 1}
        self.failure = failure
        self.calls = []

    def state(self, name):
        self.calls.append(("query", name))
        return self.states[name]

    def start(self, name):
        self.calls.append(("start", name))
        if self.failure:
            raise recovery.RecoveryError(self.failure)
        self.states[name] = 4


def run(ctl, *, role="server", blocked=False, ready=None, **kwargs):
    @contextmanager
    def lock():
        ctl.calls.append(("lock", None))
        yield
        ctl.calls.append(("unlock", None))

    def config():
        assert ctl.calls == [("lock", None)]  # inspect AFTER locking
        return role, blocked, 8420

    return recovery.recover_local_services(
        controller=ctl, config=config, lock=lock,
        ready=ready or (lambda port, **kw: ctl.calls.append(("health", port))), **kwargs,
    )


def test_stopped_server_starts_pg_then_api_and_health():
    ctl = FakeServices()
    assert run(ctl)["state"] == "ready"
    assert [call for call in ctl.calls if call[0] in ("start", "health")] == [
        ("start", "CubitaPostgres"), ("start", "CubitaApi"), ("health", 8420)]
    assert ctl.calls[-1] == ("unlock", None)


def test_running_server_is_not_restarted():
    ctl = FakeServices({services.PG_SERVICE: 4, services.API_SERVICE: 4})
    assert run(ctl)["state"] == "ready"
    assert not any(call[0] == "start" for call in ctl.calls)


@pytest.mark.parametrize("role,blocked,state", [("client", False, "client"), ("server", True, "maintenance"), ("client", True, "maintenance")])
def test_client_or_installer_never_starts_services(role, blocked, state):
    ctl = FakeServices()
    assert run(ctl, role=role, blocked=blocked)["state"] == state
    assert not any(call[0] in ("query", "start", "health") for call in ctl.calls)


@pytest.mark.parametrize("failure", ["permission", "missing", "repair"])
def test_start_failure_has_guidance_not_false_success(failure):
    ctl = FakeServices(failure=failure)
    result = run(ctl)
    assert result["state"] == failure
    assert "نصاب" in result["message"]
    assert ("start", services.API_SERVICE) not in ctl.calls


@pytest.mark.parametrize("state", [3, 5, 6, 7, 0])
def test_paused_stopping_invalid_state_is_not_overridden(state):
    ctl = FakeServices({services.PG_SERVICE: state, services.API_SERVICE: 1})
    assert run(ctl)["state"] == "repair"
    assert not any(call[0] == "start" for call in ctl.calls)


def test_start_pending_waits_without_second_start():
    ctl = FakeServices({services.PG_SERVICE: 2, services.API_SERVICE: 4})
    def sleep(_):
        ctl.states[services.PG_SERVICE] = 4
    assert run(ctl, sleep=sleep)["state"] == "ready"
    assert not any(call[0] == "start" for call in ctl.calls)


def test_pending_wait_is_bounded():
    ctl = FakeServices({services.PG_SERVICE: 2, services.API_SERVICE: 4})
    clock = iter([0, 56])
    assert run(ctl, now=lambda: next(clock))["state"] == "repair"


def test_running_wrapper_without_api_is_not_success():
    def failed_health(*a, **kw):
        raise ProvisionError("not healthy")
    assert run(FakeServices(), ready=failed_health)["state"] == "repair"


def test_installer_or_another_recovery_has_exclusive_lock():
    @contextmanager
    def busy():
        raise recovery.RecoveryError("maintenance")
        yield
    ctl = FakeServices()
    result = recovery.recover_local_services(controller=ctl, lock=busy, config=lambda: pytest.fail("no lock"))
    assert result["state"] == "maintenance"
    assert ctl.calls == []


def test_installer_grants_only_start_query_preserving_dacl():
    commands = services.automatic_service_commands()
    assert len(commands) == 6
    for index, name in enumerate((services.PG_SERVICE, services.API_SERVICE)):
        config, failure, acl = commands[index * 3:index * 3 + 3]
        assert config[:3] == ["sc", "config", name]
        assert failure == ["sc", "failure", name, "reset=", "3600", "actions=", "restart/10000/restart/30000/restart/60000"]
        script = base64.b64decode(acl[-1]).decode("utf-16le")
        assert "CommonAce]::new(0,0,20,$sid,$false,$null)" in script
        assert "RawSecurityDescriptor" in script and "sdshow" in script
        assert "DiscretionaryAcl.InsertAce" in script and "AccessDenied" in script
        assert "S-1-5-32-545" in script
        assert "netsh" not in script and "icacls" not in script
    with pytest.raises(ProvisionError):
        services.service_start_permission_command("arbitrary-service")


def test_windows_handle_operations_cannot_target_other_services(monkeypatch):
    monkeypatch.setattr(recovery, "_api", lambda: (None, None))
    ctl = recovery.WindowsServices()
    with pytest.raises(recovery.RecoveryError):
        with ctl.handle("Spooler", 0x10):
            pytest.fail("arbitrary service opened")


def test_native_status_and_start_use_only_local_minimal_handles(monkeypatch):
    calls = []
    def query(handle, level, buffer, size, needed):
        buffer._obj.field1 = 4
        return True
    adv = SimpleNamespace(
        OpenSCManagerW=lambda host, db, access: calls.append(("SCM", host, access)) or 0x123456789,
        OpenServiceW=lambda manager, name, access: calls.append(("open", name, access)) or 0x987654321,
        CloseServiceHandle=lambda handle: calls.append(("close", handle)),
        QueryServiceStatusEx=query,
        StartServiceW=lambda handle, argc, argv: calls.append(("start", argc, argv)) or True,
    )
    monkeypatch.setattr(recovery, "_api", lambda: (adv, None))
    ctl = recovery.WindowsServices()
    assert ctl.state(services.API_SERVICE) == 4
    ctl.start(services.PG_SERVICE)
    assert [call for call in calls if call[0] == "open"] == [
        ("open", "CubitaApi", 4), ("open", "CubitaPostgres", 16)]
    assert [c for c in calls if c[0] == "SCM"] == [("SCM", None, 1)] * 2
    assert [c for c in calls if c[0] == "close"] == [("close", 0x987654321), ("close", 0x123456789)] * 2


@pytest.mark.parametrize("error,state", [(5, "permission"), (1060, "missing"), (1058, "repair")])
def test_native_failure_is_not_success(monkeypatch, error, state):
    monkeypatch.setattr(recovery.ctypes, "get_last_error", lambda: error, raising=False)
    with pytest.raises(recovery.RecoveryError) as caught:
        recovery._os_error()
    assert caught.value.code == state


def test_native_pointer_bindings_are_not_default_int(monkeypatch):
    class Library:
        def __getattr__(self, name):
            fn = SimpleNamespace()
            setattr(self, name, fn)
            return fn
    adv, kernel = Library(), Library()
    monkeypatch.setattr(ctypes, "WinDLL", lambda name, **kw: adv if name == "advapi32" else kernel, raising=False)
    recovery._api()
    assert adv.OpenSCManagerW.restype == wt.HANDLE
    assert adv.OpenServiceW.restype == wt.HANDLE
    assert kernel.CreateMutexExW.restype == wt.HANDLE
    assert kernel.CreateMutexExW.argtypes[-1] == wt.DWORD
    assert kernel.LocalFree.restype == ctypes.c_void_p


def test_verified_custom_port_is_public_config_not_env_or_secrets(monkeypatch):
    calls = []
    @contextmanager
    def key(*args):
        calls.append(args)
        yield "fake-key"
    reg = SimpleNamespace(HKEY_LOCAL_MACHINE="HKLM", KEY_SET_VALUE=2, KEY_WOW64_64KEY=256,
                          REG_DWORD=4, CreateKeyEx=key, SetValueEx=lambda *args: calls.append(args))
    monkeypatch.setitem(sys.modules, "winreg", reg)
    services.write_recovery_port(8421)
    assert calls == [("HKLM", recovery.REG_KEY, 0, 258), ("fake-key", "ApiPort", 0, 4, 8421)]
