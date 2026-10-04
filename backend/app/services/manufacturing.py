"""منطقِ تولید و بهای تمام‌شده.

`post_production_order` هسته‌ی این ماژول است:
  ۱) اجزا با «میانگینِ موزون»ِ خودشان از انبار خارج می‌شوند (مثلِ مصرف در فروش).
  ۲) بهای هر واحدِ محصول = (جمعِ بهای اجزا + سربار) ÷ تعدادِ تولید.
  ۳) محصول با همین بها وارد انبار می‌شود و میانگینِ موزونِ محصول به‌روز می‌شود.
  ۴) چون اجزا و محصول در همان حسابِ «موجودی کالا»اند، فقط اگر سرباری اضافه شده باشد
     سند می‌خورد: بدهکار موجودی، بستانکار صندوق (سربار سرمایه‌ای می‌شود در بهای کالا).
"""
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from dataclasses import replace
from collections import deque
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.models.accounting import JournalEntry, JournalLine
from app.services import tafsili
from app.models.counters import DOC_JOURNAL_ENTRY, DOC_PRODUCTION_ORDER, DOC_PRODUCTION_PLAN
from app.models.inventory import Item, StockLedger
from app.models.advanced_inventory import StockBatch
from app.models.invoices import WarehouseIssue, WarehouseReceipt
from app.models.manufacturing import Bom, BomLine, ProductionOrder, ProductionOrderLine, ProductionPlan
from app.services import units
from app.models.user import User
from app.schemas.invoices import (
    DirectWarehouseIssueIn,
    WarehouseIssueLineIn,
    WarehouseReceiptIn,
    WarehouseReceiptLineIn,
)
from app.schemas.manufacturing import (
    ProductionCostCalcIn,
    ProductionMaterialIssueIn,
    ProductionOrderIn,
    ProductionPlanIn,
    ProductionReceiptIn,
)
from app.services import chart_codes as cc
from app.services import warehouse_issues as warehouse_issues_svc
from app.services import warehouse_receipts as warehouse_receipts_svc
from app.services.common import get_account, number_lines
from app.services.inventory import get_stock_qty, get_total_stock_qty, lock_items
from app.services import valuation
from app.services import batches as batches_svc
from app.services.numbering import next_document_number
from app.services.period_close import assert_period_open

#: وضعیت‌هایی که سفارش هنوز روی آن‌ها «باز» است — تحویلِ مواد/دریافتِ محصول
#: فقط رویشان مجاز است. پیش‌نویس هنوز قطعی نشده، تمام/لغوشده دیگر چیزی نمی‌خواهد.
_OPEN_PLAN_STATUSES = ("started", "in_progress", "stopped")

#: گذارِ مجازِ وضعیتِ سفارش (برنامه). همان الگوی پیمانکاری.
_PLAN_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "draft": ("started", "cancelled"),
    "started": ("in_progress", "stopped"),
    "in_progress": ("stopped", "finished"),
    "stopped": ("in_progress", "finished"),
    "finished": (),
    "cancelled": (),
}


def _whole(v: Decimal) -> Decimal:
    return Decimal(v).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def build_bom_lines(db: Session, lines) -> list[BomLine]:
    ids = {line.component_item_id for line in lines}
    items = {item.id: item for item in db.query(Item).filter(Item.id.in_(ids)).all()}
    if set(items) != ids:
        raise HTTPException(400, "کالای جزء یافت نشد")
    registry = units.OperationUnitRegistry(db, items.values())
    result = []
    for line in lines:
        item = items[line.component_item_id]
        if item.is_service:
            raise HTTPException(400, "کالای جزء معتبر و انباری نیست")
        conversion = units.convert_transaction(db, item, line.qty, line.unit_id,
            context="production", observations=line.observations, registry=registry)
        result.append(BomLine(component_item_id=item.id, qty=conversion.target_qty,
            **units.snapshot_fields(conversion)))
    return result


def frozen_recipe(db: Session, bom: Bom) -> dict:
    items = {item.id: item for item in db.query(Item).filter(
        Item.id.in_({line.component_item_id for line in bom.lines})).all()}
    return {"schema_version": 1, "yield_qty": str(bom.yield_qty), "lines": [
        {"component_item_id": str(line.component_item_id), "component_ref": str(line.id),
         "conversion": units.document_conversion(db, line, items[line.component_item_id]).snapshot()}
        for line in bom.lines]}


def scaled_bom_components(db: Session, bom: Bom, produced: Decimal,
                          *, recipe: dict | None = None, previous: Decimal = Decimal(0)):
    """Take the difference of cumulative rounded quantities; final partial closes residuals."""
    recipe = recipe or frozen_recipe(db, bom)
    yield_qty = Fraction(units.exact_quantity(recipe["yield_qty"]))
    before = Fraction(units.exact_quantity(previous)) / yield_qty
    after = (Fraction(units.exact_quantity(previous)) + Fraction(units.exact_quantity(produced))) / yield_qty
    result = []
    for entry in recipe["lines"]:
        original = units.conversion_from_snapshot(entry["conversion"])
        conversion = units.scale_document_conversion(original, after - before)
        target = units.rounded_quantity(Fraction(original.target_qty) * after) - units.rounded_quantity(Fraction(original.target_qty) * before)
        source = units.rounded_quantity(Fraction(original.source_qty) * after) - units.rounded_quantity(Fraction(original.source_qty) * before)
        if target <= 0 or source <= 0:
            raise HTTPException(400, "مقدار جزئی تولید برای دقت واحد جزء بسیار کوچک است")
        conversion = replace(conversion, source_qty=source, target_qty=target,
            rounding_adjustment=target - units.rounded_quantity(Fraction(source) * original.ratio))
        result.append((UUID(entry["component_item_id"]), conversion))
    return result


def create_production_plan(db: Session, data: ProductionPlanIn, user: User) -> ProductionPlan:
    bom = db.query(Bom).filter(Bom.id == data.bom_id).with_for_update().one_or_none()
    if bom is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "فرمولِ ساخت یافت نشد")

    finished = db.get(Item, bom.finished_item_id)
    if finished is None:
        raise HTTPException(400, "محصول نهایی یافت نشد")
    lock_items(db, {bom.finished_item_id, *(line.component_item_id for line in bom.lines)})
    conversion = units.convert_transaction(db, finished, data.qty_planned, data.unit_id,
        context="production", observations=data.observations)
    plan = ProductionPlan(
        number=next_document_number(db, DOC_PRODUCTION_PLAN),
        bom_id=bom.id,
        finished_item_id=bom.finished_item_id,
        warehouse_id=data.warehouse_id,
        planned_date=data.planned_date,
        qty_planned=conversion.target_qty,
        **units.snapshot_fields(conversion),
        recipe_snapshot=frozen_recipe(db, bom),
        notes=data.notes,
        status="draft",
        created_by_id=user.id,
    )
    db.add(plan)
    db.flush()
    db.refresh(plan)
    return plan


def change_production_plan_status(db: Session, plan_id: UUID, new_status: str, user: User) -> ProductionPlan:
    plan = db.query(ProductionPlan).filter(ProductionPlan.id == plan_id).with_for_update().one_or_none()
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سفارشِ تولید یافت نشد")

    allowed = _PLAN_TRANSITIONS.get(plan.status, ())
    if new_status not in allowed:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"گذار از «{plan.status}» به «{new_status}» مجاز نیست",
        )

    plan.status = new_status
    db.flush()
    db.refresh(plan)
    return plan


def post_production_order(db: Session, data: ProductionOrderIn, user: User) -> ProductionOrder:
    assert_period_open(db, data.production_date)

    bom = db.get(Bom, data.bom_id)
    if bom is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "فرمولِ ساخت یافت نشد")
    if not bom.lines:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "این فرمول هیچ جزئی ندارد")

    plan = None
    if data.production_plan_id is not None:
        plan = db.query(ProductionPlan).filter(ProductionPlan.id == data.production_plan_id).with_for_update().one_or_none()
        if plan is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "سفارشِ تولید یافت نشد")

    finished = db.get(Item, bom.finished_item_id)
    if finished is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "محصولِ نهایی یافت نشد")
    if finished.is_service:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "محصولِ خدماتی تولید نمی‌شود")

    recipe = plan.recipe_snapshot if plan else None
    component_ids = {UUID(entry["component_item_id"]) for entry in recipe["lines"]} if recipe else {line.component_item_id for line in bom.lines}
    lock_items(db, component_ids | {finished.id})
    output_conversion = units.convert_transaction(db, finished, data.qty_produced, data.unit_id,
        context="production", observations=data.observations)
    qty_produced = output_conversion.target_qty
    if plan and qty_produced > Decimal(plan.qty_planned) - Decimal(plan.qty_produced):
        raise HTTPException(400, "مقدار تولید بیش از باقی‌ماندهٔ سفارش است")
    scaled = scaled_bom_components(db, bom, qty_produced, recipe=recipe,
        previous=Decimal(plan.qty_produced) if plan else Decimal(0))

    # مقدارِ لازم از هر جزء (چند ردیفِ یک جزء با هم جمع می‌شوند)
    needs: dict[UUID, Decimal] = {}
    for cid, conversion in scaled:
        needs[cid] = needs.get(cid, Decimal(0)) + conversion.target_qty

    if finished.id in needs:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "محصولِ نهایی نمی‌تواند جزءِ خودش باشد")

    # قفلِ همه‌ی کالاهای درگیر (اجزا + محصول) پیش از خواندنِ موجودی و بها — جلوی مسابقه‌ی
    # هم‌زمانیِ موجودی و read-modify-writeِ average_cost را می‌گیرد.

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

    allocations = {cid: deque(batches_svc.plan_outflow(db, components[cid], data.warehouse_id,
        need, data.production_date) or [(None, need)]) for cid, need in needs.items()}

    # مصرفِ اجزا + جمعِ بها
    component_cost = Decimal(0)
    order_lines: list[ProductionOrderLine] = []
    stock_moves: list[StockLedger] = []
    material_links = []
    for cid, conversion in scaled:
        need = conversion.target_qty
        comp = components[cid]
        #: تولیدِ پیش‌تاریخ اجزا را با میانگینِ همان روز مصرف می‌کند.
        unit = valuation.cost_for_posting(db, comp, data.production_date)
        component_cost += need * unit
        order_lines.append(ProductionOrderLine(component_item_id=cid, qty=need, unit_cost=_whole(unit), **units.snapshot_fields(conversion)))
        remaining = need
        while remaining > 0:
            batch_id, available = allocations[cid].popleft()
            take = min(remaining, available)
            move = StockLedger(item_id=cid, warehouse_id=data.warehouse_id, qty=-take,
                **units.movement_snapshot_fields(conversion, -take), unit_cost=_whole(unit),
                entry_date=data.production_date, source_type="production", batch_id=batch_id)
            stock_moves.append(move)
            material_links.append((move, order_lines[-1]))
            remaining -= take
            if available > take:
                allocations[cid].appendleft((batch_id, available - take))

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
            **units.snapshot_fields(output_conversion),
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
            lines=number_lines([
                JournalLine(account_id=get_account(db, cc.INVENTORY).id, debit=overhead, credit=0, description="سربارِ تولید (سرمایه‌ای در بهای کالا)"),
                JournalLine(account_id=get_account(db, cc.CASH).id, debit=0, credit=overhead, description="پرداختِ سربارِ تولید"),
            ]),
        )
        tafsili.assert_entry_has_tafsili(db, journal_entry)
        db.add(journal_entry)
        db.flush()

    number = next_document_number(db, DOC_PRODUCTION_ORDER)
    order = ProductionOrder(
        number=number,
        bom_id=bom.id,
        finished_item_id=finished.id,
        warehouse_id=data.warehouse_id,
        production_plan_id=plan.id if plan else None,
        production_date=data.production_date,
        qty_produced=qty_produced,
        **units.snapshot_fields(output_conversion),
        component_cost=_whole(component_cost),
        overhead_cost=_whole(overhead),
        unit_cost=finished_unit_cost,
        journal_entry_id=journal_entry.id if journal_entry else None,
        created_by_id=user.id,
        lines=order_lines,
    )
    db.add(order)
    db.flush()
    output_batch = StockBatch(item_id=finished.id, warehouse_id=data.warehouse_id,
        batch_number=f"PR{number}", qty=qty_produced, received_qty=qty_produced,
        unit_cost=finished_unit_cost, source_type="production", source_id=order.id,
        received_date=data.production_date, production_date=data.production_date,
        created_by_id=user.id)
    db.add(output_batch); db.flush()
    stock_moves[-1].batch_id = output_batch.id
    units.record_batch_observations(db, output_batch, output_conversion, user)
    for move, line in material_links:
        move.source_line_id = line.id
    for move in stock_moves:
        move.source_id = order.id
        db.add(move)
    valuation.settle_posting(db, stock_moves)
    db.refresh(order)
    if plan is not None:
        plan.qty_produced = Decimal(plan.qty_produced) + qty_produced
        db.flush()
    return order


# ── تحویلِ مواد به تولید / رسیدِ محصول از تولید (سفارش↔سند، جدا) ──────────


def material_plan_quantities(db, plan, bom, data, *, lock=False):
    recipe = plan.recipe_snapshot or frozen_recipe(db, bom)
    issues = db.query(WarehouseIssue).filter(WarehouseIssue.production_plan_id == plan.id,
        WarehouseIssue.voided_at.is_(None)).all()
    covered = Decimal(0)
    for issue in issues:
        if not issue.lines:
            continue
        snapshot = issue.lines[0].unit_conversion_snapshot or {}
        value = snapshot.get("production_output_base_qty")
        if value is None:
            raise HTTPException(409, "تحویل مواد قدیمی سهم تولید ثبت‌شده ندارد؛ پیش از تحویل جزئی آن را بررسی و اصلاح کنید")
        covered += units.exact_quantity(value)
    remaining = Decimal(plan.qty_planned) - covered
    finished = db.get(Item, plan.finished_item_id)
    if lock:
        lock_items(db, {plan.finished_item_id, *(UUID(entry["component_item_id"]) for entry in recipe["lines"])})
    qty = (units.convert_transaction(db, finished, data.qty, data.unit_id, context="production",
        observations=data.observations).target_qty if data.qty is not None else remaining)
    if qty <= 0 or qty > remaining:
        raise HTTPException(400, f"مقدار تحویل مواد بیش از باقی‌ماندهٔ سفارش است ({remaining})")
    scaled = scaled_bom_components(db, bom, qty, recipe=recipe, previous=covered)

    return qty, remaining, scaled


def preview_material_issue(db: Session, plan_id: UUID, data: ProductionMaterialIssueIn) -> dict:
    plan = db.get(ProductionPlan, plan_id)
    if plan is None:
        raise HTTPException(404, "سفارش تولید یافت نشد")
    bom = db.get(Bom, plan.bom_id)
    if bom is None:
        raise HTTPException(400, "فرمول ساخت سفارش یافت نشد؛ سفارش را بررسی کنید")
    qty, remaining, scaled = material_plan_quantities(db, plan, bom, data)
    # Reservations are explanatory: derive them from each frozen recipe, never a live factor.
    reserved = {}
    others = db.query(ProductionPlan).filter(ProductionPlan.id != plan.id,
        ProductionPlan.warehouse_id == plan.warehouse_id,
        ProductionPlan.status.in_(_OPEN_PLAN_STATUSES)).all()
    other_boms = {row.id: row for row in db.query(Bom).options(selectinload(Bom.lines)).filter(
        Bom.id.in_({other.bom_id for other in others})).all()}
    issues_by_plan = {}
    for issue in db.query(WarehouseIssue).options(selectinload(WarehouseIssue.lines)).filter(
        WarehouseIssue.production_plan_id.in_([other.id for other in others]),
        WarehouseIssue.voided_at.is_(None)).all():
        issues_by_plan.setdefault(issue.production_plan_id, []).append(issue)
    for other in others:
        other_bom = other_boms.get(other.bom_id)
        if other_bom is None and not other.recipe_snapshot:
            continue
        covered = Decimal(0)
        for issue in issues_by_plan.get(other.id, []):
            if issue.lines:
                covered += Decimal((issue.lines[0].unit_conversion_snapshot or {}).get("production_output_base_qty", "0"))
        previous = max(covered, Decimal(other.qty_produced))
        left = Decimal(other.qty_planned) - previous
        if left <= 0:
            continue
        for cid, conversion in scaled_bom_components(db, other_bom, left,
            recipe=other.recipe_snapshot, previous=previous):
            reserved[cid] = reserved.get(cid, Decimal(0)) + conversion.target_qty
    return {"qty": str(qty), "remaining": str(remaining), "lines": [
        {"item_id":str(cid), "qty":str(conversion.target_qty),
         "unit":conversion.target_unit_name, "reserved_other":str(reserved.get(cid, Decimal(0)))}
        for cid, conversion in scaled]}


def issue_materials_to_production(
    db: Session, plan_id: UUID, data: ProductionMaterialIssueIn, user: User
) -> WarehouseIssue:
    """حواله‌ی خروجِ واقعیِ موادِ اولیه از انبار به خطِ تولید — طرفِ بدهکارش
    «کالای در جریان ساخت» است، نه یک ارجاعِ نازکِ داخلی."""
    plan = db.query(ProductionPlan).filter(ProductionPlan.id == plan_id).with_for_update().one_or_none()
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سفارشِ تولید یافت نشد")
    if plan.status not in _OPEN_PLAN_STATUSES:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"سفارش در وضعیتِ «{plan.status}» تحویلِ مواد نمی‌پذیرد",
        )
    bom = db.get(Bom, plan.bom_id)
    if bom is None or not bom.lines:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "فرمولِ ساختِ این سفارش یافت نشد")

    qty, remaining, scaled = material_plan_quantities(db, plan, bom, data, lock=True)

    issue_data = DirectWarehouseIssueIn(
        issue_date=data.issue_date,
        issue_type="production",
        warehouse_id=plan.warehouse_id,
        production_plan_id=plan.id,
        lines=[WarehouseIssueLineIn(item_id=cid, qty=conversion.source_qty, unit_id=conversion.source_unit_id)
            for cid, conversion in scaled],
        description=f"تحویلِ مواد برای سفارشِ تولیدِ شماره‌ی {plan.number}",
    )
    issue = warehouse_issues_svc.create_direct_warehouse_issue(db, issue_data, user,
        frozen_conversions={index: conversion for index, (_, conversion) in enumerate(scaled)})
    for line in issue.lines:
        line.unit_conversion_snapshot = {**(line.unit_conversion_snapshot or {}),
            "production_output_base_qty": str(qty)}
    plan.material_cost_issued = Decimal(plan.material_cost_issued) + issue.total_cost
    db.flush()
    return issue


def receive_production_output(
    db: Session, plan_id: UUID, data: ProductionReceiptIn, user: User
) -> WarehouseReceipt:
    """رسیدِ واقعیِ محصولِ ساخته‌شده به انبار. بهای واحد از موادِ تحویل‌شده‌ی
    همین سفارش مشتق می‌شود؛ دستمزد/سربار در «محاسبه قیمت تمام‌شده» اضافه
    می‌شوند، نه این‌جا — درست مثلِ ورودِ یک قطعه‌ی نیم‌ساخته که هزینه‌ی نهایی‌اش
    بعداً معلوم می‌شود."""
    plan = db.query(ProductionPlan).filter(ProductionPlan.id == plan_id).with_for_update().one_or_none()
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سفارشِ تولید یافت نشد")
    if plan.status not in _OPEN_PLAN_STATUSES:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"سفارش در وضعیتِ «{plan.status}» رسیدِ محصول نمی‌پذیرد",
        )
    remaining = Decimal(plan.qty_planned) - Decimal(plan.qty_produced)
    finished = db.get(Item, plan.finished_item_id)
    if finished is None:
        raise HTTPException(400, "محصول نهایی یافت نشد")
    lock_items(db, [finished.id])
    conversion = units.convert_transaction(db, finished, data.qty, data.unit_id,
        context="production", observations=data.observations)
    qty = conversion.target_qty
    if qty <= 0 or qty > remaining:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"مقدار باید بین صفر و باقی‌مانده‌ی سفارش باشد (باقی‌مانده: {remaining})",
        )
    #: نرخِ موادِ هر واحد = کلِ موادِ تحویل‌شده به این سفارش ÷ تعدادِ برنامه —
    #: یکسان روی هر رسیدِ همین سفارش، حتی اگر رسید چندبار جزئی انجام شود.
    unit_cost = (
        (Decimal(plan.material_cost_issued) / Decimal(plan.qty_planned)).quantize(Decimal(1))
        if plan.qty_planned
        else Decimal(0)
    )

    receipt_data = WarehouseReceiptIn(
        receipt_date=data.receipt_date,
        warehouse_id=plan.warehouse_id,
        receipt_type="production",
        production_plan_id=plan.id,
        lines=[WarehouseReceiptLineIn(item_id=finished.id, qty=qty, unit_cost=unit_cost)],
        description=f"رسیدِ محصول از سفارشِ تولیدِ شماره‌ی {plan.number}",
    )
    receipt = warehouse_receipts_svc.create_warehouse_receipt(db, None, receipt_data, user)
    for line in receipt.lines:
        for key, value in units.snapshot_fields(conversion).items():
            setattr(line, key, value)
    for move in db.query(StockLedger).filter_by(source_type="warehouse_receipt", source_id=receipt.id).all():
        for key, value in units.movement_snapshot_fields(conversion, move.qty).items():
            setattr(move, key, value)
    for batch in db.query(StockBatch).filter_by(source_type="warehouse_receipt", source_id=receipt.id).all():
        units.record_batch_observations(db, batch, conversion, user)
    plan.qty_produced = Decimal(plan.qty_produced) + qty
    db.flush()
    return receipt


def calculate_production_cost(
    db: Session, plan_id: UUID, data: ProductionCostCalcIn, user: User
) -> ProductionPlan:
    """توزیعِ دستمزد و سربار روی محصولی که تا امروز از این سفارش دریافت شده —
    همان الگوی «سربار» در سندِ تولیدِ پیشین، حالا یک گامِ مستقل و قابلِ‌تکرار.

    بهای واحدِ محصول را در **میانگینِ موزونِ فعلی**اش افزایش می‌دهد، نه بازنویسی
    می‌کند — چون بخشی از موجودیِ دریافت‌شده ممکن است تا امروز فروخته/مصرف شده
    باشد؛ میانگینِ موزون همان چیزی است که موجودیِ باقی‌مانده را درست
    ارزش‌گذاری می‌کند.
    """
    plan = db.query(ProductionPlan).filter(ProductionPlan.id == plan_id).with_for_update().one_or_none()
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سفارشِ تولید یافت نشد")
    if Decimal(plan.qty_produced) <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "هنوز محصولی از این سفارش دریافت نشده")

    added = Decimal(data.labor_cost or 0) + Decimal(data.overhead_cost or 0)
    if added <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "دستمزد یا سربار را وارد کنید")

    finished = db.get(Item, plan.finished_item_id)
    if finished is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "محصولِ نهایی یافت نشد")

    lock_items(db, {finished.id})
    existing_qty = get_total_stock_qty(db, finished.id)
    if existing_qty > 0:
        additional_unit = added / Decimal(plan.qty_produced)
        finished.average_cost = Decimal(finished.average_cost) + additional_unit

    #: جدا نگه داشته می‌شوند تا گزارشِ بهای تمام‌شده سه جزء را تفکیک کند.
    plan.labor_cost_applied = Decimal(plan.labor_cost_applied) + Decimal(data.labor_cost or 0)
    plan.overhead_cost_applied = Decimal(plan.overhead_cost_applied) + Decimal(data.overhead_cost or 0)

    entry_number = next_document_number(db, DOC_JOURNAL_ENTRY)
    journal_entry = JournalEntry(
        number=entry_number,
        entry_date=data.calc_date,
        description=f"دستمزد و سربارِ تولیدِ سفارشِ شماره‌ی {plan.number}",
        source_type="production_plan",
        created_by_id=user.id,
        lines=number_lines([
            JournalLine(account_id=get_account(db, cc.INVENTORY).id, debit=added, credit=0, description="دستمزد و سربارِ تولید (سرمایه‌ای در بهای کالا)"),
            JournalLine(account_id=get_account(db, cc.CASH).id, debit=0, credit=added, description="پرداختِ دستمزد و سربارِ تولید"),
        ]),
    )
    tafsili.assert_entry_has_tafsili(db, journal_entry)
    db.add(journal_entry)
    db.flush()
    db.refresh(plan)
    return plan
