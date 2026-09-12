"""چرخهٔ تجاری و سند حسابداریِ فروش، مستقل از خروج انبار."""

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.models.accounting import Account, JournalEntry, JournalLine
from app.models.inventory import Contact
from app.models.invoices import SalesInvoice, WarehouseIssue, WarehouseIssueLine
from app.models.receipt import Receipt, ReceiptRelatedDocument
from app.models.sales_ops import SaleType
from app.models.user import User
from app.schemas.invoices import WarehouseIssueIn, WarehouseIssueLineIn
from app.services import chart_codes as cc, tafsili
from app.services.common import get_account, get_or_create_account, make_journal_entry
from app.services.inventory import sales_rounding_account, vat_payable_account
from app.services.period_close import assert_period_open


def _configured_account(db: Session, account_id: UUID | None, fallback: str) -> Account:
    if account_id is None:
        return get_account(db, fallback)
    account = db.get(Account, account_id)
    if account is None or account.is_group or not account.is_active:
        raise HTTPException(status.HTTP_409_CONFLICT, "حساب تنظیم‌شدهٔ نوع فروش معتبر یا قابل ثبت نیست")
    return account


def _discount_account(db: Session) -> Account:
    return get_or_create_account(
        db, cc.SALES_DISCOUNT, code=cc.DEFAULT_CODE_BY_ROLE[cc.SALES_DISCOUNT],
        name="تخفیفات فروش", acc_type="income", parent_code="41",
    )


def _addition_account(db: Session) -> Account:
    return get_or_create_account(
        db, cc.SALES_ADDITIONS, code=cc.DEFAULT_CODE_BY_ROLE[cc.SALES_ADDITIONS],
        name="اضافات فروش", acc_type="income", parent_code="41",
    )


def issue_sales_invoice_journal(db: Session, invoice_id: UUID, user: User) -> JournalEntry:
    """سند تجاری فروش را یک‌بار صادر می‌کند؛ هیچ COGS یا حرکت انباری ندارد."""
    invoice = (
        db.query(SalesInvoice)
        .options(selectinload(SalesInvoice.lines))
        .filter(SalesInvoice.id == invoice_id)
        .with_for_update()
        .one_or_none()
    )
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "فاکتور فروش یافت نشد")
    if invoice.is_voided:
        raise HTTPException(status.HTTP_409_CONFLICT, "برای فاکتور باطل‌شده نمی‌توان سند صادر کرد")
    if invoice.journal_entry_id:
        existing = db.get(JournalEntry, invoice.journal_entry_id)
        if existing is not None:
            return existing
    assert_period_open(db, invoice.invoice_date)

    sale_type = None
    if invoice.sale_type_id:
        sale_type = db.query(SaleType).filter(SaleType.id == invoice.sale_type_id).with_for_update().one_or_none()

    revenue: dict[UUID, Decimal] = defaultdict(Decimal)
    discounts: dict[UUID, Decimal] = defaultdict(Decimal)
    for line in invoice.lines:
        is_service = line.item.is_service
        revenue_id = (
            sale_type.service_revenue_account_id if sale_type and is_service
            else sale_type.goods_revenue_account_id if sale_type
            else None
        )
        discount_id = (
            sale_type.service_discount_account_id if sale_type and is_service
            else sale_type.goods_discount_account_id if sale_type
            else None
        )
        revenue_account = _configured_account(db, revenue_id, cc.SALES_REVENUE)
        discount_account = _configured_account(db, discount_id, cc.SALES_DISCOUNT) if discount_id else _discount_account(db)
        revenue[revenue_account.id] += Decimal(line.qty) * Decimal(line.unit_price)
        discounts[discount_account.id] += Decimal(line.discount)

    final = (
        Decimal(invoice.total_amount) + Decimal(invoice.total_additions)
        + Decimal(invoice.total_duties) + Decimal(invoice.tax_amount) + Decimal(invoice.rounding)
    )
    receivable = _configured_account(db, invoice.receivable_account_id, cc.ACCOUNTS_RECEIVABLE)
    customer = db.get(Contact, invoice.contact_id) if invoice.contact_id else None
    lines = [JournalLine(
        account_id=receivable.id, analytic_id=customer.analytic_id if customer else None,
        debit=final, credit=0, description="مطالبات فاکتور فروش",
    )]
    lines.extend(JournalLine(
        account_id=account_id, debit=0, credit=amount, description="درآمد ناخالص فروش",
    ) for account_id, amount in revenue.items() if amount)
    lines.extend(JournalLine(
        account_id=account_id, debit=amount, credit=0, description="تخفیف فروش",
    ) for account_id, amount in discounts.items() if amount)
    if Decimal(invoice.total_additions):
        addition = _configured_account(
            db, sale_type.addition_account_id if sale_type else None, cc.SALES_ADDITIONS
        ) if sale_type and sale_type.addition_account_id else _addition_account(db)
        lines.append(JournalLine(
            account_id=addition.id, debit=0, credit=invoice.total_additions, description="اضافات فروش",
        ))
    tax_and_duties = Decimal(invoice.tax_amount) + Decimal(invoice.total_duties)
    if tax_and_duties:
        lines.append(JournalLine(
            account_id=vat_payable_account(db).id, debit=0, credit=tax_and_duties,
            description="مالیات و عوارض فروش",
        ))
    if Decimal(invoice.rounding):
        rounding = Decimal(invoice.rounding)
        lines.append(JournalLine(
            account_id=sales_rounding_account(db).id,
            debit=-rounding if rounding < 0 else 0,
            credit=rounding if rounding > 0 else 0,
            description="گِرد کردن مبلغ فاکتور",
        ))
    if invoice.cost_center_id:
        for line in lines:
            line.cost_center_id = invoice.cost_center_id

    entry = make_journal_entry(
        db, invoice.invoice_date, f"فاکتور فروش شماره {invoice.number}",
        "sales_invoice", user, lines,
    )
    invoice.journal_entry_id = entry.id
    invoice.receivable_account_id = receivable.id
    db.flush()
    return entry


def finalize_immediate_sale(
    db: Session, invoice: SalesInvoice, warehouse_id: UUID, user: User
) -> None:
    """هماهنگ‌کنندهٔ مسیرهای فروش فوری؛ اسناد همچنان مستقل و قابل‌ردیابی می‌مانند."""
    issue_sales_invoice_journal(db, invoice.id, user)
    physical_lines = [line for line in invoice.lines if not line.item.is_service]
    if not physical_lines:
        return
    # import دیرهنگام، چرخهٔ inventory -> sales_invoices -> warehouse_issues را می‌شکند.
    from app.services.warehouse_issues import create_warehouse_issue

    create_warehouse_issue(
        db,
        invoice.id,
        WarehouseIssueIn(
            issue_date=invoice.invoice_date,
            warehouse_id=warehouse_id,
            description=f"خروج خودکار فروش فوری شماره {invoice.number}",
            lines=[
                WarehouseIssueLineIn(sales_invoice_line_id=line.id, qty=line.qty)
                for line in physical_lines
            ],
        ),
        user,
    )


def cancel_unposted_sales_invoice(
    db: Session, invoice_id: UUID, *, reason: str, user: User
) -> SalesInvoice:
    """فاکتور تجاریِ سندنشده را با رد حسابرسی لغو می‌کند؛ چیزی برای معکوس‌کردن ندارد."""
    invoice = db.query(SalesInvoice).filter(SalesInvoice.id == invoice_id).with_for_update().one_or_none()
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "فاکتور فروش یافت نشد")
    if invoice.is_voided:
        raise HTTPException(status.HTTP_409_CONFLICT, "این فاکتور قبلاً باطل شده است")
    if invoice.journal_entry_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "فاکتور سند حسابداری دارد و باید با سند معکوس باطل شود")
    invoice.voided_at = datetime.now(timezone.utc)
    invoice.voided_by_id = user.id
    invoice.void_reason = reason.strip()
    db.flush()
    return invoice


def attach_sales_state(db: Session, invoices: list[SalesInvoice]) -> None:
    if not invoices:
        return
    ids = [invoice.id for invoice in invoices]
    issue_rows = (
        db.query(WarehouseIssue.sales_invoice_id, WarehouseIssueLine.sales_invoice_line_id,
                 func.sum(WarehouseIssueLine.qty))
        .join(WarehouseIssueLine, WarehouseIssueLine.issue_id == WarehouseIssue.id)
        .filter(WarehouseIssue.sales_invoice_id.in_(ids), WarehouseIssue.voided_at.is_(None))
        .group_by(WarehouseIssue.sales_invoice_id, WarehouseIssueLine.sales_invoice_line_id)
        .all()
    )
    issued = {(invoice_id, line_id): Decimal(qty) for invoice_id, line_id, qty in issue_rows}

    receipt_rows = (
        db.query(ReceiptRelatedDocument.document_id,
                 func.coalesce(func.sum(ReceiptRelatedDocument.allocated_amount * Receipt.exchange_rate), 0),
                 func.count(func.distinct(Receipt.id)))
        .join(Receipt, Receipt.id == ReceiptRelatedDocument.receipt_id)
        .filter(ReceiptRelatedDocument.document_type == "sales_invoice",
                ReceiptRelatedDocument.document_id.in_(ids), Receipt.voided_at.is_(None))
        .group_by(ReceiptRelatedDocument.document_id)
        .all()
    )
    receipts = {invoice_id: (Decimal(amount), count) for invoice_id, amount, count in receipt_rows}

    for invoice in invoices:
        physical_total = issued_total = Decimal(0)
        for line in invoice.lines:
            line.issued_qty = issued.get((invoice.id, line.id), Decimal(0))
            if line.item.is_service:
                line.remaining_issueable_qty = Decimal(0)
                continue
            line.remaining_issueable_qty = max(Decimal(line.qty) - line.issued_qty, Decimal(0))
            physical_total += Decimal(line.qty)
            issued_total += line.issued_qty
        invoice.issued_total_qty = issued_total
        invoice.fulfillment_status = (
            "not_applicable" if physical_total == 0 else
            "not_issued" if issued_total == 0 else
            "fully_issued" if issued_total >= physical_total else "partially_issued"
        )
        invoice.accounting_status = "posted" if invoice.journal_entry_id else "unposted"
        settled, count = receipts.get(invoice.id, (Decimal(0), 0))
        final = (Decimal(invoice.total_amount) + Decimal(invoice.total_additions)
                 + Decimal(invoice.total_duties) + Decimal(invoice.tax_amount) + Decimal(invoice.rounding))
        invoice.final_amount = final
        invoice.settled_amount = settled
        invoice.remaining_amount = max(final - settled, Decimal(0))
        invoice.related_receipt_count = count
        invoice.financial_status = (
            "unsettled" if settled == 0 else
            "fully_settled" if settled >= final else "partially_settled"
        )
