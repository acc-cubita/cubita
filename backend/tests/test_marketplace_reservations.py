"""سفارشِ بازار موجودیِ پخش‌کننده را رزرو می‌کند (فاز ۲، §۸ §۹ §۱۰ §۳۰).

**باگی که این‌جا بسته می‌شود:** `place_order` اتصال، صنف، کف/سقفِ تعداد و سقفِ
روزانه را می‌سنجید و انبارِ پخش‌کننده را **هرگز**. کمبود تازه موقعِ *تأیید*
بیرون می‌زد — یعنی فروشگاه سفارشی می‌داد که فکر می‌کرد ثبت شده و روزِ بعد رد
می‌شد. این باگ مستقل از بچ بود و برای همه‌ی کالاها وجود داشت.
"""
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.marketplace import (
    MarketplaceListing,
    MarketplaceListingComponent,
    MarketplaceSettings,
)
from app.models.stock_reservations import StockReservation
from app.schemas.marketplace import OrderLineIn, OrderPlaceIn
from app.services import marketplace as svc
from app.services import reservations as reservations_svc
from app.tenant_context import tenant_scope

from tests.test_marketplace import _approve, _bare_tenant, _make_item, _primary_id, retailer_tenant  # noqa: F401


def _stocked_item(db, sku, name, qty):
    """کالایی با موجودیِ واقعی در انبارِ پخش‌کننده."""
    from datetime import date

    from app.models.inventory import Warehouse
    from app.models.user import User
    from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn
    from app.services.inventory import post_purchase_invoice

    item = _make_item(db, sku, name)
    wh = db.query(Warehouse).filter(Warehouse.is_active.is_(True)).order_by(Warehouse.code).first()
    user = db.query(User).first()
    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=date.today(), warehouse_id=wh.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(qty), unit_cost=Decimal(1000))],
        ),
        user,
    )
    return item, wh


def _listing(db, distributor_id, item, title, price=5000, per_unit=1):
    listing = MarketplaceListing(
        distributor_tenant_id=distributor_id, kind="single", title=title,
        unit="عدد", wholesale_price=price, is_published=True, distributor_item_id=item.id,
    )
    listing.components.append(
        MarketplaceListingComponent(distributor_item_id=item.id, item_name=item.name, qty=Decimal(per_unit))
    )
    db.add(listing)
    db.flush()
    return listing


def _setup(db):
    primary_id = _primary_id(db)
    db.add(MarketplaceSettings(distributor_tenant_id=primary_id, is_active=True))
    retailer = _bare_tenant(db, "retailer", "فروشگاهِ رزرو")
    _approve(db, primary_id, retailer.id)
    return primary_id, retailer.id


# ── رزرو هنگامِ ثبتِ سفارش ────────────────────────────────────────────
def test_placing_an_order_reserves_the_distributors_stock(db):
    primary_id, retailer_id = _setup(db)
    item, wh = _stocked_item(db, "MR-OK", "شیر", 100)
    listing = _listing(db, primary_id, item, "شیرِ عمده")

    order = svc.place_order(
        db, retailer_id,
        OrderPlaceIn(distributor_tenant_id=primary_id, lines=[OrderLineIn(listing_id=listing.id, qty=Decimal(30))]),
    )
    assert order.status == "placed"

    #: ادعا در دفترِ **پخش‌کننده** نشسته، نه فروشگاه.
    with tenant_scope(db, primary_id):
        assert reservations_svc.reserved_for_item(db, item.id, wh.id) == 30
        #: موجودیِ فیزیکی تکان نخورده — §۸.
        from app.services.inventory import get_stock_qty

        assert get_stock_qty(db, item.id, wh.id) == 100
        assert reservations_svc.available_for(db, item.id, wh.id) == 70


def test_a_second_order_cannot_take_what_the_first_reserved(db):
    primary_id, retailer_id = _setup(db)
    item, _ = _stocked_item(db, "MR-RACE", "کره", 50)
    listing = _listing(db, primary_id, item, "کره‌ی عمده")

    svc.place_order(
        db, retailer_id,
        OrderPlaceIn(distributor_tenant_id=primary_id, lines=[OrderLineIn(listing_id=listing.id, qty=Decimal(40))]),
    )
    with pytest.raises(HTTPException) as err:
        svc.place_order(
            db, retailer_id,
            OrderPlaceIn(distributor_tenant_id=primary_id, lines=[OrderLineIn(listing_id=listing.id, qty=Decimal(20))]),
        )
    assert err.value.status_code == 400
    assert "کره‌ی عمده" in err.value.detail
    assert "قابلِ سفارش" in err.value.detail


def test_one_order_with_two_lines_of_one_item_is_summed(db):
    """سفارشی با دو ردیفِ ۶تایی از یک کالا نباید در برابرِ موجودیِ ۱۰ پاس شود."""
    primary_id, retailer_id = _setup(db)
    item, _ = _stocked_item(db, "MR-SUM", "پنیر", 10)
    listing = _listing(db, primary_id, item, "پنیرِ عمده")

    with pytest.raises(HTTPException) as err:
        svc.place_order(
            db, retailer_id,
            OrderPlaceIn(distributor_tenant_id=primary_id, lines=[
                OrderLineIn(listing_id=listing.id, qty=Decimal(6)),
                OrderLineIn(listing_id=listing.id, qty=Decimal(6)),
            ]),
        )
    assert err.value.status_code == 400


# ── لغو، تأیید ───────────────────────────────────────────────────────
def test_rejecting_an_order_frees_the_stock_again(db):
    """§۱۰ — بی این، ردِ سفارش موجودی را تا ابد قفل نگه می‌داشت."""
    primary_id, retailer_id = _setup(db)
    item, wh = _stocked_item(db, "MR-REJ", "ماست", 60)
    listing = _listing(db, primary_id, item, "ماستِ عمده")

    order = svc.place_order(
        db, retailer_id,
        OrderPlaceIn(distributor_tenant_id=primary_id, lines=[OrderLineIn(listing_id=listing.id, qty=Decimal(25))]),
    )
    with tenant_scope(db, primary_id):
        assert reservations_svc.reserved_for_item(db, item.id, wh.id) == 25

    svc.reject_order(db, primary_id, order.id)
    with tenant_scope(db, primary_id):
        assert reservations_svc.reserved_for_item(db, item.id, wh.id) == 0
        assert reservations_svc.available_for(db, item.id, wh.id) == 60


def test_confirming_consumes_the_claim_rather_than_releasing_it(db, retailer_tenant):
    """کالا واقعاً رفت، پس رویداد `consume` است نه `release` (§۱۵).

    این‌جا فروشگاهِ **کاملاً provision‌شده** لازم است، نه `_bare_tenant`: تأیید
    فاکتورِ خرید در دفترِ فروشگاه می‌زند و به انبار، چارتِ حساب و کاربرِ واقعی
    نیاز دارد.
    """
    from app.models.user import User

    primary_id = _primary_id(db)
    retailer_id = retailer_tenant
    db.add(MarketplaceSettings(distributor_tenant_id=primary_id, is_active=True))
    _approve(db, primary_id, retailer_id)
    item, wh = _stocked_item(db, "MR-CONF", "روغن", 80)
    listing = _listing(db, primary_id, item, "روغنِ عمده")
    order = svc.place_order(
        db, retailer_id,
        OrderPlaceIn(distributor_tenant_id=primary_id, lines=[OrderLineIn(listing_id=listing.id, qty=Decimal(20))]),
    )

    user = db.query(User).first()
    svc.confirm_order(db, primary_id, user, order.id)

    with tenant_scope(db, primary_id):
        assert reservations_svc.reserved_for_item(db, item.id, wh.id) == 0
        events = {
            r.event for r in db.query(StockReservation).filter(StockReservation.item_id == item.id).all()
        }
        assert events == {"reserve", "consume"}, "خروجِ قطعی نباید «لغو» ثبت شود"
        #: و موجودیِ فیزیکی حالا واقعاً کم شده.
        from app.services.inventory import get_stock_qty

        assert get_stock_qty(db, item.id, wh.id) == 60


# ── کاتالوگ ──────────────────────────────────────────────────────────
def test_catalog_shows_orderable_quantity_net_of_reservations(db):
    primary_id, retailer_id = _setup(db)
    item, _ = _stocked_item(db, "MR-CAT", "نان", 90)
    listing = _listing(db, primary_id, item, "نانِ عمده")

    rows = svc.list_catalog(db, retailer_id, primary_id)
    row = next(x for x in rows if x["id"] == listing.id)
    assert row["orderable_qty"] == 90

    svc.place_order(
        db, retailer_id,
        OrderPlaceIn(distributor_tenant_id=primary_id, lines=[OrderLineIn(listing_id=listing.id, qty=Decimal(15))]),
    )
    rows = svc.list_catalog(db, retailer_id, primary_id)
    row = next(x for x in rows if x["id"] == listing.id)
    assert row["orderable_qty"] == 75, "رزروِ سفارشِ ثبت‌شده باید از عددِ کاتالوگ کم شود"


def test_pack_is_limited_by_its_scarcest_component(db):
    """پکِ ۲ شامپو + ۱ صابون با ۵ صابون، بیشتر از ۵ پک نیست."""
    primary_id, retailer_id = _setup(db)
    shampoo, _ = _stocked_item(db, "MR-SH", "شامپو", 100)
    soap, _ = _stocked_item(db, "MR-SO", "صابون", 5)

    listing = MarketplaceListing(
        distributor_tenant_id=primary_id, kind="pack", title="پکِ بهداشتی",
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

    rows = svc.list_catalog(db, retailer_id, primary_id)
    row = next(x for x in rows if x["id"] == listing.id)
    assert row["orderable_qty"] == 5


def test_catalog_says_unknown_not_zero_when_there_is_no_warehouse(db):
    """`None` یعنی نمی‌دانیم؛ یکی‌کردنش با صفر یعنی «ناموجود»ِ دروغین."""
    from app.models.inventory import Warehouse

    primary_id, retailer_id = _setup(db)
    item, _ = _stocked_item(db, "MR-NOWH", "بی‌انبار", 10)
    listing = _listing(db, primary_id, item, "بی‌انبارِ عمده")

    for wh in db.query(Warehouse).all():
        wh.is_active = False
    db.flush()

    rows = svc.list_catalog(db, retailer_id, primary_id)
    row = next(x for x in rows if x["id"] == listing.id)
    assert row["orderable_qty"] is None
