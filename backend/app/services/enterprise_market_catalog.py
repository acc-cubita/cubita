"""Explicitly selected listing sync; no inventory or ledger ORM leaves on-prem."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.enterprise_market_bridge import (
    EnterpriseMarketCatalog, EnterpriseMarketCloudItemMap,
    EnterpriseMarketItemMap,
    EnterpriseMarketLink,
    EnterpriseMarketListingMap,
)
from app.models.inventory import Item
from app.models.marketplace import MarketplaceListing, MarketplaceListingComponent
from app.schemas.enterprise_market_bridge import MarketCatalogFinalize, MarketCatalogPage, MarketListingSnapshot, listing_snapshot
from app.services import marketplace as marketplace_svc
from app.tenant_context import tenant_scope


def selected_snapshots(db: Session, tenant_id: UUID) -> list[MarketListingSnapshot]:
    """Local-only read. An unmapped component fails the whole publication."""
    mappings = db.query(EnterpriseMarketListingMap).filter(
        EnterpriseMarketListingMap.tenant_id == tenant_id
    ).order_by(EnterpriseMarketListingMap.market_listing_ref).all()
    if not mappings:
        return []
    listings = db.query(MarketplaceListing).filter(
        MarketplaceListing.distributor_tenant_id == tenant_id,
        MarketplaceListing.id.in_([row.local_listing_id for row in mappings]),
    ).all()
    by_id = {row.id: row for row in listings}
    item_maps = db.query(EnterpriseMarketItemMap).filter(EnterpriseMarketItemMap.tenant_id == tenant_id).all()
    refs = {row.local_item_id: row.market_item_ref for row in item_maps}
    quantities = marketplace_svc._orderable_by_listing(db, listings, {tenant_id})
    snapshots: list[MarketListingSnapshot] = []
    for mapping in mappings:
        listing = by_id.get(mapping.local_listing_id)
        if listing is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "نگاشت کاتالوگ به کالای این شرکت اشاره نمی‌کند")
        try:
            snapshots.append(listing_snapshot(
                listing, quantities.get(listing.id) or Decimal(0),
                listing_ref=mapping.market_listing_ref, item_refs=refs,
            ))
        except KeyError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, "همهٔ اجزای کالای انتخاب‌شده باید ابتدا نگاشت و تأیید شوند") from exc
    return snapshots


def accept_page(db: Session, link: EnterpriseMarketLink, page: MarketCatalogPage) -> int:
    """Cloud upsert: the JSON contains only fields of MarketListingSnapshot."""
    if link.cloud_tenant_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "پیوند هنوز تأیید نشده است")
    now = datetime.now(timezone.utc)
    db.refresh(link, with_for_update=True)
    if link.active_generation == page.generation:
        return len(page.listings)
    if link.pending_generation not in (None, page.generation):
        if link.pending_started_at is not None and now - link.pending_started_at < timedelta(minutes=15):
            raise HTTPException(status.HTTP_409_CONFLICT, "دورِ قبلی بارگذاری کاتالوگ هنوز در جریان است")
    if link.pending_generation != page.generation:
        link.pending_generation = page.generation
        link.pending_started_at = now
    seen: set[UUID] = set()
    for snapshot in page.listings:
        if snapshot.market_listing_ref in seen:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "شناسهٔ کاتالوگ در این صفحه تکراری است")
        seen.add(snapshot.market_listing_ref)
        row = db.query(EnterpriseMarketCatalog).filter(
            EnterpriseMarketCatalog.market_listing_ref == snapshot.market_listing_ref
        ).with_for_update().first()
        if row is not None and row.link_id != link.id:
            raise HTTPException(status.HTTP_409_CONFLICT, "شناسهٔ کاتالوگ به پیوند دیگری تعلق دارد")
        if row is None:
            row = EnterpriseMarketCatalog(
                link_id=link.id, market_listing_ref=snapshot.market_listing_ref,
                public_snapshot=snapshot.model_dump(mode="json"),
                available_qty=snapshot.available_qty,
                is_published=False, last_synced_at=now,
            )
            db.add(row)
        row.staged_snapshot = snapshot.model_dump(mode="json")
        row.staged_available_qty = snapshot.available_qty
        row.sync_generation = page.generation
    db.flush()
    return len(page.listings)


def finalize(db: Session, link: EnterpriseMarketLink, data: MarketCatalogFinalize) -> int:
    """Atomic generation switch; incomplete uploads never become public."""
    db.refresh(link, with_for_update=True)
    if link.active_generation == data.generation:
        return data.expected_count
    if link.pending_generation != data.generation:
        raise HTTPException(status.HTTP_409_CONFLICT, "این دورِ بارگذاری کاتالوگ فعال نیست")
    rows = db.query(EnterpriseMarketCatalog).filter(
        EnterpriseMarketCatalog.link_id == link.id,
        EnterpriseMarketCatalog.sync_generation == data.generation,
    ).with_for_update().all()
    if len(rows) != data.expected_count:
        raise HTTPException(status.HTTP_409_CONFLICT, "بارگذاری کاتالوگ ناقص است؛ انتشار انجام نشد")
    link.catalog_approved = data.owner_approved
    # A link cannot implicitly re-publish a historical cloud listing: only
    # rows uploaded through this new, approved bridge generation are touched.
    for row in rows:
        if row.staged_snapshot is None or row.staged_available_qty is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "بارگذاری کاتالوگ ناقص است")
        row.public_snapshot = row.staged_snapshot
        row.available_qty = row.staged_available_qty
        row.is_published = bool(link.catalog_approved and row.public_snapshot["is_published"])
        row.staged_snapshot = None
        row.staged_available_qty = None
        row.last_synced_at = datetime.now(timezone.utc)
        _publish_cloud_shadow(db, link, row)
    db.query(EnterpriseMarketCatalog).filter(
        EnterpriseMarketCatalog.link_id == link.id,
        EnterpriseMarketCatalog.sync_generation != data.generation,
    ).update({EnterpriseMarketCatalog.is_published: False}, synchronize_session=False)
    inactive_rows = db.query(EnterpriseMarketCatalog).filter(
        EnterpriseMarketCatalog.link_id == link.id,
        EnterpriseMarketCatalog.sync_generation != data.generation,
    ).all()
    for old in inactive_rows:
        if old.cloud_listing_id is not None:
            listing = db.get(MarketplaceListing, old.cloud_listing_id)
            if listing is not None:
                listing.is_published = False
    market_settings = marketplace_svc.get_settings(db, link.cloud_tenant_id)
    market_settings.display_name = data.seller_settings.display_name.strip()
    market_settings.require_delivery = data.seller_settings.require_delivery
    market_settings.return_policy = data.seller_settings.return_policy.strip()
    market_settings.return_window_days = data.seller_settings.return_window_days
    market_settings.target_trades = list(data.seller_settings.target_trades)
    market_settings.settlement_mode = "credit"  # never online for an enterprise party
    market_settings.is_active = bool(
        data.seller_settings.is_active and link.catalog_approved and any(row.is_published for row in rows)
    )
    link.last_sync_at = datetime.now(timezone.utc)
    link.active_generation = data.generation
    link.pending_generation = None
    link.pending_started_at = None
    db.flush()
    return len(rows)


def _publish_cloud_shadow(db: Session, link: EnterpriseMarketLink, row: EnterpriseMarketCatalog) -> None:
    """Use market-only shadow Items so existing catalog/connection UI keeps working."""
    assert link.cloud_tenant_id is not None
    snapshot = MarketListingSnapshot.model_validate(row.public_snapshot)
    cloud_components = []
    with tenant_scope(db, link.cloud_tenant_id):
        for component in snapshot.components:
            item_map = db.query(EnterpriseMarketCloudItemMap).filter(
                EnterpriseMarketCloudItemMap.link_id == link.id,
                EnterpriseMarketCloudItemMap.market_item_ref == component.market_item_ref,
            ).first()
            item = db.get(Item, item_map.cloud_item_id) if item_map else None
            if item is None:
                item = Item(
                    tenant_id=link.cloud_tenant_id, sku=f"EM-{component.market_item_ref.hex}",
                    name=component.name, unit=snapshot.unit, sales_price=snapshot.wholesale_price,
                    average_cost=0,
                )
                db.add(item)
                db.flush()
                db.add(EnterpriseMarketCloudItemMap(
                    link_id=link.id, market_item_ref=component.market_item_ref,
                    cloud_item_id=item.id,
                ))
            else:
                item.name = component.name
                item.unit = snapshot.unit
                item.sales_price = snapshot.wholesale_price
            cloud_components.append(MarketplaceListingComponent(
                distributor_item_id=item.id, item_name=component.name, qty=component.qty,
            ))
    listing = db.get(MarketplaceListing, row.cloud_listing_id) if row.cloud_listing_id else None
    if listing is None:
        listing = MarketplaceListing(distributor_tenant_id=link.cloud_tenant_id, title=snapshot.title)
        db.add(listing)
        db.flush()
        row.cloud_listing_id = listing.id
    listing.kind = snapshot.kind
    listing.title = snapshot.title
    listing.code = snapshot.code
    listing.unit = snapshot.unit
    listing.wholesale_price = snapshot.wholesale_price
    listing.consumer_price = snapshot.consumer_price
    listing.currency_code = snapshot.currency_code
    listing.description = snapshot.description
    listing.images = snapshot.images
    listing.category = snapshot.category
    listing.extra_trades = snapshot.extra_trades
    listing.bonus_threshold_qty = snapshot.bonus_threshold_qty
    listing.bonus_qty = snapshot.bonus_qty
    listing.min_order_qty = snapshot.min_order_qty
    listing.max_order_qty = snapshot.max_order_qty
    listing.daily_order_limit = snapshot.daily_order_limit
    listing.distributor_item_id = cloud_components[0].distributor_item_id if snapshot.kind == "single" else None
    listing.components = cloud_components
    listing.is_published = row.is_published
    db.flush()
