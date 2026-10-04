"""Public trade quantities resolve against each party's private unit registry."""
from decimal import Decimal
from fastapi import HTTPException
from app.models.inventory import UnitOfMeasure
from app.models.item_units import ItemUnit
from app.services.returns import get_returnable_summary, get_purchase_returnable_summary


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
    for item_id, qty, unit_name in requests:
        left = Decimal(qty)
        for source in summary:
            if source['item_id'] != item_id:
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
