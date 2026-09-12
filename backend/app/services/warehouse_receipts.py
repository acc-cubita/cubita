"""ورود فیزیکیِ خرید؛ مستقل از ثبت تجاری و بدهی فاکتور."""

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.advanced_inventory import StockBatch
from app.models.counters import DOC_WAREHOUSE_RECEIPT
from app.models.inventory import Item, StockLedger, Warehouse
from app.models.invoices import (
    PurchaseInvoice,
    PurchaseInvoiceLine,
    WarehouseReceipt,
    WarehouseReceiptLine,
)
from app.models.user import User
from app.schemas.invoices import WarehouseReceiptIn
from app.services.inventory import get_total_stock_qty, lock_items
from app.services.numbering import next_document_number
from app.services.period_close import assert_period_open
from app.services.voiding import recompute_average_cost


def received_by_line(db: Session, invoice_id: UUID) -> dict[UUID, Decimal]:
    rows = (
        db.query(WarehouseReceiptLine.purchase_invoice_line_id, func.sum(WarehouseReceiptLine.qty))
        .join(WarehouseReceipt, WarehouseReceipt.id == WarehouseReceiptLine.receipt_id)
        .filter(
            WarehouseReceipt.purchase_invoice_id == invoice_id,
            WarehouseReceipt.voided_at.is_(None),
            WarehouseReceipt.status == "posted",
        )
        .group_by(WarehouseReceiptLine.purchase_invoice_line_id)
        .all()
    )
    return {line_id: Decimal(qty) for line_id, qty in rows}


def create_warehouse_receipt(
    db: Session, invoice_id: UUID, data: WarehouseReceiptIn, user: User
) -> WarehouseReceipt:
    assert_period_open(db, data.receipt_date)
    invoice = db.get(PurchaseInvoice, invoice_id)
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "فاکتور خرید یافت نشد")
    if invoice.is_voided:
        raise HTTPException(status.HTTP_409_CONFLICT, "برای فاکتور باطل‌شده نمی‌توان رسید انبار ساخت")
    warehouse = db.get(Warehouse, data.warehouse_id)
    if warehouse is None or not warehouse.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "انبار فعال یافت نشد")

    requested = {row.purchase_invoice_line_id: Decimal(row.qty) for row in data.lines}
    purchase_lines = (
        db.query(PurchaseInvoiceLine)
        .filter(PurchaseInvoiceLine.invoice_id == invoice.id, PurchaseInvoiceLine.id.in_(requested))
        .with_for_update()
        .all()
    )
    if len(purchase_lines) != len(requested):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "یکی از ردیف‌ها متعلق به این فاکتور نیست")
    already = received_by_line(db, invoice.id)
    for line in purchase_lines:
        remaining = Decimal(line.qty) - already.get(line.id, Decimal(0))
        if requested[line.id] > remaining:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"مقدار تحویل «{line.item_name_snapshot or line.item.name}» از مانده {remaining} بیشتر است",
            )

    stock_item_ids = [line.item_id for line in purchase_lines if not line.item.is_service]
    lock_items(db, stock_item_ids)
    receipt = WarehouseReceipt(
        number=next_document_number(db, DOC_WAREHOUSE_RECEIPT),
        receipt_date=data.receipt_date,
        purchase_invoice_id=invoice.id,
        warehouse_id=data.warehouse_id,
        description=data.description.strip(),
        created_by_id=user.id,
    )
    db.add(receipt)
    db.flush()

    for line in purchase_lines:
        qty = requested[line.id]
        line_value = (
            Decimal(line.qty) * Decimal(line.unit_cost)
            - Decimal(line.discount)
            + Decimal(line.addition)
            + Decimal(line.duty_amount)
        )
        unit_cost = line_value / Decimal(line.qty)
        receipt.lines.append(
            WarehouseReceiptLine(
                purchase_invoice_line_id=line.id,
                item_id=line.item_id,
                qty=qty,
                unit_cost=unit_cost,
                item_code_snapshot=line.item_code_snapshot or line.item.sku,
                item_name_snapshot=line.item_name_snapshot or line.item.name,
                unit_snapshot=line.unit_snapshot or line.item.unit,
                description=next(
                    row.description for row in data.lines if row.purchase_invoice_line_id == line.id
                ),
            )
        )
        if line.item.is_service:
            continue
        old_qty = get_total_stock_qty(db, line.item_id)
        new_qty = old_qty + qty
        if new_qty > 0:
            line.item.average_cost = ((old_qty * Decimal(line.item.average_cost)) + qty * unit_cost) / new_qty
        db.add(
            StockLedger(
                item_id=line.item_id,
                warehouse_id=data.warehouse_id,
                qty=qty,
                unit_cost=unit_cost,
                entry_date=data.receipt_date,
                source_type="warehouse_receipt",
                source_id=receipt.id,
            )
        )
        db.add(
            StockBatch(
                item_id=line.item_id,
                warehouse_id=data.warehouse_id,
                batch_number=f"WR{receipt.number}-{len(receipt.lines)}",
                qty=qty,
                received_qty=qty,
                unit_cost=unit_cost,
                source_type="warehouse_receipt",
                source_id=receipt.id,
                received_date=data.receipt_date,
                notes=data.description.strip(),
                created_by_id=user.id,
            )
        )
    db.flush()
    db.refresh(receipt)
    return receipt


def void_warehouse_receipt(
    db: Session, receipt_id: UUID, *, reason: str, user: User, void_date: date | None = None
) -> WarehouseReceipt:
    receipt = db.get(WarehouseReceipt, receipt_id)
    if receipt is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "رسید انبار یافت نشد")
    if receipt.is_voided:
        raise HTTPException(status.HTTP_409_CONFLICT, "این رسید قبلاً باطل شده است")
    effective_date = void_date or receipt.receipt_date
    assert_period_open(db, effective_date)
    moves = db.query(StockLedger).filter(
        StockLedger.source_type == "warehouse_receipt", StockLedger.source_id == receipt.id
    ).all()
    lock_items(db, [move.item_id for move in moves])
    for move in moves:
        current = Decimal(
            db.query(func.coalesce(func.sum(StockLedger.qty), 0))
            .filter(StockLedger.item_id == move.item_id, StockLedger.warehouse_id == move.warehouse_id)
            .scalar()
        )
        if current - Decimal(move.qty) < 0:
            raise HTTPException(status.HTTP_409_CONFLICT, "ابطال رسید، موجودی انبار را منفی می‌کند")
        db.add(
            StockLedger(
                item_id=move.item_id,
                warehouse_id=move.warehouse_id,
                qty=-Decimal(move.qty),
                unit_cost=move.unit_cost,
                entry_date=effective_date,
                source_type="void",
                source_id=receipt.id,
            )
        )
    # StockBatch دفترِ بارِ سالمِ قابل‌استفاده است و از StockLedger مشتق نمی‌شود.
    # اگر فقط حرکتِ کاردکس را برگردانیم، فهرستِ بچ همچنان یک بارِ سالم و مثبت نشان
    # می‌دهد که دیگر در موجودی وجود ندارد. received_qty را برای تاریخچه نگه می‌داریم
    # و فقط مانده‌ی سالمِ بارِ باطل‌شده را صفر می‌کنیم.
    for batch in db.query(StockBatch).filter(
        StockBatch.source_type == "warehouse_receipt", StockBatch.source_id == receipt.id
    ).all():
        batch.qty = Decimal(0)
    receipt.voided_at = datetime.now(timezone.utc)
    receipt.voided_by_id = user.id
    receipt.void_reason = reason.strip()
    receipt.status = "voided"
    db.flush()
    for item_id in {move.item_id for move in moves}:
        item = db.get(Item, item_id)
        if item is not None:
            recompute_average_cost(db, item)
    return receipt
