"""منطقِ تولید و بهای تمام‌شده.

`post_production_order` هسته‌ی این ماژول است:
  ۱) اجزا با «میانگینِ موزون»ِ خودشان از انبار خارج می‌شوند (مثلِ مصرف در فروش).
  ۲) بهای هر واحدِ محصول = (جمعِ بهای اجزا + سربار) ÷ تعدادِ تولید.
  ۳) محصول با همین بها وارد انبار می‌شود و میانگینِ موزونِ محصول به‌روز می‌شود.
  ۴) چون اجزا و محصول در همان حسابِ «موجودی کالا»اند، فقط اگر سرباری اضافه شده باشد
     سند می‌خورد: بدهکار موجودی، بستانکار صندوق (سربار سرمایه‌ای می‌شود در بهای کالا).
"""
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.accounting import JournalEntry, JournalLine
from app.models.counters import DOC_JOURNAL_ENTRY, DOC_PRODUCTION_ORDER
from app.models.inventory import Item, StockLedger
from app.models.manufacturing import Bom, ProductionOrder, ProductionOrderLine
from app.models.user import User
from app.schemas.manufacturing import ProductionOrderIn
from app.services import chart_codes as cc
from app.services.common import get_account
from app.services.inventory import get_stock_qty, get_total_stock_qty, lock_items
from app.services.numbering import next_document_number
from app.services.period_close import assert_period_open


def _whole(v: Decimal) -> Decimal:
    return Decimal(v).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def post_production_order(db: Session, data: ProductionOrderIn, user: User) -> ProductionOrder:
    assert_period_open(db, data.production_date)

    bom = db.get(Bom, data.bom_id)
    if bom is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "فرمولِ ساخت یافت نشد")
    if not bom.lines:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "این فرمول هیچ جزئی ندارد")

    finished = db.get(Item, bom.finished_item_id)
    if finished is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "محصولِ نهایی یافت نشد")
    if finished.is_service:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "محصولِ خدماتی تولید نمی‌شود")

    qty_produced = Decimal(data.qty_produced)
    batches = qty_produced / Decimal(bom.yield_qty)

    # مقدارِ لازم از هر جزء (چند ردیفِ یک جزء با هم جمع می‌شوند)
    needs: dict[UUID, Decimal] = {}
    for line in bom.lines:
        needs[line.component_item_id] = needs.get(line.component_item_id, Decimal(0)) + Decimal(line.qty) * batches

    if finished.id in needs:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "محصولِ نهایی نمی‌تواند جزءِ خودش باشد")

    # قفلِ همه‌ی کالاهای درگیر (اجزا + محصول) پیش از خواندنِ موجودی و بها — جلوی مسابقه‌ی
    # هم‌زمانیِ موجودی و read-modify-writeِ average_cost را می‌گیرد.
    lock_items(db, set(needs.keys()) | {finished.id})

    components = {i.id: i for i in db.query(Item).filter(Item.id.in_(needs.keys())).all()}
    for cid, need in needs.items():
        comp = components.get(cid)
        if comp is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "کالای جزء یافت نشد")
        if comp.is_service:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"«{comp.name}» خدمات است و نمی‌تواند جزءِ تولید باشد")
        available = get_stock_qty(db, cid, data.warehouse_id)
        if available < need:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"موجودیِ «{comp.name}» برای تولید کافی نیست (موجود: {available}, لازم: {need})",
            )

    # مصرفِ اجزا + جمعِ بها
    component_cost = Decimal(0)
    order_lines: list[ProductionOrderLine] = []
    stock_moves: list[StockLedger] = []
    for cid, need in needs.items():
        comp = components[cid]
        unit = Decimal(comp.average_cost)
        component_cost += need * unit
        order_lines.append(ProductionOrderLine(component_item_id=cid, qty=need, unit_cost=_whole(unit)))
        stock_moves.append(
            StockLedger(
                item_id=cid,
                warehouse_id=data.warehouse_id,
                qty=-need,
                unit_cost=_whole(unit),
                entry_date=data.production_date,
                source_type="production",
            )
        )

    overhead = Decimal(data.overhead_cost or 0)
    total_value = component_cost + overhead
    finished_unit_cost = _whole(total_value / qty_produced) if qty_produced else Decimal(0)

    # تولیدِ محصول: میانگینِ موزون با موجودیِ فعلیِ محصول
    existing_qty = get_total_stock_qty(db, finished.id)
    new_qty = existing_qty + qty_produced
    if new_qty > 0:
        finished.average_cost = ((existing_qty * Decimal(finished.average_cost)) + total_value) / new_qty
    stock_moves.append(
        StockLedger(
            item_id=finished.id,
            warehouse_id=data.warehouse_id,
            qty=qty_produced,
            unit_cost=finished_unit_cost,
            entry_date=data.production_date,
            source_type="production",
        )
    )

    # سند فقط برای سربار (اجزا و محصول در همان حسابِ موجودی، پس بخشِ تبدیل خنثی است)
    journal_entry = None
    if overhead > 0:
        entry_number = next_document_number(db, DOC_JOURNAL_ENTRY)
        journal_entry = JournalEntry(
            number=entry_number,
            entry_date=data.production_date,
            description=f"سربارِ تولیدِ «{finished.name}»",
            source_type="production_order",
            created_by_id=user.id,
            lines=[
                JournalLine(account_id=get_account(db, cc.INVENTORY).id, debit=overhead, credit=0, description="سربارِ تولید (سرمایه‌ای در بهای کالا)"),
                JournalLine(account_id=get_account(db, cc.CASH).id, debit=0, credit=overhead, description="پرداختِ سربارِ تولید"),
            ],
        )
        db.add(journal_entry)
        db.flush()

    number = next_document_number(db, DOC_PRODUCTION_ORDER)
    order = ProductionOrder(
        number=number,
        bom_id=bom.id,
        finished_item_id=finished.id,
        warehouse_id=data.warehouse_id,
        production_date=data.production_date,
        qty_produced=qty_produced,
        component_cost=_whole(component_cost),
        overhead_cost=_whole(overhead),
        unit_cost=finished_unit_cost,
        journal_entry_id=journal_entry.id if journal_entry else None,
        created_by_id=user.id,
        lines=order_lines,
    )
    db.add(order)
    for move in stock_moves:
        db.add(move)
    db.flush()
    db.refresh(order)
    return order
