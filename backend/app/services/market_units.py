"""Public trade quantities resolve against each party's private unit registry."""
from decimal import Decimal
from fastapi import HTTPException
from app.models.inventory import UnitOfMeasure
from app.models.item_units import ItemUnit
from app.services.returns import get_returnable_summary, get_purchase_returnable_summary
from app.models.advanced_inventory import StockBatch
from app.models.invoices import SalesInvoiceLine, PurchaseInvoiceLine
from app.services import units


def scale_contract(original, quantity):
    """Round the exact frozen ratio once at the final inventory boundary."""
    return units.convert_frozen_quantity(original,quantity)


def freeze_trade_refs(db, invoice, contracts):
    for line, contract in zip(getattr(invoice,"_inv02_input_lines",invoice.lines), contracts, strict=True):
        if contract:
            snapshot = dict(line.unit_conversion_snapshot or {})
            snapshot["market_trade_contract_ref"] = str(contract.ref if hasattr(contract,"ref") else contract["ref"])
            line.unit_conversion_snapshot = snapshot
    db.flush()


def apply_purchase_suggestions(db, invoice, prices):
    """Keep the agreed price in its commercial unit; never scale it into base price."""
    base_prices = {}
    ambiguous_items = set()
    for line, price in zip(getattr(invoice,"_inv02_input_lines",invoice.lines), prices, strict=True):
        price = Decimal(price)
        if price <= 0:
            continue
        snapshot = dict(line.unit_conversion_snapshot or {})
        snapshot["market_suggested_price"] = {"amount":str(price),
            "unit_id":str(line.entered_unit_id), "unit_name":snapshot.get("source_unit_name", "")}
        line.unit_conversion_snapshot = snapshot
        if line.entered_unit_id != line.base_unit_id or (line.item_id in base_prices and base_prices[line.item_id] != price):
            ambiguous_items.add(line.item_id)
        elif line.item_id not in ambiguous_items:
            base_prices[line.item_id] = price
    if base_prices:
        for batch in db.query(StockBatch).filter_by(source_id=invoice.id).all():
            if batch.item_id in base_prices and batch.item_id not in ambiguous_items:
                batch.consumer_price = base_prices[batch.item_id]
    db.flush()


def commercial_unit(db, item, name, *, context):
    member = db.query(ItemUnit).join(UnitOfMeasure,
        (UnitOfMeasure.id == ItemUnit.unit_id) & (UnitOfMeasure.tenant_id == ItemUnit.tenant_id)).filter(
        ItemUnit.item_id == item.id, ItemUnit.tenant_id == item.tenant_id,
        ItemUnit.is_active.is_(True), UnitOfMeasure.is_active.is_(True),
        UnitOfMeasure.name == name, getattr(ItemUnit, f"{context}_allowed").is_(True)).one_or_none()
    if member is None:
        raise HTTPException(409, f"واحد معاملهٔ «{name}» برای «{item.name}» مجاز نیست؛ واحد و تبدیل همین کالا را تعریف کنید")
    return member.unit_id


def historical_return_lines(db, invoice_id, side, requests):
    """Split in the frozen commercial unit, anchored to original invoice rows."""
    summary = (get_returnable_summary if side == 'seller' else get_purchase_returnable_summary)(db, invoice_id)
    anchor = 'sales_invoice_line_id' if side == 'seller' else 'purchase_invoice_line_id'
    result = []
    line_model = SalesInvoiceLine if side == "seller" else PurchaseInvoiceLine
    contracts = {row.id:(row.unit_conversion_snapshot or {}).get("market_trade_contract_ref")
        for row in db.query(line_model).filter(line_model.invoice_id == invoice_id).all()}
    for request in requests:
        item_id, qty, unit_name = request[:3]
        contract_ref = request[3] if len(request) > 3 else None
        left = Decimal(qty)
        for source in summary:
            if source['item_id'] != item_id:
                continue
            if contract_ref and contracts.get(source[anchor]) != str(contract_ref):
                continue
            option = next((row for row in source['return_unit_options']
                if not unit_name or row['unit_name'] == unit_name), None)
            if option is None:
                continue
            take = min(left, option['remaining'])
            if take <= 0:
                continue
            result.append({anchor:source[anchor], 'qty':take, 'unit_id':option['unit_id']})
            option['remaining'] -= take
            left -= take
            if not left:
                break
        if left:
            raise HTTPException(409, 'واحد یا مقدار باقی‌ماندهٔ تاریخی معامله پیدا نشد؛ فاکتور اصلی را بررسی کنید')
    return result
