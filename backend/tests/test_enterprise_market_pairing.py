"""Pairing is two-owner and cannot export the local company's ledger."""

from datetime import datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import HTTPException

from app.licensing import keys
from app.licensing.token import public_key_b64, sign
from app.models.enterprise_license_registry import EnterpriseLicenseRecord
from app.models.enterprise_market_bridge import EnterpriseMarketCatalog, EnterpriseMarketLink
from app.models.marketplace import MarketplaceListing, MarketplaceOrder, MarketplaceSettings
from app.models.tenant import Tenant
from app.services import enterprise_market_pairing as pairing


@pytest.fixture
def signed_install(db, monkeypatch):
    key = Ed25519PrivateKey.generate()
    monkeypatch.setattr(keys, "TRUSTED_PUBLIC_KEYS", {"test": public_key_b64(key.public_key())})
    box = Fernet(Fernet.generate_key())
    monkeypatch.setattr(pairing, "is_configured", lambda: True)
    monkeypatch.setattr(pairing, "encrypt", lambda value: "enc:v1:" + box.encrypt(value.encode()).decode())
    monkeypatch.setattr(pairing, "decrypt", lambda value: box.decrypt(value[len("enc:v1:"):].encode()).decode())
    record = EnterpriseLicenseRecord(
        lic_id="TESTMARKET", org_name="Test", code_hash="a" * 64, code_hint="TEST",
        status="active", install_id="test-install-market",
    )
    db.add(record)
    db.flush()
    token = sign({"v": 1, "lic": record.lic_id, "edition": "enterprise", "install": record.install_id, "iat": 1}, key)
    return record, token


def test_two_owner_pair_and_credential_only_once(db, tenant_id, user, signed_install):
    _, token = signed_install
    link, code = pairing.start(db, token)
    assert link.cloud_tenant_id is None
    assert link.credential_hash is None
    assert len(code) == 12
    state, _, credential = pairing.poll(db, token, link.id)
    assert (state, credential) == ("pending", None)

    approved = pairing.claim(db, code, tenant_id, user.id)
    assert approved.id == link.id
    assert approved.credential_hash is not None
    assert approved.credential_delivery_encrypted.startswith("enc:v1:")
    assert db.get(Tenant, tenant_id).kind == "both"
    state, _, credential = pairing.poll(db, token, link.id)
    assert state == "active" and credential is not None
    assert credential not in link.credential_delivery_encrypted
    assert pairing.authenticate(db, link.id, credential).id == link.id
    assert link.credential_delivery_encrypted is None
    with pytest.raises(HTTPException) as exc:
        pairing.authenticate(db, link.id, "wrong")
    assert exc.value.status_code == 401


def test_pair_requires_valid_license_and_unfinished_order_is_blocking(db, tenant_id, user, signed_install):
    record, token = signed_install
    with pytest.raises(HTTPException) as exc:
        pairing.start(db, "forged")
    assert exc.value.status_code == 403
    record.expires_at = datetime.now(timezone.utc) - timedelta(days=30)
    with pytest.raises(HTTPException) as exc:
        pairing.start(db, token)
    assert exc.value.status_code == 403
    record.expires_at = None
    link, code = pairing.start(db, token)
    db.add(MarketplaceOrder(distributor_tenant_id=tenant_id, retailer_tenant_id=tenant_id, status="placed"))
    db.flush()
    with pytest.raises(HTTPException) as exc:
        pairing.claim(db, code, tenant_id, user.id)
    assert exc.value.status_code == 409
    assert link.status == "pending"
    assert db.get(Tenant, tenant_id).kind == "standard"


def test_wrong_code_never_claims_pending_link(db, tenant_id, user, signed_install):
    _, token = signed_install
    link, _ = pairing.start(db, token)
    with pytest.raises(HTTPException) as exc:
        pairing.claim(db, "AAAAAAAAAAAA", tenant_id, user.id)
    assert exc.value.status_code == 400
    assert db.get(EnterpriseMarketLink, link.id).status == "pending"


def test_authenticated_install_must_keep_valid_license(db, tenant_id, user, signed_install):
    record, token = signed_install
    link, code = pairing.start(db, token)
    pairing.claim(db, code, tenant_id, user.id)
    _, _, credential = pairing.poll(db, token, link.id)
    record.expires_at = datetime.now(timezone.utc) - timedelta(days=100)
    with pytest.raises(HTTPException) as exc:
        pairing.authenticate(db, link.id, credential)
    assert exc.value.status_code == 403


def test_completed_local_order_blocks_revoke_to_preserve_future_returns(db, tenant_id, user, signed_install):
    from app.models.enterprise_market_bridge import EnterpriseMarketEvent
    from uuid import uuid4

    _, token = signed_install
    link, code = pairing.start(db, token)
    pairing.claim(db, code, tenant_id, user.id)
    order = MarketplaceOrder(distributor_tenant_id=tenant_id, retailer_tenant_id=tenant_id, status="delivered")
    db.add(order); db.flush()
    db.add(EnterpriseMarketEvent(id=uuid4(), link_id=link.id, order_id=order.id, operation_ref=order.id,
                                side="seller", kind="order", payload={}, status="posted"))
    db.flush()
    with pytest.raises(HTTPException) as exc:
        pairing.revoke(db, tenant_id)
    assert exc.value.status_code == 409
    assert link.status == "active" and link.credential_hash


def test_revocation_preserves_history_and_allows_new_pair_request(db, tenant_id, user, signed_install):
    _, token = signed_install
    market_settings = MarketplaceSettings(
        distributor_tenant_id=tenant_id, is_active=True, settlement_mode="online",
    )
    db.add(market_settings)
    link, code = pairing.start(db, token)
    pairing.claim(db, code, tenant_id, user.id)
    market_settings.is_active = False
    market_settings.settlement_mode = "credit"
    shadow = MarketplaceListing(distributor_tenant_id=tenant_id, title="کالای موقت", is_published=True)
    db.add(shadow)
    db.flush()
    db.add(EnterpriseMarketCatalog(
        link_id=link.id, market_listing_ref=shadow.id, cloud_listing_id=shadow.id,
        public_snapshot={}, available_qty=1, is_published=True,
        last_synced_at=datetime.now(timezone.utc),
    ))
    db.flush()
    pairing.revoke(db, tenant_id)
    db.refresh(shadow)
    assert link.status == "revoked"
    assert link.credential_hash is None
    assert db.get(Tenant, tenant_id).kind == "standard"
    assert shadow.is_published is False
    assert market_settings.is_active is True
    assert market_settings.settlement_mode == "online"
    assert pairing.poll(db, token, link.id)[0] == "revoked"
    fresh, new_code = pairing.start(db, token)
    assert fresh.id != link.id and new_code != code


def test_linked_cloud_account_cannot_write_through_legacy_market_routes(
    db, tenant_id, user, signed_install, client
):
    _, token = signed_install
    _, code = pairing.start(db, token)
    pairing.claim(db, code, tenant_id, user.id)
    response = client.post("/api/marketplace/retailer/connections", json={"distributor_tenant_id": str(tenant_id)})
    assert response.status_code == 409
    assert "نسخهٔ سازمانی" in response.json()["detail"]
