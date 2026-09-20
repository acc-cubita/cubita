"""تخصیصِ بارِ ورودی به کاتالوگِ بازار (فاز ۲، §۵ §۶ §۷ §۱۶).

بارِ ۱۰۰۰تایی در انبار لزوماً یعنی ۱۰۰۰ تا برای فروشِ عمده نیست. تا پیش از
مهاجرتِ ۰۱۷۴ چنین مرزی وجود نداشت: هرچه در انبار بود، در کاتالوگ قابلِ سفارش بود.
"""
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.advanced_inventory import StockBatch
from app.models.marketplace import MarketplaceListing, MarketplaceListingComponent, MarketplaceSettings
from app.schemas.marketplace import OrderLineIn, OrderPlaceIn
from app.services import marketplace as svc
from app.tenant_context import tenant_scope

from tests.test_marketplace import _approve, _bare_tenant, _make_item, _primary_id
from tests.test_marketplace_reservations import _listing, _stocked_item


def _setup(db):
    primary_id = _primary_id(db)
    db.add(MarketplaceSettings(distributor_tenant_id=primary_id, is_active=True))
    retailer = _bare_tenant(db, "retailer", "فروشگاهِ تخصیص")
    _approve(db, primary_id, retailer.id)
    return primary_id, retailer.id


def _batch_of(db, item):
    return db.query(StockBatch).filter(StockBatch.item_id == item.id).one()


def _orderable(db, retailer_id, primary_id, listing_id):
    rows = svc.list_catalog(db, retailer_id, primary_id)
    return next(x for x in rows if x["id"] == listing_id)["orderable_qty"]


# ── سقفِ عرضه ────────────────────────────────────────────────────────
def test_without_any_allocation_the_whole_stock_is_offered(db):
    """**پیش‌فرض = رفتارِ دیروز** — لیستینگی که تخصیص نگرفته بی‌سقف است."""
    primary_id, retailer_id = _setup(db)
    item, _ = _stocked_item(db, "CA-NONE", "بی‌سقف", 1000)
    listing = _listing(db, primary_id, item, "بی‌سقفِ عمده")
    assert _orderable(db, retailer_id, primary_id, listing.id) == 1000


def test_allocation_caps_what_the_catalog_offers(db):
    """§۶ — بارِ ۱۰۰۰تایی با تخصیصِ ۴۰۰، فقط ۴۰۰ تا عرضه می‌کند."""
    primary_id, retailer_id = _setup(db)
    item, _ = _stocked_item(db, "CA-CAP", "سقف‌دار", 1000)
    listing = _listing(db, primary_id, item, "سقف‌دارِ عمده")
    batch = _batch_of(db, item)

    svc.allocate_batch(db, primary_id, listing.id, batch.id, Decimal(400), None)
    assert _orderable(db, retailer_id, primary_id, listing.id) == 400


def test_an_order_eats_into_the_allocation_not_just_the_stock(db):
    """۴۰۰ تخصیص با ۱۰۰ سفارشِ ثبت‌شده یعنی ۳۰۰ مانده، نه ۴۰۰.

    موجودیِ آزاد رزرو را از قبل کم کرده (۹۰۰ مانده)، ولی سقف یک عددِ **ثابت**
    است؛ اگر از آن کم نشود، کاتالوگ همچنان ۴۰۰ می‌گفت.
    """
    primary_id, retailer_id = _setup(db)
    item, _ = _stocked_item(db, "CA-EAT", "خورده‌شده", 1000)
    listing = _listing(db, primary_id, item, "خورده‌شده‌ی عمده")
    batch = _batch_of(db, item)
    svc.allocate_batch(db, primary_id, listing.id, batch.id, Decimal(400), None)

    svc.place_order(
        db, retailer_id,
        OrderPlaceIn(distributor_tenant_id=primary_id, lines=[OrderLineIn(listing_id=listing.id, qty=Decimal(100))]),
    )
    assert _orderable(db, retailer_id, primary_id, listing.id) == 300


def test_allocation_cannot_exceed_the_batch(db):
    primary_id, _ = _setup(db)
    item, _ = _stocked_item(db, "CA-OVER", "زیاده", 50)
    listing = _listing(db, primary_id, item, "زیاده‌ی عمده")
    batch = _batch_of(db, item)

    with pytest.raises(HTTPException) as err:
        svc.allocate_batch(db, primary_id, listing.id, batch.id, Decimal(80), None)
    assert err.value.status_code == 400
    assert "قابلِ فروش" in err.value.detail


def test_a_batch_of_another_item_is_refused(db):
    """بی این، بارِ شامپو را می‌شد به لیستینگِ روغن داد."""
    primary_id, _ = _setup(db)
    milk, _ = _stocked_item(db, "CA-MILK", "شیر", 30)
    oil, _ = _stocked_item(db, "CA-OIL", "روغن", 30)
    listing = _listing(db, primary_id, milk, "شیرِ عمده")
    wrong = _batch_of(db, oil)

    with pytest.raises(HTTPException) as err:
        svc.allocate_batch(db, primary_id, listing.id, wrong.id, Decimal(5), None)
    assert err.value.status_code == 400
    assert "تعلق ندارد" in err.value.detail or "مالِ کالایی نیست" in err.value.detail


def test_reallocating_updates_the_same_row(db):
    """قیدِ یکتا دو جواب برای «چه‌قدر از این بار عرضه شده» نمی‌گذارد."""
    primary_id, retailer_id = _setup(db)
    item, _ = _stocked_item(db, "CA-AGAIN", "دوباره", 200)
    listing = _listing(db, primary_id, item, "دوباره‌ی عمده")
    batch = _batch_of(db, item)

    svc.allocate_batch(db, primary_id, listing.id, batch.id, Decimal(50), None)
    svc.allocate_batch(db, primary_id, listing.id, batch.id, Decimal(120), None)

    rows = svc.catalog_allocation_rows(db, primary_id, listing.id)
    assert len(rows) == 1
    assert rows[0]["qty"] == 120
    assert _orderable(db, retailer_id, primary_id, listing.id) == 120


# ── §۱۶ فراخوان ──────────────────────────────────────────────────────
def test_recalling_the_batch_removes_it_from_the_catalog(db):
    """§۱۶ «Catalog Allocation آن غیرفعال شود» — بی آنکه کسی ردیف را خاموش کند.

    بارِ فراخوان‌شده `sellable = 0` دارد و تخصیص به همان محدود می‌شود، پس
    خودبه‌خود از کاتالوگ بیرون می‌رود.
    """
    primary_id, retailer_id = _setup(db)
    item, _ = _stocked_item(db, "CA-RECALL", "فراخوانی", 300)
    listing = _listing(db, primary_id, item, "فراخوانی عمده")
    batch = _batch_of(db, item)
    svc.allocate_batch(db, primary_id, listing.id, batch.id, Decimal(200), None)
    assert _orderable(db, retailer_id, primary_id, listing.id) == 200

    with tenant_scope(db, primary_id):
        from app.services import batches as batches_svc

        batches_svc.set_hold(db, batch, hold_status="recalled", reason="اعلامِ کارخانه", user=None)

    assert _orderable(db, retailer_id, primary_id, listing.id) == 0
    #: و ردیفِ تخصیص همچنان هست — تاریخچه پاک نمی‌شود.
    rows = svc.catalog_allocation_rows(db, primary_id, listing.id)
    assert len(rows) == 1
    assert rows[0]["batch_status"] == "recalled"
    assert rows[0]["batch_sellable_qty"] == 0


def test_deactivating_an_allocation_stops_offering_it(db):
    primary_id, retailer_id = _setup(db)
    item, _ = _stocked_item(db, "CA-OFF", "خاموش", 100)
    listing = _listing(db, primary_id, item, "خاموشِ عمده")
    batch = _batch_of(db, item)
    svc.allocate_batch(db, primary_id, listing.id, batch.id, Decimal(60), None)
    rows = svc.catalog_allocation_rows(db, primary_id, listing.id)

    svc.set_allocation_active(db, primary_id, rows[0]["id"], is_active=False)
    #: تخصیصِ خاموش یعنی «سقفی اعلام نشده»، پس دوباره کلِ موجودی عرضه می‌شود.
    assert _orderable(db, retailer_id, primary_id, listing.id) == 100


# ── پک ───────────────────────────────────────────────────────────────
def test_pack_allocation_caps_only_the_allocated_component(db):
    """جزئی که تخصیص نگرفته بی‌سقف می‌ماند — «پیش‌فرض = رفتارِ دیروز»."""
    primary_id, retailer_id = _setup(db)
    shampoo, _ = _stocked_item(db, "CA-SH", "شامپو", 100)
    soap, _ = _stocked_item(db, "CA-SO", "صابون", 100)

    listing = MarketplaceListing(
        distributor_tenant_id=primary_id, kind="pack", title="پکِ سقف‌دار",
        unit="پک", wholesale_price=20000, is_published=True,
    )
    listing.components.append(
        MarketplaceListingComponent(distributor_item_id=shampoo.id, item_name="شامپو", qty=Decimal(2))
    )
    listing.components.append(
        MarketplaceListingComponent(distributor_item_id=soap.id, item_name="صابون", qty=Decimal(1))
    )
    db.add(listing)
    db.flush()

    #: بی تخصیص: شامپو ۱۰۰/۲ = ۵۰، صابون ۱۰۰/۱ = ۱۰۰ → کمینه ۵۰.
    assert _orderable(db, retailer_id, primary_id, listing.id) == 50

    #: با تخصیصِ ۲۰ صابون: ۲۰/۱ = ۲۰ → کمینه ۲۰.
    svc.allocate_batch(db, primary_id, listing.id, _batch_of(db, soap).id, Decimal(20), None)
    assert _orderable(db, retailer_id, primary_id, listing.id) == 20
