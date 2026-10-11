"""The offline view cache is a market projection, never the local ledger."""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.enterprise_market_bridge import EnterpriseMarketLocalState
from app.routers import enterprise_market_local as local_router
from app.services.enterprise_market_views import snapshot


def test_empty_market_snapshot_has_only_allowlisted_sections(db, tenant_id):
    view = snapshot(db, tenant_id)
    data = view.model_dump(mode="json")
    assert data["catalog"] == []
    assert data["retailer_orders"] == []
    assert data["distributor_orders"] == []
    assert data["buyer_unread"] == data["seller_unread"] == 0
    assert "accounts" not in data
    assert "stock_batches" not in data
    assert "journal_entries" not in data


def test_cached_market_does_not_show_buyer_data_to_seller_only_staff(db, tenant_id, monkeypatch):
    data = snapshot(db, tenant_id).model_dump(mode="json")
    data["distributors"] = [{
        "tenant_id": str(uuid4()), "display_name": "بازار خریداران",
        "connection_status": None, "matching_listings": 1, "total_listings": 1,
    }]
    db.add(EnterpriseMarketLocalState(
        tenant_id=tenant_id, link_id=uuid4(), status="active",
        market_snapshot=data, market_snapshot_at=datetime.now(timezone.utc),
    ))
    db.flush()
    monkeypatch.setattr(local_router, "get_settings", lambda: SimpleNamespace(is_enterprise=True, market_bridge_enabled=True))
    monkeypatch.setattr(local_router.license_state, "current", lambda _db: SimpleNamespace(mode="active"))
    principal = SimpleNamespace(
        tenant_id=tenant_id, has_permission=lambda module, action: module == "market_distribute" and action == "view",
    )
    response = local_router.cached_market_snapshot(principal=principal, db=db)
    assert response["snapshot"]["distributors"] == []
    assert response["snapshot"]["buyer_unread"] == 0
    assert response["offline"] is False


def test_cache_cannot_hide_rejected_bridge_credentials(db, tenant_id):
    db.add(EnterpriseMarketLocalState(tenant_id=tenant_id, link_id=uuid4(), status="active",
        market_snapshot=snapshot(db, tenant_id).model_dump(mode="json"), last_error_code="access_denied"))
    db.flush()
    with pytest.raises(HTTPException) as exc:
        local_router._market_cache(db, tenant_id)
    assert exc.value.status_code == 403


def test_new_pair_cannot_inherit_previous_cloud_cache_or_catalog_approval(db, tenant_id, monkeypatch):
    state = EnterpriseMarketLocalState(tenant_id=tenant_id, link_id=uuid4(), status="revoked",
        cloud_tenant_id=uuid4(), catalog_approved=True, market_snapshot={"old_account": True},
        market_snapshot_at=datetime.now(timezone.utc), message_threads={"old_thread": {}},
        last_sync_at=datetime.now(timezone.utc), pending_generation=uuid4(), last_error_code="access_denied")
    db.add(state); db.flush()
    monkeypatch.setattr(local_router, "_license_token", lambda _db: "signed-test")
    next_link = uuid4()
    monkeypatch.setattr(local_router, "cloud_post", lambda *args, **kwargs: {"link_id":str(next_link),"pair_code":"TEST"})
    local_router.pair_start(SimpleNamespace(tenant_id=tenant_id), db)
    assert state.link_id == next_link and state.status == "pending"
    assert state.cloud_tenant_id is None
    assert not state.catalog_approved
    assert state.market_snapshot is state.market_snapshot_at is state.message_threads is None
    assert state.pending_generation is state.last_sync_at is None
    assert state.last_error_code == ""
