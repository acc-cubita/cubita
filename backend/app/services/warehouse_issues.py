"""خروج فیزیکی فروش و COGS؛ مستقل از سند تجاری فاکتور."""

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.models.accounting import JournalEntry, JournalLine
from app.models.counters import DOC_WAREHOUSE_ISSUE
from app.models.inventory import Item, StockLedger, Warehouse
from app.models.invoices import SalesInvoice, SalesInvoiceLine, WarehouseIssue, WarehouseIssueLine
from app.models.user import User
from app.schemas.invoices import WarehouseIssueIn
from app.services import chart_codes as cc
from app.services import tafsili
from app.services import warehouses
from app.services.common import get_account, make_journal_entry
from app.services.inventory import get_stock_qty, lock_items
from app.services.numbering import next_document_number
from app.services.period_close import assert_period_open
from app.services.voiding import reverse_journal_entry


def issued_by_line(db: Session, invoice_id: UUID) -> dict[UUID, Decimal]:
    rows = (
        db.query(WarehouseIssueLine.sales_invoice_line_id, func.sum(WarehouseIssueLine.qty))
        .join(WarehouseIssue, WarehouseIssue.id == WarehouseIssueLine.issue_id)
        .filter(WarehouseIssue.sales_invoice_id == invoice_id, WarehouseIssue.voided_at.is_(None))
        .group_by(WarehouseIssueLine.sales_invoice_line_id).all()
    )
    return {line_id: Decimal(qty) for line_id, qty in rows}


def create_warehouse_issue(
    db: Session, invoice_id: UUID, data: WarehouseIssueIn, user: User
) -> WarehouseIssue:
    assert_period_open(db, data.issue_date)
    invoice = db.query(SalesInvoice).filter(SalesInvoice.id == invoice_id).with_for_update().one_or_none()
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "فاکتور فروش یافت نشد")
    if invoice.is_voided:
        raise HTTPException(status.HTTP_409_CONFLICT, "برای فاکتور باطل‌شده نمی‌توان خروج انبار ساخت")
    warehouse = db.get(Warehouse, data.warehouse_id)
    if warehouse is None or not warehouse.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "انبار فعال یافت نشد")

    requested = {row.sales_invoice_line_id: Decimal(row.qty) for row in data.lines}
    invoice_lines = (
        db.query(SalesInvoiceLine).options(selectinload(SalesInvoiceLine.item))
        .filter(SalesInvoiceLine.invoice_id == invoice.id, SalesInvoiceLine.id.in_(requested))
        .order_by(SalesInvoiceLine.id).with_for_update().all()
    )
    if len(invoice_lines) != len(requested):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "یکی از ردیف‌ها متعلق به این فاکتور نیست")
    if any(line.item.is_service for line in invoice_lines):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "خدمت، خروج فیزیکی انبار ندارد")
    already = issued_by_line(db, invoice.id)
    for line in invoice_lines:
        remaining = Decimal(line.qty) - already.get(line.id, Decimal(0))
        if requested[line.id] > remaining:
            raise HTTPException(status.HTTP_409_CONFLICT, "مقدار خروج از ماندهٔ ردیف فاکتور بیشتر است")

    by_item: dict[UUID, Decimal] = {}
    for line in invoice_lines:
        by_item[line.item_id] = by_item.get(line.item_id, Decimal(0)) + requested[line.id]
    lock_items(db, by_item.keys())
    for item_id, qty in by_item.items():
        available = get_stock_qty(db, item_id, data.warehouse_id)
        if available < qty:
            item = db.get(Item, item_id)
            # برای سازگاری قرارداد مسیرهای فروش فوری، کسری موجودی ورودی نامعتبر
            # (۴۰۰) است؛ ۴۰۹ برای تعارض ماندهٔ خودِ ردیف فاکتور نگه داشته می‌شود.
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"موجودی «{item.name}» کافی نیست")

    issue = WarehouseIssue(
        number=next_document_number(db, DOC_WAREHOUSE_ISSUE), issue_date=data.issue_date,
        sales_invoice_id=invoice.id, warehouse_id=data.warehouse_id,
        description=data.description.strip(), created_by_id=user.id,
    )
    db.add(issue)
    db.flush()
    total_cost = Decimal(0)
    descriptions = {row.sales_invoice_line_id: row.description for row in data.lines}
    for line in invoice_lines:
        qty = requested[line.id]
        unit_cost = Decimal(line.item.average_cost)
        total_cost += qty * unit_cost
        issue.lines.append(WarehouseIssueLine(
            sales_invoice_line_id=line.id, item_id=line.item_id, qty=qty, unit_cost=unit_cost,
            item_code_snapshot=line.item_code_snapshot or line.item.sku,
            item_name_snapshot=line.item_name_snapshot or line.item.name,
            unit_snapshot=line.unit_snapshot or line.item.unit,
            description=descriptions[line.id],
        ))
        db.add(StockLedger(
            item_id=line.item_id, warehouse_id=data.warehouse_id, qty=-qty, unit_cost=unit_cost,
            entry_date=data.issue_date, source_type="warehouse_issue", source_id=issue.id,
        ))
    if total_cost > 0:
        journal = make_journal_entry(db, data.issue_date, f"خروج انبار فروش شماره {issue.number}",
                                     "warehouse_issue", user, [
            JournalLine(account_id=get_account(db, cc.COGS).id, debit=total_cost, credit=0,
                        cost_center_id=invoice.cost_center_id, description="بهای تمام‌شده فروش"),
            #: معینِ **همان انبار**، نه حسابِ تختِ موجودی. اگر انبار نگاشتِ خودش
            #: را نداشته باشد همان پیش‌فرض برمی‌گردد — یعنی رفتارِ پیشین.
            JournalLine(account_id=warehouses.inventory_account_id(db, data.warehouse_id),
                        debit=0, credit=total_cost,
                        cost_center_id=invoice.cost_center_id, description="کسر موجودی بابت خروج فروش"),
        ])
        #: گاردِ تفصیلی روی **هر** سندِ سندپشتیبان اجرا می‌شود؛ سندِ COGS هم
        #: استثنا نیست، وگرنه حسابی که تفصیلی لازم دارد از این مسیر بی‌تفصیلی رد می‌شد.
        tafsili.assert_entry_has_tafsili(db, journal)
        issue.journal_entry_id = journal.id
    invoice.total_cost = Decimal(invoice.total_cost or 0) + total_cost
    db.flush()
    db.refresh(issue)
    return issue


def void_warehouse_issue(
    db: Session, issue_id: UUID, *, reason: str, user: User, void_date: date | None = None
) -> WarehouseIssue:
    issue = db.query(WarehouseIssue).filter(WarehouseIssue.id == issue_id).with_for_update().one_or_none()
    if issue is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "خروج انبار یافت نشد")
    if issue.is_voided:
        raise HTTPException(status.HTTP_409_CONFLICT, "این خروج قبلاً باطل شده است")
    effective = void_date or issue.issue_date
    assert_period_open(db, effective)
    moves = db.query(StockLedger).filter(
        StockLedger.source_type == "warehouse_issue", StockLedger.source_id == issue.id
    ).all()
    lock_items(db, [move.item_id for move in moves])
    for move in moves:
        db.add(StockLedger(
            item_id=move.item_id, warehouse_id=move.warehouse_id, qty=-Decimal(move.qty),
            unit_cost=move.unit_cost, entry_date=effective, source_type="void", source_id=issue.id,
        ))
    original = db.get(JournalEntry, issue.journal_entry_id) if issue.journal_entry_id else None
    if original is not None:
        reverse_journal_entry(
            db, original, void_date=effective, user=user,
            description=f"ابطال خروج انبار شماره {issue.number} — {reason.strip()}",
        )
    issue.voided_at = datetime.now(timezone.utc)
    issue.voided_by_id = user.id
    issue.void_reason = reason.strip()
    issue.status = "voided"
    invoice = db.get(SalesInvoice, issue.sales_invoice_id)
    if invoice:
        invoice.total_cost = max(Decimal(invoice.total_cost or 0) - sum(
            (-Decimal(move.qty)) * Decimal(move.unit_cost) for move in moves
        ), Decimal(0))
    db.flush()
    return issue
