"""Real ledgers for two enterprise installs and both hybrid directions."""
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.models.enterprise_market_bridge import EnterpriseMarketItemMap, EnterpriseMarketCloudItemMap, EnterpriseMarketEvent, EnterpriseMarketLocalPosting
from app.models.inventory import Item, Warehouse
from app.models.invoices import SalesInvoice, PurchaseInvoice
from app.models.marketplace import MarketplaceCommission
from app.schemas.enterprise_market_bridge import MarketFinancialEvent
from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn
from app.schemas.marketplace import ReturnRequestIn, ReturnRequestLineIn
from app.seed import provision_tenant
from app.services import marketplace as market, inventory, enterprise_market_posting as posting, enterprise_market_transport as transport
from app.tenant_context import tenant_scope
from tests.test_marketplace import retailer_tenant, as_distributor, _primary_id, _setup_delivery_scenario, _link_both_market_parties  # noqa: F401


def _install(db, side):
    tenant = provision_tenant(db, name=f"نصب محلی {side}", slug=f"local-{uuid4().hex[:12]}",
                              owner_email=f"{uuid4().hex}@example.invalid", owner_password="LocalTest!2026", kind="standard")
    return tenant.id


def test_commercial_unit_posts_each_installation_own_base_and_returns_frozen_ratio(db):
    from app.models.item_units import ItemUnitConversion
    from app.schemas.item_units import ConversionRuleIn
    from app.schemas.enterprise_market_bridge import MarketFinancialLine
    from app.services import units
    from tests.test_item_unit_registry import configured
    item_ref, order_id = uuid4(), uuid4()
    installs = {side:_install(db, side) for side in ('seller', 'buyer')}
    item_ids = {}
    for side, tenant_id in installs.items():
        with tenant_scope(db, tenant_id):
            actor = market._tenant_actor(db, tenant_id)
            item, base, carton = configured(db)
            item_ids[side] = item.id
            rule = db.query(ItemUnitConversion).filter_by(item_id=item.id).one()
            units.configure_rule(db, item, ConversionRuleIn(from_unit_id=carton.id, to_unit_id=base.id,
                factor='24' if side == 'seller' else '30'), rule_id=rule.id)
            if side == 'seller':
                warehouse = db.query(Warehouse).filter_by(code='MAIN').one()
                inventory.post_purchase_invoice(db, PurchaseInvoiceIn(invoice_date=date.today(), warehouse_id=warehouse.id,
                    lines=[PurchaseInvoiceLineIn(item_id=item.id,qty='100',unit_cost='100')]),actor)
            db.add(EnterpriseMarketItemMap(tenant_id=tenant_id,market_item_ref=item_ref,local_item_id=item.id,
                approved_by_id=actor.id,approved_at=datetime.now(timezone.utc)))
            db.flush()
            event = MarketFinancialEvent(event_id=uuid4(),operation_ref=order_id,order_id=order_id,kind='order',
                side=side,counterparty_ref=uuid4(),counterparty_name='طرف آزمون واحد',order_date=date.today(),
                order_number=1,cash_amount='0',lines=[MarketFinancialLine(market_item_ref=item_ref,name='کالا',
                    unit='کارتن',qty='2',unit_price='2400',discount='0',consumer_price='0')])
            receipt = posting.consume(db,tenant_id,event)
            inbox = db.query(EnterpriseMarketLocalPosting).filter_by(event_id=event.event_id).one()
            assert receipt.outcome == 'posted', inbox.error_detail
            assert posting.consume(db,tenant_id,event) == receipt
            assert inventory.get_total_stock_qty(db,item.id) == (52 if side == 'seller' else 60)
            units.configure_rule(db,item,ConversionRuleIn(from_unit_id=carton.id,to_unit_id=base.id,factor='100'),rule_id=rule.id)
            carton.name='کارتن تازه';db.flush()
            returned=MarketFinancialEvent(event_id=uuid4(),operation_ref=uuid4(),order_id=order_id,kind='return',
                return_id=uuid4(),return_number=1,return_total='2400',side=side,counterparty_ref=event.counterparty_ref,
                counterparty_name=event.counterparty_name,order_date=date.today(),order_number=1,cash_amount='0',
                lines=[MarketFinancialLine(market_item_ref=item_ref,unit='کارتن',qty='1',unit_price='0',discount='0',consumer_price='0')])
            receipt=posting.consume(db,tenant_id,returned)
            inbox=db.query(EnterpriseMarketLocalPosting).filter_by(event_id=returned.event_id).one()
            assert receipt.outcome == 'posted',inbox.error_detail
            assert inventory.get_total_stock_qty(db,item.id) == (76 if side == 'seller' else 30)


@pytest.mark.parametrize("linked_sides", [("seller", "buyer"), ("seller",), ("buyer",)])
def test_real_order_cash_return_and_lost_receipts(db, user, as_distributor, retailer_tenant, linked_sides):
    seller_id = _primary_id(db)
    item, _, order = _setup_delivery_scenario(db, user, seller_id, retailer_tenant, require_delivery=False)
    links = _link_both_market_parties(db, seller_id, retailer_tenant, item.id)
    ref = db.query(EnterpriseMarketCloudItemMap).filter_by(cloud_item_id=item.id).one().market_item_ref
    locals_by_side = {}
    for side in ("seller", "buyer"):
        if side not in linked_sides:
            links[side].status = "revoked"
            continue
        local_id = _install(db, side)
        locals_by_side[side] = local_id
        if side == "seller":
            with tenant_scope(db, local_id):
                actor = market._tenant_actor(db, local_id)
                local_item = Item(tenant_id=local_id, sku="LOCAL-SELL", name="کالای محلی", unit="عدد", sales_price=8000)
                db.add(local_item); db.flush()
                warehouse = db.query(Warehouse).filter_by(code="MAIN").one()
                inventory.post_purchase_invoice(db, PurchaseInvoiceIn(invoice_date=date.today(), warehouse_id=warehouse.id,
                    lines=[PurchaseInvoiceLineIn(item_id=local_item.id, qty=100, unit_cost=5000)]), actor)
                db.add(EnterpriseMarketItemMap(tenant_id=local_id, market_item_ref=ref, local_item_id=local_item.id,
                                              approved_by_id=actor.id, approved_at=datetime.now(timezone.utc)))
                db.flush()
    with tenant_scope(db, seller_id):
        market.confirm_order(db, seller_id, user, order.id, Decimal(25))
    assert order.status == "sync_pending"
    assert order.cash_amount == Decimal(20000)

    def process(operation_id):
        rows = db.query(EnterpriseMarketEvent).filter_by(operation_ref=operation_id).all()
        for row in rows:
            if row.side not in linked_sides:
                assert row.status == "posted"
                continue
            local_id = locals_by_side[row.side]
            event = MarketFinancialEvent.model_validate(row.payload)
            with tenant_scope(db, local_id):
                first = posting.consume(db, local_id, event)
                assert first.outcome == "posted", first.error_code
                second = posting.consume(db, local_id, event)  # lost HTTP acknowledgement
                assert second == first
                assert db.query(EnterpriseMarketLocalPosting).filter_by(event_id=row.id).count() == 1
            transport.record_receipt(db, links[row.side].id, row.id, first)
            transport.record_receipt(db, links[row.side].id, row.id, second)

    process(order.id)
    assert order.status == "confirmed"
    assert db.query(MarketplaceCommission).filter_by(order_id=order.id).count() == 1
    with tenant_scope(db, seller_id):
        ret = market.request_return(db, retailer_tenant, ReturnRequestIn(order_id=order.id,
            lines=[ReturnRequestLineIn(order_line_id=order.lines[0].id, qty=2)]))
        market.approve_return(db, seller_id, user, ret.id)
    assert ret.status == "sync_pending"
    process(ret.id)
    assert ret.status == "approved"
    for side, local_id in locals_by_side.items():
        with tenant_scope(db, local_id):
            mapped = db.query(EnterpriseMarketItemMap).one()
            assert inventory.get_total_stock_qty(db, mapped.local_item_id) == Decimal(92 if side == "seller" else 8)
            assert db.query(SalesInvoice if side == "seller" else PurchaseInvoice).count() == 1
    with tenant_scope(db, seller_id):
        assert db.query(SalesInvoice).count() == (0 if "seller" in linked_sides else 1)
    with tenant_scope(db, retailer_tenant):
        assert db.query(PurchaseInvoice).count() == (0 if "buyer" in linked_sides else 1)
