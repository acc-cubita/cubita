"""Catalog publication is allowlisted, owner-approved, and atomic by generation."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.enterprise_license_registry import EnterpriseLicenseRecord
from app.models.enterprise_market_bridge import (
    EnterpriseMarketCatalog, EnterpriseMarketItemMap, EnterpriseMarketLink, EnterpriseMarketListingMap,
)
from app.models.inventory import Item
from app.models.marketplace import MarketplaceListing, MarketplaceListingComponent
from app.schemas.enterprise_market_bridge import (
    MarketCatalogFinalize, MarketCatalogPage, MarketComponentSnapshot, MarketListingSnapshot,
    MarketSellerSettingsSnapshot,
)
from app.services import enterprise_market_catalog as catalog

SELLER_SETTINGS = MarketSellerSettingsSnapshot(
    display_name="پخش نمونه", is_active=True, require_delivery=False,
    return_policy="", return_window_days=0, target_trades=[],
)


def _link(db, tenant_id, user_id):
    record = EnterpriseLicenseRecord(
        lic_id="CATALOG1", org_name="Test", code_hash="b" * 64, code_hint="LOG1",
        status="active", install_id="catalog-install",
    )
    db.add(record)
    db.flush()
    link = EnterpriseMarketLink(
        license_id=record.id, install_id=record.install_id,
        cloud_tenant_id=tenant_id, cloud_owner_id=user_id,
        status="active", credential_hash="c" * 64,
    )
    db.add(link)
    db.flush()
    return link


def _listing(ref=None, *, title="کالای نمونه", qty="5"):
    return MarketListingSnapshot(
        market_listing_ref=ref or uuid4(), kind="single", title=title, code="P1",
        unit="عدد", wholesale_price=Decimal(1000), consumer_price=Decimal(1200),
        currency_code="IRR", description="عمومی", images=[], category="نمونه",
        is_published=True, extra_trades=[], bonus_threshold_qty=Decimal(0),
        bonus_qty=Decimal(0), min_order_qty=Decimal(1), max_order_qty=Decimal(0),
        daily_order_limit=0, available_qty=Decimal(qty),
        components=[MarketComponentSnapshot(market_item_ref=uuid4(), name="کالا", qty=Decimal(1))],
    )


def test_catalog_never_publishes_before_owner_approval_or_complete_generation(db, tenant_id, user):
    link = _link(db, tenant_id, user.id)
    ref = uuid4()
    first = uuid4()
    snap = _listing(ref)
    assert catalog.accept_page(db, link, MarketCatalogPage(generation=first, listings=[snap])) == 1
    row = db.query(EnterpriseMarketCatalog).filter_by(market_listing_ref=ref).one()
    assert row.is_published is False
    with pytest.raises(HTTPException) as exc:
        catalog.finalize(db, link, MarketCatalogFinalize(generation=first, expected_count=2, owner_approved=True, seller_settings=SELLER_SETTINGS))
    assert exc.value.status_code == 409
    assert row.is_published is False
    assert catalog.finalize(db, link, MarketCatalogFinalize(generation=first, expected_count=1, owner_approved=False, seller_settings=SELLER_SETTINGS)) == 1
    assert row.is_published is False
    assert catalog.finalize(db, link, MarketCatalogFinalize(generation=first, expected_count=1, owner_approved=False, seller_settings=SELLER_SETTINGS)) == 1

    second = uuid4()
    catalog.accept_page(db, link, MarketCatalogPage(generation=second, listings=[_listing(ref, title="قیمت تازه")]))
    assert row.public_snapshot["title"] == "کالای نمونه"  # interrupted sync did not change public view
    catalog.finalize(db, link, MarketCatalogFinalize(generation=second, expected_count=1, owner_approved=True, seller_settings=SELLER_SETTINGS))
    assert row.is_published is True
    assert row.public_snapshot["title"] == "قیمت تازه"


def test_unselected_listing_is_unpublished_without_deleting_history(db, tenant_id, user):
    link = _link(db, tenant_id, user.id)
    one = _listing()
    two = _listing()
    gen = uuid4()
    catalog.accept_page(db, link, MarketCatalogPage(generation=gen, listings=[one, two]))
    catalog.finalize(db, link, MarketCatalogFinalize(generation=gen, expected_count=2, owner_approved=True, seller_settings=SELLER_SETTINGS))
    gen2 = uuid4()
    catalog.accept_page(db, link, MarketCatalogPage(generation=gen2, listings=[one]))
    catalog.finalize(db, link, MarketCatalogFinalize(generation=gen2, expected_count=1, owner_approved=True, seller_settings=SELLER_SETTINGS))
    rows = {row.market_listing_ref: row for row in db.query(EnterpriseMarketCatalog).all()}
    assert rows[one.market_listing_ref].is_published is True
    assert rows[two.market_listing_ref].is_published is False


def test_extra_internal_fields_rejected_at_cloud_boundary():
    payload = _listing().model_dump(mode="json")
    payload["warehouse_id"] = str(uuid4())
    with pytest.raises(ValueError):
        MarketListingSnapshot.model_validate(payload)


def test_local_selection_never_serializes_private_item_or_batch_data(db, tenant_id, user):
    item = Item(tenant_id=tenant_id, sku="BRIDGE-PRIVATE", name="کالای محلی", average_cost=Decimal(717))
    db.add(item)
    db.flush()
    listing = MarketplaceListing(
        distributor_tenant_id=tenant_id, kind="single", title="کالای عمومی",
        wholesale_price=Decimal(1000), consumer_price=Decimal(1100),
        distributor_item_id=item.id, is_published=True,
        components=[MarketplaceListingComponent(distributor_item_id=item.id, item_name="کالای عمومی", qty=1)],
    )
    db.add(listing)
    db.flush()
    db.add(EnterpriseMarketItemMap(
        tenant_id=tenant_id, local_item_id=item.id, market_item_ref=uuid4(),
        approved_by_id=user.id, approved_at=datetime.now(timezone.utc),
    ))
    db.add(EnterpriseMarketListingMap(
        tenant_id=tenant_id, local_listing_id=listing.id, market_listing_ref=uuid4(),
        approved_by_id=user.id, approved_at=datetime.now(timezone.utc),
    ))
    db.flush()
    sent = catalog.selected_snapshots(db, tenant_id)[0].model_dump(mode="json")
    assert sent["title"] == "کالای عمومی"
    assert sent["available_qty"] == "0"  # no configured warehouse: fail closed
    assert str(item.id) not in str(sent)
    assert str(listing.id) not in str(sent)
    assert "average_cost" not in str(sent)
