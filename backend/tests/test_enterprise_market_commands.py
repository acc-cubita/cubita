"""The enterprise broker must not duplicate an order after a lost reply."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.enterprise_license_registry import EnterpriseLicenseRecord
from app.models.enterprise_market_bridge import EnterpriseMarketCommand, EnterpriseMarketLink
from app.services import enterprise_market_commands as commands


def _link(db, tenant_id, user):
    record = EnterpriseLicenseRecord(
        lic_id="CMDBRIDGE", org_name="Market test", code_hash="b" * 64,
        code_hint="TEST", status="active", install_id="test-command-install",
    )
    db.add(record)
    db.flush()
    link = EnterpriseMarketLink(
        license_id=record.id, install_id=record.install_id, status="active",
        cloud_tenant_id=tenant_id, cloud_owner_id=user.id,
    )
    db.add(link)
    db.flush()
    return link


def test_order_retry_returns_original_result_and_rejects_changed_payload(db, tenant_id, user, monkeypatch):
    link = _link(db, tenant_id, user)
    calls = []
    monkeypatch.setattr(commands.market, "place_order", lambda _db, _tid, data: calls.append(data) or SimpleNamespace(id=uuid4()))
    monkeypatch.setattr(commands, "_order_result", lambda _db, row, _tid: {"id": str(row.id)})
    key = uuid4()
    payload = {"distributor_tenant_id": str(uuid4()), "lines": [{"listing_id": str(uuid4()), "qty": "2"}]}

    first = commands.execute(db, link, key, "buyer.place", payload, "حسابدار")
    second = commands.execute(db, link, key, "buyer.place", payload, "حسابدار")
    assert first == second
    assert len(calls) == 1
    assert db.query(EnterpriseMarketCommand).filter_by(link_id=link.id).count() == 1

    changed = {**payload, "note": "متفاوت"}
    with pytest.raises(HTTPException) as exc:
        commands.execute(db, link, key, "buyer.place", changed, "حسابدار")
    assert exc.value.status_code == 409
    assert len(calls) == 1


def test_failed_market_mutation_rolls_back_command_with_request(db, tenant_id, user, monkeypatch):
    link = _link(db, tenant_id, user)
    link_id = link.id
    payload = {"distributor_tenant_id": str(uuid4()), "lines": [{"listing_id": str(uuid4()), "qty": "1"}]}
    key = uuid4()
    monkeypatch.setattr(commands.market, "place_order", lambda *_: (_ for _ in ()).throw(HTTPException(409, "موجودی کافی نیست")))
    with pytest.raises(HTTPException):
        commands.execute(db, link, key, "buyer.place", payload, "خریدار")
    db.rollback()
    assert db.query(EnterpriseMarketCommand).filter_by(link_id=link_id, request_id=key).count() == 0


@pytest.mark.parametrize("operation,payload", [
    ("seller.confirm", {}), ("seller.reject", {"order_id": "wrong"}),
    ("buyer.place", {"lines": []}),
    ("connection.message", {"body": "پیام", "thread_id": None}),
])
def test_invalid_commands_fail_cleanly_before_receipt(db, tenant_id, user, operation, payload):
    link = _link(db, tenant_id, user)
    with pytest.raises(HTTPException) as exc:
        commands.execute(db, link, uuid4(), operation, payload, "حسابدار")
    assert exc.value.status_code == 422
    assert db.query(EnterpriseMarketCommand).filter_by(link_id=link.id).count() == 0


def test_zone_commands_retry_update_and_delete(db, tenant_id, user):
    from app.models.marketplace import MarketplaceZone

    link = _link(db, tenant_id, user)
    key = uuid4()
    payload = {"name": "شرق", "notes": "ناحیهٔ اول"}
    created = commands.execute(db, link, key, "seller.zone.create", payload, "پخش")
    assert commands.execute(db, link, key, "seller.zone.create", payload, "پخش") == created
    assert db.query(MarketplaceZone).filter_by(distributor_tenant_id=tenant_id).count() == 1
    updated = commands.execute(db, link, uuid4(), "seller.zone.update", {"zone_id": created["id"], "name": "غرب"}, "پخش")
    assert updated["name"] == "غرب"
    key = uuid4()
    result = commands.execute(db, link, key, "seller.zone.delete", {"zone_id": created["id"]}, "پخش")
    assert commands.execute(db, link, key, "seller.zone.delete", {"zone_id": created["id"]}, "پخش") == result
    assert db.query(MarketplaceZone).filter_by(distributor_tenant_id=tenant_id).count() == 0


def test_concurrent_zone_retry_commits_one_mutation(tenant_id, user):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from app.models.marketplace import MarketplaceZone
    from tests.conftest import tenant_session

    link_id = None
    license_id = None
    barrier = Barrier(2)
    key = uuid4()
    try:
        with tenant_session(tenant_id) as session:
            link = _link(session, tenant_id, user)
            link_id, license_id = link.id, link.license_id
            session.commit()

        def run():
            with tenant_session(tenant_id) as session:
                link = session.get(EnterpriseMarketLink, link_id)
                barrier.wait(timeout=10)
                result = commands.execute(session, link, key, "seller.zone.create", {"name": "ناحیهٔ همزمان"}, "پخش")
                session.commit()
                return result

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: run(), range(2)))
        assert results[0] == results[1]
        with tenant_session(tenant_id) as session:
            assert session.query(EnterpriseMarketCommand).filter_by(link_id=link_id, request_id=key).count() == 1
            assert session.query(MarketplaceZone).filter_by(id=results[0]["id"]).count() == 1
    finally:
        with tenant_session(tenant_id) as session:
            session.query(MarketplaceZone).filter_by(distributor_tenant_id=tenant_id, name="ناحیهٔ همزمان").delete()
            if link_id:
                session.query(EnterpriseMarketCommand).filter_by(link_id=link_id).delete()
                session.query(EnterpriseMarketLink).filter_by(id=link_id).delete()
            if license_id:
                session.query(EnterpriseLicenseRecord).filter_by(id=license_id).delete()
            session.commit()
