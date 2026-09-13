"""انبارگردانی (شمارش فیزیکی موجودی).

یک لایه‌ی جلسه‌ای بالای تعدیلِ تک‌کالاییِ موجود: به‌جای ثبتِ دستیِ هر کالا، از کلِ
انبار عکس‌برداری می‌شود، کاربر شمارشِ فیزیکی را وارد می‌کند، و در پایان یک بار همه‌ی
مغایرت‌ها با یک سندِ تجمیعی اعمال می‌شوند. قرارداد حسابداری همان تعدیلِ تک‌کالایی است:
اضافیِ خالص → بدهکارِ موجودی/بستانکارِ مغایرت انبار؛ کسریِ خالص → برعکس. بهای هر
مغایرت از `unit_cost`‌ای که هنگام ایجادِ جلسه عکس‌برداری شده حساب می‌شود (میانگین
موزون در آن لحظه)، پس میانگینِ موزون با تعدیلِ مقداری تغییر نمی‌کند.
"""
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.accounting import JournalEntry, JournalLine
from app.services import tafsili
from app.models.counters import DOC_JOURNAL_ENTRY
from app.models.inventory import Item, StockLedger, Warehouse
from app.models.stock_count import StockCountLine, StockCountSession
from app.models.user import User
from app.services import chart_codes as cc
from app.services import warehouses
from app.services.common import get_account as _get_account
from app.services.common import number_lines
from app.services import valuation
from app.services.numbering import next_document_number
from app.services.period_close import assert_period_open


def _get_session(db: Session, session_id: UUID) -> StockCountSession:
    session = db.get(StockCountSession, session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "جلسه‌ی انبارگردانی یافت نشد")
    return session


def create_session(db: Session, warehouse_id: UUID, count_date, user: User, notes: str = "") -> StockCountSession:
    """جلسه‌ی تازه می‌سازد و از موجودیِ سیستمیِ همه‌ی کالاهای غیرخدماتی عکس‌برداری می‌کند."""
    warehouses.assert_usable(db, warehouse_id, action="انبارگردانی")
    warehouse = db.get(Warehouse, warehouse_id)
    if warehouse is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "انبار یافت نشد")

    # اجازه‌ی بیش از یک جلسه‌ی بازِ همزمان روی یک انبار داده نمی‌شود — دو شمارشِ موازی
    # روی یک انبار یعنی دو عکسِ متناقض از یک واقعیت.
    existing = (
        db.query(StockCountSession)
        .filter(StockCountSession.warehouse_id == warehouse_id, StockCountSession.status == "open")
        .first()
    )
    if existing is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "یک جلسه‌ی انبارگردانیِ باز برای این انبار وجود دارد")

    qty_rows = (
        db.query(StockLedger.item_id, func.coalesce(func.sum(StockLedger.qty), 0))
        .filter(StockLedger.warehouse_id == warehouse_id)
        .group_by(StockLedger.item_id)
        .all()
    )
    qty_map = {item_id: Decimal(q) for item_id, q in qty_rows}

    session = StockCountSession(
        warehouse_id=warehouse_id,
        count_date=count_date,
        status="open",
        notes=notes or "",
        created_by_id=user.id,
    )
    items = db.query(Item).filter(Item.is_service.is_(False)).order_by(Item.sku).all()
    for item in items:
        sys_qty = qty_map.get(item.id, Decimal(0))
        session.lines.append(
            StockCountLine(
                item_id=item.id,
                system_qty=sys_qty,
                counted_qty=sys_qty,  # پیش‌فرض = سیستمی؛ کاربر فقط اختلاف‌ها را دست می‌زند
                unit_cost=item.average_cost,
            )
        )
    db.add(session)
    db.flush()
    db.refresh(session)
    return session


def set_counts(db: Session, session_id: UUID, updates: list) -> StockCountSession:
    """شمارشِ فیزیکیِ چند ردیف را به‌روزرسانی می‌کند. فقط روی جلسه‌ی باز مجاز است."""
    session = _get_session(db, session_id)
    if session.status != "open":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "فقط جلسه‌ی باز قابل ویرایش است")

    line_map = {line.id: line for line in session.lines}
    for upd in updates:
        line = line_map.get(upd.line_id)
        if line is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "ردیف انبارگردانی یافت نشد")
        line.counted_qty = upd.counted_qty
    db.flush()
    db.refresh(session)
    return session


def cancel_session(db: Session, session_id: UUID) -> StockCountSession:
    session = _get_session(db, session_id)
    if session.status != "open":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "فقط جلسه‌ی باز قابل لغو است")
    session.status = "cancelled"
    db.flush()
    db.refresh(session)
    return session


def post_session(db: Session, session_id: UUID, user: User) -> StockCountSession:
    """مغایرت‌ها را به دفتر موجودی و یک سندِ تجمیعی اعمال می‌کند و جلسه را می‌بندد."""
    session = _get_session(db, session_id)
    if session.status != "open":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "فقط جلسه‌ی باز قابل ثبت است")
    assert_period_open(db, session.count_date)

    total_delta = Decimal(0)  # تغییرِ خالصِ ارزشِ موجودی (علامت‌دار)
    moves: list[StockLedger] = []
    for line in session.lines:
        variance = Decimal(line.counted_qty) - Decimal(line.system_qty)
        if variance == 0:
            continue
        move = StockLedger(
            item_id=line.item_id,
            warehouse_id=session.warehouse_id,
            qty=variance,
            unit_cost=line.unit_cost,
            entry_date=session.count_date,
            source_type="stock_count",
            source_id=session.id,
        )
        db.add(move)
        moves.append(move)
        total_delta += variance * Decimal(line.unit_cost)
    valuation.settle_posting(db, moves)

    if total_delta != 0:
        amount = abs(total_delta)
        #: سمتِ موجودی معینِ همان انباری است که شمرده شده (§۹).
        inventory_id = warehouses.inventory_account_id(db, session.warehouse_id)
        adjustment_id = _get_account(db, cc.INVENTORY_ADJUSTMENT).id
        if total_delta > 0:  # موجودی خالص زیاد شد (اضافی)
            debit_id, credit_id = inventory_id, adjustment_id
        else:  # موجودی خالص کم شد (کسری)
            debit_id, credit_id = adjustment_id, inventory_id
        entry = JournalEntry(
            number=next_document_number(db, DOC_JOURNAL_ENTRY),
            entry_date=session.count_date,
            description=f"انبارگردانی انبار «{session.warehouse.name}»",
            source_type="stock_count",
            created_by_id=user.id,
            lines=number_lines([
                JournalLine(account_id=debit_id, debit=amount, credit=0),
                JournalLine(account_id=credit_id, debit=0, credit=amount),
            ]),
        )
        tafsili.assert_entry_has_tafsili(db, entry)
        db.add(entry)
        db.flush()
        session.journal_entry_id = entry.id

    session.status = "posted"
    session.posted_at = datetime.now(timezone.utc)
    db.flush()
    db.refresh(session)
    return session


# --- سریال‌سازی -------------------------------------------------------------------


def _serialize_line(line: StockCountLine) -> dict:
    variance = Decimal(line.counted_qty) - Decimal(line.system_qty)
    return {
        "id": line.id,
        "item_id": line.item_id,
        "item_name": line.item.name,
        "item_sku": line.item.sku,
        "unit": line.item.unit,
        "system_qty": Decimal(line.system_qty),
        "counted_qty": Decimal(line.counted_qty),
        "unit_cost": Decimal(line.unit_cost),
        "variance": variance,
        "variance_value": variance * Decimal(line.unit_cost),
    }


def serialize_session(session: StockCountSession) -> dict:
    lines = [_serialize_line(line) for line in sorted(session.lines, key=lambda x: x.item.sku)]
    variance_lines = [l for l in lines if l["variance"] != 0]
    return {
        "id": session.id,
        "warehouse_id": session.warehouse_id,
        "warehouse_name": session.warehouse.name,
        "count_date": session.count_date,
        "status": session.status,
        "notes": session.notes,
        "journal_entry_id": session.journal_entry_id,
        "posted_at": session.posted_at,
        "created_at": session.created_at,
        "line_count": len(lines),
        "variance_line_count": len(variance_lines),
        "total_variance_value": sum((l["variance_value"] for l in variance_lines), Decimal(0)),
        "lines": lines,
    }


def summarize_session(session: StockCountSession) -> dict:
    return {
        "id": session.id,
        "warehouse_id": session.warehouse_id,
        "warehouse_name": session.warehouse.name,
        "count_date": session.count_date,
        "status": session.status,
        "notes": session.notes,
        "posted_at": session.posted_at,
        "created_at": session.created_at,
        "line_count": len(session.lines),
    }


def list_sessions(db: Session) -> list[dict]:
    sessions = (
        db.query(StockCountSession)
        .order_by(StockCountSession.created_at.desc())
        .all()
    )
    return [summarize_session(s) for s in sessions]


def get_session_detail(db: Session, session_id: UUID) -> dict:
    return serialize_session(_get_session(db, session_id))
