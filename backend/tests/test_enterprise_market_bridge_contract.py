"""فیلدهای دفتر/انبارِ داخلی نباید با فهرستِ بازار همگام شوند."""
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.schemas.enterprise_market_bridge import MarketPostingReceipt, listing_snapshot
from app.services.enterprise_market_orders import _public_lines


def test_listing_snapshot_exports_only_market_fields():
    item_id = uuid4()
    market_item_ref = uuid4()
    market_listing_ref = uuid4()
    listing = SimpleNamespace(
        id=uuid4(), kind="single", title="کالای نمونه", code="P-1", unit="عدد",
        wholesale_price=1000, consumer_price=1200, currency_code="IRR",
        description="شرح عمومی", images=[], category="عمومی", is_published=True,
        extra_trades=[], bonus_threshold_qty=0, bonus_qty=0, min_order_qty=1,
        max_order_qty=0, daily_order_limit=0,
        components=[SimpleNamespace(distributor_item_id=item_id, item_name="کالای نمونه", qty=1,
                                    purchase_cost=700, stock_batch_id=uuid4())],
        purchase_cost=700, journal_entry_id=uuid4(), warehouse_id=uuid4(),
    )

    sent = listing_snapshot(
        listing, Decimal(5), listing_ref=market_listing_ref, item_refs={item_id: market_item_ref}
    ).model_dump(mode="json")

    assert sent["available_qty"] == "5"
    assert sent["market_listing_ref"] == str(market_listing_ref)
    assert sent["components"][0]["market_item_ref"] == str(market_item_ref)
    assert str(item_id) not in str(sent)
    assert str(listing.id) not in str(sent)
    assert "purchase_cost" not in str(sent)
    assert "journal_entry_id" not in str(sent)
    assert "warehouse_id" not in str(sent)
    assert "stock_batch_id" not in str(sent)


def test_listing_without_approved_item_mapping_fails_closed():
    listing = SimpleNamespace(
        id=uuid4(), kind="single", title="کالا", code="", unit="عدد", wholesale_price=1,
        consumer_price=0, currency_code="IRR", description="", images=[], category="",
        is_published=True, extra_trades=[], bonus_threshold_qty=0, bonus_qty=0,
        min_order_qty=0, max_order_qty=0, daily_order_limit=0,
        components=[SimpleNamespace(distributor_item_id=uuid4(), item_name="کالا", qty=1)],
    )
    try:
        listing_snapshot(listing, Decimal(1), listing_ref=uuid4(), item_refs={})
    except KeyError:
        pass
    else:
        raise AssertionError("کالای بدون نگاشت نباید منتشر شود")


def test_posting_receipt_contains_no_local_document_reference():
    sent = MarketPostingReceipt(
        event_id=uuid4(), order_id=uuid4(), side="seller", outcome="posted"
    ).model_dump(mode="json")
    assert set(sent) == {"event_id", "order_id", "side", "outcome", "error_code"}


def test_linked_seller_never_falls_back_to_a_private_item_id(db):
    local_id = uuid4()
    line = [{
        "distributor_item_id": local_id, "units": Decimal(1),
        "name": "کالای عمومی", "unit": "عدد",
        "unit_price": Decimal(1000), "discount": Decimal(0),
        "consumer_price": Decimal(0),
    }]
    with pytest.raises(HTTPException) as exc:
        _public_lines(db, line, seller_linked=True)
    assert exc.value.status_code == 409
    assert _public_lines(db, line, seller_linked=False)[0].market_item_ref == local_id
