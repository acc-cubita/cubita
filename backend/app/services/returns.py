from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.models.accounting import JournalLine
from app.models.inventory import Item, StockLedger
from app.models.invoices import PurchaseInvoice, PurchaseInvoiceLine, SalesInvoice, SalesInvoiceLine
from app.models.returns import PurchaseReturn, PurchaseReturnLine, SalesReturn, SalesReturnLine
from app.models.user import User
from app.schemas.returns import PurchaseReturnIn, SalesReturnIn
from app.services import chart_codes as cc
from app.services.common import get_account, make_journal_entry
from app.services.inventory import get_stock_qty, get_total_stock_qty
from app.services.period_close import assert_period_open


def _sales_invoice_line_summary(db: Session, invoice_id: UUID) -> dict[UUID, dict]:
    """برای هر کالای فاکتور: تعداد فروخته‌شده، میانگین وزنی قیمت/بهای آن، و مجموع قبلاً برگشت‌خورده."""
    lines = db.query(SalesInvoiceLine).filter(SalesInvoiceLine.invoice_id == invoice_id).all()
    summary: dict[UUID, dict] = {}
    for line in lines:
        entry = summary.setdefault(line.item_id, {"qty": Decimal(0), "amount": Decimal(0), "cost_amount": Decimal(0)})
        entry["qty"] += Decimal(line.qty)
        entry["amount"] += Decimal(line.qty) * Decimal(line.unit_price)
        entry["cost_amount"] += Decimal(line.qty) * Decimal(line.unit_cost)

    already_returned = (
        db.query(SalesReturnLine.item_id, func.coalesce(func.sum(SalesReturnLine.qty), 0))
        .join(SalesReturn, SalesReturn.id == SalesReturnLine.return_id)
        .filter(SalesReturn.sales_invoice_id == invoice_id)
        .group_by(SalesReturnLine.item_id)
        .all()
    )
    returned_by_item = {item_id: Decimal(qty) for item_id, qty in already_returned}

    for item_id, entry in summary.items():
        entry["unit_price"] = entry["amount"] / entry["qty"] if entry["qty"] else Decimal(0)
        entry["unit_cost"] = entry["cost_amount"] / entry["qty"] if entry["qty"] else Decimal(0)
        entry["already_returned"] = returned_by_item.get(item_id, Decimal(0))
        entry["remaining"] = entry["qty"] - entry["already_returned"]
    return summary


def post_sales_return(db: Session, data: SalesReturnIn, user: User) -> SalesReturn:
    assert_period_open(db, data.return_date)

    invoice = db.get(SalesInvoice, data.sales_invoice_id)
    if invoice is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "فاکتور فروش یافت نشد")

    summary = _sales_invoice_line_summary(db, data.sales_invoice_id)
    items_by_id = {i.id: i for i in db.query(Item).filter(Item.id.in_([l.item_id for l in data.lines])).all()}

    total_amount = Decimal(0)
    total_cost = Decimal(0)
    return_lines: list[SalesReturnLine] = []
    stock_moves: list[StockLedger] = []

    for line in data.lines:
        item = items_by_id.get(line.item_id)
        info = summary.get(line.item_id)
        if info is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"کالا «{item.name if item else line.item_id}» در این فاکتور فروش نبوده است")
        if line.qty > info["remaining"]:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"مقدار برگشتی «{item.name}» بیش از باقی‌مانده‌ی قابل‌برگشت است (باقی‌مانده: {info['remaining']})",
            )

        unit_price = info["unit_price"]
        unit_cost = info["unit_cost"]
        total_amount += line.qty * unit_price
        total_cost += line.qty * unit_cost
        return_lines.append(
            SalesReturnLine(
                item_id=line.item_id,
                qty=line.qty,
                unit_price=unit_price,
                unit_cost=unit_cost,
                description=line.description,
            )
        )

        if not item.is_service:
            existing_qty = get_total_stock_qty(db, item.id)
            new_qty = existing_qty + line.qty
            if new_qty > 0:
                item.average_cost = ((existing_qty * item.average_cost) + (line.qty * unit_cost)) / new_qty
            stock_moves.append(
                StockLedger(
                    item_id=line.item_id,
                    warehouse_id=invoice.warehouse_id,
                    qty=line.qty,
                    unit_cost=unit_cost,
                    entry_date=data.return_date,
                    source_type="sales_return",
                )
            )

    journal_lines = [
        JournalLine(
            account_id=get_account(db, cc.SALES_REVENUE).id, debit=total_amount, credit=0, description="برگشت از فروش"
        ),
        JournalLine(
            account_id=(get_account(db, cc.ACCOUNTS_RECEIVABLE) if invoice.contact_id else get_account(db, cc.CASH)).id,
            debit=0,
            credit=total_amount,
            description="برگشت از فروش",
        ),
    ]
    if total_cost > 0:
        journal_lines.append(
            JournalLine(
                account_id=get_account(db, cc.INVENTORY).id, debit=total_cost, credit=0, description="بازگشت کالا به موجودی"
            )
        )
        journal_lines.append(
            JournalLine(
                account_id=get_account(db, cc.COGS).id,
                debit=0,
                credit=total_cost,
                description="کاهش بهای تمام‌شده بابت برگشت از فروش",
            )
        )

    number = db.execute(text("SELECT nextval('sales_return_number_seq')")).scalar_one()
    journal_entry = make_journal_entry(
        db, data.return_date, f"برگشت از فروش شماره {number} (فاکتور فروش {invoice.number})", "sales_return", user, journal_lines
    )

    sales_return = SalesReturn(
        number=number,
        return_date=data.return_date,
        sales_invoice_id=data.sales_invoice_id,
        description=data.description,
        total_amount=total_amount,
        total_cost=total_cost,
        journal_entry_id=journal_entry.id,
        created_by_id=user.id,
        lines=return_lines,
    )
    db.add(sales_return)
    for move in stock_moves:
        move.source_id = sales_return.id
        db.add(move)

    db.commit()
    db.refresh(sales_return)
    return sales_return


def _purchase_invoice_line_summary(db: Session, invoice_id: UUID) -> dict[UUID, dict]:
    lines = db.query(PurchaseInvoiceLine).filter(PurchaseInvoiceLine.invoice_id == invoice_id).all()
    summary: dict[UUID, dict] = {}
    for line in lines:
        entry = summary.setdefault(line.item_id, {"qty": Decimal(0), "cost_amount": Decimal(0)})
        entry["qty"] += Decimal(line.qty)
        entry["cost_amount"] += Decimal(line.qty) * Decimal(line.unit_cost)

    already_returned = (
        db.query(PurchaseReturnLine.item_id, func.coalesce(func.sum(PurchaseReturnLine.qty), 0))
        .join(PurchaseReturn, PurchaseReturn.id == PurchaseReturnLine.return_id)
        .filter(PurchaseReturn.purchase_invoice_id == invoice_id)
        .group_by(PurchaseReturnLine.item_id)
        .all()
    )
    returned_by_item = {item_id: Decimal(qty) for item_id, qty in already_returned}

    for item_id, entry in summary.items():
        entry["unit_cost"] = entry["cost_amount"] / entry["qty"] if entry["qty"] else Decimal(0)
        entry["already_returned"] = returned_by_item.get(item_id, Decimal(0))
        entry["remaining"] = entry["qty"] - entry["already_returned"]
    return summary


def post_purchase_return(db: Session, data: PurchaseReturnIn, user: User) -> PurchaseReturn:
    assert_period_open(db, data.return_date)

    invoice = db.get(PurchaseInvoice, data.purchase_invoice_id)
    if invoice is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "فاکتور خرید یافت نشد")

    summary = _purchase_invoice_line_summary(db, data.purchase_invoice_id)
    items_by_id = {i.id: i for i in db.query(Item).filter(Item.id.in_([l.item_id for l in data.lines])).all()}

    total_amount = Decimal(0)
    return_lines: list[PurchaseReturnLine] = []
    stock_moves: list[StockLedger] = []

    for line in data.lines:
        item = items_by_id.get(line.item_id)
        info = summary.get(line.item_id)
        if info is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"کالا «{item.name if item else line.item_id}» در این فاکتور خرید نبوده است")
        if line.qty > info["remaining"]:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"مقدار برگشتی «{item.name}» بیش از باقی‌مانده‌ی قابل‌برگشت است (باقی‌مانده: {info['remaining']})",
            )
        if not item.is_service:
            available = get_stock_qty(db, line.item_id, invoice.warehouse_id)
            if available < line.qty:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    f"موجودی «{item.name}» برای این میزان برگشت کافی نیست (موجود: {available})",
                )

        unit_cost = info["unit_cost"]
        total_amount += line.qty * unit_cost
        return_lines.append(PurchaseReturnLine(item_id=line.item_id, qty=line.qty, unit_cost=unit_cost, description=line.description))

        if not item.is_service:
            existing_qty = get_total_stock_qty(db, item.id)
            new_qty = existing_qty - line.qty
            if new_qty > 0:
                item.average_cost = ((existing_qty * item.average_cost) - (line.qty * unit_cost)) / new_qty
            stock_moves.append(
                StockLedger(
                    item_id=line.item_id,
                    warehouse_id=invoice.warehouse_id,
                    qty=-line.qty,
                    unit_cost=unit_cost,
                    entry_date=data.return_date,
                    source_type="purchase_return",
                )
            )

    journal_lines = [
        JournalLine(
            account_id=(get_account(db, cc.ACCOUNTS_PAYABLE) if invoice.contact_id else get_account(db, cc.CASH)).id,
            debit=total_amount,
            credit=0,
            description="برگشت از خرید",
        ),
        JournalLine(
            account_id=get_account(db, cc.INVENTORY).id, debit=0, credit=total_amount, description="کاهش موجودی بابت برگشت از خرید"
        ),
    ]
    number = db.execute(text("SELECT nextval('purchase_return_number_seq')")).scalar_one()
    journal_entry = make_journal_entry(
        db, data.return_date, f"برگشت از خرید شماره {number} (فاکتور خرید {invoice.number})", "purchase_return", user, journal_lines
    )

    purchase_return = PurchaseReturn(
        number=number,
        return_date=data.return_date,
        purchase_invoice_id=data.purchase_invoice_id,
        description=data.description,
        total_amount=total_amount,
        journal_entry_id=journal_entry.id,
        created_by_id=user.id,
        lines=return_lines,
    )
    db.add(purchase_return)
    for move in stock_moves:
        move.source_id = purchase_return.id
        db.add(move)

    db.commit()
    db.refresh(purchase_return)
    return purchase_return
