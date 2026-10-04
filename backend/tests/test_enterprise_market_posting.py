"""A lost acknowledgement or duplicate event must not create a second invoice."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.models.enterprise_market_bridge import EnterpriseMarketLocalPosting
from app.schemas.enterprise_market_bridge import MarketFinancialEvent, MarketFinancialLine
from app.services import enterprise_market_posting as posting


def _event(*, event_id=None, item_ref=None):
    return MarketFinancialEvent(
        event_id=event_id or uuid4(), operation_ref=uuid4(), order_id=uuid4(),
        kind="order", side="seller", counterparty_ref=uuid4(),
        counterparty_name="خریدار عمومی", order_date=date(2026, 9, 30),
        order_number=17, cash_amount=Decimal(0),
        lines=[MarketFinancialLine(
            market_item_ref=item_ref or uuid4(), qty=Decimal(2),
            unit_price=Decimal(1000), discount=Decimal(0), consumer_price=Decimal(0),
        )],
    )


def test_duplicate_delivery_returns_same_receipt_without_second_document(db, tenant_id, monkeypatch):
    event = _event()
    made = []

    def fake_post(_db, _tenant_id, _event):
        made.append(uuid4())
        return made[-1]

    monkeypatch.setattr(posting, "_post_document", fake_post)
    first = posting.consume(db, tenant_id, event)
    second = posting.consume(db, tenant_id, event)
    assert first.outcome == second.outcome == "posted"
    assert len(made) == 1
    row = db.query(EnterpriseMarketLocalPosting).filter_by(event_id=event.event_id).one()
    assert row.local_document_id == made[0]
    assert "local_document_id" not in first.model_dump()


def test_same_event_id_with_changed_trade_is_blocked(db, tenant_id, monkeypatch):
    event = _event()
    made = []
    monkeypatch.setattr(posting, "_post_document", lambda *_: made.append(uuid4()) or made[-1])
    assert posting.consume(db, tenant_id, event).outcome == "posted"
    changed = event.model_copy(update={"cash_amount": Decimal(100)})
    receipt = posting.consume(db, tenant_id, changed)
    assert receipt.outcome == "blocked"
    assert receipt.error_code == "event_payload_mismatch"
    assert len(made) == 1


def test_unmapped_item_is_recorded_without_financial_document(db, tenant_id):
    event = _event()
    receipt = posting.consume(db, tenant_id, event)
    assert receipt.outcome == "blocked"
    assert receipt.error_code == "item_mapping_missing"
    row = db.query(EnterpriseMarketLocalPosting).filter_by(event_id=event.event_id).one()
    assert row.local_document_id is None
    assert row.attempts == 1
    assert row.error_detail
    assert "error_detail" not in receipt.model_dump()


def test_internal_invoice_or_warehouse_fields_cannot_cross_event_contract():
    payload = _event().model_dump(mode="json")
    payload["local_invoice_id"] = str(uuid4())
    from pytest import raises

    with raises(ValueError):
        MarketFinancialEvent.model_validate(payload)


def test_private_variable_measurement_freezes_purchase_and_replay(db,tenant_id,user):
    from types import SimpleNamespace
    from datetime import datetime, timezone
    from app.models.enterprise_market_bridge import EnterpriseMarketItemMap
    from app.models.item_units import ItemUnitConversion
    from app.models.invoices import PurchaseInvoice
    from app.routers import enterprise_market_local as local
    from app.services.inventory import get_total_stock_qty
    from tests.test_item_unit_registry import configured
    item,meter,kg=configured(db,variable=True)
    rule=db.query(ItemUnitConversion).filter_by(item_id=item.id).one()
    event=_event().model_copy(update={'side':'buyer','order_date':date.today(),'lines':[
        MarketFinancialLine(market_item_ref=uuid4(),name='پارچه',unit='واحد وزنی توافق‌شده',qty='36',
            unit_price='500',discount='0',consumer_price='0')]})
    db.add(EnterpriseMarketItemMap(tenant_id=tenant_id,market_item_ref=event.lines[0].market_item_ref,
        local_item_id=item.id,approved_by_id=user.id,approved_at=datetime.now(timezone.utc)));db.flush()
    assert posting.consume(db,tenant_id,event).outcome=='blocked'
    assert get_total_stock_qty(db,item.id)==0
    owner=SimpleNamespace(tenant_id=tenant_id,user=user,has_permission=lambda module,action:True)
    import pytest
    from fastapi import HTTPException
    readonly=SimpleNamespace(tenant_id=tenant_id,user=user,has_permission=lambda module,action:action=='view')
    with pytest.raises(HTTPException) as denied:
        local.approve_posting_quantity(event.event_id,local.LocalQuantityInputIn(line_index=0,unit_id=kg.id),readonly,db)
    assert denied.value.status_code==403
    other=SimpleNamespace(tenant_id=uuid4(),user=user,has_permission=lambda module,action:True)
    with pytest.raises(HTTPException) as hidden:
        local.approve_posting_quantity(event.event_id,local.LocalQuantityInputIn(line_index=0,unit_id=kg.id),other,db)
    assert hidden.value.status_code==404
    with pytest.raises(HTTPException) as invalid:
        local.approve_posting_quantity(event.event_id,local.LocalQuantityInputIn(line_index=1,unit_id=kg.id),owner,db)
    assert invalid.value.status_code==422
    inbox=db.query(EnterpriseMarketLocalPosting).filter_by(event_id=event.event_id).one()
    assert inbox.quantity_inputs=={}
    public_payload=dict(inbox.payload)
    local.approve_posting_quantity(event.event_id,local.LocalQuantityInputIn(line_index=0,unit_id=kg.id,
        observations=[{'rule_id':rule.id,'from_qty':'36','to_qty':'150'}]),owner,db)
    rule.is_active=False;kg.name='عنوان تازه';db.flush()
    result=posting.consume(db,tenant_id,event)
    inbox=db.query(EnterpriseMarketLocalPosting).filter_by(event_id=event.event_id).one()
    assert result.outcome=='posted',inbox.error_detail
    assert inbox.payload==public_payload
    assert posting.consume(db,tenant_id,event)==result
    assert get_total_stock_qty(db,item.id)==150
    invoice=db.query(PurchaseInvoice).one()
    assert invoice.lines[0].qty==36 and invoice.lines[0].base_qty==150
    assert invoice.lines[0].unit_conversion_snapshot['source_unit_name']=='کیلوگرم'
    assert db.query(PurchaseInvoice).count()==1
    assert 'quantity_inputs' not in result.model_dump()
    returned=event.model_copy(update={'event_id':uuid4(),'operation_ref':uuid4(),'kind':'return',
        'return_id':uuid4(),'return_number':1,'return_total':Decimal(6000),
        'lines':[event.lines[0].model_copy(update={'qty':Decimal(12),'unit_price':Decimal(0)})]})
    receipt=posting.consume(db,tenant_id,returned)
    inbox=db.query(EnterpriseMarketLocalPosting).filter_by(event_id=returned.event_id).one()
    assert receipt.outcome=='posted',inbox.error_detail
    assert get_total_stock_qty(db,item.id)==100
    with pytest.raises(HTTPException):
        local.approve_posting_quantity(event.event_id,local.LocalQuantityInputIn(line_index=0,unit_id=meter.id),owner,db)


def test_owner_repairs_mapping_and_retries_real_posting_without_changing_history(db, tenant_id, user):
    from types import SimpleNamespace
    import pytest
    from fastapi import HTTPException
    from app.models.inventory import Item, Warehouse
    from app.models.invoices import SalesInvoice
    from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn
    from app.services.inventory import post_purchase_invoice
    from app.routers import enterprise_market_local as local

    item = Item(tenant_id=tenant_id, sku="RECOVERY", name="کالای اصلاحی", unit="عدد", sales_price=1000)
    db.add(item); db.flush()
    warehouse = db.query(Warehouse).filter_by(code="MAIN").one()
    post_purchase_invoice(db, PurchaseInvoiceIn(invoice_date=date.today(), warehouse_id=warehouse.id,
        lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=10, unit_cost=500)]), user)
    event = _event().model_copy(update={"order_date": date.today()})
    assert posting.consume(db, tenant_id, event).outcome == "blocked"
    readonly = SimpleNamespace(tenant_id=tenant_id, user=user, has_permission=lambda module, action: action == "view")
    with pytest.raises(HTTPException) as exc:
        local.retry_posting(event.event_id, readonly, db)
    assert exc.value.status_code == 403
    owner = SimpleNamespace(tenant_id=tenant_id, user=user, has_permission=lambda module, action: True)
    local.repair_posting_mapping(event.event_id,
        local.LocalItemMapIn(market_item_ref=event.lines[0].market_item_ref, local_item_id=item.id), owner, db)
    receipt = local.retry_posting(event.event_id, owner, db)
    row = db.query(EnterpriseMarketLocalPosting).filter_by(event_id=event.event_id).one()
    assert receipt.outcome == "posted", row.error_detail
    assert local.retry_posting(event.event_id, owner, db).outcome == "posted"
    assert db.query(SalesInvoice).count() == 1
    another = _event(item_ref=event.lines[0].market_item_ref)
    # Keep a second failed event for the same reference: repairing it must not
    # rewrite the identity used by the first invoice and its future returns.
    db.add(EnterpriseMarketLocalPosting(tenant_id=tenant_id, event_id=another.event_id, order_id=another.order_id,
        side="seller", kind="order", payload=another.model_dump(mode="json"), status="blocked"))
    db.flush()
    with pytest.raises(HTTPException) as exc:
        local.repair_posting_mapping(another.event_id,
            local.LocalItemMapIn(market_item_ref=another.lines[0].market_item_ref, local_item_id=item.id), owner, db)
    assert exc.value.status_code == 409
