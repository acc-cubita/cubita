"""برگشتِ خروجِ انبار — حرکتِ مثبتی که یک خروجِ مشخص را برمی‌گرداند.

**یک موتور، سه نوع.** فروش، مصرف و سایر از همین مسیر می‌گذرند: قفلِ ردیف‌های مبدأ و
کالا، سنجشِ باقیمانده، حرکتِ مثبت در دفترِ انبار، سندِ بها. خروجِ اصلی هرگز ویرایش
نمی‌شود — کاردکس هر دو رویداد را با تاریخِ واقعی‌شان نشان می‌دهد:

    خروج          −۱۰
    برگشتِ خروج    +۵
    خالص           −۵

**بها و حساب از خروجِ مبدأ می‌آیند، نه از قالبِ ثابت.** بها همان بهایی است که خروج
سند زد (قاعده‌ی موجودِ کوبیتا برای هر برگشت: برگشتِ فروش با بهای خروج، برگشتِ خرید با
بهای تمام‌شده‌ی رسید). طرفِ بستانکار **همان حسابی است که خروج بدهکار کرده بود** —
بهای تمام‌شده برای فروش، هزینه‌ی انتخابیِ کاربر برای مصرف — با مرکزِ هزینه‌ی همان
خروج. برگشتِ مصرف هیچ درآمد یا طلبی نمی‌سازد.

**مالکیتِ برگشتِ فیزیکی.** فاکتور برگشتی از مهاجرتِ ۰۱۳۴ فقط سندِ تجاری است و کالا
را این سند برمی‌گرداند؛ دقیقاً یک حرکتِ مثبت برای هر برگشتِ فیزیکی (`SalesReturn.stock_mode`).
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.models.accounting import Account, JournalEntry, JournalLine
from app.models.counters import DOC_WAREHOUSE_ISSUE_RETURN
from app.models.inventory import Contact, Item, Warehouse
from app.models.invoices import ISSUE_TYPE_LABELS, SalesInvoice, WarehouseIssue, WarehouseIssueLine
from app.models.issue_returns import (
    ISSUE_RETURN_TYPE_LABELS,
    WarehouseIssueReturn,
    WarehouseIssueReturnLine,
)
from app.models.returns import SalesReturn, SalesReturnLine
from app.models.inventory import StockLedger
from app.models.user import User
from app.pagination import PageParams, paginate
from app.schemas.issue_returns import IssueReturnIn
from app.services import chart_codes as cc
from app.services import items as items_svc
from app.services import units
from app.services import valuation
from app.services import warehouses
from app.services.common import get_account, make_journal_entry
from app.services.inventory import get_total_stock_qty, lock_items
from app.services.numbering import next_document_number
from app.services.period_close import assert_period_open
from app.services.voiding import (
    _compensating_moves,
    _guard_stock_stays_valid,
    reverse_journal_entry,
)
from app.services.warehouse_issues import _secondary, _user_label, returned_by_issue_line

SOURCE_TYPE = "warehouse_issue_return"

#: شرحِ دو طرفِ سند برای هر نوع.
_JOURNAL_TEXT = {
    "sale": ("بازگشت کالا به موجودی بابت برگشت فروش", "کاهش بهای تمام‌شده بابت برگشت کالا"),
    "consumption": ("بازگشت کالا به موجودی بابت برگشت مصرف", "برگشت هزینه‌ی مصرف"),
    "other": ("بازگشت کالا به موجودی (سایر)", "برگشت خروجِ سایر"),
}


def _q(value) -> str:
    """مقدار برای پیامِ خطا — بی‌صفرهای بی‌معنای اعشار."""
    return f"{Decimal(value).normalize():f}"


@dataclass
class _Row:
    source: WarehouseIssueLine
    issue: WarehouseIssue
    qty: Decimal
    sales_return_line_id: UUID | None = None
    description: str = ""


# ─────────────────────────── مانده‌های مشتق ───────────────────────────


def physically_returned_by_sales_return_line(db: Session, line_ids) -> dict[UUID, Decimal]:
    """آنچه از هر ردیفِ فاکتور برگشتی **واقعاً** به انبار برگشته — جمعِ برگشت‌های معتبر.

    شمارنده‌ای ذخیره نمی‌شود؛ ابطالِ یک برگشت، مانده را خودبه‌خود آزاد می‌کند.
    """
    ids = [line_id for line_id in line_ids if line_id]
    if not ids:
        return {}
    rows = (
        db.query(WarehouseIssueReturnLine.sales_return_line_id, func.sum(WarehouseIssueReturnLine.qty))
        .join(WarehouseIssueReturn, WarehouseIssueReturn.id == WarehouseIssueReturnLine.return_id)
        .filter(
            WarehouseIssueReturnLine.sales_return_line_id.in_(ids),
            WarehouseIssueReturn.voided_at.is_(None),
        )
        .group_by(WarehouseIssueReturnLine.sales_return_line_id)
        .all()
    )
    return {line_id: Decimal(qty) for line_id, qty in rows}


def issued_net_by_invoice_line(db: Session, invoice_line_ids) -> dict[UUID, Decimal]:
    """آنچه از هر ردیفِ فاکتور **بیرون است**: خروج‌های معتبر منهای برگشت‌های پیش از فاکتور.

    برگشتِ «مستقیمِ» فروش فقط پیش از فاکتور ممکن است (خروجی که هنوز فاکتور ندارد)؛
    فاکتوری که بعد از آن صادر شود همان مقدارِ خالص را دارد. برگشت‌هایی که مبنایشان
    فاکتور برگشتی است این‌جا کم نمی‌شوند — آن‌ها را فاکتور برگشتی از قبل شمرده.
    """
    ids = [line_id for line_id in invoice_line_ids if line_id]
    if not ids:
        return {}
    issued = dict(
        db.query(WarehouseIssueLine.sales_invoice_line_id, func.sum(WarehouseIssueLine.qty))
        .join(WarehouseIssue, WarehouseIssue.id == WarehouseIssueLine.issue_id)
        .filter(WarehouseIssueLine.sales_invoice_line_id.in_(ids), WarehouseIssue.voided_at.is_(None))
        .group_by(WarehouseIssueLine.sales_invoice_line_id)
        .all()
    )
    direct = dict(
        db.query(WarehouseIssueLine.sales_invoice_line_id, func.sum(WarehouseIssueReturnLine.qty))
        .join(WarehouseIssueLine, WarehouseIssueLine.id == WarehouseIssueReturnLine.warehouse_issue_line_id)
        .join(WarehouseIssueReturn, WarehouseIssueReturn.id == WarehouseIssueReturnLine.return_id)
        .filter(
            WarehouseIssueLine.sales_invoice_line_id.in_(ids),
            WarehouseIssueReturn.voided_at.is_(None),
            WarehouseIssueReturnLine.sales_return_line_id.is_(None),
        )
        .group_by(WarehouseIssueLine.sales_invoice_line_id)
        .all()
    )
    return {
        line_id: Decimal(qty) - Decimal(direct.get(line_id) or 0)
        for line_id, qty in issued.items()
    }


def _lock_issue_lines(
    db: Session, line_ids
) -> tuple[dict[UUID, WarehouseIssueLine], dict[UUID, WarehouseIssue]]:
    """خروج‌ها و ردیف‌هایشان را تا پایانِ تراکنش قفل می‌کند.

    قفلِ سربرگ جلوی ابطالِ هم‌زمانِ همان خروج را می‌گیرد (ابطال هم سربرگ را قفل
    می‌کند)؛ قفلِ ردیف جلوی دو برگشتِ هم‌زمان که هر دو باقیمانده‌ی ۵ را ببینند.
    """
    ids = sorted(set(line_ids), key=str)
    if not ids:
        return {}, {}
    issue_ids = sorted(
        {issue_id for (issue_id,) in db.query(WarehouseIssueLine.issue_id).filter(WarehouseIssueLine.id.in_(ids)).all()},
        key=str,
    )
    issues = {
        issue.id: issue
        for issue in db.query(WarehouseIssue)
        .filter(WarehouseIssue.id.in_(issue_ids))
        .order_by(WarehouseIssue.id)
        .with_for_update()
        .all()
    }
    lines = {
        line.id: line
        for line in db.query(WarehouseIssueLine)
        .filter(WarehouseIssueLine.id.in_(ids))
        .order_by(WarehouseIssueLine.id)
        .with_for_update()
        .all()
    }
    return lines, issues


def _issue_lines_for_invoice_line(db: Session, invoice_line_id: UUID | None) -> list[WarehouseIssueLine]:
    """ردیف‌های خروجِ معتبرِ یک ردیفِ فاکتور — به ترتیبِ خروج: اول‌رفته، اول‌برگشته."""
    if invoice_line_id is None:
        return []
    return (
        db.query(WarehouseIssueLine)
        .join(WarehouseIssue, WarehouseIssue.id == WarehouseIssueLine.issue_id)
        .filter(WarehouseIssueLine.sales_invoice_line_id == invoice_line_id, WarehouseIssue.voided_at.is_(None))
        .order_by(WarehouseIssue.issue_date, WarehouseIssue.number, WarehouseIssueLine.seq, WarehouseIssueLine.id)
        .all()
    )


def _allocate_sales_return_line(
    db: Session,
    sr_line: SalesReturnLine,
    qty: Decimal,
    *,
    planned: dict[UUID, Decimal],
    name: str,
) -> list[tuple[WarehouseIssueLine, WarehouseIssue, Decimal]]:
    """مقدارِ برگشتیِ یک ردیفِ فاکتور برگشتی را روی ردیف‌های خروجِ همان فروش پخش می‌کند.

    هر ردیفِ برگشت به ردیفِ خروجی گره می‌خورد که برمی‌گرداند؛ پس سقفِ ردیفِ خروج
    (خارج‌شده − برگشت‌های معتبر) از هر مسیری که بیاید یکی است.
    """
    candidates = _issue_lines_for_invoice_line(db, sr_line.sales_invoice_line_id)
    lines, issues = _lock_issue_lines(db, [c.id for c in candidates])
    returned = returned_by_issue_line(db, list(lines))
    plan: list[tuple[WarehouseIssueLine, WarehouseIssue, Decimal]] = []
    left = qty
    for candidate in candidates:
        if left <= 0:
            break
        line = lines[candidate.id]
        room = Decimal(line.qty) - returned.get(line.id, Decimal(0)) - planned[line.id]
        if room <= 0:
            continue
        take = min(room, left)
        planned[line.id] += take
        plan.append((line, issues[line.issue_id], take))
        left -= take
    if left > 0:
        if not candidates:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"«{name}» خروجِ انبارِ معتبری ندارد؛ برگرداندنش موجودی‌ای اضافه می‌کند که هرگز کم نشده بود.",
            )
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"از «{name}» بیشتر از آنچه از انبار خارج شده به انبار برمی‌گردد "
            f"(باقیمانده‌ی قابلِ برگشت: {_q(qty - left)}).",
        )
    return plan


# ─────────────────────────── هسته ───────────────────────────


def _post(db: Session, ret: WarehouseIssueReturn, rows: list[_Row], user: User) -> WarehouseIssueReturn:
    """هسته‌ی مشترکِ هر برگشت: قفلِ کالا، حرکتِ مثبت، میانگینِ بها، سندِ منبع‌محور."""
    by_item: dict[UUID, Decimal] = defaultdict(Decimal)
    for row in rows:
        by_item[row.source.item_id] += row.qty

    lock_items(db, by_item.keys())
    fresh = {
        item.id: item
        for item in db.query(Item).filter(Item.id.in_(by_item.keys())).populate_existing().all()
    }
    for item in fresh.values():
        items_svc.assert_warehouse_allowed(db, item, ret.warehouse_id)
    #: میانگینِ موزون با همان فرمولی که `recompute_average_cost` بازپخش می‌کند.
    running = {
        item_id: [get_total_stock_qty(db, item_id), Decimal(fresh[item_id].average_cost or 0)]
        for item_id in by_item
    }

    ret.number = next_document_number(db, DOC_WAREHOUSE_ISSUE_RETURN)
    db.add(ret)
    db.flush()

    inventory_account_id = warehouses.inventory_account_id(db, ret.warehouse_id)
    debit_text, credit_text = _JOURNAL_TEXT[ret.return_type]
    cogs_id: UUID | None = None
    debits: dict[UUID | None, Decimal] = defaultdict(Decimal)
    moves: list[StockLedger] = []
    credits: dict[tuple[UUID, UUID | None], Decimal] = defaultdict(Decimal)

    for seq, row in enumerate(rows, start=1):
        source = row.source
        item = fresh[source.item_id]
        unit_cost = Decimal(source.unit_cost or 0)
        account_id = source.account_id
        if account_id is None:
            #: ردیفِ خروجی که حسابش ثبت نشده فقط می‌تواند خروجِ فروشِ پیش از ۰۱۳۳ باشد،
            #: و آن همیشه بهای تمام‌شده را بدهکار کرده بود.
            cogs_id = cogs_id or get_account(db, cc.COGS).id
            account_id = cogs_id
        cost_center_id = row.issue.cost_center_id
        secondary_qty, secondary_unit = _secondary(db, item, row.qty)
        line = WarehouseIssueReturnLine(
            seq=seq,
            warehouse_issue_line_id=source.id,
            sales_return_line_id=row.sales_return_line_id,
            item_id=item.id,
            qty=row.qty,
            unit_cost=unit_cost,
            account_id=account_id,
            cost_center_id=cost_center_id,
            secondary_qty=secondary_qty,
            secondary_unit_snapshot=secondary_unit,
            item_code_snapshot=source.item_code_snapshot or item.sku,
            item_name_snapshot=source.item_name_snapshot or item.name,
            unit_snapshot=source.unit_snapshot or item.unit,
            description=row.description,
        )
        ret.lines.append(line)
        move = StockLedger(
            item_id=item.id, warehouse_id=ret.warehouse_id, qty=row.qty, unit_cost=unit_cost,
            entry_date=ret.return_date, source_type=SOURCE_TYPE, source_id=ret.id,
        )
        db.add(move)
        moves.append(move)

        qty_before, average = running[item.id]
        qty_after = qty_before + row.qty
        if qty_after > 0:
            average = ((qty_before * average) + (row.qty * unit_cost)) / qty_after
        running[item.id] = [qty_after, average]

        amount = line.amount
        debits[cost_center_id] += amount
        credits[(account_id, cost_center_id)] += amount

    for item_id, (_, average) in running.items():
        fresh[item_id].average_cost = average
    valuation.settle_posting(db, moves)

    total = sum(debits.values(), Decimal(0))
    if total > 0:
        journal_lines = [
            JournalLine(
                #: معینِ **انباری که کالا به آن برمی‌گردد** — نه انبارِ سربرگِ فاکتور.
                account_id=inventory_account_id, debit=amount, credit=0,
                cost_center_id=cost_center_id, description=debit_text,
            )
            for cost_center_id, amount in debits.items()
            if amount > 0
        ] + [
            JournalLine(
                account_id=account_id, debit=0, credit=amount,
                cost_center_id=cost_center_id, description=credit_text,
            )
            for (account_id, cost_center_id), amount in credits.items()
            if amount > 0
        ]
        label = ISSUE_RETURN_TYPE_LABELS[ret.return_type]
        entry = make_journal_entry(
            db, ret.return_date, f"برگشت خروج انبار {label} شماره {ret.number}", SOURCE_TYPE, user, journal_lines
        )
        ret.journal_entry_id = entry.id
    db.flush()
    return ret


# ─────────────────────────── ثبت ───────────────────────────


def _resolve_rows(db: Session, data: IssueReturnIn) -> list[_Row]:
    sr_line_ids = [line.sales_return_line_id for line in data.lines if line.sales_return_line_id]
    issue_line_ids = [line.warehouse_issue_line_id for line in data.lines if line.warehouse_issue_line_id]

    sr_lines = {
        line.id: line
        for line in db.query(SalesReturnLine)
        .filter(SalesReturnLine.id.in_(sr_line_ids))
        .order_by(SalesReturnLine.id)
        .with_for_update()
        .all()
    } if sr_line_ids else {}
    sales_returns = {
        doc.id: doc
        for doc in db.query(SalesReturn).filter(SalesReturn.id.in_({l.return_id for l in sr_lines.values()})).all()
    } if sr_lines else {}
    physical = physically_returned_by_sales_return_line(db, list(sr_lines))

    lines, issues = _lock_issue_lines(db, issue_line_ids)
    returned = returned_by_issue_line(db, list(lines))

    item_ids = {l.item_id for l in sr_lines.values()} | {l.item_id for l in lines.values()}
    items = {item.id: item for item in db.query(Item).filter(Item.id.in_(item_ids)).all()} if item_ids else {}

    planned_issue: dict[UUID, Decimal] = defaultdict(Decimal)
    planned_sr: dict[UUID, Decimal] = defaultdict(Decimal)
    label = ISSUE_RETURN_TYPE_LABELS[data.return_type]
    rows: list[_Row] = []
    for req in data.lines:
        description = req.description.strip()
        if req.sales_return_line_id is not None:
            sr_line = sr_lines.get(req.sales_return_line_id)
            if sr_line is None:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "ردیفِ فاکتور برگشتیِ انتخاب‌شده یافت نشد")
            doc = sales_returns[sr_line.return_id]
            if doc.is_voided:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, f"برگشت از فروش شماره {doc.number} باطل شده است")
            if doc.stock_mode != "issue_return":
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    f"برگشت از فروش شماره {doc.number} کالا را همان روز خودش به انبار برگردانده است؛ "
                    "برگشتِ انبارِ دوباره موجودی را دو بار زیاد می‌کند.",
                )
            item = items[sr_line.item_id]
            if item.is_service:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, f"«{item.name}» خدمت است و به انبار برنمی‌گردد")
            qty = units.to_primary(db, item, Decimal(req.qty), req.unit_id)
            remaining = Decimal(sr_line.qty) - physical.get(sr_line.id, Decimal(0)) - planned_sr[sr_line.id]
            if qty > remaining:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    f"مقدارِ برگشتِ «{item.name}» بیش از باقیمانده‌ی برگشت از فروش شماره {doc.number} است "
                    f"(باقیمانده: {_q(max(remaining, Decimal(0)))})",
                )
            planned_sr[sr_line.id] += qty
            for source, issue, take in _allocate_sales_return_line(
                db, sr_line, qty, planned=planned_issue, name=item.name
            ):
                rows.append(_Row(source, issue, take, sr_line.id, description))
            continue

        source = lines.get(req.warehouse_issue_line_id)
        if source is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "ردیفِ خروجِ انتخاب‌شده یافت نشد")
        issue = issues[source.issue_id]
        if issue.is_voided:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"خروج انبار شماره {issue.number} باطل شده است؛ کالایی از آن بیرون نیست که برگردد.",
            )
        if issue.issue_type != data.return_type:
            issue_label = ISSUE_TYPE_LABELS.get(issue.issue_type, issue.issue_type)
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"خروج انبار شماره {issue.number} از نوعِ «{issue_label}» است؛ "
                f"برگشتِ «{label}» فقط خروجِ «{label}» را برمی‌گرداند، چون حسابِ برگشت از همان خروج می‌آید.",
            )
        if issue.issue_type == "sale" and issue.sales_invoice_id is not None:
            invoice = db.get(SalesInvoice, issue.sales_invoice_id)
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"خروج انبار شماره {issue.number} فاکتور فروش شماره {invoice.number if invoice else ''} دارد. "
                "برگشتِ کالای فاکتورشده از «برگشت از فروش» می‌گذرد تا طلبِ مشتری هم برگردد؛ "
                "آن را ثبت کنید و مبنای این برگشت قرار دهید.",
            )
        item = items[source.item_id]
        qty = units.to_primary(db, item, Decimal(req.qty), req.unit_id)
        remaining = Decimal(source.qty) - returned.get(source.id, Decimal(0)) - planned_issue[source.id]
        if qty > remaining:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"مقدارِ برگشتِ «{item.name}» بیش از باقیمانده‌ی خروج انبار شماره {issue.number} است "
                f"(باقیمانده: {_q(max(remaining, Decimal(0)))})",
            )
        planned_issue[source.id] += qty
        rows.append(_Row(source, issue, qty, None, description))
    return rows


def create_issue_return(db: Session, data: IssueReturnIn, user: User) -> WarehouseIssueReturn:
    assert_period_open(db, data.return_date)
    warehouses.assert_usable(db, data.warehouse_id, action="برگشت خروج انبار")
    if data.deliverer_id is not None and db.get(Contact, data.deliverer_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "تحویل‌دهنده یافت نشد")
    rows = _resolve_rows(db, data)
    deliverer_id = data.deliverer_id
    if deliverer_id is None:
        sr_line_id = next((row.sales_return_line_id for row in rows if row.sales_return_line_id), None)
        if sr_line_id is not None:
            #: پیش‌فرض: همان مشتریِ فاکتوری که برگشت خورده.
            doc = db.get(SalesReturn, db.get(SalesReturnLine, sr_line_id).return_id)
            invoice = db.get(SalesInvoice, doc.sales_invoice_id)
            deliverer_id = invoice.contact_id if invoice else None
    ret = WarehouseIssueReturn(
        return_date=data.return_date,
        return_type=data.return_type,
        origin="direct",
        warehouse_id=data.warehouse_id,
        deliverer_id=deliverer_id,
        description=data.description.strip(),
        created_by_id=user.id,
    )
    _post(db, ret, rows, user)
    db.refresh(ret)
    return ret


def return_goods_for_sales_return(
    db: Session, sales_return: SalesReturn, invoice: SalesInvoice, user: User
) -> list[WarehouseIssueReturn]:
    """سیاستِ خودکار: کالا همان لحظه به **همان انباری که از آن رفته** برمی‌گردد.

    همان‌طور که «ثبت فاکتور» خروج را خودش می‌سازد. اگر کالا از دو انبار رفته باشد،
    برای هر انبار یک برگشت — سربرگِ برگشت یک انبار دارد.
    """
    items = {
        item.id: item
        for item in db.query(Item).filter(Item.id.in_({l.item_id for l in sales_return.lines})).all()
    }
    planned: dict[UUID, Decimal] = defaultdict(Decimal)
    by_warehouse: dict[UUID, list[_Row]] = {}
    for sr_line in sales_return.lines:
        item = items[sr_line.item_id]
        if item.is_service:
            continue
        for source, issue, take in _allocate_sales_return_line(
            db, sr_line, Decimal(sr_line.qty), planned=planned, name=item.name
        ):
            by_warehouse.setdefault(issue.warehouse_id, []).append(_Row(source, issue, take, sr_line.id))

    created: list[WarehouseIssueReturn] = []
    for warehouse_id, rows in by_warehouse.items():
        ret = WarehouseIssueReturn(
            return_date=sales_return.return_date,
            return_type="sale",
            origin="sales_return",
            warehouse_id=warehouse_id,
            deliverer_id=invoice.contact_id,
            sales_return_id=sales_return.id,
            description=f"برگشتِ کالا بابت برگشت از فروش شماره {sales_return.number}",
            created_by_id=user.id,
        )
        created.append(_post(db, ret, rows, user))
    return created


# ─────────────────────────── ابطال ───────────────────────────


def void_issue_return(
    db: Session,
    return_id: UUID,
    *,
    reason: str,
    user: User,
    void_date: date | None = None,
    cascade: bool = False,
) -> WarehouseIssueReturn:
    """حرکتِ جبرانی و سندِ معکوس. خروجِ اصلی و فاکتور برگشتی دست نمی‌خورند؛ فقط
    باقیمانده‌ی برگشت آزاد می‌شود — چون مشتق است، نه شمارنده."""
    ret = (
        db.query(WarehouseIssueReturn)
        .options(selectinload(WarehouseIssueReturn.lines))
        .filter(WarehouseIssueReturn.id == return_id)
        .with_for_update()
        .one_or_none()
    )
    if ret is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "برگشت خروج انبار یافت نشد")
    if ret.is_voided:
        raise HTTPException(status.HTTP_409_CONFLICT, "این برگشت قبلاً باطل شده است")
    if ret.origin == "sales_return" and not cascade:
        doc = db.get(SalesReturn, ret.sales_return_id) if ret.sales_return_id else None
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"این برگشت را «برگشت از فروش» شماره {doc.number if doc else ''} خودش ساخته است؛ "
            "همان سند را باطل کنید تا طلبِ مشتری و موجودی با هم برگردند.",
        )

    #: برگشتِ مستقیمِ فروش پیش از فاکتور ثبت شده و فاکتورِ بعدی **مقدارِ خالص** را
    #: گرفته. ابطالش کالایی را بیرون می‌فرستد که هیچ فاکتوری آن را نمی‌شناسد.
    direct_sources = [line.warehouse_issue_line_id for line in ret.lines if line.sales_return_line_id is None]
    if direct_sources and ret.return_type == "sale":
        invoiced = (
            db.query(WarehouseIssue)
            .join(WarehouseIssueLine, WarehouseIssueLine.issue_id == WarehouseIssue.id)
            .filter(WarehouseIssueLine.id.in_(direct_sources), WarehouseIssue.sales_invoice_id.isnot(None))
            .first()
        )
        if invoiced is not None:
            invoice = db.get(SalesInvoice, invoiced.sales_invoice_id)
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"پس از این برگشت، برای خروج انبار شماره {invoiced.number} فاکتور فروش شماره "
                f"{invoice.number if invoice else ''} صادر شده و فاکتور مقدارِ خالص را دارد. ابطالِ برگشت "
                "کالایی را بیرون می‌فرستد که فاکتور ندارد؛ اول آن فاکتور را باطل کنید.",
            )

    effective = void_date or ret.return_date
    assert_period_open(db, effective)
    moves = _compensating_moves(db, SOURCE_TYPE, ret.id, effective)
    item_ids = sorted({move.item_id for move in moves}, key=str)
    lock_items(db, item_ids)
    #: کالای برگشتی ممکن است دوباره فروخته یا مصرف شده باشد؛ ابطال موجودی را منفی نکند.
    _guard_stock_stays_valid(db, moves)
    #: همان گاردِ خطِ زمانِ هر ابطالِ ورود.
    valuation.guard_void(db, (SOURCE_TYPE,), ret.id)

    entry = db.get(JournalEntry, ret.journal_entry_id) if ret.journal_entry_id else None
    if entry is not None:
        reverse_journal_entry(
            db, entry, void_date=effective, user=user,
            description=f"ابطال برگشت خروج انبار شماره {ret.number}"
            + (f" — {reason.strip()}" if reason.strip() else ""),
        )
    for move in moves:
        db.add(move)
    ret.voided_at = datetime.now(timezone.utc)
    ret.voided_by_id = user.id
    ret.void_reason = reason.strip()
    db.flush()
    #: پس از علامتِ ابطال — بازپخش حرکتِ اسنادِ باطل را کنار می‌گذارد.
    valuation.settle_void(db, item_ids)
    return ret


def release_for_sales_return(
    db: Session, sales_return: SalesReturn, *, reason: str, user: User, void_date: date | None = None
) -> None:
    """ابطالِ فاکتور برگشتی: برگشتی که خودش ساخته همراهش باطل می‌شود؛ برگشتی که کاربر
    ثبت کرده جلوی ابطال را می‌گیرد — کالا واقعاً به انبار برگشته و راهی برای وصل‌کردنِ
    دوباره‌اش به فاکتور برگشتیِ دیگری نیست."""
    line_ids = [line.id for line in sales_return.lines]
    if not line_ids:
        return
    linked = (
        db.query(WarehouseIssueReturn)
        .filter(
            WarehouseIssueReturn.id.in_(
                db.query(WarehouseIssueReturnLine.return_id).filter(
                    WarehouseIssueReturnLine.sales_return_line_id.in_(line_ids)
                )
            ),
            WarehouseIssueReturn.voided_at.is_(None),
        )
        .order_by(WarehouseIssueReturn.number)
        .all()
    )
    manual = [ret for ret in linked if ret.origin != "sales_return" or ret.sales_return_id != sales_return.id]
    if manual:
        numbers = "، ".join(str(ret.number) for ret in manual)
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"برای این برگشت، «برگشت خروج انبار» شماره {numbers} ثبت شده و کالا به انبار برگشته است. "
            "اول آن برگشت را باطل کنید، سپس برگشت از فروش را.",
        )
    for ret in linked:
        void_issue_return(
            db, ret.id, reason=reason, user=user,
            void_date=void_date or sales_return.return_date, cascade=True,
        )


# ─────────────────────────── وضعیت، مبنا، فهرست، چاپ ───────────────────────────


def attach_physical_state(db: Session, returns: list[SalesReturn]) -> None:
    """وضعیتِ برگشتِ فیزیکیِ هر فاکتور برگشتی — **مستقل از وضعیتِ تجاری و مالی**.

    یک برگشت می‌تواند از نظرِ تجاری قطعی باشد و از نظرِ انبار «بخشی برگشته».
    """
    if not returns:
        return
    item_ids = {line.item_id for doc in returns for line in doc.lines}
    services = {
        item_id for (item_id,) in db.query(Item.id).filter(Item.id.in_(item_ids), Item.is_service.is_(True)).all()
    } if item_ids else set()
    returned = physically_returned_by_sales_return_line(db, [line.id for doc in returns for line in doc.lines])
    for doc in returns:
        physical = [line for line in doc.lines if line.item_id not in services]
        total = sum((Decimal(line.qty) for line in physical), Decimal(0))
        doc.physical_qty = total
        if (doc.stock_mode or "inline") == "inline":
            doc.physical_status = "inline"
            doc.physical_returned_qty = total
            doc.physical_remaining_qty = Decimal(0)
            continue
        done = sum((min(returned.get(line.id, Decimal(0)), Decimal(line.qty)) for line in physical), Decimal(0))
        doc.physical_returned_qty = done
        doc.physical_remaining_qty = max(total - done, Decimal(0))
        doc.physical_status = (
            "none" if total == 0
            else "not_returned" if done == 0
            else "fully_returned" if done >= total
            else "partially_returned"
        )


def basis_documents(db: Session, return_type: str, *, limit: int = 200) -> list[dict]:
    """پنجره‌ی «مبنا»: سندهایی که هنوز چیزی برای برگشت دارند (تازه‌ترین‌ها).

    * فروش ← فاکتورهای برگشتیِ تجاری که کالایشان کامل برنگشته، و خروج‌های فروشی که
      هنوز فاکتور ندارند.
    * مصرف و سایر ← خروج‌های همان نوع.
    """
    out: list[dict] = []
    if return_type == "sale":
        docs = (
            db.query(SalesReturn)
            .options(selectinload(SalesReturn.lines))
            .filter(SalesReturn.stock_mode == "issue_return", SalesReturn.voided_at.is_(None))
            .order_by(SalesReturn.return_date.desc(), SalesReturn.number.desc())
            .limit(limit)
            .all()
        )
        attach_physical_state(db, docs)
        invoices = {
            inv.id: inv
            for inv in db.query(SalesInvoice).filter(SalesInvoice.id.in_({d.sales_invoice_id for d in docs})).all()
        } if docs else {}
        contact_ids = {inv.contact_id for inv in invoices.values() if inv.contact_id}
        contacts = dict(db.query(Contact.id, Contact.name).filter(Contact.id.in_(contact_ids)).all()) if contact_ids else {}
        for doc in docs:
            if doc.physical_remaining_qty <= 0:
                continue
            invoice = invoices.get(doc.sales_invoice_id)
            contact_id = invoice.contact_id if invoice else None
            out.append({
                "kind": "sales_return", "id": doc.id, "number": doc.number, "doc_date": doc.return_date,
                "party_id": contact_id, "party_name": contacts.get(contact_id, "مشتری نقدی"),
                "warehouse_id": None, "warehouse_name": "",
                "remaining_qty": doc.physical_remaining_qty,
            })

    query = (
        db.query(WarehouseIssue)
        .options(selectinload(WarehouseIssue.lines))
        .filter(WarehouseIssue.issue_type == return_type, WarehouseIssue.voided_at.is_(None))
    )
    if return_type == "sale":
        query = query.filter(WarehouseIssue.sales_invoice_id.is_(None))
    issues = query.order_by(WarehouseIssue.issue_date.desc(), WarehouseIssue.number.desc()).limit(limit).all()
    returned = returned_by_issue_line(db, [line.id for issue in issues for line in issue.lines])
    warehouse_names = dict(
        db.query(Warehouse.id, Warehouse.name).filter(Warehouse.id.in_({i.warehouse_id for i in issues})).all()
    ) if issues else {}
    receiver_ids = {i.receiver_id for i in issues if i.receiver_id}
    receivers = dict(db.query(Contact.id, Contact.name).filter(Contact.id.in_(receiver_ids)).all()) if receiver_ids else {}
    for issue in issues:
        remaining = sum(
            (max(Decimal(line.qty) - returned.get(line.id, Decimal(0)), Decimal(0)) for line in issue.lines),
            Decimal(0),
        )
        if remaining <= 0:
            continue
        out.append({
            "kind": "issue", "id": issue.id, "number": issue.number, "doc_date": issue.issue_date,
            "party_id": issue.receiver_id, "party_name": receivers.get(issue.receiver_id, ""),
            "warehouse_id": issue.warehouse_id, "warehouse_name": warehouse_names.get(issue.warehouse_id, ""),
            "remaining_qty": remaining,
        })
    out.sort(key=lambda row: (row["doc_date"], row["number"] or 0), reverse=True)
    return out


def basis_detail(db: Session, kind: str, doc_id: UUID) -> dict:
    """ردیف‌های یک مبنا با مقدار، برگشت‌خورده و باقیمانده‌ی مشتق."""
    if kind == "sales_return":
        doc = db.query(SalesReturn).options(selectinload(SalesReturn.lines)).filter(SalesReturn.id == doc_id).one_or_none()
        if doc is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "برگشت از فروش یافت نشد")
        if doc.is_voided:
            raise HTTPException(status.HTTP_409_CONFLICT, "این برگشت از فروش باطل شده است")
        if doc.stock_mode != "issue_return":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "این برگشت از فروش کالا را همان روز خودش به انبار برگردانده است"
            )
        invoice = db.get(SalesInvoice, doc.sales_invoice_id)
        contact = db.get(Contact, invoice.contact_id) if invoice and invoice.contact_id else None
        items = {i.id: i for i in db.query(Item).filter(Item.id.in_({l.item_id for l in doc.lines})).all()}
        returned = physically_returned_by_sales_return_line(db, [l.id for l in doc.lines])
        lines = []
        warehouse_id = None
        for line in doc.lines:
            item = items.get(line.item_id)
            if item is None or item.is_service:
                continue
            sources = _issue_lines_for_invoice_line(db, line.sales_invoice_line_id)
            source_warehouse = sources[0].issue.warehouse_id if sources else None
            warehouse_id = warehouse_id or source_warehouse
            done = returned.get(line.id, Decimal(0))
            remaining = max(Decimal(line.qty) - done, Decimal(0))
            unit_cost = Decimal(line.unit_cost or 0)
            lines.append({
                "kind": kind, "basis_line_id": line.id, "item_id": line.item_id,
                "item_code": item.sku or "", "item_name": item.name, "unit": item.unit or "",
                "qty": line.qty, "returned": done, "remaining": remaining,
                "unit_cost": unit_cost, "amount": (remaining * unit_cost).quantize(Decimal(1)),
                "source_warehouse_id": source_warehouse,
            })
        return {
            "kind": kind, "id": doc.id, "number": doc.number, "doc_date": doc.return_date,
            "party_id": contact.id if contact else None, "party_name": contact.name if contact else "مشتری نقدی",
            "warehouse_id": warehouse_id, "lines": lines,
        }
    if kind == "issue":
        issue = db.query(WarehouseIssue).options(selectinload(WarehouseIssue.lines)).filter(WarehouseIssue.id == doc_id).one_or_none()
        if issue is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "خروج انبار یافت نشد")
        if issue.is_voided:
            raise HTTPException(status.HTTP_409_CONFLICT, "این خروج باطل شده است")
        receiver = db.get(Contact, issue.receiver_id) if issue.receiver_id else None
        returned = returned_by_issue_line(db, [l.id for l in issue.lines])
        lines = []
        for line in issue.lines:
            done = returned.get(line.id, Decimal(0))
            remaining = max(Decimal(line.qty) - done, Decimal(0))
            unit_cost = Decimal(line.unit_cost or 0)
            lines.append({
                "kind": kind, "basis_line_id": line.id, "item_id": line.item_id,
                "item_code": line.item_code_snapshot, "item_name": line.item_name_snapshot,
                "unit": line.unit_snapshot, "qty": line.qty, "returned": done, "remaining": remaining,
                "unit_cost": unit_cost, "amount": (remaining * unit_cost).quantize(Decimal(1)),
                "source_warehouse_id": issue.warehouse_id,
            })
        return {
            "kind": kind, "id": issue.id, "number": issue.number, "doc_date": issue.issue_date,
            "party_id": receiver.id if receiver else None, "party_name": receiver.name if receiver else "",
            "warehouse_id": issue.warehouse_id, "lines": lines,
        }
    raise HTTPException(status.HTTP_400_BAD_REQUEST, "نوعِ مبنا نامعتبر است")


def _line_sources(db: Session, rets: list[WarehouseIssueReturn]) -> tuple[dict, dict]:
    """ردیف‌ها → (شناسه و شماره‌ی خروج)، (شناسه و شماره‌ی فاکتور برگشتی)."""
    issue_line_ids = {line.warehouse_issue_line_id for ret in rets for line in ret.lines}
    by_issue_line = {
        line_id: (issue_id, number)
        for line_id, issue_id, number in db.query(WarehouseIssueLine.id, WarehouseIssue.id, WarehouseIssue.number)
        .join(WarehouseIssue, WarehouseIssue.id == WarehouseIssueLine.issue_id)
        .filter(WarehouseIssueLine.id.in_(issue_line_ids))
        .all()
    } if issue_line_ids else {}
    sr_line_ids = {line.sales_return_line_id for ret in rets for line in ret.lines if line.sales_return_line_id}
    by_sr_line = {
        line_id: (return_id, number)
        for line_id, return_id, number in db.query(SalesReturnLine.id, SalesReturn.id, SalesReturn.number)
        .join(SalesReturn, SalesReturn.id == SalesReturnLine.return_id)
        .filter(SalesReturnLine.id.in_(sr_line_ids))
        .all()
    } if sr_line_ids else {}
    return by_issue_line, by_sr_line


def attach_line_details(db: Session, rets: list[WarehouseIssueReturn]) -> None:
    """حسابِ معین و سندهای مبدأِ هر ردیف — برای جزئیات و ناوبری."""
    account_ids = {line.account_id for ret in rets for line in ret.lines if line.account_id}
    accounts = {a.id: a for a in db.query(Account).filter(Account.id.in_(account_ids)).all()} if account_ids else {}
    by_issue_line, by_sr_line = _line_sources(db, rets)
    for ret in rets:
        for line in ret.lines:
            account = accounts.get(line.account_id)
            line.account_code = account.code if account else ""
            line.account_name = account.name if account else ""
            line.issue_id, line.issue_number = by_issue_line.get(line.warehouse_issue_line_id, (None, None))
            line.sales_return_id, line.sales_return_number = by_sr_line.get(line.sales_return_line_id, (None, None))


def ledger_page(
    db: Session,
    params: PageParams,
    *,
    return_type: str | None = None,
    warehouse_id: UUID | None = None,
    deliverer_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    state: str | None = None,
) -> tuple[list[dict], str | None]:
    """فهرستِ برگشت‌ها — یک فهرست برای هر سه نوع، با فیلترِ نوع."""
    query = db.query(WarehouseIssueReturn).options(selectinload(WarehouseIssueReturn.lines))
    if return_type:
        query = query.filter(WarehouseIssueReturn.return_type == return_type)
    if warehouse_id:
        query = query.filter(WarehouseIssueReturn.warehouse_id == warehouse_id)
    if deliverer_id:
        query = query.filter(WarehouseIssueReturn.deliverer_id == deliverer_id)
    if date_from:
        query = query.filter(WarehouseIssueReturn.return_date >= date_from)
    if date_to:
        query = query.filter(WarehouseIssueReturn.return_date <= date_to)
    if state == "active":
        query = query.filter(WarehouseIssueReturn.voided_at.is_(None))
    elif state == "voided":
        query = query.filter(WarehouseIssueReturn.voided_at.isnot(None))
    rets, next_cursor = paginate(query, [WarehouseIssueReturn.return_date, WarehouseIssueReturn.number], params)

    warehouse_by_id = {
        w.id: w for w in db.query(Warehouse).filter(Warehouse.id.in_({r.warehouse_id for r in rets})).all()
    } if rets else {}
    deliverer_ids = {r.deliverer_id for r in rets if r.deliverer_id}
    contacts = dict(db.query(Contact.id, Contact.name).filter(Contact.id.in_(deliverer_ids)).all()) if deliverer_ids else {}
    entry_ids = {r.journal_entry_id for r in rets if r.journal_entry_id}
    entries = {
        e_id: (number, entry_date)
        for e_id, number, entry_date in db.query(JournalEntry.id, JournalEntry.number, JournalEntry.entry_date)
        .filter(JournalEntry.id.in_(entry_ids)).all()
    } if entry_ids else {}
    users = {u.id: u for u in db.query(User).filter(User.id.in_({r.created_by_id for r in rets})).all()} if rets else {}
    by_issue_line, by_sr_line = _line_sources(db, rets)

    out: list[dict] = []
    for ret in rets:
        warehouse = warehouse_by_id.get(ret.warehouse_id)
        entry_number, entry_date = entries.get(ret.journal_entry_id, (None, None))
        out.append({
            "id": ret.id, "number": ret.number, "return_date": ret.return_date,
            "return_type": ret.return_type,
            "type_label": ISSUE_RETURN_TYPE_LABELS.get(ret.return_type, ret.return_type),
            "origin": ret.origin,
            "warehouse_id": ret.warehouse_id,
            "warehouse_code": warehouse.code if warehouse else "",
            "warehouse_name": warehouse.name if warehouse else "",
            "deliverer_id": ret.deliverer_id, "deliverer_name": contacts.get(ret.deliverer_id, ""),
            "sales_return_numbers": sorted({
                by_sr_line[l.sales_return_line_id][1] for l in ret.lines
                if l.sales_return_line_id in by_sr_line and by_sr_line[l.sales_return_line_id][1] is not None
            }),
            "issue_numbers": sorted({
                by_issue_line[l.warehouse_issue_line_id][1] for l in ret.lines
                if l.warehouse_issue_line_id in by_issue_line
            }),
            "journal_entry_id": ret.journal_entry_id,
            "journal_entry_number": entry_number, "journal_entry_date": entry_date,
            "created_by_name": _user_label(users.get(ret.created_by_id)),
            "line_count": len(ret.lines), "total_qty": ret.total_qty, "total_cost": ret.total_cost,
            "description": ret.description or "", "voided_at": ret.voided_at,
            "void_reason": ret.void_reason or "",
        })
    return out, next_cursor


def print_projection(db: Session, ret: WarehouseIssueReturn) -> dict:
    """ورودیِ برگه‌ی «برگشت خروج انبار» — **با فی و مبلغ**، برخلافِ مجوزِ خروج.

    این برگه فاکتور برگشتی نیست؛ سندِ ورودِ دوباره‌ی فیزیکیِ کالاست و مبلغش بهای
    موجودی است، نه قیمتی که به مشتری برمی‌گردد.
    """
    warehouse = db.get(Warehouse, ret.warehouse_id)
    deliverer = db.get(Contact, ret.deliverer_id) if ret.deliverer_id else None
    label = ISSUE_RETURN_TYPE_LABELS.get(ret.return_type, ret.return_type)
    by_issue_line, by_sr_line = _line_sources(db, [ret])
    references: list[tuple[str, str]] = []
    for number in sorted({by_sr_line[l.sales_return_line_id][1] for l in ret.lines if l.sales_return_line_id in by_sr_line}):
        references.append(("برگشت از فروش", str(number)))
    for number in sorted({by_issue_line[l.warehouse_issue_line_id][1] for l in ret.lines if l.warehouse_issue_line_id in by_issue_line}):
        references.append(("خروج انبار", str(number)))
    return {
        "title": f"برگشت خروج انبار ({label})",
        "number": ret.number,
        "doc_date": ret.return_date,
        "type_label": label,
        "warehouse_code": warehouse.code if warehouse else "",
        "warehouse_name": warehouse.name if warehouse else "",
        "party_label": "تحویل‌دهنده",
        "party_name": deliverer.name if deliverer else "بدونِ تحویل‌دهنده",
        "party_detail": " — ".join(
            filter(None, [deliverer.national_id, deliverer.economic_code, deliverer.phone])
        ) if deliverer else "",
        "lines": [
            {
                "seq": line.seq,
                "code": line.item_code_snapshot,
                "name": line.item_name_snapshot,
                "qty": line.qty,
                "unit": line.unit_snapshot,
                "secondary_qty": line.secondary_qty,
                "secondary_unit": line.secondary_unit_snapshot,
                "unit_cost": Decimal(line.unit_cost or 0).quantize(Decimal(1)),
                "amount": line.amount,
                "description": line.description,
            }
            for line in ret.lines
        ],
        "total_qty": ret.total_qty,
        "total_amount": ret.total_cost,
        "show_amounts": True,
        "references": references,
        "description": ret.description or "",
        "sign_labels": ("تحویل‌دهنده", "انباردار"),
        "voided_at": ret.voided_at,
        "void_reason": ret.void_reason or "",
    }
