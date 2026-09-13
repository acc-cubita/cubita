"""خروجِ انبار — حرکتِ واقعیِ کالا به بیرون از یک انبار، مستقل از سندِ تجاری.

**یک موتور، سه نوع (§۲).** فروش، مصرف و سایر از همین یک مسیر می‌گذرند: قفلِ کالا،
سنجشِ موجودی، حرکتِ منفی در دفترِ انبار، و سندِ بها. تنها چیزی که با نوع عوض
می‌شود طرفِ بدهکارِ سند است. «انتقال بین انبار» موتورِ خودش را دارد
(`services/transfers.py`) و از این‌جا بازسازی نمی‌شود.

**خروج ≠ فاکتور (§۱۵–§۱۹).** خروج مقدار و بها را می‌داند، فاکتور قیمت و درآمد را.
پس سندِ خروج هرگز درآمد یا طلبِ مشتری نمی‌زند، و فاکتوری که از خروج ساخته شود
هرگز دوباره موجودی کم نمی‌کند.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, literal_column, select, union_all
from sqlalchemy.orm import Session, selectinload

from app.models.accounting import Account, JournalEntry, JournalLine
from app.models.counters import DOC_WAREHOUSE_ISSUE
from app.models.inventory import Contact, Item, StockLedger, UnitOfMeasure, Warehouse
from app.models.invoices import (
    ISSUE_TYPE_LABELS,
    SalesInvoice,
    SalesInvoiceLine,
    WarehouseIssue,
    WarehouseIssueLine,
)
from app.models.quotations import SalesQuotation
from app.models.returns import SalesReturn
from app.models.transfers import StockTransfer
from app.models.user import User
from app.pagination import PageParams, paginate
from app.schemas.invoices import DirectWarehouseIssueIn, SalesInvoiceIn, WarehouseIssueIn
from app.services import chart_codes as cc
from app.services import items as items_svc
from app.services import units
from app.services import warehouses
from app.services.common import get_account, make_journal_entry
from app.services.cost_centers import resolve_cost_center_id
from app.services.inventory import get_stock_qty, lock_items, post_sales_invoice
from app.services.numbering import next_document_number
from app.services.period_close import assert_period_open
from app.services.voiding import reverse_journal_entry

#: نقش‌هایی که هرگز طرفِ بدهکارِ «مصرف» یا «سایر» نمی‌شوند: خودِ موجودی، و حساب‌هایی
#: که موتورِ دیگری مانده‌شان را می‌سازد — طرف‌حساب، نقد و بانک، چک، مالیات، درآمد،
#: حساب‌های پایانِ سال. نشستنِ خروج روی آن‌ها سند را متوازن می‌گذارد ولی مانده‌ی آن
#: موتور را بی‌صدا خراب می‌کند؛ هیچ ترازی هم خبر نمی‌دهد.
_FORBIDDEN_DEBIT_ROLES = frozenset(
    {
        cc.INVENTORY,
        "goods_in_transit",
        cc.ACCOUNTS_RECEIVABLE,
        cc.ACCOUNTS_PAYABLE,
        cc.CASH,
        cc.BANK,
        cc.PETTY_CASH,
        cc.CHECKS_RECEIVABLE,
        cc.CHECKS_PAYABLE,
        cc.CHECKS_IN_COLLECTION,
        cc.POS_CLEARING,
        cc.VAT_PAYABLE,
        cc.VAT_RECEIVABLE,
        cc.SALES_REVENUE,
        cc.SALES_RETURN,
        cc.RETAINED_EARNINGS,
        cc.CLOSING_ACCOUNT,
        cc.OPENING_ACCOUNT,
    }
)

#: شرحِ دو طرفِ سند برای هر نوع. شرحِ «فروش» همانی است که پیش از این فصل بود.
_JOURNAL_TEXT = {
    "sale": ("بهای تمام‌شده فروش", "کسر موجودی بابت خروج فروش"),
    "consumption": ("مصرفِ کالا", "کسر موجودی بابت مصرف"),
    "other": ("خروجِ کالا (سایر)", "کسر موجودی بابت خروجِ سایر"),
}


@dataclass
class _Row:
    item: Item
    qty: Decimal  # به واحدِ اصلی
    account_id: UUID
    description: str = ""
    sales_invoice_line_id: UUID | None = None
    code: str = ""
    name: str = ""
    unit: str = ""


# ─────────────────────────── قاعده‌های مشترک ───────────────────────────


def issued_by_line(db: Session, invoice_id: UUID) -> dict[UUID, Decimal]:
    rows = (
        db.query(WarehouseIssueLine.sales_invoice_line_id, func.sum(WarehouseIssueLine.qty))
        .join(WarehouseIssue, WarehouseIssue.id == WarehouseIssueLine.issue_id)
        .filter(WarehouseIssue.sales_invoice_id == invoice_id, WarehouseIssue.voided_at.is_(None))
        .group_by(WarehouseIssueLine.sales_invoice_line_id).all()
    )
    return {line_id: Decimal(qty) for line_id, qty in rows if line_id is not None}


def issued_unit_cost_by_line(db: Session, invoice_id: UUID) -> dict[UUID, Decimal]:
    """بهای واحدی که خروج‌های **معتبرِ** هر ردیفِ فاکتور واقعاً سند زده‌اند.

    برگشتِ فروش باید COGS را با همین عدد برگرداند، نه با `sales_invoice_lines.unit_cost`
    که میانگینِ لحظه‌ی *صدورِ فاکتور* است. در سیاستِ دومرحله‌ای، خریدی بینِ فاکتور و
    خروج میانگین را عوض می‌کند؛ آن‌وقت برگشتِ کامل COGS را صفر نمی‌کرد.
    """
    rows = (
        db.query(
            WarehouseIssueLine.sales_invoice_line_id,
            func.sum(WarehouseIssueLine.qty),
            func.sum(WarehouseIssueLine.qty * WarehouseIssueLine.unit_cost),
        )
        .join(WarehouseIssue, WarehouseIssue.id == WarehouseIssueLine.issue_id)
        .filter(
            WarehouseIssue.sales_invoice_id == invoice_id,
            WarehouseIssue.voided_at.is_(None),
            WarehouseIssueLine.sales_invoice_line_id.isnot(None),
        )
        .group_by(WarehouseIssueLine.sales_invoice_line_id)
        .all()
    )
    return {line_id: Decimal(value) / Decimal(qty) for line_id, qty, value in rows if qty}


def _inventory_account_ids(db: Session) -> set[UUID]:
    ids = {get_account(db, cc.INVENTORY).id}
    ids |= {gl for (gl,) in db.query(Warehouse.gl_account_id).filter(Warehouse.gl_account_id.isnot(None)).all()}
    return ids


def _debit_account(db: Session, account_id: UUID, inventory_ids: set[UUID]) -> Account:
    """طرفِ بدهکارِ «مصرف» یا «سایر» — انتخابِ کاربر، ولی نه هر حسابی (§۲۵ §۲۶)."""
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "حسابِ انتخاب‌شده برای خروج یافت نشد")
    if account.is_group:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"«{account.name}» حسابِ گروه است و ردیفِ سند نمی‌پذیرد؛ یکی از حساب‌های زیرِ آن را انتخاب کنید.",
        )
    if not account.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"حسابِ «{account.name}» غیرفعال است")
    if account.id in inventory_ids or account.system_role in _FORBIDDEN_DEBIT_ROLES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"«{account.name}» نمی‌تواند طرفِ بدهکارِ خروجِ انبار باشد؛ خروج باید به هزینه یا "
            "حسابِ مصرفِ مشخصی برود، نه به موجودی، طرف‌حساب، نقد، مالیات یا درآمد.",
        )
    return account


def _secondary(db: Session, item: Item, qty: Decimal) -> tuple[Decimal | None, str]:
    """مقدارِ فرعیِ نمایشی از نسبتِ **ثابتِ** همان کالا (§۱۱)."""
    if item.secondary_unit_id is None or item.conversion_mode != "fixed":
        return None, ""
    factor = Decimal(item.conversion_factor or 0)
    if factor <= 0:
        return None, ""
    unit = db.get(UnitOfMeasure, item.secondary_unit_id)
    return (qty / factor).quantize(Decimal("0.001")), unit.name if unit else ""


def _post_issue(db: Session, issue: WarehouseIssue, rows: list[_Row], user: User) -> WarehouseIssue:
    """هسته‌ی مشترکِ هر خروج: قفل، سنجشِ موجودی، حرکتِ منفی، سندِ بها."""
    by_item: dict[UUID, Decimal] = defaultdict(Decimal)
    for row in rows:
        by_item[row.item.id] += row.qty

    #: قفل **پیش از** خواندنِ موجودی و بها (§۱۴). و بعد از قفل، کالاها دوباره
    #: خوانده می‌شوند: میانگینی که پیش از قفل در حافظه نشسته ممکن است مالِ پیش
    #: از تراکنشِ هم‌زمانی باشد که همین حالا commit کرد.
    lock_items(db, by_item.keys())
    fresh = {item.id: item for item in db.query(Item).filter(Item.id.in_(by_item.keys())).populate_existing().all()}
    for item_id, qty in by_item.items():
        available = get_stock_qty(db, item_id, issue.warehouse_id)
        if available < qty:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"موجودی «{fresh[item_id].name}» کافی نیست (موجود: {available}, درخواستی: {qty})",
            )

    issue.number = next_document_number(db, DOC_WAREHOUSE_ISSUE)
    db.add(issue)
    db.flush()

    debit_text, credit_text = _JOURNAL_TEXT[issue.issue_type]
    debits: dict[UUID, Decimal] = defaultdict(Decimal)
    total = Decimal(0)
    for seq, row in enumerate(rows, start=1):
        item = fresh[row.item.id]
        unit_cost = Decimal(item.average_cost or 0)
        secondary_qty, secondary_unit = _secondary(db, item, row.qty)
        line = WarehouseIssueLine(
            seq=seq,
            sales_invoice_line_id=row.sales_invoice_line_id,
            item_id=item.id,
            qty=row.qty,
            unit_cost=unit_cost,
            account_id=row.account_id,
            secondary_qty=secondary_qty,
            secondary_unit_snapshot=secondary_unit,
            item_code_snapshot=row.code or item.sku,
            item_name_snapshot=row.name or item.name,
            unit_snapshot=row.unit or item.unit,
            description=row.description,
        )
        issue.lines.append(line)
        db.add(StockLedger(
            item_id=item.id, warehouse_id=issue.warehouse_id, qty=-row.qty, unit_cost=unit_cost,
            entry_date=issue.issue_date, source_type="warehouse_issue", source_id=issue.id,
        ))
        amount = line.amount
        debits[row.account_id] += amount
        total += amount

    if total > 0:
        journal_lines = [
            JournalLine(
                account_id=account_id, debit=amount, credit=0,
                cost_center_id=issue.cost_center_id, description=debit_text,
            )
            for account_id, amount in debits.items()
            if amount > 0
        ]
        #: معینِ **همان انبار**، نه حسابِ تختِ موجودی (§۹ فصلِ انبار).
        journal_lines.append(JournalLine(
            account_id=warehouses.inventory_account_id(db, issue.warehouse_id), debit=0, credit=total,
            cost_center_id=issue.cost_center_id, description=credit_text,
        ))
        label = ISSUE_TYPE_LABELS[issue.issue_type]
        #: `make_journal_entry` گاردِ تفصیلی را هم می‌زند؛ سندِ خروج استثنا نیست.
        journal = make_journal_entry(
            db, issue.issue_date, f"خروج انبار {label} شماره {issue.number}", "warehouse_issue", user, journal_lines
        )
        issue.journal_entry_id = journal.id
    db.flush()
    return issue


# ─────────────────────────── خروج از فاکتور ───────────────────────────


def create_warehouse_issue(
    db: Session, invoice_id: UUID, data: WarehouseIssueIn, user: User
) -> WarehouseIssue:
    """خروج از روی ردیف‌های یک فاکتور — جزئی، چندباره، تا سقفِ ماندهٔ هر ردیف."""
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
        items_svc.assert_warehouse_allowed(db, line.item, data.warehouse_id)

    by_id = {line.id: line for line in invoice_lines}
    cogs = get_account(db, cc.COGS).id
    rows = [
        _Row(
            item=by_id[row.sales_invoice_line_id].item,
            qty=Decimal(row.qty),
            account_id=cogs,
            description=row.description,
            sales_invoice_line_id=row.sales_invoice_line_id,
            code=by_id[row.sales_invoice_line_id].item_code_snapshot or "",
            name=by_id[row.sales_invoice_line_id].item_name_snapshot or "",
            unit=by_id[row.sales_invoice_line_id].unit_snapshot or "",
        )
        #: ترتیبِ ردیف‌ها همان ترتیبی است که کاربر فرستاده، نه ترتیبِ تصادفیِ UUID.
        for row in data.lines
    ]
    issue = WarehouseIssue(
        issue_date=data.issue_date, issue_type="sale", origin="invoice",
        sales_invoice_id=invoice.id, warehouse_id=data.warehouse_id,
        receiver_id=invoice.contact_id, cost_center_id=invoice.cost_center_id,
        description=data.description.strip(), created_by_id=user.id,
    )
    _post_issue(db, issue, rows, user)
    invoice.total_cost = Decimal(invoice.total_cost or 0) + issue.total_cost
    db.flush()
    db.refresh(issue)
    return issue


# ─────────────────────────── خروجِ مستقل ───────────────────────────


def create_direct_warehouse_issue(db: Session, data: DirectWarehouseIssueIn, user: User) -> WarehouseIssue:
    """خروجی که فاکتور ندارد — فروشی که تحویلش جلوتر از فاکتور است، مصرف، یا سایر."""
    assert_period_open(db, data.issue_date)
    warehouses.assert_usable(db, data.warehouse_id, action="خروج انبار")
    if data.receiver_id is not None and db.get(Contact, data.receiver_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "تحویل‌گیرنده یافت نشد")
    if data.source_quotation_id is not None and db.get(SalesQuotation, data.source_quotation_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "پیش‌فاکتورِ انتخاب‌شده یافت نشد")
    cost_center_id = resolve_cost_center_id(db, data.cost_center_id)

    items_by_id = {
        item.id: item
        for item in db.query(Item).filter(Item.id.in_([line.item_id for line in data.lines])).all()
    }
    sale = data.issue_type == "sale"
    cogs = get_account(db, cc.COGS).id if sale else None
    inventory_ids = set() if sale else _inventory_account_ids(db)
    checked: dict[UUID, UUID] = {}

    rows: list[_Row] = []
    for line in data.lines:
        item = items_by_id.get(line.item_id)
        if item is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "کالای ردیفِ خروج یافت نشد")
        if item.is_service:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"«{item.name}» خدمت است و خروجِ انبار ندارد")
        items_svc.assert_warehouse_allowed(db, item, data.warehouse_id)
        qty = units.to_primary(db, item, Decimal(line.qty), line.unit_id)
        if sale:
            account_id = cogs
        else:
            wanted = line.account_id or data.account_id
            if wanted not in checked:
                checked[wanted] = _debit_account(db, wanted, inventory_ids).id
            account_id = checked[wanted]
        rows.append(_Row(item=item, qty=qty, account_id=account_id, description=line.description.strip()))
    if sale:
        #: §۷ §۵۳ فصلِ کالا — ماده‌ی اولیه موجودی دارد ولی فروختنی نیست.
        items_svc.assert_sellable(db, [row.item for row in rows])

    issue = WarehouseIssue(
        issue_date=data.issue_date, issue_type=data.issue_type, origin="direct",
        warehouse_id=data.warehouse_id, receiver_id=data.receiver_id,
        source_quotation_id=data.source_quotation_id if sale else None,
        cost_center_id=cost_center_id, description=data.description.strip(), created_by_id=user.id,
    )
    _post_issue(db, issue, rows, user)
    db.refresh(issue)
    return issue


# ─────────────────────────── ابطال و جداسازی ───────────────────────────


def void_warehouse_issue(
    db: Session,
    issue_id: UUID,
    *,
    reason: str,
    user: User,
    void_date: date | None = None,
    guard_returns: bool = True,
) -> WarehouseIssue:
    issue = db.query(WarehouseIssue).filter(WarehouseIssue.id == issue_id).with_for_update().one_or_none()
    if issue is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "خروج انبار یافت نشد")
    if issue.is_voided:
        raise HTTPException(status.HTTP_409_CONFLICT, "این خروج قبلاً باطل شده است")
    #: کالای برگشتی از قبل به انبار برگشته. ابطالِ خروجِ همان فاکتور، آن را **دوباره**
    #: برمی‌گرداند. `guard_returns=False` فقط برای ابطالِ آبشاریِ خودِ فاکتور است که
    #: گاردِ برگشتِ خودش را دارد.
    if guard_returns and issue.sales_invoice_id and db.query(SalesReturn.id).filter(
        SalesReturn.sales_invoice_id == issue.sales_invoice_id, SalesReturn.voided_at.is_(None)
    ).first():
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "فاکتورِ این خروج برگشتِ فعال دارد؛ ابتدا برگشت را باطل کنید، وگرنه کالای برگشتی دو بار به انبار برمی‌گردد.",
        )
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
    invoice = db.get(SalesInvoice, issue.sales_invoice_id) if issue.sales_invoice_id else None
    if invoice:
        invoice.total_cost = max(Decimal(invoice.total_cost or 0) - issue.total_cost, Decimal(0))
    db.flush()
    return issue


def detach_direct_issues(db: Session, invoice: SalesInvoice) -> None:
    """ابطالِ فاکتوری که از خروجِ **مستقل** ساخته شده، خروج را باطل نمی‌کند.

    کالا واقعاً رفته است؛ باطل‌کردنِ سندِ تجاری آن را به قفسه برنمی‌گرداند. خروج
    فقط از فاکتور جدا می‌شود و دوباره «بی‌فاکتور» در فهرست می‌نشیند تا فاکتورِ
    درستش صادر شود. خروجی که «ثبت فاکتور» خودش ساخته، همان مسیرِ پیشین را دارد.
    """
    issues = (
        db.query(WarehouseIssue)
        .filter(
            WarehouseIssue.sales_invoice_id == invoice.id,
            WarehouseIssue.origin == "direct",
            WarehouseIssue.voided_at.is_(None),
        )
        .with_for_update()
        .all()
    )
    for issue in issues:
        for line in issue.lines:
            line.sales_invoice_line_id = None
        issue.sales_invoice_id = None
    if issues:
        db.flush()


# ─────────────────────────── خروج ← فاکتور فروش ───────────────────────────


def _lock_issue_for_invoice(db: Session, data: SalesInvoiceIn) -> tuple[WarehouseIssue, dict[int, UUID]]:
    issue = (
        db.query(WarehouseIssue)
        .options(selectinload(WarehouseIssue.lines))
        .filter(WarehouseIssue.id == data.source_warehouse_issue_id)
        .with_for_update()
        .one_or_none()
    )
    if issue is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "خروج انبار یافت نشد")
    if issue.is_voided:
        raise HTTPException(status.HTTP_409_CONFLICT, "از خروجِ باطل‌شده نمی‌توان فاکتور فروش ساخت")
    if issue.issue_type != "sale":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "فقط خروجِ «فروش» به فاکتور فروش می‌رسد؛ مصرف و سایر درآمد یا طلبِ مشتری نمی‌سازند.",
        )
    #: **گاردِ تکرار روی خودِ داده، نه فقط کلیدِ تکرار (§۳۹).** دو کلیک با دو کلید،
    #: یا دو کاربر هم‌زمان، باید به همان پاسخ برسند: یک فاکتور.
    if issue.sales_invoice_id is not None:
        existing = db.get(SalesInvoice, issue.sales_invoice_id)
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"برای این خروج قبلاً فاکتور فروش شماره {existing.number if existing else ''} صادر شده است.",
        )
    if data.warehouse_id is not None and data.warehouse_id != issue.warehouse_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "انبارِ فاکتور باید همان انبارِ خروج باشد")

    by_id = {line.id: line for line in issue.lines}
    linked: dict[int, UUID] = {}
    for index, line in enumerate(data.lines):
        if line.source_issue_line_id is None:
            item = db.get(Item, line.item_id)
            if item is not None and not item.is_service:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    f"«{item.name}» در این خروج نیست. کالای فاکتوری که از خروج ساخته می‌شود همان "
                    "کالای خروج است؛ برای کالای دیگر فاکتورِ جدا صادر کنید.",
                )
            continue
        source = by_id.get(line.source_issue_line_id)
        if source is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "ردیفی از فاکتور به ردیفِ خروجِ دیگری اشاره می‌کند")
        if source.id in linked.values():
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "هر ردیفِ خروج فقط یک بار در فاکتور می‌آید")
        if line.item_id != source.item_id or Decimal(line.qty) != Decimal(source.qty):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"مقدارِ «{source.item_name_snapshot}» در فاکتور باید همان مقدارِ خروج "
                f"({Decimal(source.qty).normalize()}) باشد؛ مقدار را خروج تعیین کرده است.",
            )
        linked[index] = source.id
    if set(by_id) - set(linked.values()):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "همه‌ی ردیف‌های خروج باید در فاکتور بیایند")
    return issue, linked


def post_sales_invoice_from_issue(
    db: Session, data: SalesInvoiceIn, user: User, *, enforce_credit: bool = True, issue_accounting: bool = True
) -> SalesInvoice:
    """فاکتورِ فروش از روی خروجِ ثبت‌شده (§۱۵ §۱۶).

    **هیچ حرکتِ انباری نمی‌سازد** — کالا از قبل رفته، و فاکتوری که دوباره کم کند
    همان «دو بار کسرِ موجودی» است که فصل صریح منعش می‌کند. سندِ حسابداریِ فاکتور
    (درآمد و طلب) طبقِ سیاستِ صدورِ همان کسب‌وکار زده می‌شود؛ COGS را خروج از قبل
    زده و فاکتور هرگز دوباره نمی‌زند.
    """
    issue, linked = _lock_issue_for_invoice(db, data)
    payload = data.model_copy(update={"warehouse_id": issue.warehouse_id, "source_warehouse_issue_id": None})
    invoice = post_sales_invoice(
        db, payload, user, enforce_credit=enforce_credit, move_inventory=False, issue_accounting=issue_accounting,
    )

    #: `post_sales_invoice` ردیف‌ها را به ترتیبِ ورودی می‌سازد ولی رابطه با UUID
    #: مرتب می‌شود؛ پس تطبیق روی (کالا، مقدار، فی) است. هر دو ردیفی که هر سه‌شان
    #: یکی باشد هم‌ارزند — همان کالا با همان بهای همان خروج.
    by_id = {line.id: line for line in issue.lines}
    pool = list(invoice.lines)
    total = Decimal(0)
    for index, source_id in linked.items():
        source = by_id[source_id]
        wanted = data.lines[index]
        match = next(
            line for line in pool
            if line.item_id == source.item_id
            and Decimal(line.qty) == Decimal(source.qty)
            and Decimal(line.unit_price) == Decimal(wanted.unit_price)
        )
        pool.remove(match)
        source.sales_invoice_line_id = match.id
        #: بهای این ردیفِ فاکتور همان بهایی است که خروج واقعاً سند زد.
        match.unit_cost = Decimal(source.unit_cost)
        total += source.amount
    issue.sales_invoice_id = invoice.id
    invoice.total_cost = Decimal(invoice.total_cost or 0) + total
    db.flush()
    db.refresh(invoice)
    return invoice


def invoice_context(db: Session, issue: WarehouseIssue) -> dict:
    if issue.is_voided:
        raise HTTPException(status.HTTP_409_CONFLICT, "از خروجِ باطل‌شده نمی‌توان فاکتور فروش ساخت")
    if issue.issue_type != "sale":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "فقط خروجِ «فروش» به فاکتور فروش می‌رسد")
    if issue.sales_invoice_id is not None:
        existing = db.get(SalesInvoice, issue.sales_invoice_id)
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"برای این خروج قبلاً فاکتور فروش شماره {existing.number if existing else ''} صادر شده است.",
        )
    receiver = db.get(Contact, issue.receiver_id) if issue.receiver_id else None
    return {
        "issue_id": issue.id,
        "issue_number": issue.number,
        "warehouse_id": issue.warehouse_id,
        "receiver_id": issue.receiver_id,
        "receiver_name": receiver.name if receiver else "",
        "lines": [
            {
                "issue_line_id": line.id,
                "item_id": line.item_id,
                "item_name": line.item_name_snapshot or (line.item.name if line.item else ""),
                "qty": line.qty,
                "unit": line.unit_snapshot,
                "suggested_unit_price": Decimal(line.item.sales_price or 0) if line.item else Decimal(0),
            }
            for line in issue.lines
        ],
    }


# ─────────────────────────── فهرست و چاپ ───────────────────────────


def attach_issue_accounts(db: Session, issues: list[WarehouseIssue]) -> None:
    """کد و عنوانِ معینِ هر ردیف — ستونِ «حساب معین» (§۹)."""
    ids = {line.account_id for issue in issues for line in issue.lines if line.account_id}
    accounts = {a.id: a for a in db.query(Account).filter(Account.id.in_(ids)).all()} if ids else {}
    for issue in issues:
        for line in issue.lines:
            account = accounts.get(line.account_id)
            line.account_code = account.code if account else ""
            line.account_name = account.name if account else ""


def _user_label(user: User | None) -> str:
    if user is None:
        return ""
    return getattr(user, "full_name", None) or getattr(user, "name", None) or user.email


def ledger_page(
    db: Session,
    params: PageParams,
    *,
    issue_type: str | None = None,
    warehouse_id: UUID | None = None,
    receiver_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    state: str | None = None,
) -> tuple[list[dict], str | None]:
    """یک صفحه از فهرستِ خروج‌ها — خروج‌ها و انتقال‌ها در یک صفحه‌بندیِ keyset.

    **انتقال از جدولِ خودش خوانده می‌شود، نه از نسخه‌ی دومی در این جدول (§۲۸).**
    «انبار» یعنی انبارِ **مبدأ**: انتقالی که *به* این انبار آمده، برای آن ورود است.
    """
    selects = []
    if issue_type in (None, "", "sale", "consumption", "other"):
        q = select(
            literal_column("'issue'").label("kind"),
            WarehouseIssue.id.label("id"),
            WarehouseIssue.issue_date.label("doc_date"),
            func.coalesce(WarehouseIssue.number, 0).label("number"),
        )
        if issue_type:
            q = q.where(WarehouseIssue.issue_type == issue_type)
        if warehouse_id:
            q = q.where(WarehouseIssue.warehouse_id == warehouse_id)
        if receiver_id:
            q = q.where(WarehouseIssue.receiver_id == receiver_id)
        if date_from:
            q = q.where(WarehouseIssue.issue_date >= date_from)
        if date_to:
            q = q.where(WarehouseIssue.issue_date <= date_to)
        if state == "active":
            q = q.where(WarehouseIssue.voided_at.is_(None))
        elif state == "voided":
            q = q.where(WarehouseIssue.voided_at.isnot(None))
        selects.append(q)
    if issue_type in (None, "", "transfer") and receiver_id is None:
        q = select(
            literal_column("'transfer'").label("kind"),
            StockTransfer.id.label("id"),
            StockTransfer.transfer_date.label("doc_date"),
            func.coalesce(StockTransfer.number, 0).label("number"),
        )
        if warehouse_id:
            q = q.where(StockTransfer.from_warehouse_id == warehouse_id)
        if date_from:
            q = q.where(StockTransfer.transfer_date >= date_from)
        if date_to:
            q = q.where(StockTransfer.transfer_date <= date_to)
        if state == "active":
            q = q.where(StockTransfer.voided_at.is_(None))
        elif state == "voided":
            q = q.where(StockTransfer.voided_at.isnot(None))
        selects.append(q)
    if not selects:
        return [], None

    sub = (union_all(*selects) if len(selects) > 1 else selects[0]).subquery("issue_ledger")
    keys, next_cursor = paginate(
        db.query(sub.c.kind, sub.c.id, sub.c.doc_date, sub.c.number),
        [sub.c.doc_date, sub.c.number, sub.c.id],
        params,
    )

    issue_ids = [k.id for k in keys if k.kind == "issue"]
    transfer_ids = [k.id for k in keys if k.kind == "transfer"]
    issues = {
        i.id: i
        for i in db.query(WarehouseIssue).options(selectinload(WarehouseIssue.lines))
        .filter(WarehouseIssue.id.in_(issue_ids)).all()
    } if issue_ids else {}
    transfers = {
        t.id: t
        for t in db.query(StockTransfer).options(selectinload(StockTransfer.lines))
        .filter(StockTransfer.id.in_(transfer_ids)).all()
    } if transfer_ids else {}

    warehouse_ids = {i.warehouse_id for i in issues.values()} | {
        w for t in transfers.values() for w in (t.from_warehouse_id, t.to_warehouse_id)
    }
    warehouse_by_id = {w.id: w for w in db.query(Warehouse).filter(Warehouse.id.in_(warehouse_ids)).all()} if warehouse_ids else {}
    contact_ids = {i.receiver_id for i in issues.values() if i.receiver_id}
    contacts = dict(db.query(Contact.id, Contact.name).filter(Contact.id.in_(contact_ids)).all()) if contact_ids else {}
    invoice_ids = {i.sales_invoice_id for i in issues.values() if i.sales_invoice_id}
    invoice_numbers = dict(
        db.query(SalesInvoice.id, SalesInvoice.number).filter(SalesInvoice.id.in_(invoice_ids)).all()
    ) if invoice_ids else {}
    quotation_ids = {i.source_quotation_id for i in issues.values() if i.source_quotation_id}
    quotation_numbers = dict(
        db.query(SalesQuotation.id, SalesQuotation.number).filter(SalesQuotation.id.in_(quotation_ids)).all()
    ) if quotation_ids else {}
    entry_ids = {d.journal_entry_id for d in [*issues.values(), *transfers.values()] if d.journal_entry_id}
    entry_numbers = dict(
        db.query(JournalEntry.id, JournalEntry.number).filter(JournalEntry.id.in_(entry_ids)).all()
    ) if entry_ids else {}
    user_ids = {d.created_by_id for d in [*issues.values(), *transfers.values()]}
    users = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()} if user_ids else {}
    transfer_cost = dict(
        db.query(StockLedger.source_id, func.sum(-StockLedger.qty * StockLedger.unit_cost))
        .filter(StockLedger.source_type == "transfer_out", StockLedger.source_id.in_(transfer_ids))
        .group_by(StockLedger.source_id).all()
    ) if transfer_ids else {}

    def wh(warehouse_id_):
        w = warehouse_by_id.get(warehouse_id_)
        return (w.code if w else ""), (w.name if w else "")

    out: list[dict] = []
    for key in keys:
        if key.kind == "issue":
            issue = issues[key.id]
            code, name = wh(issue.warehouse_id)
            out.append({
                "kind": "issue", "id": issue.id, "number": issue.number, "doc_date": issue.issue_date,
                "issue_type": issue.issue_type, "type_label": ISSUE_TYPE_LABELS.get(issue.issue_type, issue.issue_type),
                "origin": issue.origin,
                "warehouse_id": issue.warehouse_id, "warehouse_code": code, "warehouse_name": name,
                "receiver_id": issue.receiver_id, "receiver_name": contacts.get(issue.receiver_id, ""),
                "sales_invoice_id": issue.sales_invoice_id,
                "sales_invoice_number": invoice_numbers.get(issue.sales_invoice_id),
                "source_quotation_id": issue.source_quotation_id,
                "quotation_number": quotation_numbers.get(issue.source_quotation_id),
                "journal_entry_id": issue.journal_entry_id,
                "journal_entry_number": entry_numbers.get(issue.journal_entry_id),
                "created_by_name": _user_label(users.get(issue.created_by_id)),
                "line_count": len(issue.lines), "total_qty": issue.total_qty, "total_cost": issue.total_cost,
                "description": issue.description or "", "voided_at": issue.voided_at,
                "void_reason": issue.void_reason or "",
            })
        else:
            transfer = transfers[key.id]
            code, name = wh(transfer.from_warehouse_id)
            dest_code, dest_name = wh(transfer.to_warehouse_id)
            out.append({
                "kind": "transfer", "id": transfer.id, "number": transfer.number, "doc_date": transfer.transfer_date,
                "issue_type": "transfer", "type_label": ISSUE_TYPE_LABELS["transfer"],
                "warehouse_id": transfer.from_warehouse_id, "warehouse_code": code, "warehouse_name": name,
                "destination_warehouse_id": transfer.to_warehouse_id,
                "destination_warehouse_code": dest_code, "destination_warehouse_name": dest_name,
                "journal_entry_id": transfer.journal_entry_id,
                "journal_entry_number": entry_numbers.get(transfer.journal_entry_id),
                "created_by_name": _user_label(users.get(transfer.created_by_id)),
                "line_count": len(transfer.lines),
                "total_qty": sum((Decimal(line.qty) for line in transfer.lines), Decimal(0)),
                "total_cost": Decimal(transfer_cost.get(transfer.id) or 0).quantize(Decimal(1)),
                "description": transfer.description or "", "voided_at": transfer.voided_at,
                "void_reason": transfer.void_reason or "",
            })
    return out, next_cursor


def issue_print_projection(db: Session, issue: WarehouseIssue) -> dict:
    """ورودیِ «مجوز خروج انبار» (§۳۳ §۳۴) — از همان سند، و بدونِ هیچ مبلغی.

    مجوزِ خروج برگه‌ی فیزیکیِ بیرون‌رفتنِ کالاست، نه فاکتور؛ قیمت رویش نمی‌آید.
    """
    warehouse = db.get(Warehouse, issue.warehouse_id)
    receiver = db.get(Contact, issue.receiver_id) if issue.receiver_id else None
    label = ISSUE_TYPE_LABELS.get(issue.issue_type, issue.issue_type)
    references: list[tuple[str, str]] = []
    if issue.sales_invoice_id:
        invoice = db.get(SalesInvoice, issue.sales_invoice_id)
        if invoice is not None:
            references.append(("فاکتور فروش", str(invoice.number)))
    if issue.source_quotation_id:
        quotation = db.get(SalesQuotation, issue.source_quotation_id)
        if quotation is not None and quotation.number is not None:
            references.append(("پیش‌فاکتور", str(quotation.number)))
    return {
        "title": f"مجوز خروج انبار ({label})",
        "number": issue.number,
        "doc_date": issue.issue_date,
        "type_label": label,
        "warehouse_code": warehouse.code if warehouse else "",
        "warehouse_name": warehouse.name if warehouse else "",
        "party_label": "تحویل‌گیرنده",
        "party_name": receiver.name if receiver else "بدونِ تحویل‌گیرنده",
        "party_detail": " — ".join(
            filter(None, [receiver.national_id, receiver.economic_code, receiver.phone])
        ) if receiver else "",
        "lines": [
            {
                "seq": line.seq,
                "code": line.item_code_snapshot or (line.item.sku if line.item else ""),
                "name": line.item_name_snapshot or (line.item.name if line.item else ""),
                "qty": line.qty,
                "unit": line.unit_snapshot,
                "secondary_qty": line.secondary_qty,
                "secondary_unit": line.secondary_unit_snapshot,
                "description": line.description,
            }
            for line in issue.lines
        ],
        "total_qty": issue.total_qty,
        "references": references,
        "description": issue.description or "",
        "sign_labels": ("صادرکننده", "تحویل‌گیرنده"),
        "voided_at": issue.voided_at,
        "void_reason": issue.void_reason or "",
    }
