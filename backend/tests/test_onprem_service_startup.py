"""Startup/health failures must not become a successful enterprise installation.

Pure unit tests: --noconftest runs these without any database or Windows service.
"""

import io
import subprocess
from types import SimpleNamespace
from urllib.error import URLError

import pytest

from app.onprem import services as svc
from app.onprem.provision import Layout, ProvisionError


@pytest.fixture(autouse=True)
def no_real_processes(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("Unit tests must not execute OS commands")

    monkeypatch.setattr(svc.subprocess, "run", refuse)
    monkeypatch.setattr(svc, "app_version", lambda: "1.9.99")


def states(monkeypatch, values):
    sequence = iter(values)
    monkeypatch.setattr(svc, "_service_state", lambda name: next(sequence))
    monkeypatch.setattr(svc.time, "sleep", lambda seconds: None)


def test_running_service_is_not_started_again(monkeypatch):
    states(monkeypatch, [4, 4])
    logs = []
    svc._ensure_service_running(svc.API_SERVICE, log=logs.append)
    assert len(logs) == 1 and svc.API_SERVICE in logs[0]


def test_stopped_service_is_started_and_checked(monkeypatch):
    states(monkeypatch, [1, 2, 4])
    calls = []

    def run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(svc.subprocess, "run", run)
    svc._ensure_service_running(svc.PG_SERVICE, log=lambda _: None)
    assert calls[0][0] == ["net", "start", "CubitaPostgres"]
    assert calls[0][1]["timeout"] == 60


@pytest.mark.parametrize("state", [2, 4])
def test_failed_start_is_tolerated_only_if_service_really_started(monkeypatch, state):
    states(monkeypatch, [1, state, 4])
    monkeypatch.setattr(svc.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=2))
    svc._ensure_service_running(svc.API_SERVICE, log=lambda _: None)


def test_failed_start_while_stopped_is_an_install_failure(monkeypatch):
    states(monkeypatch, [1, 1])
    monkeypatch.setattr(svc.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=2))
    with pytest.raises(ProvisionError, match="راه‌اندازی.*شکست خورد"):
        svc._ensure_service_running(svc.API_SERVICE)


@pytest.mark.parametrize("error", [OSError("unavailable"), subprocess.TimeoutExpired("net", 60)])
def test_start_command_failure_is_actionable(monkeypatch, error):
    states(monkeypatch, [1])

    def run(*a, **kw):
        raise error

    monkeypatch.setattr(svc.subprocess, "run", run)
    with pytest.raises(ProvisionError, match="Services.*logs"):
        svc._ensure_service_running(svc.API_SERVICE)


def test_start_pending_waits_without_another_start(monkeypatch):
    states(monkeypatch, [2, 2, 4])
    svc._ensure_service_running(svc.API_SERVICE, log=lambda _: None)


def test_stop_pending_finishes_before_start(monkeypatch):
    states(monkeypatch, [3, 3, 1, 4])
    monkeypatch.setattr(svc.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=0))
    svc._ensure_service_running(svc.API_SERVICE, log=lambda _: None)


@pytest.mark.parametrize("state", [5, 6, 7])
def test_paused_and_other_states_are_not_silently_ignored(monkeypatch, state):
    states(monkeypatch, [state])
    with pytest.raises(ProvisionError, match="Services"):
        svc._ensure_service_running(svc.API_SERVICE)


def test_pending_timeout_is_bounded(monkeypatch):
    monkeypatch.setattr(svc, "_service_state", lambda name: 2)
    clock = iter([0, 31])
    monkeypatch.setattr(svc.time, "monotonic", lambda: next(clock))
    with pytest.raises(ProvisionError, match="مورد انتظار"):
        svc._wait_service_state(svc.API_SERVICE, 4)


@pytest.mark.parametrize("returncode,output", [(0, "4\r\n"), (0, "1\n")])
def test_service_query_uses_locale_independent_status(monkeypatch, returncode, output):
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        return SimpleNamespace(returncode=returncode, stdout=output)

    monkeypatch.setattr(svc.subprocess, "run", run)
    assert svc._service_state(svc.API_SERVICE) == int(output)
    assert "[int](Get-Service" in calls[0][-1]
    assert "-NonInteractive" in calls[0]


@pytest.mark.parametrize("code,output", [(1, ""), (0, "Running"), (0, "0"), (0, "8")])
def test_query_failure_is_not_treated_as_stopped(monkeypatch, code, output):
    monkeypatch.setattr(svc.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=code, stdout=output))
    with pytest.raises(ProvisionError, match="خوانده نشد"):
        svc._service_state(svc.API_SERVICE)


def test_query_rejects_arbitrary_service_names():
    with pytest.raises(ProvisionError, match="نام سرویس"):
        svc._service_state("arbitrary'; exit 0")


class HealthResponse(io.BytesIO):
    def __init__(self, data, status=200):
        super().__init__(data)
        self.status = status


def health_probe(monkeypatch, responses):
    responses = iter(responses)
    calls = []
    handlers = []

    def open_health(url, **kwargs):
        calls.append((url, kwargs))
        value = next(responses)
        if isinstance(value, Exception):
            raise value
        return value

    def opener(handler):
        handlers.append(handler)
        return SimpleNamespace(open=open_health)

    monkeypatch.setattr(svc, "build_opener", opener)
    clock = iter(range(100))
    monkeypatch.setattr(svc.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(svc.time, "sleep", lambda seconds: None)
    return calls, handlers


def test_readiness_is_direct_localhost_and_enterprise(monkeypatch):
    calls, handlers = health_probe(monkeypatch, [HealthResponse(b'{"status":"ok","edition":"enterprise","version":"1.9.99"}')])
    svc._wait_api_ready(8421)
    assert calls[0][0] == "http://127.0.0.1:8421/api/health"
    assert calls[0][1]["timeout"] <= 3
    assert handlers[0].proxies == {}


@pytest.mark.parametrize("bad", [
    URLError("unavailable"), HealthResponse(b"invalid json"),
    HealthResponse(b"[]"), HealthResponse(b'{"status":"ok","edition":"cloud"}'),
    HealthResponse(b'{"status":"ok","edition":"enterprise","version":"1.9.5"}'),
    HealthResponse(b'{"status":"error","edition":"enterprise"}'),
    HealthResponse(b'{"status":"ok","edition":"enterprise","version":"1.9.99"}', status=503),
])
def test_health_retries_until_really_ready(monkeypatch, bad):
    calls, _ = health_probe(monkeypatch, [bad, HealthResponse(b'{"status":"ok","edition":"enterprise","version":"1.9.99"}')])
    svc._wait_api_ready(8420)
    assert len(calls) == 2


def test_running_wrapper_without_healthy_api_is_failure(monkeypatch):
    health_probe(monkeypatch, [URLError("unavailable")])
    with pytest.raises(ProvisionError, match="نصب هنوز کامل نیست"):
        svc._wait_api_ready(8420, timeout=3)


@pytest.mark.parametrize("port", [0, 65536])
def test_health_rejects_invalid_port(port):
    with pytest.raises(ProvisionError, match="پورت"):
        svc._wait_api_ready(port)


@pytest.mark.parametrize("failure", [None, svc.PG_SERVICE, svc.API_SERVICE, "health"])
def test_install_requires_postgres_then_api_then_health(tmp_path, monkeypatch, failure):
    layout = Layout(tmp_path / "Cubita")
    winsw = tmp_path / "winsw.exe"
    winsw.write_bytes(b"test fixture only")
    monkeypatch.setattr(svc, "run_all", lambda *a, **kw: None)
    monkeypatch.setattr(svc, "_service_exists", lambda _: True)
    steps = []

    def running(name, **kwargs):
        steps.append(name)
        if failure == name:
            raise ProvisionError("startup failure")

    def ready(port):
        steps.append("health")
        assert port == 8420
        if failure == "health":
            raise ProvisionError("health failure")

    monkeypatch.setattr(svc, "_ensure_service_running", running)
    monkeypatch.setattr(svc, "_wait_api_ready", ready)
    logs = []
    args = dict(layout=layout, pg_bin=tmp_path, server_exe=tmp_path / "server.exe", winsw_exe=winsw, api_port=8420, log=logs.append)
    if failure:
        with pytest.raises(ProvisionError):
            svc.install_services(**args)
        assert "سرورِ سازمانی پاسخ سالم می‌دهد" not in " ".join(logs)
    else:
        svc.install_services(**args)
        assert "سرورِ سازمانی پاسخ سالم می‌دهد" in " ".join(logs)
    expected = [svc.PG_SERVICE, svc.API_SERVICE, "health"]
    if failure:
        expected = expected[:expected.index(failure) + 1]
    assert steps == expected
