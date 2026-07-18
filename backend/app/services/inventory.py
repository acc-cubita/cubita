from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.models.accounting import JournalEntry, JournalLine
from app.models.inventory import Item, StockAdjustment, StockLedger
from app.models.invoices import (
    PurchaseInvoice,
    PurchaseInvoiceLine,
    SalesInvoice,
    SalesInvoiceLine,
)
from app.models.user import User
from app.schemas.inventory import StockAdjustmentIn
from app.schemas.invoices import PurchaseInvoiceIn, SalesInvoiceIn
from app.services import chart_codes as cc
from app.services.common import get_account as _get_account
from app.services.period_close import assert_period_open


def get_stock_qty(db: Session, item_id: UUID, warehouse_id: UUID) -> Decimal:
    total = (
        db.query(func.coalesce(func.sum(StockLedger.qty), 0))
        .filter(StockLedger.item_id == item_id, StockLedger.warehouse_id == warehouse_id)
        .scalar()
    )
    return Decimal(total)


def get_total_stock_qty(db: Session, item_id: UUID) -> Decimal:
    total = db.query(func.coalesce(func.sum(StockLedger.qty), 0)).filter(StockLedger.item_id == item_id).scalar()
    return Decimal(total)


def post_sales_invoice(db: Session, data: SalesInvoiceIn, user: User) -> SalesInvoice:
    assert_period_open(db, data.invoice_date)

    items_by_id = {item.id: item for item in db.query(Item).filter(Item.id.in_([l.item_id for l in data.lines])).all()}
    for line in data.lines:
        item = items_by_id.get(line.item_id)
        if item is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"کالا با شناسه {line.item_id} یافت نشد")
        if not item.is_service:
            available = get_stock_qty(db, line.item_id, data.warehouse_id)
            if available < line.qty:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    f"موجودی «{item.name}» کافی نیست (موجود: {available}, درخواستی: {line.qty})",
                )

    number = db.execute(text("SELECT nextval('sales_invoice_number_seq')")).scalar_one()

    total_amount = Decimal(0)
    total_cost = Decimal(0)
    invoice_lines: list[SalesInvoiceLine] = []
    stock_moves: list[StockLedger] = []

    for line in data.lines:
        item = items_by_id[line.item_id]
        unit_cost = item.average_cost if not item.is_service else Decimal(0)
        total_amount += line.qty * line.unit_price
        total_cost += line.qty * unit_cost
        invoice_lines.append(
            SalesInvoiceLine(
                item_id=line.item_id,
                qty=line.qty,
                unit_price=line.unit_price,
                unit_cost=unit_cost,
                description=line.description,
            )
        )
        if not item.is_service:
            stock_moves.append(
                StockLedger(
                    item_id=line.item_id,
                    warehouse_id=data.warehouse_id,
                    qty=-line.qty,
                    unit_cost=unit_cost,
                    entry_date=data.invoice_date,
                    source_type="sales_invoice",
                )
            )

    journal_lines = [
        JournalLine(
            account_id=(_get_account(db, cc.ACCOUNTS_RECEIVABLE) if data.contact_id else _get_account(db, cc.CASH)).id,
            debit=total_amount,
            credit=0,
            description="بابت فروش کالا/خدمت",
        ),
        JournalLine(
            account_id=_get_account(db, cc.SALES_REVENUE).id,
            debit=0,
            credit=total_amount,
            description="بابت فروش کالا/خدمت",
        ),
    ]
    if total_cost > 0:
        journal_lines.append(
            JournalLine(
                account_id=_get_account(db, cc.COGS).id,
                debit=total_cost,
                credit=0,
                description="بهای تمام‌شده کالای فروش‌رفته",
            )
        )
        journal_lines.append(
            JournalLine(
                account_id=_get_account(db, cc.INVENTORY).id,
                debit=0,
                credit=total_cost,
                description="کسر از موجودی کالا بابت فروش",
            )
        )

    entry_number = db.execute(text("SELECT nextval('journal_entry_number_seq')")).scalar_one()
    journal_entry = JournalEntry(
        number=entry_number,
        entry_date=data.invoice_date,
        description=f"فاکتور فروش شماره {number}",
        source_type="sales_invoice",
        created_by_id=user.id,
        lines=journal_lines,
    )
    db.add(journal_entry)
    db.flush()

    invoice = SalesInvoice(
        number=number,
        invoice_date=data.invoice_date,
        contact_id=data.contact_id,
        warehouse_id=data.warehouse_id,
        description=data.description,
        total_amount=total_amount,
        total_cost=total_cost,
        journal_entry_id=journal_entry.id,
        source_order_id=data.source_order_id,
        created_by_id=user.id,
        lines=invoice_lines,
    )
    db.add(invoice)
    for move in stock_moves:
        move.source_id = invoice.id
        db.add(move)

    db.commit()
    db.refresh(invoice)
    return invoice


def post_purchase_invoice(db: Session, data: PurchaseInvoiceIn, user: User) -> PurchaseInvoice:
    assert_period_open(db, data.invoice_date)

    items_by_id = {item.id: item for item in db.query(Item).filter(Item.id.in_([l.item_id for l in data.lines])).all()}
    for line in data.lines:
        if line.item_id not in items_by_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"کالا با شناسه {line.item_id} یافت نشد")

    number = db.execute(text("SELECT nextval('purchase_invoice_number_seq')")).scalar_one()

    total_amount = Decimal(0)
    invoice_lines: list[PurchaseInvoiceLine] = []
    stock_moves: list[StockLedger] = []

    for line in data.lines:
        item = items_by_id[line.item_id]
        total_amount += line.qty * line.unit_cost
        invoice_lines.append(
            PurchaseInvoiceLine(
                item_id=line.item_id,
                qty=line.qty,
                unit_cost=line.unit_cost,
                description=line.description,
            )
        )
        if not item.is_service:
            existing_qty = get_total_stock_qty(db, item.id)
            new_qty = existing_qty + line.qty
            if new_qty > 0:
                item.average_cost = ((existing_qty * item.average_cost) + (line.qty * line.unit_cost)) / new_qty
            stock_moves.append(
                StockLedger(
                    item_id=line.item_id,
                    warehouse_id=data.warehouse_id,
                    qty=line.qty,
                    unit_cost=line.unit_cost,
                    entry_date=data.invoice_date,
                    source_type="purchase_invoice",
                )
            )

    journal_lines = [
        JournalLine(
            account_id=_get_account(db, cc.INVENTORY).id,
            debit=total_amount,
            credit=0,
            description="بابت خرید کالا",
        ),
        JournalLine(
            account_id=(_get_account(db, cc.ACCOUNTS_PAYABLE) if data.contact_id else _get_account(db, cc.CASH)).id,
            debit=0,
            credit=total_amount,
            description="بابت خرید کالا",
        ),
    ]

    entry_number = db.execute(text("SELECT nextval('journal_entry_number_seq')")).scalar_one()
    journal_entry = JournalEntry(
        number=entry_number,
        entry_date=data.invoice_date,
        description=f"فاکتور خرید شماره {number}",
        source_type="purchase_invoice",
        created_by_id=user.id,
        lines=journal_lines,
    )
    db.add(journal_entry)
    db.flush()

    invoice = PurchaseInvoice(
        number=number,
        invoice_date=data.invoice_date,
        contact_id=data.contact_id,
        warehouse_id=data.warehouse_id,
        description=data.description,
        total_amount=total_amount,
        journal_entry_id=journal_entry.id,
        created_by_id=user.id,
        lines=invoice_lines,
    )
    db.add(invoice)
    for move in stock_moves:
        move.source_id = invoice.id
        db.add(move)

    db.commit()
    db.refresh(invoice)
    return invoice


def post_stock_adjustment(db: Session, data: StockAdjustmentIn, user: User) -> StockAdjustment:
    assert_period_open(db, data.adjustment_date)

    item = db.get(Item, data.item_id)
    if item is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "کالا یافت نشد")
    if item.is_service:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "خدمت موجودی ندارد که تعدیل شود")

    if data.qty_diff < 0:
        available = get_stock_qty(db, data.item_id, data.warehouse_id)
        if available < abs(data.qty_diff):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"موجودی «{item.name}» برای این میزان کسری کافی نیست (موجود: {available})",
            )

    unit_cost = item.average_cost
    amount = abs(data.qty_diff) * unit_cost

    # کسری: بدهکار حساب مغایرت انبار (هزینه)، بستانکار موجودی کالا. اضافی: برعکس (کاهش هزینه‌ی مغایرت).
    if data.qty_diff < 0:
        debit_account, credit_account = cc.INVENTORY_ADJUSTMENT, cc.INVENTORY
    else:
        debit_account, credit_account = cc.INVENTORY, cc.INVENTORY_ADJUSTMENT

    journal_entry = None
    if amount > 0:
        entry_number = db.execute(text("SELECT nextval('journal_entry_number_seq')")).scalar_one()
        journal_entry = JournalEntry(
            number=entry_number,
            entry_date=data.adjustment_date,
            description=f"تعدیل موجودی «{item.name}»: {data.reason}".strip(),
            source_type="stock_adjustment",
            created_by_id=user.id,
            lines=[
                JournalLine(account_id=_get_account(db, debit_account).id, debit=amount, credit=0),
                JournalLine(account_id=_get_account(db, credit_account).id, debit=0, credit=amount),
            ],
        )
        db.add(journal_entry)
        db.flush()

    adjustment = StockAdjustment(
        item_id=data.item_id,
        warehouse_id=data.warehouse_id,
        qty_diff=data.qty_diff,
        unit_cost=unit_cost,
        reason=data.reason,
        adjustment_date=data.adjustment_date,
        journal_entry_id=journal_entry.id if journal_entry else None,
        created_by_id=user.id,
    )
    db.add(adjustment)
    db.add(
        StockLedger(
            item_id=data.item_id,
            warehouse_id=data.warehouse_id,
            qty=data.qty_diff,
            unit_cost=unit_cost,
            entry_date=data.adjustment_date,
            source_type="adjustment",
        )
    )
    db.commit()
    db.refresh(adjustment)
    return adjustment
