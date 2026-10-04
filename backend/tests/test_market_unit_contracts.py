"""Selected market units stay historical and never leak private conversions."""
from datetime import date,datetime,timezone
from decimal import Decimal
from uuid import uuid4

from app.models.inventory import Warehouse
from app.models.item_units import ItemUnitConversion
from app.models.invoices import SalesInvoice,PurchaseInvoice
from app.models.marketplace import MarketplaceSettings,MarketplaceItemLink
from app.models.advanced_inventory import StockBatch
from app.models.enterprise_market_bridge import EnterpriseMarketItemMap,EnterpriseMarketListingMap,EnterpriseMarketLocalPosting
from app.schemas.invoices import PurchaseInvoiceIn,PurchaseInvoiceLineIn
from app.schemas.marketplace import ListingIn,OrderPlaceIn,OrderLineIn,ReturnRequestIn,ReturnRequestLineIn
from app.schemas.enterprise_market_bridge import MarketFinancialEvent,MarketFinancialLine,listing_snapshot
from app.services import marketplace as market,inventory,enterprise_market_catalog as catalog,enterprise_market_posting as posting
from app.services import market_units,units
from app.tenant_context import tenant_scope
from tests.test_marketplace import as_distributor,retailer_tenant,_approve
from tests.test_item_unit_registry import configured


def test_native_selected_carton_freezes_order_and_returns_each_base(db,user,tenant_id,as_distributor,retailer_tenant):
    item,base,carton=configured(db)
    warehouse=db.query(Warehouse).filter_by(code='MAIN').one()
    inventory.post_purchase_invoice(db,PurchaseInvoiceIn(invoice_date=date.today(),warehouse_id=warehouse.id,
        lines=[PurchaseInvoiceLineIn(item_id=item.id,qty='100',unit_cost='100')]),user)
    db.add(MarketplaceSettings(distributor_tenant_id=tenant_id,is_active=True));db.flush()
    _approve(db,tenant_id,retailer_tenant)
    listing=market.create_listing(db,tenant_id,ListingIn(kind='single',title='کارتن منتخب',item_id=item.id,
        unit_id=carton.id,wholesale_price='2400',consumer_price='3000',is_published=True))
    assert listing.unit=='کارتن' and listing.components[0].qty==24
    order=market.place_order(db,retailer_tenant,OrderPlaceIn(distributor_tenant_id=tenant_id,
        lines=[OrderLineIn(listing_id=listing.id,qty='2')]))
    rule=db.query(ItemUnitConversion).filter_by(item_id=item.id).one()
    rule.factor=100;rule.version+=1;carton.name='کارتن تازه';db.flush()
    response=as_distributor.post(f'/api/marketplace/distributor/orders/{order.id}/confirm')
    assert response.status_code==200,response.text
    db.refresh(order)
    invoice=db.get(SalesInvoice,order.distributor_sales_invoice_id)
    assert invoice.lines[0].qty==2 and invoice.lines[0].base_qty==48
    assert inventory.get_total_stock_qty(db,item.id)==52
    with tenant_scope(db,retailer_tenant):
        purchase=db.get(PurchaseInvoice,order.retailer_purchase_invoice_id)
        assert purchase.lines[0].qty==purchase.lines[0].base_qty==2
        assert purchase.lines[0].unit_conversion_snapshot['market_suggested_price']['amount']=='3000'
    ret=market.request_return(db,retailer_tenant,ReturnRequestIn(order_id=order.id,
        lines=[ReturnRequestLineIn(order_line_id=order.lines[0].id,qty='1')]))
    market.approve_return(db,tenant_id,user,ret.id)
    assert inventory.get_total_stock_qty(db,item.id)==76


def test_same_item_two_contract_versions_return_only_selected_order_line(db,user,tenant_id,as_distributor,retailer_tenant):
    item,base,carton=configured(db)
    warehouse=db.query(Warehouse).filter_by(code='MAIN').one()
    inventory.post_purchase_invoice(db,PurchaseInvoiceIn(invoice_date=date.today(),warehouse_id=warehouse.id,
        lines=[PurchaseInvoiceLineIn(item_id=item.id,qty='1000',unit_cost='100')]),user)
    db.add(MarketplaceSettings(distributor_tenant_id=tenant_id,is_active=True));db.flush()
    _approve(db,tenant_id,retailer_tenant)
    first=market.create_listing(db,tenant_id,ListingIn(title='نسخه یک',item_id=item.id,unit_id=carton.id,
        wholesale_price='2400',consumer_price='2700',is_published=True))
    rule=db.query(ItemUnitConversion).filter_by(item_id=item.id).one()
    rule.factor=30;rule.version+=1;db.flush()
    second=market.create_listing(db,tenant_id,ListingIn(title='نسخه دو',item_id=item.id,unit_id=carton.id,
        wholesale_price='3000',consumer_price='3400',is_published=True))
    order=market.place_order(db,retailer_tenant,OrderPlaceIn(distributor_tenant_id=tenant_id,
        lines=[OrderLineIn(listing_id=first.id,qty='1'),OrderLineIn(listing_id=second.id,qty='1')]))
    response=as_distributor.post(f'/api/marketplace/distributor/orders/{order.id}/confirm')
    assert response.status_code==200,response.text
    assert inventory.get_total_stock_qty(db,item.id)==946
    db.refresh(order)
    with tenant_scope(db,retailer_tenant):
        purchase=db.get(PurchaseInvoice,order.retailer_purchase_invoice_id)
        quotes={line.unit_conversion_snapshot['market_trade_contract_ref']:
            line.unit_conversion_snapshot['market_suggested_price']['amount'] for line in purchase.lines}
        assert quotes[str(first.components[0].trade_contract_ref)]=='2700'
        assert quotes[str(second.components[0].trade_contract_ref)]=='3400'
    source=next(line for line in order.lines if line.listing_id==first.id)
    ret=market.request_return(db,retailer_tenant,ReturnRequestIn(order_id=order.id,
        lines=[ReturnRequestLineIn(order_line_id=source.id,qty='1')]))
    market.approve_return(db,tenant_id,user,ret.id)
    assert inventory.get_total_stock_qty(db,item.id)==970


def test_contract_scaling_rounds_exact_ratio_only_at_final_boundary():
    from fractions import Fraction
    conversion=units.QuantityConversion(Decimal(1),uuid4(),Decimal('0.33333333'),uuid4(),
        Fraction(1,3),(), 'الف','ب')
    assert market_units.scale_contract(conversion,Decimal(3)).target_qty==1


def test_private_seller_contract_survives_listing_replacement_without_exporting_ratio(db,user,tenant_id):
    item,base,carton=configured(db)
    warehouse=db.query(Warehouse).filter_by(code='MAIN').one()
    inventory.post_purchase_invoice(db,PurchaseInvoiceIn(invoice_date=date.today(),warehouse_id=warehouse.id,
        lines=[PurchaseInvoiceLineIn(item_id=item.id,qty='100',unit_cost='100')]),user)
    listing=market.create_listing(db,tenant_id,ListingIn(title='عرضه',item_id=item.id,unit_id=carton.id,wholesale_price='1200'))
    ref=uuid4()
    db.add(EnterpriseMarketItemMap(tenant_id=tenant_id,market_item_ref=ref,local_item_id=item.id,
        approved_by_id=user.id,approved_at=datetime.now(timezone.utc)))
    db.add(EnterpriseMarketListingMap(tenant_id=tenant_id,market_listing_ref=uuid4(),local_listing_id=listing.id,
        approved_by_id=user.id,approved_at=datetime.now(timezone.utc)));db.flush()
    public=catalog.selected_snapshots(db,tenant_id)[0].components[0]
    payload=public.model_dump(mode='json')
    assert payload['qty']=='1' and payload['unit']=='کارتن'
    assert set(payload)=={'market_item_ref','name','unit','qty','trade_contract'}
    assert str(carton.id) not in str(payload) and str(base.id) not in str(payload)
    rule=db.query(ItemUnitConversion).filter_by(item_id=item.id).one()
    rule.factor=100;rule.version+=1;db.flush()
    market.update_listing(db,tenant_id,listing.id,ListingIn(title='نسخه تازه',item_id=item.id,unit_id=carton.id,wholesale_price='1200'))
    catalog.selected_snapshots(db,tenant_id)
    event=MarketFinancialEvent(event_id=uuid4(),operation_ref=uuid4(),order_id=uuid4(),kind='order',side='seller',
        counterparty_ref=uuid4(),counterparty_name='خریدار',order_date=date.today(),order_number=1,cash_amount='0',
        lines=[MarketFinancialLine(market_item_ref=ref,name=item.name,unit='کارتن',qty='2',unit_price='1200',
            discount='0',consumer_price='0',trade_contract=public.trade_contract)])
    receipt=posting.consume(db,tenant_id,event)
    inbox=db.query(EnterpriseMarketLocalPosting).filter_by(event_id=event.event_id).one()
    assert receipt.outcome=='posted',inbox.error_detail
    assert inventory.get_total_stock_qty(db,item.id)==52
    returned=event.model_copy(update={'event_id':uuid4(),'operation_ref':uuid4(),'kind':'return',
        'return_id':uuid4(),'return_number':1,'return_total':Decimal(1200),
        'lines':[event.lines[0].model_copy(update={'qty':Decimal(1),'unit_price':Decimal(0)})]})
    result=posting.consume(db,tenant_id,returned)
    inbox=db.query(EnterpriseMarketLocalPosting).filter_by(event_id=returned.event_id).one()
    assert result.outcome=='posted',inbox.error_detail
    assert inventory.get_total_stock_qty(db,item.id)==76


def test_variable_offer_reserves_and_posts_final_ratio_without_per_offer_rounding(db,user,tenant_id,as_distributor,retailer_tenant):
    item,base,kg=configured(db,variable=True)
    warehouse=db.query(Warehouse).filter_by(code='MAIN').one()
    inventory.post_purchase_invoice(db,PurchaseInvoiceIn(invoice_date=date.today(),warehouse_id=warehouse.id,
        lines=[PurchaseInvoiceLineIn(item_id=item.id,qty='150',unit_cost='100')]),user)
    db.add(MarketplaceSettings(distributor_tenant_id=tenant_id,is_active=True));db.flush()
    _approve(db,tenant_id,retailer_tenant)
    rule=db.query(ItemUnitConversion).filter_by(item_id=item.id).one()
    listing=market.create_listing(db,tenant_id,ListingIn(title='پارچه وزنی',item_id=item.id,unit_id=kg.id,
        observations=[{'rule_id':rule.id,'from_qty':'36','to_qty':'150'}],wholesale_price='500',is_published=True))
    assert market._orderable_by_listing(db,[listing],{tenant_id})[listing.id]==36
    order=market.place_order(db,retailer_tenant,OrderPlaceIn(distributor_tenant_id=tenant_id,
        lines=[OrderLineIn(listing_id=listing.id,qty='36')]))
    rule.is_active=False;db.flush()
    response=as_distributor.post(f'/api/marketplace/distributor/orders/{order.id}/confirm')
    assert response.status_code==200,response.text
    assert inventory.get_total_stock_qty(db,item.id)==0
