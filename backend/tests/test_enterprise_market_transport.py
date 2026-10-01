"""Authorization failures must not masquerade as an offline cache outage."""
import httpx
import pytest
from fastapi import HTTPException
from app.services import enterprise_market_sync as sync


@pytest.mark.parametrize("method", ["get", "post"])
@pytest.mark.parametrize("code", [400, 401, 402, 403, 404, 409, 422, 429, 500, 503])
def test_cloud_http_status_preserves_client_rejection(monkeypatch, method, code):
    monkeypatch.setattr(sync, "_base_url", lambda: "https://market.example.invalid")
    response = httpx.Response(code, json={"detail": "مجوز رد شد"}, request=httpx.Request(method, "https://market.example.invalid"))
    monkeypatch.setattr(sync.httpx, method, lambda *args, **kwargs: response)
    with pytest.raises(HTTPException) as exc:
        if method == "get":
            sync.cloud_get("snapshot", credential="test")
        else:
            sync.cloud_post("command", {}, credential="test")
    assert exc.value.status_code == (code if code < 500 else 503)


def test_network_failure_can_use_offline_cache(monkeypatch):
    monkeypatch.setattr(sync, "_base_url", lambda: "https://market.example.invalid")
    def fail(*args, **kwargs):
        raise httpx.ConnectError("offline")
    monkeypatch.setattr(sync.httpx, "get", fail)
    with pytest.raises(HTTPException) as exc:
        sync.cloud_get("snapshot", credential="test")
    assert exc.value.status_code == 503
