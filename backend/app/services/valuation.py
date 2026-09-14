"""قیمت‌گذاریِ اسنادِ انبار — یک موتور، یک تعریف.

کوبیتا ارزش‌گذاری را **دائمی** انجام می‌دهد: هر سندِ انبار همان لحظه بها و سندِ
حسابداری‌اش را می‌زند. این ماژول آن را عوض نمی‌کند. کاری که می‌کند این است که «بهای
درست» فقط **یک تعریف** داشته باشد و همه — بازمحاسبه‌ی پس از ابطال، بهای سندِ
پیش‌تاریخ، کاردکس، ارزشِ موجودی، تطبیق با دفتر — از همان بخوانند.

**تعریف.** میانگینِ موزونِ متحرک، یک میانگین برای هر کالا در کلِ شرکت، با بازپخشِ
دفترِ موجودی به ترتیبِ **(تاریخِ سند، ترتیبِ ثبت)**؛ اسنادِ باطل انگار هرگز نبوده‌اند.

تا پیش از این ترتیب فقط `seq` بود. سندی که امروز با تاریخِ ماهِ پیش ثبت می‌شد در
بازپخش **بعد از** همه‌ی اسنادِ ماهِ پیش می‌نشست: خروجِ پیش‌تاریخ میانگینِ امروز را
می‌گرفت، کاردکس ردیفش را جای غلط می‌گذاشت، و موجودیِ منفیِ گذشته دیده نمی‌شد.
`seq` هنوز لازم است — فقط برای چیدنِ حرکاتِ **هم‌روز**.

**چهار قاعده‌ی حرکت** (`rule_of`)؛ هر کدام همان کاری است که ثبتِ لحظه‌ای می‌کند:

* **ورود با بهای خودش** — خرید، رسید، اول دوره، محصولِ تولید، و برگشت‌ها با بهای
  سندِ مبدأ؛
* **ورود با میانگین** — انتقال به انبار، تعدیل و انبارگردانیِ اضافی: جابه‌جاییِ
  درونی‌اند و میانگین را تکان نمی‌دهند؛
* **خروج با میانگین** — خروجِ انبار، انتقال از انبار، کسری، مصرفِ تولید؛
* **خروج با بهای خودش** — برگشت از خرید: همان بهای تمام‌شده‌ای که آمده بود بیرون
  می‌رود. ثبتِ لحظه‌ای از اول همین را می‌کرد، ولی بازپخشِ قدیمی خروج را بی‌اثر
  می‌گرفت؛ پس **ابطالِ هر سندِ دیگری** میانگینِ کالای برگشت‌خورده را بی‌صدا
  می‌پراند.

**«منقضی» ذخیره نمی‌شود، مشتق می‌شود.** حرکتی که با میانگین ارزش‌گذاری شده و
بهای ثبت‌شده‌اش با بازپخش نمی‌خواند، منقضی است. علتش هم از خودِ دفتر پیدا
می‌شود: ردیفی که **بعد از** آن ثبت شده ولی در زمان **پیش از** آن نشسته (سندِ
پیش‌تاریخ)، یا ابطالی که بعد از آن آمده و سندِ پیش از آن را برداشته. علامتِ
ذخیره‌شده فقط همان اسنادی را می‌دید که از امروز ثبت می‌شوند؛ این تعریف دفترِ
پیش از امروز را هم می‌بیند، و با اصلاحِ ارزش‌گذاری خودش پاک می‌شود.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from itertools import groupby
from typing import Iterable, Sequence
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.inventory import Item, StockLedger, Warehouse
from app.models.inventory_valuation import InventoryValuationAdjustment, InventoryValuationRun
from app.models.invoices import PurchaseInvoice, SalesInvoice, WarehouseIssue, WarehouseIssueLine, WarehouseReceipt
from app.models.issue_returns import WarehouseIssueReturn, WarehouseIssueReturnLine
from app.models.returns import PurchaseReturn, SalesReturn
from app.models.transfers import StockTransfer

#: منشأ ردیف‌های جبرانیِ ابطال در دفترِ موجودی.
VOID_SOURCE = "void"

#: برچسبِ فارسیِ منشأ هر حرکت — همان مقادیری که سرویس‌ها می‌نویسند.
SOURCE_LABELS = {
    "purchase_invoice": "فاکتور خرید",
    "sales_invoice": "فاکتور فروش",
    "warehouse_receipt": "رسید انبار",
    "warehouse_issue": "خروج انبار",
    "warehouse_issue_return": "برگشت خروج انبار",
    "purchase_return": "برگشت از خرید",
    "sales_return": "برگشت از فروش",
    "adjustment": "تعدیل انبار",
    "stock_count": "انبارگردانی",
    "production": "تولید",
    "transfer_in": "انتقال (ورود)",
    "transfer_out": "انتقال (خروج)",
    "opening": "موجودی اول دوره",
    VOID_SOURCE: "ابطال",
}

IN_COST = "in_cost"
IN_AVERAGE = "in_average"
OUT_AVERAGE = "out_average"
OUT_COST = "out_cost"

#: ورودهایی که با میانگینِ همان لحظه می‌نشینند، نه با بهای ثبت‌شده‌شان.
AVERAGE_INFLOWS = frozenset({"transfer_in", "adjustment", "stock_count"})
#: خروج‌هایی که با بهای خودشان بیرون می‌روند و ارزش را کم می‌کنند.
COST_OUTFLOWS = frozenset({"purchase_return"})
TRANSFER_SOURCES = frozenset({"transfer_in", "transfer_out"})
#: ورودی که بهایش از **حرکتِ مبدأ** می‌آید، نه از عددِ ثبت‌شده‌ی خودش: برگشتِ خروج با بهای
#: همان خروج برمی‌گردد. اگر بهای خروج اصلاح شود و برگشت نه، کالای برگشتی با بهای کهنه در
#: میانگین می‌نشست و «بهای تمام‌شده‌ی» همان واحدهای برگشتی در سود و زیان می‌ماند.
SOURCE_FOLLOWING = frozenset({"warehouse_issue_return"})

#: همان دقتِ `Item.average_cost`. بازپخش هر بار گِرد می‌کند چون ثبتِ لحظه‌ای هم از
#: عددِ ذخیره‌شده‌ی چهاررقمی ادامه می‌دهد؛ بی‌گِردکردن، بازپخش در حرکتِ هزارم چند
#: ریال از ثبتِ لحظه‌ای فاصله می‌گرفت و هر حرکتی «منقضی» دیده می‌شد.
_AVERAGE_PLACES = Decimal("0.0001")
#: اختلافِ بهای واحدی که «منقضی» حساب می‌شود. نیم ریال، چون مصرفِ تولید بها را به
#: ریالِ صحیح ثبت می‌کند و تا نیم ریال اختلافِ ذاتیِ همان گِردکردن است، نه خطا.
STALE_TOLERANCE = Decimal("0.5")

#: کلیدِ `Session.info`: همگام‌سازیِ فروشِ آفلاین. آن فروش قبلاً انجام شده و کالایش
#: رفته؛ ردّش سرِ همگام‌سازی کارِ فروشنده را نابود می‌کند (همان استدلالِ سقفِ
#: اعتبار). گاردِ موجودیِ لحظه‌ی حال سر جایش است؛ فقط گاردِ خطِ زمان کنار می‌رود و
#: اثرش در ارزش‌گذاریِ منقضی دیده می‌شود.
LENIENT_TIMELINE = "valuation.lenient_timeline"

#: اسنادِ ابطال‌پذیری که حرکتِ انبار دارند، با منشأهایی که می‌نویسند.
#:
#: حرکتِ سندِ باطل باید از بازپخش **حذف** شود، نه اینکه ردیفِ جبرانی‌اش بازپخش شود:
#: جبرانِ ابطالِ یک خرید، خروج است و خروج میانگین را عوض نمی‌کند. هر سندی که این‌جا
#: نباشد، حرکتِ باطل‌شده‌اش در میانگین می‌ماند و **بی‌صدا منحرفش می‌کند** — هیچ
#: ترازی هم لو نمی‌دهد، چون هر دو سند متوازن‌اند.
_VOIDABLE = (
    (SalesInvoice, ("sales_invoice",)),
    (PurchaseInvoice, ("purchase_invoice",)),
    (WarehouseReceipt, ("warehouse_receipt",)),
    (SalesReturn, ("sales_return",)),
    (PurchaseReturn, ("purchase_return",)),
    (WarehouseIssue, ("warehouse_issue",)),
    (StockTransfer, ("transfer_out", "transfer_in")),
    (WarehouseIssueReturn, ("warehouse_issue_return",)),
)

_SOURCE_MODELS = {source: model for model, sources in _VOIDABLE for source in sources}

_COLUMNS = (
    StockLedger.id,
    StockLedger.seq,
    StockLedger.item_id,
    StockLedger.warehouse_id,
    StockLedger.qty,
    StockLedger.unit_cost,
    StockLedger.entry_date,
    StockLedger.source_type,
    StockLedger.source_id,
)


def rule_of(source_type: str, qty: Decimal) -> str:
    if qty >= 0:
        return IN_AVERAGE if source_type in AVERAGE_INFLOWS else IN_COST
    return OUT_COST if source_type in COST_OUTFLOWS else OUT_AVERAGE


def voided_sources(db: Session) -> set[tuple[str, UUID]]:
    """کلیدِ (منشأ، شناسه‌ی سند) هر سندِ باطل‌شده‌ای که حرکتِ انبار دارد."""
    voided: set[tuple[str, UUID]] = set()
    for model, sources in _VOIDABLE:
        for (doc_id,) in db.query(model.id).filter(model.voided_at.isnot(None)).all():
            for source in sources:
                voided.add((source, doc_id))
    return voided


def _rows(
    db: Session,
    *,
    item_ids: Iterable[UUID] | None = None,
    warehouse_id: UUID | None = None,
    until: date | None = None,
):
    stmt = select(*_COLUMNS)
    if item_ids is not None:
        stmt = stmt.where(StockLedger.item_id.in_(list(item_ids)))
    if warehouse_id is not None:
        stmt = stmt.where(StockLedger.warehouse_id == warehouse_id)
    if until is not None:
        stmt = stmt.where(StockLedger.entry_date <= until)
    stmt = stmt.order_by(StockLedger.item_id, StockLedger.entry_date, StockLedger.seq)
    return db.execute(stmt).all()


#: نامِ عمومیِ همان کوئری — برای اجرای قیمت‌گذاری که خودش بازپخش می‌کند.
ledger_rows = _rows


@dataclass
class Valued:
    """یک حرکت، پس از ارزش‌گذاری.

    `cost` بهایی است که موتور به حرکت می‌دهد و `value` اثرِ علامت‌دارِ آن بر ارزشِ
    موجودی. ردیف‌های ابطال (هم حرکتِ سندِ باطل، هم جبرانش) با بهای **ثبت‌شده‌ی**
    خودشان می‌آیند تا در جمع صفر شوند و میانگین را تکان ندهند.
    """

    row: object
    rule: str
    voided: bool
    cost: Decimal
    value: Decimal
    #: میانگینِ کالا در کلِ شرکت، پس از این حرکت.
    average: Decimal
    stale: bool
    #: بهایی که دفتر برای این حرکت می‌شناسد: آخرین اصلاحِ باطل‌نشده، وگرنه بهای خودِ سند.
    booked: Decimal = Decimal(0)

    @property
    def qty(self) -> Decimal:
        return Decimal(self.row.qty)

    @property
    def recorded_cost(self) -> Decimal:
        return self.booked

    @property
    def document_cost(self) -> Decimal:
        return Decimal(self.row.unit_cost)

    @property
    def adjusted(self) -> bool:
        return self.booked != self.document_cost


def replay(
    rows: Iterable, voided: set, active: dict | None = None, sources: dict | None = None
) -> list[Valued]:
    """حرکاتِ **یک** کالا را، به ترتیبِ (تاریخ، seq)، ارزش‌گذاری می‌کند."""
    qty = Decimal(0)
    average = Decimal(0)
    costs: dict = {}
    out: list[Valued] = []
    for row in rows:
        move_qty = Decimal(row.qty)
        recorded = active.get(row.id, Decimal(row.unit_cost)) if active else Decimal(row.unit_cost)
        rule = rule_of(row.source_type, move_qty)
        if row.source_type == VOID_SOURCE or (row.source_type, row.source_id) in voided:
            out.append(Valued(row, rule, True, recorded, move_qty * recorded, average, False, recorded))
            continue
        follows = False
        if rule in (IN_COST, OUT_COST):
            cost = recorded
            source = sources.get(row.id) if sources else None
            if source is not None and source in costs:
                cost, follows = costs[source], True
            new_qty = qty + move_qty
            if new_qty > 0:
                average = (((qty * average) + (move_qty * cost)) / new_qty).quantize(
                    _AVERAGE_PLACES, rounding=ROUND_HALF_UP
                )
            qty = new_qty
        else:
            cost = average
            qty += move_qty
        costs[row.id] = cost
        stale = (follows or rule in (IN_AVERAGE, OUT_AVERAGE)) and abs(recorded - cost) > STALE_TOLERANCE
        out.append(Valued(row, rule, False, cost, move_qty * cost, average, stale, recorded))
    return out


def active_costs(db: Session, item_ids: Iterable[UUID] | None = None) -> dict[UUID, Decimal]:
    """بهای فعالِ حرکاتِ اصلاح‌شده — از اجراهای باطل‌نشده، آخرین اجرا برنده.

    فقط آخرین اجرای باطل‌نشده ابطال‌پذیر است، پس «آخرین» همیشه همانی است که سندِ
    اصلاحی‌اش در دفتر مانده.
    """
    query = (
        db.query(InventoryValuationAdjustment.stock_ledger_id, InventoryValuationAdjustment.new_cost)
        .join(InventoryValuationRun, InventoryValuationRun.id == InventoryValuationAdjustment.run_id)
        .filter(InventoryValuationRun.voided_at.is_(None))
    )
    if item_ids is not None:
        query = query.filter(InventoryValuationAdjustment.item_id.in_(list(item_ids)))
    return {move_id: Decimal(cost) for move_id, cost in query.order_by(InventoryValuationRun.number).all()}


def moves_by_line(
    db: Session, *, source_type: str, line_model, parent_column, item_ids: Iterable[UUID] | None = None
) -> dict[UUID, UUID]:
    """ردیفِ سند ← حرکتِ دفترِ موجودی‌اش.

    حرکت شناسه‌ی ردیف را ندارد، فقط شناسه‌ی سند را؛ ولی هر ردیف دقیقاً یک حرکت ساخته و
    هر دو به ترتیبِ ثبت‌اند. پس ردیف‌های یک (سند، کالا) به ترتیبِ `seq` با حرکاتِ همان
    (سند، کالا) به ترتیبِ `seq` جفت می‌شوند.
    """
    ids = None if item_ids is None else list(item_ids)
    moves = db.query(StockLedger.id, StockLedger.source_id, StockLedger.item_id).filter(
        StockLedger.source_type == source_type
    )
    lines = db.query(line_model.id, parent_column, line_model.item_id)
    if ids is not None:
        moves = moves.filter(StockLedger.item_id.in_(ids))
        lines = lines.filter(line_model.item_id.in_(ids))
    by_doc: dict[tuple, list[UUID]] = defaultdict(list)
    for move_id, doc_id, item_id in moves.order_by(StockLedger.seq).all():
        by_doc[(doc_id, item_id)].append(move_id)
    grouped: dict[tuple, list[UUID]] = defaultdict(list)
    for line_id, doc_id, item_id in lines.order_by(parent_column, line_model.seq, line_model.id).all():
        grouped[(doc_id, item_id)].append(line_id)
    out: dict[UUID, UUID] = {}
    for key, line_ids in grouped.items():
        for line_id, move_id in zip(line_ids, by_doc.get(key, ())):
            out[line_id] = move_id
    return out


def issue_return_sources(db: Session, item_ids: Iterable[UUID] | None = None) -> dict[UUID, UUID]:
    """حرکتِ برگشتِ خروج ← حرکتِ خروجی که برمی‌گرداند."""
    ids = None if item_ids is None else list(item_ids)
    links = db.query(WarehouseIssueReturnLine.id, WarehouseIssueReturnLine.warehouse_issue_line_id)
    if ids is not None:
        links = links.filter(WarehouseIssueReturnLine.item_id.in_(ids))
    links = links.all()
    if not links:
        return {}
    issue_moves = moves_by_line(
        db, source_type="warehouse_issue", line_model=WarehouseIssueLine,
        parent_column=WarehouseIssueLine.issue_id, item_ids=ids,
    )
    return_moves = moves_by_line(
        db, source_type="warehouse_issue_return", line_model=WarehouseIssueReturnLine,
        parent_column=WarehouseIssueReturnLine.return_id, item_ids=ids,
    )
    out: dict[UUID, UUID] = {}
    for return_line_id, issue_line_id in links:
        return_move, issue_move = return_moves.get(return_line_id), issue_moves.get(issue_line_id)
        if return_move is not None and issue_move is not None:
            out[return_move] = issue_move
    return out


def context(db: Session, item_ids: Iterable[UUID] | None = None) -> tuple[set, dict, dict]:
    """سه چیزی که بازپخش لازم دارد: اسنادِ باطل، بهای فعال، مبدأِ برگشت‌ها."""
    ids = None if item_ids is None else list(item_ids)
    return voided_sources(db), active_costs(db, ids), issue_return_sources(db, ids)


def assert_not_adjusted(db: Session, source_types: Iterable[str], source_id: UUID) -> None:
    """سندی که بهایش در اجرای باطل‌نشده‌ای اصلاح شده، پیش از آن اجرا باطل نمی‌شود.

    ابطالِ سند سندِ **اصلی**اش را معکوس می‌کند، ولی سندِ اصلاحیِ اجرا در دفتر می‌ماند:
    اختلافی می‌ساخت که هیچ اجرای تازه‌ای نمی‌توانست پاکش کند، چون حرکتِ باطل دیگر منقضی
    نیست. همان الگوی «اول برگشت را باطل کن، بعد فاکتور».
    """
    found = (
        db.query(InventoryValuationRun.number)
        .join(InventoryValuationAdjustment, InventoryValuationAdjustment.run_id == InventoryValuationRun.id)
        .filter(
            InventoryValuationRun.voided_at.is_(None),
            InventoryValuationAdjustment.source_id == source_id,
            InventoryValuationAdjustment.source_type.in_(tuple(source_types)),
        )
        .order_by(InventoryValuationRun.number.desc())
        .first()
    )
    if found is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"بهای این سند در «قیمت‌گذاری اسناد انبار» شماره {found.number} اصلاح شده است؛ ابطالش سندِ "
            "اصلاحی را بی‌پشتوانه می‌گذارد. اول آن اجرا (و اجراهای بعد از آن) را باطل کنید، سپس این سند را.",
        )


def item_moves(
    db: Session, item_id: UUID, *, until: date | None = None, ctx: tuple | None = None
) -> list[Valued]:
    voided, active, sources = ctx if ctx is not None else context(db, [item_id])
    return replay(_rows(db, item_ids=[item_id], until=until), voided, active, sources)


def recompute(db: Session, item: Item, *, ctx: tuple | None = None, voided: set | None = None) -> None:
    """میانگینِ کالا را از بازپخش می‌سازد — تنها جایی که میانگین از صفر ساخته می‌شود."""
    if ctx is None and voided is not None:
        #: فراخوانی که فهرستِ اسنادِ باطل را خودش یک بار ساخته (مثلِ قیمت‌گذاریِ ورودی‌های
        #: بی‌فی برای چند کالا) — بهای فعال و مبدأِ برگشت‌ها همچنان باید خوانده شوند.
        ctx = (voided, active_costs(db, [item.id]), issue_return_sources(db, [item.id]))
    moves = item_moves(db, item.id, ctx=ctx)
    item.average_cost = moves[-1].average if moves else Decimal(0)


def _has_later_moves(db: Session, item_id: UUID, on: date, exclude_ids: Iterable[UUID] = ()) -> bool:
    query = db.query(StockLedger.id).filter(
        StockLedger.item_id == item_id,
        StockLedger.entry_date > on,
        StockLedger.source_type != VOID_SOURCE,
    )
    exclude = list(exclude_ids)
    if exclude:
        query = query.filter(StockLedger.id.notin_(exclude))
    return query.first() is not None


def cost_for_posting(db: Session, item: Item, on: date) -> Decimal:
    """بهای واحدِ خروجی که با تاریخِ `on` ثبت می‌شود.

    سندِ هم‌تاریخ یا تازه‌تر از آخرین حرکت، همان میانگینِ ذخیره‌شده را می‌گیرد —
    رفتاری که همیشه بوده. سندِ **پیش‌تاریخ** میانگینِ **همان روز** را می‌گیرد: خروجِ
    دهمِ ماه نباید بهای خریدِ بیستم را بخورد.
    """
    if not _has_later_moves(db, item.id, on):
        return Decimal(item.average_cost or 0)
    moves = item_moves(db, item.id, until=on)
    return moves[-1].average if moves else Decimal(0)


def _jalali(value: date) -> str:
    from app.services.printing import format_jalali

    return format_jalali(value)


def _qty_text(value: Decimal) -> str:
    text = format(Decimal(value).normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def document_numbers(db: Session, keys: Iterable[tuple[str, UUID | None]]) -> dict[tuple[str, UUID], int]:
    """شماره‌ی سندِ هر (منشأ، شناسه) — دسته‌ای، یک کوئری برای هر نوعِ سند."""
    wanted: dict[type, set[UUID]] = defaultdict(set)
    for source_type, source_id in keys:
        model = _SOURCE_MODELS.get(source_type)
        if model is not None and source_id is not None:
            wanted[model].add(source_id)
    by_model: dict[tuple[type, UUID], int] = {}
    for model, ids in wanted.items():
        for doc_id, number in db.query(model.id, model.number).filter(model.id.in_(ids)).all():
            by_model[(model, doc_id)] = number
    out: dict[tuple[str, UUID], int] = {}
    for source_type, source_id in keys:
        model = _SOURCE_MODELS.get(source_type)
        if model is not None and (model, source_id) in by_model:
            out[(source_type, source_id)] = by_model[(model, source_id)]
    return out


def document_label(source_type: str, number: int | None) -> str:
    label = SOURCE_LABELS.get(source_type, source_type)
    return f"{label} شماره {number}" if number is not None else label


# ─────────────────────────── گاردِ خطِ زمان ───────────────────────────


def _assert_timeline(
    db: Session,
    rows: Sequence,
    *,
    voided: set,
    exclude_with: set,
    exclude_baseline: set,
    since: date,
    voiding: bool,
) -> None:
    """موجودیِ یک کالا در یک انبار، در هیچ لحظه‌ای از `since` به بعد، منفی نشود.

    **فقط منفی‌ای که همین تغییر ساخته رد می‌شود.** دفترِ پیش از این قاعده ممکن
    است جایی منفی باشد؛ اگر آن گذشته هر ثبتِ تازه‌ای را قفل می‌کرد، کسب‌وکار راهی
    برای ادامه نداشت. پس خطِ زمانِ «با تغییر» با «بی تغییر» مقایسه می‌شود و فقط
    نقطه‌ای که تازه منفی شده یا منفی‌تر شده جلوی ثبت را می‌گیرد.
    """

    def running(exclude: set):
        total = Decimal(0)
        for row in rows:
            if row.source_type == VOID_SOURCE or (row.source_type, row.source_id) in voided or row.id in exclude:
                continue
            total += Decimal(row.qty)
            yield row, total

    baseline = {row.id: total for row, total in running(exclude_baseline)}
    for row, total in running(exclude_with):
        if row.entry_date < since or total >= 0:
            continue
        before = baseline.get(row.id)
        if before is not None and total >= before:
            continue
        item = db.get(Item, row.item_id)
        warehouse = db.get(Warehouse, row.warehouse_id)
        numbers = document_numbers(db, [(row.source_type, row.source_id)])
        label = document_label(row.source_type, numbers.get((row.source_type, row.source_id)))
        where = f"«{item.name if item else row.item_id}» در «{warehouse.name if warehouse else ''}»"
        if voiding:
            message = (
                f"ابطالِ این سند موجودیِ {where} را در تاریخِ {_jalali(row.entry_date)} منفی می‌کند "
                f"(مانده پس از «{label}»: {_qty_text(total)}). آن سند به کالای همین ورود تکیه کرده؛ "
                "اول آن را باطل کنید."
            )
        else:
            message = (
                f"با تاریخِ {_jalali(since)}، موجودیِ {where} در تاریخِ {_jalali(row.entry_date)} منفی می‌شود "
                f"(مانده پس از «{label}»: {_qty_text(total)}). کالایی که آن روز در انبار نبوده نمی‌تواند "
                "خارج شود؛ تاریخِ سند را اصلاح کنید یا ورودِ کالا را با تاریخِ درستش ثبت کنید."
            )
        raise HTTPException(status.HTTP_409_CONFLICT, message)


def settle_posting(db: Session, moves: Sequence[StockLedger]) -> None:
    """پس از ثبتِ حرکاتِ یک سند صدا زده می‌شود — هر سندی که `StockLedger` می‌نویسد.

    سندی که از آخرین حرکتِ کالا جلوتر یا هم‌تاریخ است کاری ندارد: ثبتِ لحظه‌ای با
    بازپخش یکی است. سندِ **پیش‌تاریخ** دو کار دارد:

    1. خروجش نباید گذشته را منفی کند — گاردِ لحظه‌ی حال فقط موجودیِ امروز را می‌بیند.
    2. میانگینِ کالا از بازپخش ساخته می‌شود، چون فرمولِ افزایشیِ ثبت فرض کرده
       این سند آخرین است.
    """
    moves = [move for move in moves if move is not None]
    if not moves:
        return
    db.flush()
    new_ids = {move.id for move in moves}
    earliest: dict[UUID, date] = {}
    for move in moves:
        current = earliest.get(move.item_id)
        earliest[move.item_id] = move.entry_date if current is None else min(current, move.entry_date)

    voided: set | None = None
    for item_id, on in earliest.items():
        if not _has_later_moves(db, item_id, on, new_ids):
            continue
        voided = voided_sources(db) if voided is None else voided
        rows = _rows(db, item_ids=[item_id])
        if not db.info.get(LENIENT_TIMELINE):
            outflow_warehouses = {
                move.warehouse_id for move in moves if move.item_id == item_id and Decimal(move.qty) < 0
            }
            for warehouse_id in outflow_warehouses:
                _assert_timeline(
                    db,
                    [row for row in rows if row.warehouse_id == warehouse_id],
                    voided=voided,
                    exclude_with=set(),
                    exclude_baseline=new_ids,
                    since=on,
                    voiding=False,
                )
        item = db.get(Item, item_id)
        if item is not None:
            valued = replay(rows, voided, active_costs(db, [item_id]), issue_return_sources(db, [item_id]))
            item.average_cost = valued[-1].average if valued else Decimal(0)
    db.flush()


def guard_void(db: Session, source_types: Iterable[str], source_id: UUID) -> None:
    """ابطالی که ورودِ گذشته را برمی‌دارد نباید خروجِ بعدی را بی‌پشتوانه کند.

    گاردِ قدیمی موجودیِ **امروز** را می‌سنجید: رسیدِ ۱۰تاییِ اولِ ماه، خروجِ ۱۰تاییِ
    پنجم و رسیدِ ۱۰تاییِ دهم — ابطالِ رسیدِ اول امروز صفر می‌گذارد و پاس می‌شد، در
    حالی که خروجِ پنجم از انبارِ خالی بیرون رفته بود. برداشتنِ خروج هیچ‌وقت منفی
    نمی‌سازد، پس فقط ورودها سنجیده می‌شوند.
    """
    types = tuple(source_types)
    assert_not_adjusted(db, types, source_id)
    doc_rows = db.execute(
        select(*_COLUMNS).where(StockLedger.source_id == source_id, StockLedger.source_type.in_(types))
    ).all()
    inflows: dict[tuple[UUID, UUID], date] = {}
    for row in doc_rows:
        if Decimal(row.qty) <= 0:
            continue
        key = (row.item_id, row.warehouse_id)
        inflows[key] = row.entry_date if key not in inflows else min(inflows[key], row.entry_date)
    if not inflows:
        return
    voided = voided_sources(db)
    exclude = {row.id for row in doc_rows}
    for (item_id, warehouse_id), since in inflows.items():
        _assert_timeline(
            db,
            _rows(db, item_ids=[item_id], warehouse_id=warehouse_id),
            voided=voided,
            exclude_with=exclude,
            exclude_baseline=set(),
            since=since,
            voiding=True,
        )


def settle_void(db: Session, item_ids: Iterable[UUID]) -> None:
    """پس از علامتِ ابطال: میانگینِ هر کالای درگیر از بازپخش.

    **هر ابطالی، نه فقط ابطالِ ورود.** برداشتنِ یک خروج هم میانگین را عوض می‌کند،
    چون وزنِ ورودهای بعدی را تغییر می‌دهد: خرید ۱۰@۱۰۰۰، خروج ۱۰، خرید ۱۰@۲۰۰۰
    میانگینِ ۲۰۰۰ می‌دهد؛ بی آن خروج، ۱۵۰۰. ابطالِ خروج و انتقال تا امروز
    بازمحاسبه نمی‌کرد.
    """
    db.flush()
    for item_id in sorted(set(item_ids), key=str):
        item = db.get(Item, item_id)
        if item is not None:
            recompute(db, item)
    db.flush()


# ─────────────────────────── گزارش ───────────────────────────


@dataclass
class Position:
    """وضعیتِ ریالی و مقداریِ یک کالا در یک بازه."""

    item_id: UUID
    opening_qty: Decimal = Decimal(0)
    opening_value: Decimal = Decimal(0)
    in_qty: Decimal = Decimal(0)
    in_value: Decimal = Decimal(0)
    out_qty: Decimal = Decimal(0)
    out_value: Decimal = Decimal(0)
    closing_qty: Decimal = Decimal(0)
    closing_value: Decimal = Decimal(0)
    #: جمعِ «مقدار × بهای ثبت‌شده» — همان چیزی که اسناد در دفتر نوشته‌اند.
    book_value: Decimal = Decimal(0)
    #: میانگینِ کلِ شرکت در پایانِ بازه.
    average: Decimal = Decimal(0)
    stale_from: date | None = None
    stale_count: int = 0
    #: انبار ← [مقدار، ارزش، ارزشِ ثبت‌شده] در پایانِ بازه.
    by_warehouse: dict = field(default_factory=dict)


def _origin_types(rows: Sequence) -> dict[UUID, str]:
    return {row.source_id: row.source_type for row in rows if row.source_type != VOID_SOURCE and row.source_id}


def positions(
    db: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    warehouse_id: UUID | None = None,
    item_ids: Iterable[UUID] | None = None,
) -> dict[UUID, Position]:
    """مانده‌ی اول، ورود، خروج و مانده‌ی پایانِ هر کالا — به مقدار **و** ریال.

    **میانگین همیشه مالِ کلِ شرکت است**، حتی وقتی گزارش یک انبار را می‌خواهد: بازپخش
    روی همه‌ی انبارها اجرا می‌شود و فیلترِ انبار فقط در جمع‌زدن اعمال می‌شود.

    **انتقالِ درونی** در گزارشِ کلِ شرکت ورود و خروج نیست — مقدار و ارزشش صفر است
    و فقط ستون‌ها را باد می‌کرد. در گزارشِ یک انبار، واقعاً ورود یا خروجِ همان انبار است.
    """
    ids = None if item_ids is None else list(item_ids)
    voided, active, sources = context(db, ids)
    result: dict[UUID, Position] = {}
    for item_id, group in groupby(_rows(db, item_ids=ids, until=date_to), key=lambda row: row.item_id):
        rows = list(group)
        origin = _origin_types(rows)
        position = Position(item_id=item_id)
        for valued in replay(rows, voided, active, sources):
            row = valued.row
            position.average = valued.average
            if warehouse_id is not None and row.warehouse_id != warehouse_id:
                continue
            qty = valued.qty
            book = qty * valued.recorded_cost
            slot = position.by_warehouse.setdefault(row.warehouse_id, [Decimal(0), Decimal(0), Decimal(0)])
            slot[0] += qty
            slot[1] += valued.value
            slot[2] += book
            position.closing_qty += qty
            position.closing_value += valued.value
            position.book_value += book
            if valued.stale:
                position.stale_count += 1
                position.stale_from = position.stale_from or row.entry_date
            if date_from is not None and row.entry_date < date_from:
                position.opening_qty += qty
                position.opening_value += valued.value
                continue
            kind = origin.get(row.source_id, row.source_type) if row.source_type == VOID_SOURCE else row.source_type
            if warehouse_id is None and kind in TRANSFER_SOURCES:
                continue
            if qty > 0:
                position.in_qty += qty
                position.in_value += valued.value
            elif qty < 0:
                position.out_qty -= qty
                position.out_value -= valued.value
        result[item_id] = position
    return result


def rial(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal(1), rounding=ROUND_HALF_UP)


def kardex_lines(
    db: Session,
    item_id: UUID,
    *,
    warehouse_id: UUID | None,
    date_from: date | None,
    date_to: date | None,
) -> dict:
    """ردیف‌های کاردکس با ارزش — به ترتیبِ زمان، نه ترتیبِ ثبت."""
    voided, active, sources = context(db, [item_id])
    rows = _rows(db, item_ids=[item_id], until=date_to)
    origin = _origin_types(rows)
    valued = replay(rows, voided, active, sources)
    numbers = document_numbers(
        db,
        {
            (origin.get(row.source_id, row.source_type) if row.source_type == VOID_SOURCE else row.source_type, row.source_id)
            for row in rows
        },
    )

    opening_qty = opening_value = Decimal(0)
    balance_qty = balance_value = Decimal(0)
    total_in = total_out = value_in = value_out = Decimal(0)
    average = Decimal(0)
    stale_count = 0
    lines = []
    for move in valued:
        row = move.row
        average = move.average
        if warehouse_id is not None and row.warehouse_id != warehouse_id:
            continue
        qty = move.qty
        balance_qty += qty
        balance_value += move.value
        if date_from is not None and row.entry_date < date_from:
            opening_qty += qty
            opening_value += move.value
            continue
        kind = origin.get(row.source_id, row.source_type) if row.source_type == VOID_SOURCE else row.source_type
        number = numbers.get((kind, row.source_id))
        #: برچسب خودِ نوع است و شماره جدا می‌آید — قراردادِ کاردکس برای موبایل و خروجیِ CSV.
        label = SOURCE_LABELS.get(kind, kind)
        if row.source_type == VOID_SOURCE:
            label = f"ابطالِ {label}"
        line_in = qty if qty > 0 else Decimal(0)
        line_out = -qty if qty < 0 else Decimal(0)
        total_in += line_in
        total_out += line_out
        value_in += move.value if qty > 0 else Decimal(0)
        value_out += -move.value if qty < 0 else Decimal(0)
        stale_count += 1 if move.stale else 0
        lines.append(
            {
                "entry_date": row.entry_date,
                "source_type": row.source_type,
                "source_label": label,
                "source_id": row.source_id,
                "source_number": number,
                "voided": move.voided,
                "qty_in": line_in,
                "qty_out": line_out,
                "unit_cost": move.cost,
                "recorded_unit_cost": move.recorded_cost,
                "adjusted": move.adjusted,
                "stale": move.stale,
                "value_in": rial(move.value) if qty > 0 else Decimal(0),
                "value_out": rial(-move.value) if qty < 0 else Decimal(0),
                "balance_qty": balance_qty,
                "balance_value": rial(balance_value),
                "average_cost": move.average,
            }
        )
    return {
        "opening_qty": opening_qty,
        "opening_value": rial(opening_value),
        "lines": lines,
        "total_in": total_in,
        "total_out": total_out,
        "total_value_in": rial(value_in),
        "total_value_out": rial(value_out),
        "closing_qty": balance_qty,
        "closing_value": rial(balance_value),
        "average_cost": average,
        "stale_count": stale_count,
    }


def stale_items(db: Session, *, until: date | None = None) -> list[dict]:
    """کالاهایی که ارزش‌گذاری‌شان منقضی است — از کِی، چند حرکت، چه‌قدر، و چرا.

    «چرا» از خودِ دفتر درمی‌آید. اولین حرکتِ منقضی را `S` بنامیم؛ علت ردیفی است که
    `seq`اش از `S` بزرگ‌تر است (بعد از آن ثبت شده) ولی در زمان پیش از آن می‌نشیند:
    یا سندِ پیش‌تاریخ است، یا جبرانِ ابطالِ سندی که پیش از `S` بوده. اگر هیچ‌کدام
    نبود، بهای خودِ `S` از روزِ ثبت با میانگینِ آن روز نمی‌خوانده — دفتری که پیش
    از ترتیبِ تاریخی ثبت شده، یا انبارگردانی‌ای که بهایش را روزِ بازکردنِ جلسه گرفته.
    """
    voided, active, sources = context(db)
    found = []
    for item_id, group in groupby(_rows(db, until=until), key=lambda row: row.item_id):
        rows = list(group)
        valued = replay(rows, voided, active, sources)
        stale = [move for move in valued if move.stale]
        if not stale:
            continue
        first = stale[0].row
        first_key = (first.entry_date, first.seq)
        origin = _origin_types(rows)
        doc_position: dict[UUID, tuple] = {}
        for row in rows:
            if row.source_type != VOID_SOURCE and row.source_id is not None:
                key = (row.entry_date, row.seq)
                doc_position[row.source_id] = min(doc_position.get(row.source_id, key), key)
        causes: list[tuple[str, str, UUID | None]] = []
        for row in rows:
            if row.seq <= first.seq:
                continue
            if row.source_type == VOID_SOURCE:
                position = doc_position.get(row.source_id)
                if position is not None and position < first_key:
                    cause = ("void", origin.get(row.source_id, VOID_SOURCE), row.source_id)
                else:
                    continue
            elif (row.entry_date, row.seq) < first_key:
                cause = ("backdated", row.source_type, row.source_id)
            else:
                continue
            if cause not in causes:
                causes.append(cause)
        found.append(
            {
                "item_id": item_id,
                "from_date": first.entry_date,
                "count": len(stale),
                "difference": sum((move.value - move.qty * move.recorded_cost for move in valued), Decimal(0)),
                "causes": causes,
            }
        )
    return found
