"""انتقال بین انبار — خروج از مبدأ و ورود به مقصد، اتمی و قابلِ ردیابی (§۲۷–§۲۹ فصلِ خروج).

تا امروز این مسیر پنج شکاف داشت که همه‌شان بی‌صدا بودند:

* **قفل نداشت.** دو انتقالِ هم‌زمان (یا یک انتقال و یک خروج) از یک انبار هر دو
  همان موجودی را می‌خواندند و هر دو پاس می‌شدند؛ موجودی منفی می‌شد.
* **ردیف‌ها را جمع نمی‌زد.** دو ردیفِ ۶تایی از یک کالا هرکدام جدا با موجودیِ ۱۰
  سنجیده می‌شدند — همان خطایی که فاکتورِ فروش سال‌ها پیش بسته بود.
* **دوره‌ی بسته و انبارهای مجازِ کالا را نمی‌سنجید.**
* **کلیدِ تکرار و ابطال نداشت.** تکرارِ شبکه‌ای انتقالِ دوم می‌ساخت و اشتباه اصلاح‌پذیر نبود.
* **سند نمی‌زد، حتی میانِ دو انبار با دو معینِ موجودیِ متفاوت.**
"""

from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.accounting import JournalEntry, JournalLine
from app.models.counters import DOC_STOCK_TRANSFER
from app.models.inventory import Item, StockLedger, Warehouse
from app.models.transfers import StockTransfer, StockTransferLine
from app.models.user import User
from app.schemas.transfers import StockTransferIn
from app.services import items as items_svc
from app.services import batches as batches_svc
from app.services import valuation
from app.services import units
from app.services import warehouses
from app.services.common import make_journal_entry
from app.services.inventory import get_stock_qty, lock_items
from app.services.numbering import next_document_number
from app.services.period_close import assert_period_open
from app.services.voiding import reverse_journal_entry


def post_stock_transfer(db: Session, data: StockTransferIn, user: User) -> StockTransfer:
    assert_period_open(db, data.transfer_date)
    #: §۲۲ فصلِ انبار — هر دو سر باید انبارِ فعال باشند: انتقال **به** انبارِ
    #: غیرفعال یعنی کالا همان‌جا گیر بیفتد.
    warehouses.assert_usable(db, data.from_warehouse_id, action="انتقال از انبار")
    warehouses.assert_usable(db, data.to_warehouse_id, action="انتقال به انبار")

    items_by_id = {i.id: i for i in db.query(Item).filter(Item.id.in_([l.item_id for l in data.lines])).all()}
    requested: dict[UUID, Decimal] = defaultdict(Decimal)
    lock_items(db, items_by_id.keys())
    unit_registry = units.OperationUnitRegistry(db, items_by_id.values(),
        batch_ids=[allocation.batch_id for line in data.lines for allocation in (line.batch_allocations or [])])
    conversions = []
    for line in data.lines:
        item = items_by_id.get(line.item_id)
        if item is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"کالا با شناسه {line.item_id} یافت نشد")
        if item.is_service:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"«{item.name}» خدمت است و قابل جابه‌جایی بین انبارها نیست")
        selected_batch = line.batch_allocations[0].batch_id if line.batch_allocations and len(line.batch_allocations) == 1 else None
        conversion = units.convert_transaction(db, item, line.qty, line.unit_id,
            context="inventory", batch_id=selected_batch, observations=line.observations, registry=unit_registry)
        conversions.append(conversion)
        requested[line.item_id] += conversion.target_qty
    for item_id in requested:
        #: §۲۹ فصلِ کالا — کالا فقط به انبارهای مرتبطش وارد می‌شود.
        items_svc.assert_warehouse_allowed(db, items_by_id[item_id], data.to_warehouse_id)

    lock_items(db, requested.keys())
    fresh = {i.id: i for i in db.query(Item).filter(Item.id.in_(requested.keys())).populate_existing().all()}
    for item_id, qty in requested.items():
        available = get_stock_qty(db, item_id, data.from_warehouse_id)
        if available < qty:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"موجودی «{fresh[item_id].name}» در انبار مبدأ کافی نیست (موجود: {available}, درخواستی: {qty})",
            )

    transfer = StockTransfer(
        number=next_document_number(db, DOC_STOCK_TRANSFER),
        transfer_date=data.transfer_date,
        from_warehouse_id=data.from_warehouse_id,
        to_warehouse_id=data.to_warehouse_id,
        description=data.description,
        created_by_id=user.id,
        lines=[StockTransferLine(item_id=line.item_id, qty=conversion.target_qty,
            **units.snapshot_fields(conversion)) for line, conversion in zip(data.lines, conversions, strict=True)],
    )
    stored_lines = list(transfer.lines)
    db.add(transfer)
    db.flush()

    total = Decimal(0)
    moves: list[StockLedger] = []
    for line, conversion, stored_line in zip(data.lines, conversions, stored_lines, strict=True):
        #: انتقالِ پیش‌تاریخ با میانگینِ همان روز — همان قاعده‌ی خروج.
        unit_cost = valuation.cost_for_posting(db, fresh[line.item_id], data.transfer_date)
        total += (conversion.target_qty * unit_cost).quantize(Decimal(1))
        #: **بار باید از مرزِ انبار رد شود، وگرنه گم می‌شود.**
        #:
        #: `StockBatch` به `(کالا، انبار)` بسته است. بی این تفکیک، انتقال از
        #: مبدأ کم می‌کرد و در مقصد کالا **بی‌بچ** ظاهر می‌شد — با تاریخِ انقضایی
        #: که دیگر هیچ‌جا نوشته نبود. برای هر بارِ مبدأ یک بارِ آینه در مقصد ساخته
        #: می‌شود که `parent_batch_id`ش زنجیره را نگه می‌دارد.
        plan = batches_svc.plan_outflow(
            db, fresh[line.item_id], data.from_warehouse_id, conversion.target_qty, data.transfer_date,
            wanted=[(a.batch_id, a.qty) for a in line.batch_allocations] if line.batch_allocations else None,
        )
        splits = plan or [(None, conversion.target_qty)]
        for batch_id, take in splits:
            mirror_id = (
                batches_svc.mirror_batch(db, batch_id, data.to_warehouse_id, user, conversion=conversion).id
                if batch_id is not None
                else None
            )
            for warehouse_id, qty, source_type, tag in (
                (data.from_warehouse_id, -take, "transfer_out", batch_id),
                (data.to_warehouse_id, take, "transfer_in", mirror_id),
            ):
                move = StockLedger(
                    **units.movement_snapshot_fields(conversion, qty),
                    item_id=line.item_id, warehouse_id=warehouse_id, qty=qty, unit_cost=unit_cost,
                    entry_date=data.transfer_date, source_type=source_type, source_id=transfer.id,
                    batch_id=tag,
                    source_line_id=stored_line.id,
                )
                db.add(move)
                moves.append(move)
    valuation.settle_posting(db, moves)

    #: جمعِ موجودیِ شرکت عوض نمی‌شود (§۲۸)، پس میانِ دو انبارِ هم‌حساب سندی نیست.
    #: ولی دو معینِ متفاوت یعنی ارزش واقعاً از یکی به دیگری رفته.
    source_account = warehouses.inventory_account_id(db, data.from_warehouse_id)
    target_account = warehouses.inventory_account_id(db, data.to_warehouse_id)
    if source_account != target_account and total > 0:
        journal = make_journal_entry(
            db, data.transfer_date, f"انتقال بین انبار شماره {transfer.number}", "stock_transfer", user,
            [
                JournalLine(account_id=target_account, debit=total, credit=0, description="ورودِ کالا به انبارِ مقصد"),
                JournalLine(account_id=source_account, debit=0, credit=total, description="خروجِ کالا از انبارِ مبدأ"),
            ],
        )
        transfer.journal_entry_id = journal.id

    db.flush()
    db.refresh(transfer)
    return transfer


def void_stock_transfer(
    db: Session, transfer_id: UUID, *, reason: str, user: User, void_date: date | None = None
) -> StockTransfer:
    """هر دو حرکت با هم برمی‌گردند — همان اتمی‌بودنی که ثبت داشت."""
    transfer = db.query(StockTransfer).filter(StockTransfer.id == transfer_id).with_for_update().one_or_none()
    if transfer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "انتقال یافت نشد")
    if transfer.voided_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "این انتقال قبلاً باطل شده است")
    effective = void_date or transfer.transfer_date
    assert_period_open(db, effective)

    moves = db.query(StockLedger).filter(
        StockLedger.source_id == transfer.id, StockLedger.source_type.in_(("transfer_out", "transfer_in"))
    ).all()
    arrived: dict[UUID, Decimal] = defaultdict(Decimal)
    for move in moves:
        if move.source_type == "transfer_in":
            arrived[move.item_id] += Decimal(move.qty)
    lock_items(db, arrived.keys())
    for item_id, qty in arrived.items():
        available = get_stock_qty(db, item_id, transfer.to_warehouse_id)
        if available < qty:
            item = db.get(Item, item_id)
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"«{item.name if item else ''}» از انبارِ مقصد خارج شده است (موجود: {available}، لازم برای "
                f"ابطال: {qty}). ابطال یعنی کالا به مبدأ برگردد؛ اول خروج‌های بعدی را باطل کنید.",
            )

    #: ابطالِ انتقال ورودِ انبارِ مقصد را برمی‌دارد؛ خروجی که بعد از آن رفته بی‌پشتوانه نشود.
    valuation.guard_void(db, ("transfer_out", "transfer_in"), transfer.id)
    needed_by_batch = defaultdict(Decimal)
    for move in moves:
        if move.source_type == "transfer_in" and move.batch_id is not None:
            needed_by_batch[move.batch_id] += Decimal(move.qty)
    available_by_batch = batches_svc.on_hand(db, list(needed_by_batch))
    if any(available_by_batch.get(key, Decimal(0)) < qty for key, qty in needed_by_batch.items()):
        raise HTTPException(409, "بار منتقل‌شده در مقصد مصرف شده است؛ ابتدا خروج‌های همان بار را باطل کنید")
    for move in moves:
        db.add(StockLedger(
            **units.negated_snapshot_fields(move),
            item_id=move.item_id, warehouse_id=move.warehouse_id, qty=-Decimal(move.qty),
            unit_cost=move.unit_cost, entry_date=effective, source_type="void", source_id=transfer.id,
            batch_id=move.batch_id, source_line_id=move.source_line_id,
        ))
    original = db.get(JournalEntry, transfer.journal_entry_id) if transfer.journal_entry_id else None
    if original is not None:
        reverse_journal_entry(
            db, original, void_date=effective, user=user,
            description=f"ابطال انتقال بین انبار شماره {transfer.number} — {reason.strip()}",
        )
    transfer.voided_at = datetime.now(timezone.utc)
    transfer.voided_by_id = user.id
    transfer.void_reason = reason.strip()
    valuation.settle_void(db, [move.item_id for move in moves])
    return transfer


def transfer_print_projection(db: Session, transfer: StockTransfer) -> dict:
    """همان «مجوز خروج انبار»، با انبارِ مقصد به‌جای تحویل‌گیرنده."""
    source = db.get(Warehouse, transfer.from_warehouse_id)
    target = db.get(Warehouse, transfer.to_warehouse_id)
    lines = []
    for seq, line in enumerate(transfer.lines, start=1):
        item = line.item
        lines.append({
            "seq": seq,
            "code": item.sku if item else "",
            "name": item.name if item else "",
            "qty": line.qty,
            "unit": (line.unit_conversion_snapshot or {}).get("target_unit_name") or (item.unit if item else ""),
            "secondary_qty": line.entered_qty if line.entered_unit_id != line.base_unit_id else None,
            "secondary_unit": (line.unit_conversion_snapshot or {}).get("source_unit_name", ""),
            "description": "",
        })
    return {
        "title": "مجوز خروج انبار (انتقال بین انبار)",
        "number": transfer.number,
        "doc_date": transfer.transfer_date,
        "type_label": "انتقال بین انبار",
        "warehouse_code": source.code if source else "",
        "warehouse_name": source.name if source else "",
        "party_label": "انبار مقصد",
        "party_name": target.name if target else "",
        "party_detail": target.code if target else "",
        "lines": lines,
        "total_qty": sum((Decimal(line.qty) for line in transfer.lines), Decimal(0)),
        "references": [],
        "description": transfer.description or "",
        "sign_labels": ("صادرکننده", "تحویل‌گیرنده‌ی انبارِ مقصد"),
        "voided_at": transfer.voided_at,
        "void_reason": transfer.void_reason or "",
    }
