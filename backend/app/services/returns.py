from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.models.counters import DOC_PURCHASE_RETURN, DOC_SALES_RETURN
from app.services.numbering import next_document_number
from app.models.accounting import JournalLine
from app.models.inventory import Contact, Item, StockLedger, Warehouse
from app.models.advanced_inventory import StockBatch
from app.models.invoices import (
    PurchaseInvoice,
    PurchaseInvoiceLine,
    SalesInvoice,
    SalesInvoiceLine,
    WarehouseIssue,
    WarehouseIssueLine,
    WarehouseReceipt,
    WarehouseReceiptLine,
)
from app.models.returns import (
    RETURN_TYPE_LABELS,
    PurchaseReturn,
    PurchaseReturnLine,
    SalesReturn,
    SalesReturnLine,
    SalesReturnReason,
)
from app.models.user import User
from app.schemas.returns import PurchaseReturnIn, SalesReturnIn
from app.services import chart_codes as cc
from app.services import items as items_svc
from app.services import warehouses
from app.services.common import get_account, get_or_create_account, make_journal_entry
from app.services.inventory import (
    compute_tax,
    get_stock_qty,
    get_total_stock_qty,
    lock_items,
    vat_payable_account,
    vat_receivable_account,
)
from app.services.period_close import assert_period_open
from app.services import valuation


@dataclass
class _SourceLine:
    """یک ردیفِ فاکتورِ فروش، به‌همراهِ آن‌چه از آن برگشت خورده و آن‌چه مانده."""

    line: SalesInvoiceLine
    sold: Decimal
    #: قیمتِ واحدِ **مؤثر** — پس از کسرِ تخفیفِ همین ردیف. مشتری همین را پرداخته.
    unit_price: Decimal
    unit_cost: Decimal
    #: نرخِ مالیاتِ قفل‌شده‌ی همین ردیف. سربرگ به کار نمی‌آید: فاکتوری که هم قلمِ
    #: مشمول دارد هم معاف، نرخِ سربرگش برای هیچ‌کدام درست نیست.
    tax_rate: Decimal
    returned: Decimal
    remaining: Decimal


def _drain_legacy(rows: list[_SourceLine], legacy_by_item: dict[UUID, Decimal]) -> None:
    """برگشت‌های پیش از مهاجرتِ ۰۱۲۱ را از استخرِ همان کالا کم می‌کند.

    آن ردیف‌ها `sales_invoice_line_id` ندارند (مهاجرت روی جدولِ RLS‌دار `UPDATE`
    نمی‌زند، پس backfill نشدند) و فقط می‌دانیم «از این کالا چقدر برگشت خورده».
    اگر نادیده گرفته می‌شدند، لحظه‌ی مهاجرت مانده‌ی قابلِ برگشت بی‌صدا بالا
    می‌پرید و کالایی که کامل برگشت خورده بود دوباره قابلِ برگشت می‌شد.

    ترتیب همان ترتیبی است که خودِ فاکتور ردیف‌هایش را نشان می‌دهد
    (`order_by(id)` — روی UUID دلخواه است ولی **پایدار**، و همان ترتیبی که
    `SalesInvoice.lines` و در نتیجه فرم و چاپ دارند). قطعی‌بودنش کافی است:
    مهم این است که **جمعِ کل** حفظ شود و هیچ مقداری دوبار شمرده نشود.
    """
    for row in rows:
        left = legacy_by_item.get(row.line.item_id, Decimal(0))
        if left <= 0:
            continue
        take = min(left, row.remaining)
        row.returned += take
        row.remaining -= take
        legacy_by_item[row.line.item_id] = left - take


def _returnable_lines(db: Session, invoice_id: UUID, *, lock: bool = False) -> list[_SourceLine]:
    """ردیف‌های فاکتور با ماندهٔ قابلِ برگشتِ **هر ردیف** (§۷ §۹).

    `lock=True` ردیف‌ها را تا پایانِ تراکنش قفل می‌کند. بدونش دو برگشتِ هم‌زمان
    هر دو ماندهٔ ۵ را می‌بینند و هر دو ۵ ثبت می‌کنند — مجموع ۱۰ از فروشِ ۵ (§۱۳).
    """
    query = db.query(SalesInvoiceLine).filter(SalesInvoiceLine.invoice_id == invoice_id)
    if lock:
        query = query.with_for_update()
    lines = query.order_by(SalesInvoiceLine.id).all()

    #: تخصیص‌های **فعال** — برگشتِ باطل‌شده مانده را آزاد می‌کند (§۷۶).
    allocated = dict(
        db.query(SalesReturnLine.sales_invoice_line_id, func.coalesce(func.sum(SalesReturnLine.qty), 0))
        .join(SalesReturn, SalesReturn.id == SalesReturnLine.return_id)
        .filter(
            SalesReturn.sales_invoice_id == invoice_id,
            SalesReturn.voided_at.is_(None),
            SalesReturnLine.sales_invoice_line_id.isnot(None),
        )
        .group_by(SalesReturnLine.sales_invoice_line_id)
        .all()
    )
    legacy = {
        item_id: Decimal(qty)
        for item_id, qty in db.query(
            SalesReturnLine.item_id, func.coalesce(func.sum(SalesReturnLine.qty), 0)
        )
        .join(SalesReturn, SalesReturn.id == SalesReturnLine.return_id)
        .filter(
            SalesReturn.sales_invoice_id == invoice_id,
            SalesReturn.voided_at.is_(None),
            SalesReturnLine.sales_invoice_line_id.is_(None),
        )
        .group_by(SalesReturnLine.item_id)
        .all()
    }

    from app.services.warehouse_issues import issued_unit_cost_by_line

    #: **بهای برگشت = بهایی که خروج واقعاً سند زد**، نه میانگینِ لحظه‌ی صدورِ فاکتور.
    #: در سیاستِ دومرحله‌ای، خریدی بینِ فاکتور و خروج میانگین را عوض می‌کند و
    #: برگشتِ کامل دیگر COGS را صفر نمی‌کرد. ردیفی که خروج ندارد همان عددِ قبلی را دارد.
    issued_cost = issued_unit_cost_by_line(db, invoice_id)
    rows: list[_SourceLine] = []
    for line in lines:
        sold = Decimal(line.qty)
        # مبلغ **پس از کسر تخفیف** تا قیمتِ واحدِ مؤثر همان چیزی باشد که مشتری
        # واقعاً پرداخت کرده؛ وگرنه برگشت، بیش از دریافتی به او برمی‌گرداند و
        # تخفیف عملاً دو بار داده می‌شود.
        net = (sold * Decimal(line.unit_price)) - Decimal(line.discount or 0)
        returned = Decimal(allocated.get(line.id, 0))
        rows.append(
            _SourceLine(
                line=line,
                sold=sold,
                unit_price=net / sold if sold else Decimal(0),
                unit_cost=issued_cost.get(line.id, Decimal(line.unit_cost or 0)),
                tax_rate=Decimal(line.tax_rate_snapshot or 0),
                returned=returned,
                remaining=max(sold - returned, Decimal(0)),
            )
        )
    _drain_legacy(rows, legacy)
    return rows


def get_returnable_summary(db: Session, invoice_id: UUID) -> list[dict]:
    """برای هر **ردیفِ** فاکتور فروش: فروخته‌شده، قبلاً برگشت‌خورده، و باقی‌ماندهٔ قابل‌برگشت.

    تا فرمِ برگشت «باقی‌مانده» را نشان دهد نه «تعداد فروخته‌شده» — و تا کاربر
    ببیند از **کدام ردیف** با **کدام قیمت** برمی‌گرداند. فاکتوری که یک کالا را
    در دو ردیف با دو قیمت فروخته، اینجا دو سطر دارد نه یک میانگین.
    """
    invoice = db.get(SalesInvoice, invoice_id)
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "فاکتور فروش یافت نشد")
    rows = _returnable_lines(db, invoice_id)
    items = {i.id: i for i in db.query(Item).filter(Item.id.in_([r.line.item_id for r in rows])).all()}
    return [
        {
            "sales_invoice_line_id": row.line.id,
            "invoice_number": invoice.number,
            "item_id": row.line.item_id,
            "item_name": items[row.line.item_id].name if row.line.item_id in items else "",
            "unit": items[row.line.item_id].unit if row.line.item_id in items else "",
            "sold": row.sold,
            "already_returned": row.returned,
            "remaining": row.remaining,
            "unit_price": row.unit_price,
        }
        for row in rows
    ]


def _allocate(
    rows: list[_SourceLine],
    requested,
    items_by_id: dict[UUID, Item],
    *,
    source_attr: str,
    doc_label: str,
) -> list[tuple[_SourceLine, Decimal, object]]:
    """هر ردیفِ درخواست را به ردیف(های) واقعیِ فاکتور می‌بندد (§۷ §۱۲).

    دو شکلِ ورودی پذیرفته می‌شود و **هر دو** به تخصیصِ سطحِ ردیف ختم می‌شوند:

    * شناسه‌ی ردیفِ فاکتور داده شده → همان ردیف، بی‌ابهام.
    * فقط `item_id` داده شده → روی ردیف‌های همان کالا پخش می‌شود، به همان
      ترتیبِ پایداری که فاکتور نشان می‌دهد. این مسیر برای فراخوان‌های موجود است
      (`marketplace` و اپِ موبایل هنوز کالا-محور می‌فرستند)؛ شکلِ درخواستشان عوض
      نمی‌شود ولی ردیفِ حاصل از این پس هویتِ مبدأ دارد.

    `remaining` همان‌جا کم می‌شود تا دو ردیفِ درخواست روی یک ردیفِ فاکتور
    نتوانند از ماندهٔ مشترک بیشتر بردارند.
    """
    by_line = {row.line.id: row for row in rows}
    plan: list[tuple[_SourceLine, Decimal, object]] = []

    for req in requested:
        item = items_by_id.get(req.item_id) if req.item_id else None
        source_id = getattr(req, source_attr, None)

        if source_id is not None:
            row = by_line.get(source_id)
            if row is None:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST, f"ردیفِ انتخاب‌شده متعلق به این {doc_label} نیست"
                )
            if Decimal(req.qty) > row.remaining:
                name = items_by_id.get(row.line.item_id)
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    f"مقدار برگشتی «{name.name if name else ''}» بیش از باقی‌ماندهٔ این ردیف است "
                    f"(باقی‌مانده: {row.remaining})",
                )
            row.remaining -= Decimal(req.qty)
            plan.append((row, Decimal(req.qty), req))
            continue

        candidates = [row for row in rows if row.line.item_id == req.item_id]
        if not candidates:
            label = item.name if item else req.item_id
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, f"کالا «{label}» در این {doc_label} نبوده است"
            )
        available = sum((row.remaining for row in candidates), Decimal(0))
        if Decimal(req.qty) > available:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"مقدار برگشتی «{item.name if item else ''}» بیش از باقی‌مانده‌ی قابل‌برگشت است "
                f"(باقی‌مانده: {available})",
            )
        left = Decimal(req.qty)
        for row in candidates:
            if left <= 0:
                break
            take = min(left, row.remaining)
            if take <= 0:
                continue
            row.remaining -= take
            left -= take
            plan.append((row, take, req))
    return plan


def _assert_reasons_selectable(db: Session, requested) -> None:
    """علتِ برگشتِ **غیرفعال** روی سندِ تازه ننشیند (§۸۵).

    غیرفعال‌کردن یعنی «دیگر این را انتخاب نکن»، نه «هرگز نبوده». پس سندهای
    تاریخی علتشان را نگه می‌دارند و فقط انتخابِ تازه بسته می‌شود.
    """
    ids = {r.return_reason_id for r in requested if getattr(r, "return_reason_id", None)}
    if not ids:
        return
    found = {
        reason.id: reason
        for reason in db.query(SalesReturnReason).filter(SalesReturnReason.id.in_(ids)).all()
    }
    for reason_id in ids:
        reason = found.get(reason_id)
        if reason is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "علتِ برگشتِ انتخاب‌شده پیدا نشد")
        if not reason.is_active:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"علتِ برگشتِ «{reason.title}» غیرفعال شده و برای سندِ تازه قابلِ انتخاب نیست",
            )


def sales_return_account(db: Session):
    """حسابِ «برگشت از فروش» — کاهنده‌ی درآمد، نه بدهکارکردنِ خودِ درآمد (§۴۵ §۹۴).

    تنبل ساخته می‌شود تا چارتِ کسب‌وکارهای موجود هم بدونِ مهاجرتِ داده تکمیل شود.
    """
    return get_or_create_account(
        db,
        cc.SALES_RETURN,
        code=cc.DEFAULT_CODE_BY_ROLE[cc.SALES_RETURN],
        name="برگشت از فروش",
        acc_type="income",
        parent_code="4",
    )



def _issued_by_warehouse(db: Session, invoice_line_id: UUID) -> list[tuple[UUID, Decimal]]:
    """انبارهایی که این ردیفِ فاکتور واقعاً از آن‌ها خارج شده، با مقدارِ هرکدام.

    به ترتیبِ خروج برمی‌گردد — کالایی که اول رفته اول هم برمی‌گردد. خروجِ
    باطل‌شده شمرده نمی‌شود، چون سندِ ابطالش موجودی را از قبل برگردانده.
    """
    rows = (
        db.query(WarehouseIssue.warehouse_id, WarehouseIssueLine.qty)
        .join(WarehouseIssue, WarehouseIssue.id == WarehouseIssueLine.issue_id)
        .filter(
            WarehouseIssueLine.sales_invoice_line_id == invoice_line_id,
            WarehouseIssue.voided_at.is_(None),
        )
        .order_by(WarehouseIssue.issue_date, WarehouseIssue.number)
        .all()
    )
    merged: dict[UUID, Decimal] = {}
    order: list[UUID] = []
    for warehouse_id, qty in rows:
        if warehouse_id not in merged:
            merged[warehouse_id] = Decimal(0)
            order.append(warehouse_id)
        merged[warehouse_id] += Decimal(qty)
    return [(warehouse_id, merged[warehouse_id]) for warehouse_id in order]


def _return_stock_moves(
    db: Session, invoice: SalesInvoice, invoice_line_id: UUID, item_id: UUID,
    qty: Decimal, unit_cost: Decimal, entry_date, item_name: str,
) -> list[StockLedger]:
    """کالای برگشتی به **همان انباری** برمی‌گردد که از آن خارج شده بود.

    تا امروز انبار از سربرگِ فاکتور خوانده می‌شد. مهاجرتِ ۰۱۲۵ آن ستون را
    `nullable` کرد و سیاستِ «دومرحله‌ای» فاکتورِ بی‌انبار را دست‌یافتنی کرد — پس
    برگشتِ چنین فاکتوری `NULL` را در `stock_ledger.warehouse_id` می‌نوشت و با
    **خطای ۵۰۰ مدیریت‌نشده** می‌شکست.

    ولی مسئله فقط `NULL` نبود. در حالتِ دومرحله‌ای ممکن است کالا **هنوز خارج
    نشده باشد**؛ برگرداندنش موجودی‌ای اضافه می‌کرد که هرگز کم نشده بود. پس
    برگشتِ تجاری مجاز است و ثبت می‌شود، ولی حرکتِ موجودی فقط به اندازه‌ای که
    واقعاً خارج شده انجام می‌شود.

    **مسیرِ فاکتورهای انبار‌دار عوض نمی‌شود.** وقتی سربرگ انبار دارد (هر فاکتوری
    که در حالتِ خودکار ثبت شده، یعنی همه‌ی فاکتورهای تا امروز) همان انبار
    استفاده می‌شود و رفتار مو‌به‌مو همان است.
    """
    if invoice.warehouse_id is not None:
        return [
            StockLedger(
                item_id=item_id, warehouse_id=invoice.warehouse_id, qty=qty,
                unit_cost=unit_cost, entry_date=entry_date, source_type="sales_return",
            )
        ]

    issued = _issued_by_warehouse(db, invoice_line_id)
    if not issued:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"«{item_name}» هنوز از انبار خارج نشده، پس برگشتش موجودی‌ای اضافه می‌کند که "
            "هرگز کم نشده بود. اگر فروش انجام نشده، خودِ فاکتور را باطل کنید؛ اگر کالا "
            "تحویل رفته، اول «صدور خروج انبار» را بزنید.",
        )

    #: کالا از چند انبار رفته باشد، به همان نسبت برمی‌گردد — به ترتیبِ خروج.
    moves: list[StockLedger] = []
    remaining = qty
    for warehouse_id, available in issued:
        if remaining <= 0:
            break
        take = min(remaining, available)
        moves.append(
            StockLedger(
                item_id=item_id, warehouse_id=warehouse_id, qty=take,
                unit_cost=unit_cost, entry_date=entry_date, source_type="sales_return",
            )
        )
        remaining -= take
    if remaining > 0:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"از «{item_name}» بیشتر از آنچه از انبار خارج شده برگشت داده‌اید. "
            "برای بقیه‌اش اول «صدور خروج انبار» را بزنید.",
        )
    return moves


def _invoice_moved_stock_itself(db: Session, invoice_id: UUID) -> bool:
    """فاکتورهای پیش از مهاجرتِ ۰۱۲۵ کالا را **مستقیم** از خودشان کم کرده‌اند و خروج ندارند.

    آن مهاجرت خروجِ گذشته را backfill نکرد؛ پس برگشتِ چنین فاکتوری راهی جز برگرداندنِ
    مستقیمِ موجودی ندارد — همان مسیری که تا امروز داشت.
    """
    return (
        db.query(StockLedger.id)
        .filter(StockLedger.source_type == "sales_invoice", StockLedger.source_id == invoice_id)
        .first()
        is not None
    )


def post_sales_return(
    db: Session, data: SalesReturnIn, user: User, *, physical: bool | None = None
) -> SalesReturn:
    """برگشت از فروش — **سندِ تجاری** (درآمد، مالیات، طلبِ مشتری).

    **برگشتِ فیزیکی مالِ «برگشت خروج انبار» است (مهاجرتِ ۰۱۳۴).** این سند دیگر خودش
    موجودی را زیاد نمی‌کند و «موجودی / بهای تمام‌شده» نمی‌زند:

    * `physical=None` → سیاستِ صدورِ فاکتورِ همین کسب‌وکار. «خودکار» کالا را همان لحظه
      با برگشتِ خروجی که خودش می‌سازد برمی‌گرداند؛ «دومرحله‌ای» فقط تجاری ثبت می‌کند و
      برگشتِ انبار بعداً — جزئی و چندباره — روی همین سند ثبت می‌شود.
    * فاکتوری که پیش از ۰۱۲۵ ثبت شده خروج ندارد و مسیرِ قدیمی (`inline`) را می‌رود.

    در هر دو حالت برای هر برگشتِ فیزیکی دقیقاً **یک** حرکتِ مثبت ساخته می‌شود.
    """
    assert_period_open(db, data.return_date)

    #: قفلِ سربرگ پیش از هر خواندنی. همراهِ قفلِ ردیف‌ها در `_returnable_lines`،
    #: دو برگشتِ هم‌زمان روی یک فاکتور پشتِ سرِ هم اجرا می‌شوند نه موازی (§۱۳).
    invoice = (
        db.query(SalesInvoice)
        .filter(SalesInvoice.id == data.sales_invoice_id)
        .with_for_update()
        .one_or_none()
    )
    if invoice is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "فاکتور فروش یافت نشد")
    # روی فاکتورِ باطل‌شده نباید برگشت خورد: ابطال، خودش کلِ فروش را معکوس کرده؛ یک
    # برگشتِ اضافه، فروش را «دوبار» برمی‌گرداند و صندوق/فروش را منفی می‌کند.
    if invoice.voided_at is not None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "این فاکتور فروش باطل شده است؛ روی فاکتورِ باطل‌شده نمی‌توان برگشت زد.",
        )

    rows = _returnable_lines(db, data.sales_invoice_id, lock=True)
    item_ids = {row.line.item_id for row in rows} | {l.item_id for l in data.lines if l.item_id}
    items_by_id = {i.id: i for i in db.query(Item).filter(Item.id.in_(item_ids)).all()}
    _assert_reasons_selectable(db, data.lines)
    plan = _allocate(
        rows, data.lines, items_by_id,
        source_attr="sales_invoice_line_id", doc_label="فاکتور فروش",
    )

    #: قفلِ کالاها پیش از خواندنِ موجودی و بازمحاسبه‌ی میانگین — همان دلیلی که
    #: `voiding._apply_void` دارد: read-modify-write روی `average_cost`.
    lock_items(db, {row.line.item_id for row, _, _ in plan})
    inline = _invoice_moved_stock_itself(db, invoice.id)
    #: مقدارِ کالاییِ درخواستیِ هر ردیفِ فاکتور — برای سقفِ «آنچه واقعاً بیرون است».
    requested_physical: dict[UUID, Decimal] = {}

    total_amount = Decimal(0)
    total_cost = Decimal(0)
    tax_amount = Decimal(0)
    tax_weight = Decimal(0)
    return_lines: list[SalesReturnLine] = []
    stock_moves: list[StockLedger] = []

    for row, qty, req in plan:
        item = items_by_id[row.line.item_id]
        line_net = qty * row.unit_price
        total_amount += line_net
        total_cost += qty * row.unit_cost
        #: مالیات با نرخِ **همان ردیفِ فاکتورِ اصلی** برمی‌گردد، نه نرخِ سرِ فاکتور.
        tax_amount += compute_tax(line_net, row.tax_rate)
        tax_weight += line_net * row.tax_rate
        return_lines.append(
            SalesReturnLine(
                sales_invoice_line_id=row.line.id,
                item_id=row.line.item_id,
                qty=qty,
                unit_price=row.unit_price,
                unit_cost=row.unit_cost,
                return_reason_id=getattr(req, "return_reason_id", None),
                description=req.description,
            )
        )

        if not item.is_service and inline:
            existing_qty = get_total_stock_qty(db, item.id)
            new_qty = existing_qty + qty
            if new_qty > 0:
                item.average_cost = ((existing_qty * item.average_cost) + (qty * row.unit_cost)) / new_qty
            stock_moves.extend(
                _return_stock_moves(
                    db, invoice, row.line.id, row.line.item_id,
                    qty, row.unit_cost, data.return_date, item.name,
                )
            )
        elif not item.is_service:
            requested_physical[row.line.id] = requested_physical.get(row.line.id, Decimal(0)) + qty

    #: **کالایی که بیرون نرفته، برگشتِ تجاری هم ندارد.** سقفِ جمعِ برگشت‌های هر ردیف
    #: همان مقداری است که خروج‌های معتبر واقعاً بیرون فرستاده‌اند. بدونِ این، خروجی که
    #: باطل شده و فاکتورش مانده، برگشتی می‌پذیرفت که موجودیِ نداشته می‌ساخت.
    if requested_physical:
        from app.services.issue_returns import issued_net_by_invoice_line

        out = issued_net_by_invoice_line(db, list(requested_physical))
        rows_by_line = {row.line.id: row for row, _, _ in plan}
        for line_id, qty in requested_physical.items():
            row = rows_by_line[line_id]
            name = items_by_id[row.line.item_id].name
            available = out.get(line_id, Decimal(0))
            if row.returned + qty <= available:
                continue
            if available <= 0:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    f"«{name}» هنوز از انبار خارج نشده، پس برگشتش موجودی‌ای اضافه می‌کند که "
                    "هرگز کم نشده بود. اگر فروش انجام نشده، خودِ فاکتور را باطل کنید؛ اگر کالا "
                    "تحویل رفته، اول «صدور خروج انبار» را بزنید.",
                )
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"از «{name}» بیشتر از آنچه از انبار خارج شده برگشت داده‌اید. "
                "برای بقیه‌اش اول «صدور خروج انبار» را بزنید.",
            )

    # مالیاتی که هنگام فروش بستانکار شده بود باید با برگشتِ کالا آزاد شود، وگرنه
    # ماندهٔ «مالیات پرداختنی» — همان عددی که مبنای اظهارنامه است — برای همیشه
    # بیشتر از واقعیت می‌ماند.
    #
    # نرخ از ردیف‌های خودِ فاکتور می‌آید نه از سربرگش: اگر فاکتور هم قلمِ مشمول
    # داشته و هم معاف، نرخِ سربرگ برای هیچ‌کدام درست نیست.
    tax_rate = (tax_weight / total_amount) if total_amount else Decimal(0)

    journal_lines = [
        JournalLine(
            #: **کاهنده‌ی درآمد، نه بدهکارکردنِ درآمد** (§۴۵ §۹۴): فروشِ ناخالص و
            #: برگشتی باید هر دو قابلِ گزارش بمانند، وگرنه «چقدر فروختیم و چقدر
            #: برگشت خورد؟» — مبنای نرخِ برگشت — دیگر پرسیدنی نیست.
            account_id=sales_return_account(db).id, debit=total_amount, credit=0, description="برگشت از فروش"
        ),
    ]
    if tax_amount > 0:
        journal_lines.append(
            JournalLine(
                account_id=vat_payable_account(db).id,
                debit=tax_amount,
                credit=0,
                description="برگشت مالیات بر ارزش افزوده فروش",
            )
        )
    journal_lines.append(
        JournalLine(
            account_id=(get_account(db, cc.ACCOUNTS_RECEIVABLE) if invoice.contact_id else get_account(db, cc.CASH)).id,
            debit=0,
            credit=total_amount + tax_amount,  # کلِ مبلغی که به مشتری برمی‌گردد
            description="برگشت از فروش",
        )
    )
    #: «موجودی / بهای تمام‌شده» فقط در مسیرِ قدیمی این‌جاست؛ در مسیرِ تازه سندِ
    #: برگشتِ خروج آن را با معینِ انبارِ واقعی و حسابِ خودِ خروج می‌زند.
    if total_cost > 0 and inline:
        journal_lines.append(
            JournalLine(
                #: معینِ همان انباری که کالا به آن برمی‌گردد (§۹).
                account_id=warehouses.inventory_account_id(db, invoice.warehouse_id), debit=total_cost, credit=0,
                description="بازگشت کالا به موجودی"
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

    number = next_document_number(db, DOC_SALES_RETURN)
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
        tax_rate=tax_rate,
        tax_amount=tax_amount,
        stock_mode="inline" if inline else "issue_return",
        journal_entry_id=journal_entry.id,
        created_by_id=user.id,
        lines=return_lines,
    )
    db.add(sales_return)
    # flush اجباری است و تزئینی نیست: شناسه‌ی کلید اصلی با default=uuid4 در لحظه‌ی
    # INSERT ساخته می‌شود، نه موقع ساختن شیء. بدون این خط، مقدارِ خوانده‌شده None
    # است و حرکت انبار بی‌صدا بدون منشأ ذخیره می‌شود — کاردکس و ابطال هر دو می‌شکنند.
    db.flush()
    for move in stock_moves:
        move.source_id = sales_return.id
        db.add(move)

    db.flush()
    valuation.settle_posting(db, stock_moves)
    if not inline:
        if physical is None:
            from app.services.sales_posting import posts_immediately

            physical = posts_immediately(db)
        if physical:
            from app.services.issue_returns import return_goods_for_sales_return

            return_goods_for_sales_return(db, sales_return, invoice, user)
    db.refresh(sales_return)
    return sales_return


def _purchase_returnable_lines(db: Session, invoice_id: UUID, *, lock: bool = False) -> list[_SourceLine]:
    """قرینه‌ی `_returnable_lines` برای خرید — همان قاعده‌ها، همان دلایل.

    `unit_price` و `unit_cost` هر دو بهای واحدِ **پس از تخفیف** را حمل می‌کنند:
    باید همان مبلغی به تأمین‌کننده برگردد که به او پرداخت شده، نه قیمتِ فهرست.
    """
    query = db.query(PurchaseInvoiceLine).filter(PurchaseInvoiceLine.invoice_id == invoice_id)
    if lock:
        query = query.with_for_update()
    lines = query.order_by(PurchaseInvoiceLine.id).all()

    allocated = dict(
        db.query(
            PurchaseReturnLine.purchase_invoice_line_id, func.coalesce(func.sum(PurchaseReturnLine.qty), 0)
        )
        .join(PurchaseReturn, PurchaseReturn.id == PurchaseReturnLine.return_id)
        .filter(
            PurchaseReturn.purchase_invoice_id == invoice_id,
            PurchaseReturn.voided_at.is_(None),
            PurchaseReturnLine.purchase_invoice_line_id.isnot(None),
        )
        .group_by(PurchaseReturnLine.purchase_invoice_line_id)
        .all()
    )
    legacy = {
        item_id: Decimal(qty)
        for item_id, qty in db.query(
            PurchaseReturnLine.item_id, func.coalesce(func.sum(PurchaseReturnLine.qty), 0)
        )
        .join(PurchaseReturn, PurchaseReturn.id == PurchaseReturnLine.return_id)
        .filter(
            PurchaseReturn.purchase_invoice_id == invoice_id,
            PurchaseReturn.voided_at.is_(None),
            PurchaseReturnLine.purchase_invoice_line_id.is_(None),
        )
        .group_by(PurchaseReturnLine.item_id)
        .all()
    }

    rows: list[_SourceLine] = []
    for line in lines:
        bought = Decimal(line.qty)
        net = (bought * Decimal(line.unit_cost)) - Decimal(line.discount or 0)
        unit = net / bought if bought else Decimal(0)
        returned = Decimal(allocated.get(line.id, 0))
        rows.append(
            _SourceLine(
                line=line,
                sold=bought,
                unit_price=unit,
                unit_cost=unit,
                #: برگشتِ قلمِ معاف نباید اعتبارِ مالیاتی‌ای را پس بدهد که هرگز
                #: گرفته نشده بود — پس نرخ از خودِ ردیف می‌آید، نه سربرگ.
                tax_rate=Decimal(line.tax_rate_snapshot or 0),
                returned=returned,
                remaining=max(bought - returned, Decimal(0)),
            )
        )
    _drain_legacy(rows, legacy)
    return rows


def get_purchase_returnable_summary(db: Session, invoice_id: UUID) -> list[dict]:
    """قرینه‌ی get_returnable_summary برای خرید: باقی‌ماندهٔ قابلِ برگشتِ هر **ردیف**.

    `unit_price` در خروجی بهای واحد (unit_cost) را حمل می‌کند تا از همان اسکیمای
    ReturnableLineOut استفاده شود.
    """
    invoice = db.get(PurchaseInvoice, invoice_id)
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "فاکتور خرید یافت نشد")
    rows = _purchase_returnable_lines(db, invoice_id)
    items = {i.id: i for i in db.query(Item).filter(Item.id.in_([r.line.item_id for r in rows])).all()}
    return [
        {
            "purchase_invoice_line_id": row.line.id,
            "invoice_number": invoice.number,
            "item_id": row.line.item_id,
            "item_name": items[row.line.item_id].name if row.line.item_id in items else "",
            "unit": items[row.line.item_id].unit if row.line.item_id in items else "",
            "sold": row.sold,
            "already_returned": row.returned,
            "remaining": row.remaining,
            "unit_price": row.unit_cost,
        }
        for row in rows
    ]


def _release_batch(
    db: Session, receipt: WarehouseReceipt, receipt_line, qty: Decimal
) -> None:
    """مقدارِ برگشتی را از **همان بارِ ورودی** کم می‌کند.

    فصل: «Where the source Item is Batch/Serial/Tracking controlled, return the
    actual eligible source tracking identity. Do not detach the returned
    quantity from its historical tracking context.»

    تا امروز برگشت از خرید اصلاً `StockBatch` را لمس نمی‌کرد — یعنی کاردکس
    درست می‌شد ولی فهرستِ بارها همچنان یک بارِ سالم و مثبت نشان می‌داد که دیگر
    در انبار نبود. `received_qty` برای تاریخچه دست نمی‌خورد؛ فقط ماندهٔ سالم کم
    می‌شود — همان قاعده‌ای که ابطالِ رسید دارد.
    """
    batch = (
        db.query(StockBatch)
        .filter(
            StockBatch.source_type == "warehouse_receipt",
            StockBatch.source_id == receipt.id,
            StockBatch.item_id == receipt_line.item_id,
            StockBatch.batch_number == f"WR{receipt.number}-{receipt_line.seq}",
        )
        .with_for_update()
        .one_or_none()
    )
    if batch is None:
        return
    batch.qty = max(Decimal(batch.qty) - Decimal(qty), Decimal(0))


def _receipt_returnable_lines(
    db: Session, receipt_id: UUID, *, lock: bool = False
) -> list[_SourceLine]:
    """ردیف‌های یک رسیدِ انبار با ماندهٔ قابلِ برگشتِ **هر ردیف**.

    **باقیمانده مشتق است، نه ذخیره‌شده:**

        مقدارِ رسید  −  جمعِ برگشت‌های معتبرِ همان ردیف  =  باقیمانده

    فصل صریح می‌گوید «Do not maintain an unrelated manually updated
    remaining-return scalar when the value can be derived» و «Do not use a
    simple boolean returned = true/false». پس یک ردیفِ رسید می‌تواند چند بار
    و جزئی برگشت بخورد تا ماندهٔ آن صفر شود.

    **ابطالِ یک برگشت مقدارش را آزاد می‌کند** — چون فیلترِ `voided_at is NULL`
    آن را از جمع بیرون می‌گذارد. فصل همین را می‌خواهد: «Releasing a valid
    Return should restore the corresponding returnable quantity».

    `lock=True` ردیف‌های رسید را تا پایانِ تراکنش قفل می‌کند. بدونش دو برگشتِ
    هم‌زمان هر دو ماندهٔ ۲۰ را می‌خوانند و در پایان ۳۰ واحد برگشت می‌خورد —
    دقیقاً سناریوی «Concurrent Return» فصل.
    """
    query = db.query(WarehouseReceiptLine).filter(WarehouseReceiptLine.receipt_id == receipt_id)
    if lock:
        query = query.with_for_update()
    lines = query.order_by(WarehouseReceiptLine.seq, WarehouseReceiptLine.id).all()

    allocated = dict(
        db.query(
            PurchaseReturnLine.warehouse_receipt_line_id,
            func.coalesce(func.sum(PurchaseReturnLine.qty), 0),
        )
        .join(PurchaseReturn, PurchaseReturn.id == PurchaseReturnLine.return_id)
        .filter(
            PurchaseReturn.warehouse_receipt_id == receipt_id,
            PurchaseReturn.voided_at.is_(None),
            PurchaseReturnLine.warehouse_receipt_line_id.isnot(None),
        )
        .group_by(PurchaseReturnLine.warehouse_receipt_line_id)
        .all()
    )

    rows: list[_SourceLine] = []
    for line in lines:
        received = Decimal(line.qty)
        returned = Decimal(allocated.get(line.id, 0))
        rows.append(
            _SourceLine(
                line=line,
                sold=received,
                #: «فی» و «فی تمام‌شده» جدا می‌مانند (§۲۰ فصلِ رسید): بدهیِ
                #: تأمین‌کننده با فی برمی‌گردد، ولی از انبار بهای تمام‌شده خارج
                #: می‌شود. `unit_price` فی را حمل می‌کند و `unit_cost` بهای
                #: تمام‌شده را.
                unit_price=Decimal(line.unit_cost),
                unit_cost=line.landed_unit_cost,
                tax_rate=Decimal(line.tax_rate_snapshot or 0),
                returned=returned,
                remaining=max(received - returned, Decimal(0)),
            )
        )
    return rows


def get_receipt_returnable_summary(db: Session, receipt_id: UUID) -> list[dict]:
    """پنجره‌ی «مبنا» — چه چیزی از این رسید هنوز قابلِ برگشت است.

    فصل ستون‌های این پنجره را نام می‌برد: تاریخ، باقیمانده، کد کالا، عنوان،
    ردیابی، مقدار.
    """
    receipt = db.get(WarehouseReceipt, receipt_id)
    if receipt is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "رسید انبار یافت نشد")
    rows = _receipt_returnable_lines(db, receipt_id)
    items = {i.id: i for i in db.query(Item).filter(Item.id.in_([r.line.item_id for r in rows])).all()}
    return [
        {
            "warehouse_receipt_line_id": row.line.id,
            "purchase_invoice_line_id": row.line.purchase_invoice_line_id,
            "receipt_number": receipt.number,
            "receipt_date": receipt.receipt_date,
            "item_id": row.line.item_id,
            "item_code": row.line.item_code_snapshot
            or (items[row.line.item_id].sku if row.line.item_id in items else ""),
            "item_name": row.line.item_name_snapshot
            or (items[row.line.item_id].name if row.line.item_id in items else ""),
            "unit": row.line.unit_snapshot
            or (items[row.line.item_id].unit if row.line.item_id in items else ""),
            "received": row.sold,
            "already_returned": row.returned,
            "remaining": row.remaining,
            #: «فی» و «فی تمام‌شده» هر دو، چون فصل هر دو را در جدول دارد.
            "unit_cost": row.unit_price,
            "landed_unit_cost": row.unit_cost,
            #: وضعیت **مشتق** است، نه یک بولینِ مستقل (§RETURN STATUS).
            "return_status": (
                "not_returned"
                if row.returned == 0
                else "fully_returned"
                if row.remaining == 0
                else "partially_returned"
            ),
        }
        for row in rows
    ]


def _resolve_return_source(
    db: Session, data: PurchaseReturnIn
) -> tuple[PurchaseInvoice | None, WarehouseReceipt | None, UUID | None]:
    """کدام سند مبدأِ این برگشت است — و کالا از کدام انبار خارج می‌شود.

    دو لنگرِ معتبر (§SOURCE / BASIS). رسید ارجح است وقتی داده شده باشد، چون
    اوست که انبار و بهای تمام‌شده‌ی ورود را می‌شناسد.
    """
    receipt: WarehouseReceipt | None = None
    if data.warehouse_receipt_id is not None:
        receipt = (
            db.query(WarehouseReceipt)
            .filter(WarehouseReceipt.id == data.warehouse_receipt_id)
            .with_for_update()
            .one_or_none()
        )
        if receipt is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "رسید انبار یافت نشد")
        if receipt.voided_at is not None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "این رسید انبار باطل شده است؛ روی رسیدِ باطل‌شده نمی‌توان برگشت زد.",
            )

    invoice_id = data.purchase_invoice_id or (receipt.purchase_invoice_id if receipt else None)
    invoice: PurchaseInvoice | None = None
    if invoice_id is not None:
        invoice = (
            db.query(PurchaseInvoice)
            .filter(PurchaseInvoice.id == invoice_id)
            .with_for_update()
            .one_or_none()
        )
        if invoice is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "فاکتور خرید یافت نشد")
        if invoice.voided_at is not None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "این فاکتور خرید باطل شده است؛ روی فاکتورِ باطل‌شده نمی‌توان برگشت زد.",
            )

    if invoice is None and receipt is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "برگشت باید به فاکتور خرید یا رسید انبار گره بخورد"
        )

    if invoice is not None and Decimal(invoice.total_deductions or 0) > 0:
        #: **کسورات در برگشتِ جزئی قاعده‌ی تسهیم می‌خواهند که تعریف نشده.** برگشتِ
        #: نیمی از خدمت یعنی چه مقدار از مالیات تکلیفی و بیمه برگردد؟ متناسب با مبنا؟
        #: کاملاً تا مبلغِ باقی؟ فصل نگفته، و حدسش یعنی بدهیِ مالیاتی یا بیمه‌ای که
        #: بی‌صدا غلط می‌شود. اصلاحِ کنترل‌شده همین است: ابطال و ثبتِ دوباره.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "این فاکتور خرید خدمات کسورات (مالیات تکلیفی/بیمه) دارد و برگشتِ آن هنوز قاعده‌ی "
            "تسهیمِ کسورات ندارد. برای اصلاح، فاکتور را باطل و دوباره ثبت کنید.",
        )

    warehouse_id = receipt.warehouse_id if receipt is not None else (
        invoice.warehouse_id if invoice is not None else None
    )
    if warehouse_id is None and receipt is None and invoice is not None and invoice.kind == "service":
        #: فاکتور خرید خدمات هرگز انبار ندارد و رسیدی هم نمی‌آوردش؛ برگشتش فقط
        #: حسابِ هزینه و بدهی را برمی‌گرداند و موجودی‌ای نمی‌جوید.
        return invoice, None, None
    if warehouse_id is None:
        #: **پیامِ صادق به‌جای «موجودی کافی نیست (موجود: ۰)».**
        #:
        #: از مهاجرتِ ۰۱۳۰ فاکتور `warehouse_id` ندارد و کالا با رسید وارد
        #: می‌شود. تا دیروز برگشت موجودی را در انبارِ خالیِ فاکتور می‌جست و
        #: همیشه صفر می‌دید — خطایی که کاربر را دنبالِ نخود سیاه می‌فرستاد.
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "کالای این فاکتور با رسید انبار وارد شده است؛ برگشت را باید روی همان رسید ثبت کنید.",
        )
    return invoice, receipt, warehouse_id


def post_purchase_return(db: Session, data: PurchaseReturnIn, user: User) -> PurchaseReturn:
    assert_period_open(db, data.return_date)

    invoice, receipt, warehouse_id = _resolve_return_source(db, data)

    if receipt is not None:
        rows = _receipt_returnable_lines(db, receipt.id, lock=True)
        source_attr, doc_label = "warehouse_receipt_line_id", "رسید انبار"
    else:
        rows = _purchase_returnable_lines(db, invoice.id, lock=True)
        source_attr, doc_label = "purchase_invoice_line_id", "فاکتور خرید"

    item_ids = {row.line.item_id for row in rows} | {l.item_id for l in data.lines if l.item_id}
    items_by_id = {i.id: i for i in db.query(Item).filter(Item.id.in_(item_ids)).all()}
    plan = _allocate(rows, data.lines, items_by_id, source_attr=source_attr, doc_label=doc_label)
    lock_items(db, {row.line.item_id for row, _, _ in plan})

    total_amount = Decimal(0)
    tax_amount = Decimal(0)
    tax_weight = Decimal(0)
    return_lines: list[PurchaseReturnLine] = []
    stock_moves: list[StockLedger] = []
    #: خالصِ برگشتیِ هر حساب — قرینه‌ی تفکیکِ کالا/خدمتِ فاکتورِ خرید (§۱۵ §۱۶).
    #: برگشتِ خریدِ خدمت باید حسابِ **هزینه** را بستانکار کند، نه موجودیِ کالا؛
    #: وگرنه موجودیِ دفتری بی‌آنکه کالایی جابه‌جا شود کم می‌شود.
    credit_by_account: dict[UUID, Decimal] = {}
    inventory_account_id = warehouses.inventory_account_id(db, warehouse_id)
    agreed_total = Decimal(0)
    agreed_by_source = {
        line_in.warehouse_receipt_line_id or line_in.purchase_invoice_line_id: line_in
        for line_in in data.lines
    }

    for index, (row, qty, req) in enumerate(plan, start=1):
        item = items_by_id[row.line.item_id]
        if not item.is_service:
            #: **دو سقفِ جدا، و فصل صریح می‌گوید قاطی‌شان نکنیم.**
            #:
            #: «باقیمانده‌ی قابلِ برگشت از مبدأ» را `_allocate` بالاتر گرفته؛
            #: این‌جا سقفِ دوم است: موجودیِ واقعیِ همان انبار. ممکن است رسیدِ
            #: ۱۰۰تایی هنوز ۱۰۰ واحد قابلِ برگشت داشته باشد ولی ۷۰ واحدش
            #: فروخته شده باشد.
            available = get_stock_qty(db, row.line.item_id, warehouse_id)
            if available < qty:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    f"موجودی «{item.name}» برای این میزان برگشت کافی نیست (موجود: {available})",
                )

        #: «فی» و «فی تمام‌شده» جدا می‌مانند (§۲۰ فصلِ رسید). از انبار بهای
        #: تمام‌شده خارج می‌شود؛ بدهیِ تأمین‌کننده با فی برمی‌گردد.
        unit_price = row.unit_price
        unit_cost = row.unit_cost
        line_goods = qty * unit_price
        line_landed = qty * unit_cost
        freight_share = line_landed - line_goods
        line_tax = compute_tax(line_goods, row.tax_rate)

        total_amount += line_landed
        tax_amount += line_tax
        tax_weight += line_goods * row.tax_rate
        account_id = items_svc.purchase_account_id(db, item, inventory_account_id=inventory_account_id)
        if item.is_service:
            #: **حسابی که فاکتور واقعاً بدهکار کرد، نه نگاشتِ امروزِ خدمت.** اگر معینِ
            #: هزینه‌ی خدمت بعد از فاکتور عوض شده باشد، نگاشتِ امروز حسابی را بستانکار
            #: می‌کرد که هرگز بدهکار نشده بود. ردیف‌های پیش از ۰۱۴۱ این ستون را ندارند
            #: و همان رفتارِ قبلی را می‌گیرند.
            source_line = (
                row.line
                if receipt is None
                else (
                    db.get(PurchaseInvoiceLine, row.line.purchase_invoice_line_id)
                    if row.line.purchase_invoice_line_id
                    else None
                )
            )
            if source_line is not None and source_line.expense_account_id is not None:
                account_id = source_line.expense_account_id
        credit_by_account[account_id] = credit_by_account.get(account_id, Decimal(0)) + line_landed

        #: **مبلغ مرجوعی توافقی — جدا، ولی پیش‌فرضش ارزشِ دفتری است.**
        #:
        #: فصل می‌گوید این دو را یکی فرض نکنیم و حسابِ اختلاف را هم اختراع
        #: نکنیم. پس وقتی کاربر عددی نداده، پیش‌فرض همان ارزشِ موجودی است و
        #: اختلافی وجود ندارد؛ وقتی داده و فرق می‌کند، پایین‌تر رد می‌شود.
        source_key = row.line.id
        requested = agreed_by_source.get(source_key)
        agreed_unit = (
            Decimal(requested.agreed_unit_value)
            if requested is not None and requested.agreed_unit_value is not None
            else unit_cost
        )
        line_agreed = (qty * agreed_unit).quantize(Decimal(1))
        agreed_total += line_agreed

        return_lines.append(
            PurchaseReturnLine(
                seq=index,
                #: لنگر روی همان سندی که مبدأ بوده — و اگر رسید به فاکتوری گره
                #: خورده، **هر دو** نوشته می‌شوند تا برگشت از مسیرِ فاکتور هم
                #: همین مقدار را مصرف‌شده ببیند و کالا دو بار برگشت نخورد.
                purchase_invoice_line_id=(
                    row.line.purchase_invoice_line_id if receipt is not None else row.line.id
                ),
                warehouse_receipt_line_id=row.line.id if receipt is not None else None,
                item_id=row.line.item_id,
                qty=qty,
                unit_cost=unit_price,
                freight_share=freight_share,
                agreed_unit_value=agreed_unit,
                agreed_amount=line_agreed,
                tax_rate_snapshot=row.tax_rate,
                tax_amount_snapshot=line_tax,
                description=req.description,
            )
        )

        if not item.is_service:
            existing_qty = get_total_stock_qty(db, item.id)
            new_qty = existing_qty - qty
            if new_qty > 0:
                item.average_cost = ((existing_qty * item.average_cost) - line_landed) / new_qty
            stock_moves.append(
                StockLedger(
                    item_id=row.line.item_id,
                    warehouse_id=warehouse_id,
                    qty=-qty,
                    unit_cost=unit_cost,
                    entry_date=data.return_date,
                    source_type="purchase_return",
                )
            )
            if receipt is not None:
                _release_batch(db, receipt, row.line, qty)

    #: **اختلافِ ارزشِ دفتری و مبلغ توافقی، سندی ندارد که در آن بنشیند.**
    #:
    #: فصل صریح است: «Do not invent or hard-code a price-difference account
    #: yet.» پس به‌جای اینکه اختلاف را بی‌صدا در یک حسابِ دلخواه بگذاریم یا
    #: سندِ نامتوازن بسازیم، ثبت رد می‌شود و علتش گفته می‌شود. هر دو مبلغ در
    #: مدل هستند و وقتی سیاستِ حسابداری‌اش تعریف شد، همین‌جا باز می‌شود.
    if agreed_total != total_amount:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "مبلغ مرجوعی توافقی با ارزش دفتری کالا برابر نیست "
            f"({agreed_total:,} در برابر {total_amount:,}). "
            "سیاست حسابداری این اختلاف هنوز تعریف نشده است.",
        )

    # قرینهٔ برگشت از فروش: اعتبار مالیاتیِ خرید هم باید پس برود، وگرنه اعتبارِ
    # مالیاتی بابت کالایی که دیگر نداریم روی حساب می‌ماند. نرخ از ردیف‌های خودِ
    # فاکتور می‌آید نه از سربرگش.
    tax_rate = (tax_weight / total_amount) if total_amount else Decimal(0)

    #: **طرفِ مقابل از خودِ سندِ مبدأ می‌آید، نه از یک قالبِ ثابت.**
    #:
    #: فصل: «اگر Receipt اصلی از Account Mapping خاصی استفاده کرده، Return باید
    #: بتواند بفهمد چه چیزی را دارد معکوس می‌کند.» رسیدِ مستقیمِ بی‌تحویل‌دهنده
    #: نقد ثبت شده بود، پس برگشتش هم نقد است.
    counterparty = (
        data.receiver_id
        or (receipt.contact_id if receipt is not None else None)
        or (invoice.contact_id if invoice is not None else None)
    )
    journal_lines = [
        JournalLine(
            account_id=(get_account(db, cc.ACCOUNTS_PAYABLE) if counterparty else get_account(db, cc.CASH)).id,
            debit=agreed_total + tax_amount,  # کلِ مبلغی که از طرفِ مقابل پس گرفته می‌شود
            credit=0,
            description="برگشت از خرید",
        ),
    ] + [
        JournalLine(
            account_id=account_id,
            debit=0,
            credit=amount,
            description=(
                "کاهش موجودی بابت برگشت از خرید"
                if account_id == inventory_account_id
                else "برگشت هزینه‌ی خریدِ خدمت"
            ),
        )
        for account_id, amount in credit_by_account.items()
    ]
    if tax_amount > 0:
        journal_lines.append(
            JournalLine(
                account_id=vat_receivable_account(db).id,
                debit=0,
                credit=tax_amount,
                description="برگشت مالیات بر ارزش افزوده خرید (اعتبار مالیاتی)",
            )
        )
    number = next_document_number(db, DOC_PURCHASE_RETURN)
    journal_entry = make_journal_entry(
        db,
        data.return_date,
        (
            f"برگشت از خرید شماره {number} (رسید انبار {receipt.number})"
            if receipt is not None
            else f"برگشت از خرید شماره {number} (فاکتور خرید {invoice.number})"
        ),
        "purchase_return",
        user,
        journal_lines,
    )

    purchase_return = PurchaseReturn(
        number=number,
        return_date=data.return_date,
        purchase_invoice_id=invoice.id if invoice is not None else None,
        warehouse_receipt_id=receipt.id if receipt is not None else None,
        warehouse_id=warehouse_id,
        receiver_id=counterparty,
        return_type=data.return_type,
        currency_code=(data.currency_code or None),
        exchange_rate=data.exchange_rate,
        description=data.description,
        total_amount=total_amount,
        tax_rate=tax_rate,
        tax_amount=tax_amount,
        journal_entry_id=journal_entry.id,
        created_by_id=user.id,
        lines=return_lines,
    )
    db.add(purchase_return)
    # flush اجباری است و تزئینی نیست: شناسه‌ی کلید اصلی با default=uuid4 در لحظه‌ی
    # INSERT ساخته می‌شود، نه موقع ساختن شیء. بدون این خط، مقدارِ خوانده‌شده None
    # است و حرکت انبار بی‌صدا بدون منشأ ذخیره می‌شود — کاردکس و ابطال هر دو می‌شکنند.
    db.flush()
    for move in stock_moves:
        move.source_id = purchase_return.id
        db.add(move)

    db.flush()
    #: برگشتِ پیش‌تاریخ نباید گذشته را منفی کند؛ و میانگین از بازپخش — که حالا همان
    #: خروجِ با بهای تمام‌شده‌ی بالا را می‌شناسد.
    valuation.settle_posting(db, stock_moves)
    db.refresh(purchase_return)
    return purchase_return


def attach_return_state(db: Session, returns: list) -> None:
    """وضعیت‌های **مشتق** روی هر سندِ برگشت — بدونِ هیچ شمارنده‌ی ذخیره‌شده (§۹۲).

    فهرستِ مرجع سه عدد کنارِ هم دارد: مبلغِ برگشت، پرداخت‌شده، و ماندهٔ برگشت
    (§۶۴ §۶۵). این‌ها سه حقیقتِ جدا هستند و «پرداخت‌شده» از خزانه/تسویه می‌آید،
    نه از خودِ برگشت — یک برگشتِ پرداخت‌نشده حالتِ کاملاً معتبری است (§۶۷).

    ذخیره‌کردنشان روی سربرگ یعنی دو نمای یک داده که بی‌صدا از هم جدا می‌افتند؛
    پس هر بار از منبع خوانده می‌شوند.
    """
    if not returns:
        return
    # import دیرهنگام: open_items خودش returns را می‌شناسد.
    from app.services.open_items import settled_amounts

    kind = "sales_return" if isinstance(returns[0], SalesReturn) else "purchase_return"
    settled = settled_amounts(db, [(kind, r.id) for r in returns])
    for doc in returns:
        final = Decimal(doc.total_amount or 0) + Decimal(doc.tax_amount or 0)
        paid = settled.get((kind, doc.id), Decimal(0))
        doc.final_amount = final
        doc.settled_amount = paid
        doc.remaining_amount = max(final - paid, Decimal(0))
        doc.accounting_status = "posted" if doc.journal_entry_id else "unposted"
        #: «باطل» یک وضعیتِ مالی نیست، ولی در فهرست باید از «تسویه‌نشده» جدا
        #: دیده شود وگرنه کاربر دنبالِ پولی می‌گردد که اصلاً قرار نیست برود.
        doc.financial_status = (
            "voided" if doc.voided_at is not None
            else "unsettled" if paid == 0
            else "fully_settled" if paid >= final
            else "partially_settled"
        )
    if kind == "sales_return":
        #: وضعیتِ فیزیکی **کنارِ** وضعیتِ مالی، نه جایش — دو حقیقتِ مستقل.
        from app.services.issue_returns import attach_physical_state

        attach_physical_state(db, returns)


def return_print_projection(db: Session, pret: PurchaseReturn) -> dict:
    """ورودیِ برگه‌ی چاپیِ «برگشت رسید انبار» — Projectionِ همان سند.

    فصل هر دو عدد را روی کاغذ می‌خواهد: «خالص» (ارزشِ دفتریِ کالای خارج‌شده) و
    «خالص توافقی». پس دومی ردیفِ جدای جمع‌هاست، نه جایگزینِ اولی.
    """
    warehouse = db.get(Warehouse, pret.warehouse_id) if pret.warehouse_id else None
    receiver = db.get(Contact, pret.receiver_id) if pret.receiver_id else None
    receipt = db.get(WarehouseReceipt, pret.warehouse_receipt_id) if pret.warehouse_receipt_id else None
    items = {i.id: i for i in db.query(Item).filter(Item.id.in_([l.item_id for l in pret.lines])).all()}
    lines = []
    goods = freight = tax = Decimal(0)
    for line in pret.lines:
        item = items.get(line.item_id)
        amount = line.goods_amount
        line_freight = Decimal(line.freight_share or 0)
        line_tax = Decimal(line.tax_amount_snapshot or 0)
        goods += amount
        freight += line_freight
        tax += line_tax
        lines.append(
            {
                "seq": line.seq,
                "code": item.sku if item else "",
                "name": item.name if item else "",
                "unit": item.unit if item else "",
                "qty": line.qty,
                "unit_cost": line.unit_cost,
                "amount": amount,
                "tax": line_tax,
                "freight": line_freight,
                "net": amount + line_freight + line_tax,
            }
        )
    return {
        "title": "برگشت رسید انبار",
        "number": pret.number,
        "doc_date": pret.return_date,
        "type_label": RETURN_TYPE_LABELS.get(pret.return_type, pret.return_type),
        "warehouse_code": warehouse.code if warehouse else "",
        "warehouse_name": warehouse.name if warehouse else "",
        "party_label": "تحویل‌گیرنده",
        "party_name": receiver.name if receiver else "بدونِ تحویل‌گیرنده (نقدی)",
        "party_detail": " — ".join(filter(None, [receiver.phone, receiver.address])) if receiver else "",
        "lines": lines,
        "goods_amount": goods,
        "freight_amount": freight,
        "duty_amount": Decimal(0),
        "tax_amount": tax,
        "net_amount": goods + freight + tax,
        "description": pret.description or (f"بابت رسید انبار شماره {receipt.number}" if receipt else ""),
        "sign_labels": ("صادرکننده", "تحویل‌گیرنده"),
        "extra_totals": [("خالص توافقی (ریال)", pret.agreed_total + tax)],
        "voided_at": pret.voided_at,
        "void_reason": pret.void_reason or "",
    }
