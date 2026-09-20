"""مانده‌ی بارِ ورودی (بچ) — از دفترِ انبار، نه از یک ستونِ شمارنده.

تا پیش از مهاجرتِ ۰۱۷۱، `stock_batches.qty` ادعا می‌کرد «مانده‌ی سالمِ این بار»
است ولی **هیچ فروشی، هیچ خروجی و هیچ انتقالی کمش نمی‌کرد** — فقط تعدیلِ دستی،
برگشت از خرید و ابطال. بارِ ۱۰۰۰تایی که تمامش فروخته شده بود هنوز ۱۰۰۰ نشان
می‌داد.

حالا مانده از `stock_ledger.batch_id` مشتق می‌شود، دقیقاً همان‌طور که موجودیِ
کالا از روزِ اول `SUM(qty)` بوده. هیچ ستونی این عدد را نگه نمی‌دارد تا کهنه شود.

## چرا همه‌ی بارها مشتق نمی‌شوند — و چرا این عمدی است

بارهای **پیش از** ۰۱۷۱ ورودشان برچسب خورده (جایی که بی‌ابهام بود) ولی خروجشان
هرگز برچسب نداشته. اگر همان‌ها را هم مشتق کنیم، عددشان از مانده‌ی واقعی بیشتر
درمی‌آید؛ و باری که اصلاً ردیفِ ورودیِ برچسب‌خورده ندارد (بارِ دستی، که هیچ حرکتِ
انباری نمی‌سازد) به **صفر** مشتق می‌شود — یک دروغِ بااعتمادبه‌نفس، جایی که ستونِ
قدیمی دست‌کم یک راستِ کهنه بود.

پس دو حالت داریم و صریح اعلامشان می‌کنیم:

    qty_source = 'ledger'  → ورودِ این بار در دفتر برچسب دارد؛ عدد دقیق است
    qty_source = 'legacy'  → ندارد؛ عددِ ستونِ قدیمی با نشانه نشان داده می‌شود

معیارِ تفکیک **وجودِ یک حرکتِ ورودیِ برچسب‌خورده** است، نه «هر حرکتی»: تعدیلِ
کسری روی یک بارِ قدیمی یک ردیفِ *منفیِ* برچسب‌خورده می‌سازد، و اگر همان کافی
می‌بود، مانده‌ی آن بار ناگهان منفی مشتق می‌شد.

ستونِ `qty` عمداً زنده می‌ماند و همان‌طور که تا امروز نگهداری می‌شده نگهداری
می‌شود — چون برای بارهای `legacy` هنوز **تنها** عددِ موجود است. وقتی گزارشِ
مغایرت برای یک مستأجر پاک شد، آن ستون دیگر خواننده ندارد.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.advanced_inventory import HOLD_STATUS_LABELS, StockBatch
from app.models.inventory import StockAdjustment, StockLedger

if TYPE_CHECKING:  # pragma: no cover - فقط برای نوع، نه زمانِ اجرا
    from app.models.inventory import Item

#: سندِ «انتسابِ موجودی به بار» — جفتِ حرکتِ جمع‌صفری که موجودیِ ناشناسِ قدیمی را
#: روی یک بارِ اول‌دوره می‌نشاند. در `valuation.AVERAGE_INFLOWS` ثبت شده تا ورودی‌اش
#: با میانگینِ جاری ارزش‌گذاری شود و میانگین **ساختاراً** دست‌نخورده بماند.
BATCH_OPENING = "batch_opening"

#: منشأهای مانده — در پاسخِ API هم همین دو واژه می‌آیند.
QTY_SOURCE_LEDGER = "ledger"
QTY_SOURCE_LEGACY = "legacy"


def on_hand(db: Session, batch_ids: list[UUID]) -> dict[UUID, Decimal]:
    """مانده‌ی هر بار از دفتر: `SUM(qty)` روی حرکت‌های برچسب‌خورده.

    بارِ بدونِ حرکت در خروجی **نمی‌آید** (نه با صفر) — تا فراخوان بتواند «حرکتی
    نداشته» را از «مانده‌اش صفر است» تشخیص دهد.
    """
    if not batch_ids:
        return {}
    rows = (
        db.query(StockLedger.batch_id, func.coalesce(func.sum(StockLedger.qty), 0))
        .filter(StockLedger.batch_id.in_(batch_ids))
        .group_by(StockLedger.batch_id)
        .all()
    )
    return {bid: Decimal(total) for bid, total in rows}


def with_ledger_inbound(db: Session, batch_ids: list[UUID]) -> set[UUID]:
    """بارهایی که **ورودشان** در دفتر برچسب خورده — مرزِ ledger/legacy."""
    if not batch_ids:
        return set()
    rows = (
        db.query(StockLedger.batch_id)
        .filter(StockLedger.batch_id.in_(batch_ids), StockLedger.qty > 0)
        .distinct()
        .all()
    )
    return {bid for (bid,) in rows}


def defect_qty(db: Session, batch_ids: list[UUID]) -> dict[UUID, Decimal]:
    """کسری/معیوب/ضایعاتِ ثبت‌شده روی هر بار — از سندِ تعدیل، نه از تفاضلِ ستون‌ها.

    پیش از این `received_qty − qty` حساب می‌شد، که با راست‌شدنِ مانده بی‌معنا
    می‌شود: فروش هم مانده را کم می‌کند و فروش کسری نیست. تعدیلِ **باطل‌شده**
    شمرده نمی‌شود، چون ابطال یعنی آن کسری هرگز رخ نداد.
    """
    if not batch_ids:
        return {}
    rows = (
        db.query(
            StockAdjustment.batch_id,
            func.coalesce(func.sum(case((StockAdjustment.qty_diff < 0, -StockAdjustment.qty_diff), else_=0)), 0),
        )
        .filter(StockAdjustment.batch_id.in_(batch_ids), StockAdjustment.voided_at.is_(None))
        .group_by(StockAdjustment.batch_id)
        .all()
    )
    return {bid: Decimal(total) for bid, total in rows}


def qty_view(db: Session, batches: list[StockBatch]) -> dict[UUID, dict]:
    """برای هر بار: مانده‌ی نمایشی، منشأش، و هر دو عددِ خام کنار هم.

    هر دو عدد برمی‌گردند حتی وقتی یکی انتخاب شده — گزارشِ مغایرت دقیقاً از همین
    اختلاف ساخته می‌شود و نباید پرسشِ دوم بزند.
    """
    ids = [b.id for b in batches]
    ledger = on_hand(db, ids)
    tagged = with_ledger_inbound(db, ids)
    out: dict[UUID, dict] = {}
    for batch in batches:
        legacy_qty = Decimal(batch.qty or 0)
        ledger_qty = ledger.get(batch.id)
        is_tagged = batch.id in tagged
        out[batch.id] = {
            "qty": (ledger_qty if is_tagged else legacy_qty),
            "qty_source": QTY_SOURCE_LEDGER if is_tagged else QTY_SOURCE_LEGACY,
            "ledger_qty": (ledger_qty if ledger_qty is not None else Decimal(0)),
            "legacy_qty": legacy_qty,
        }
    return out


def untagged_on_hand(db: Session, item_id: UUID, warehouse_id: UUID | None = None) -> Decimal:
    """موجودیِ کالا که به **هیچ باری** منتسب نیست.

    گاردِ روشن‌کردنِ «ردیابیِ بار» روی همین می‌نشیند: تا وقتی صفر نشده، جمعِ
    بارها هرگز با موجودیِ کالا برابر نمی‌شود.
    """
    q = db.query(func.coalesce(func.sum(StockLedger.qty), 0)).filter(
        StockLedger.item_id == item_id, StockLedger.batch_id.is_(None)
    )
    if warehouse_id is not None:
        q = q.filter(StockLedger.warehouse_id == warehouse_id)
    return Decimal(q.scalar())


def ledger_rows(db: Session, batch_id: UUID) -> list[StockLedger]:
    """گردشِ یک بار، به ترتیبِ زمانی — همان ترتیبی که کاردکس دارد."""
    return (
        db.query(StockLedger)
        .filter(StockLedger.batch_id == batch_id)
        .order_by(StockLedger.entry_date, StockLedger.seq)
        .all()
    )


def reconciliation(db: Session, batches: list[StockBatch]) -> list[dict]:
    """بارهایی که مانده‌شان از دفتر درنمی‌آید — با دلیلِ هرکدام.

    این **گزارش** است نه گارد: هیچ‌کدام از این ردیف‌ها مانعِ کار نمی‌شوند. کاربر
    با «هم‌ترازسازی» یکی‌یکی می‌بنددشان، یا رهایشان می‌کند و بارهای تازه از همان
    اول درست‌اند.
    """
    view = qty_view(db, batches)
    rows: list[dict] = []
    for batch in batches:
        v = view[batch.id]
        if v["qty_source"] == QTY_SOURCE_LEDGER:
            continue
        rows.append(
            {
                "batch_id": batch.id,
                "item_id": batch.item_id,
                "warehouse_id": batch.warehouse_id,
                "batch_number": batch.batch_number,
                "received_date": batch.received_date,
                "legacy_qty": v["legacy_qty"],
                "ledger_qty": v["ledger_qty"],
                "delta": v["legacy_qty"] - v["ledger_qty"],
                "reason": _reason(batch),
            }
        )
    return rows


#: دلیل‌ها ماشین‌خوان‌اند تا رابط بتواند گروه‌بندی کند؛ برچسبِ فارسی سمتِ رابط است.
REASON_MANUAL = "manual"
REASON_PRE_TRACKING = "pre_tracking"
REASON_AMBIGUOUS = "ambiguous"


def _reason(batch: StockBatch) -> str:
    if batch.source_id is None or batch.source_type == "manual":
        #: بارِ دستی اصلاً حرکتِ انباری نمی‌سازد — موجودی‌اش از سندِ دیگری آمده.
        return REASON_MANUAL
    if batch.source_type in ("purchase_invoice", "warehouse_receipt"):
        #: سندش برچسب‌پذیر بود ولی مهاجرت از آن رد شد: بیش از یک ردیفِ همان کالا
        #: در همان سند بود و انتسابِ خودکار حدس می‌شد.
        return REASON_AMBIGUOUS
    return REASON_PRE_TRACKING


# ── وضعیتِ مشتق، قابلیتِ فروش، و FEFO (مهاجرتِ ۰۱۷۲) ────────────────────
def days_to_expiry(batch: StockBatch, on: date) -> int | None:
    """روزهای مانده تا انقضا. تهی = این بار تاریخِ انقضا ندارد (§۲۸)."""
    if batch.expiry_date is None:
        return None
    return (batch.expiry_date - on).days


#: واژگانِ وضعیتِ §۳. فقط سه‌تایش ستون دارد (`qc_status`، `hold_status`،
#: `is_closed`)؛ بقیه از عدد و تاریخ مشتق می‌شوند.
#:
#: **`received` عمداً در این فهرست نیست.** در کوبیتا بینِ «رسید» و «قابلِ فروش»
#: مرحله‌ی سومی (انبارش/put-away) وجود ندارد، پس `received` و `available` دقیقاً
#: یک حالت‌اند. برگرداندنِ هر دو یعنی ادعای تفکیکی که پشتش چیزی نیست.
DERIVED_STATUSES = (
    "draft", "qc_pending", "available", "partially_reserved", "fully_reserved",
    "near_expiry", "blocked", "recalled", "expired", "depleted", "closed",
)


def derived_status(
    batch: StockBatch,
    *,
    physical: Decimal,
    reserved: Decimal,
    has_inbound: bool,
    shelf_life_days: int | None,
    on: date,
) -> str:
    """وضعیتِ نمایشیِ یک بار — **محاسبه می‌شود، ذخیره نمی‌شود.**

    ترتیب از شدید به خفیف است و اولین تطابق برنده: باری که هم فراخوان شده و هم
    منقضی است، «فراخوان‌شده» نشان داده می‌شود چون آن است که باید کاری در موردش
    بشود.
    """
    if batch.hold_status == "recalled":
        return "recalled"
    if batch.hold_status == "blocked" or batch.qc_status == "failed":
        return "blocked"
    if batch.is_closed:
        return "closed"
    if not has_inbound:
        #: ردیفِ باری که هیچ حرکتِ انباری پشتش نیست — هنوز واقعاً وارد نشده.
        return "draft"
    days = days_to_expiry(batch, on)
    if days is not None and days < 0:
        return "expired"
    if physical <= 0:
        return "depleted"
    if batch.qc_status == "pending":
        return "qc_pending"
    if days is not None and shelf_life_days is not None and days < shelf_life_days:
        return "near_expiry"
    if reserved > 0:
        return "fully_reserved" if reserved >= physical else "partially_reserved"
    return "available"


def sellable_qty(
    batch: StockBatch,
    *,
    physical: Decimal,
    reserved: Decimal,
    shelf_life_days: int | None,
    on: date,
) -> Decimal:
    """مقدارِ واقعاً قابلِ فروشِ این بار (§۴ §۲۹).

        available = physical − reserved
        sellable  = 0  اگر بار منعقد/مردود/بسته/منقضی است
                       یا عمرِ مانده‌اش از حداقلِ کالا کمتر است

    **موجودیِ فیزیکی هرگز تکان نمی‌خورد.** §۲۹ صریح است: بارِ نزدیک به انقضا
    ممکن است هنوز موجودی داشته باشد ولی فروختنی نباشد. این دو عدد جدا می‌مانند.
    """
    if batch.hold_status != "none" or batch.qc_status != "passed" or batch.is_closed:
        return Decimal(0)
    days = days_to_expiry(batch, on)
    if days is not None:
        if days < 0:
            return Decimal(0)
        if shelf_life_days is not None and days < shelf_life_days:
            return Decimal(0)
    return max(physical - reserved, Decimal(0))


def numbers(db: Session, batches: list[StockBatch], item_by_id: dict[UUID, "Item"], on: date) -> dict[UUID, dict]:
    """چهار عددِ §۴ به‌علاوه‌ی وضعیتِ مشتق، برای هر بار.

    `reserved` فعلاً همیشه صفر است چون موتورِ رزرو هنوز نیامده (گامِ بعد). شکلِ
    خروجی از همین حالا جا دارد تا وصل‌کردنش یک خط باشد، نه بازنویسیِ مصرف‌کننده‌ها.
    """
    ids = [b.id for b in batches]
    ledger = on_hand(db, ids)
    tagged = with_ledger_inbound(db, ids)
    out: dict[UUID, dict] = {}
    for batch in batches:
        has_inbound = batch.id in tagged
        physical = ledger.get(batch.id, Decimal(0)) if has_inbound else Decimal(batch.qty or 0)
        reserved = Decimal(0)
        item = item_by_id.get(batch.item_id)
        shelf = getattr(item, "minimum_sellable_shelf_life_days", None) if item else None
        out[batch.id] = {
            "physical_qty": physical,
            "reserved_qty": reserved,
            "available_qty": max(physical - reserved, Decimal(0)),
            "sellable_qty": sellable_qty(
                batch, physical=physical, reserved=reserved, shelf_life_days=shelf, on=on
            ),
            "days_to_expiry": days_to_expiry(batch, on),
            "status": derived_status(
                batch,
                physical=physical,
                reserved=reserved,
                has_inbound=has_inbound,
                shelf_life_days=shelf,
                on=on,
            ),
        }
    return out


def fefo_order(batches: list[StockBatch]) -> list[StockBatch]:
    """First Expired, First Out (§۱۱).

    بارِ **بدونِ** تاریخِ انقضا آخر می‌آید، نه اول: `None` در مرتب‌سازی یعنی
    «نمی‌دانیم»، و «نمی‌دانم» نباید جلوی باری بیفتد که تاریخش دارد می‌گذرد.
    بینِ بارهای هم‌تاریخ، قدیمی‌ترِ ورودی اول (FIFO به‌عنوانِ داورِ دوم).
    """
    return sorted(
        batches,
        key=lambda b: (
            b.expiry_date is None,
            b.expiry_date or date.max,
            b.received_date or date.max,
            b.batch_number or "",
        ),
    )


def suggest_fefo(
    db: Session, item: "Item", warehouse_id: UUID, qty: Decimal, on: date
) -> list[tuple[StockBatch, Decimal]]:
    """تقسیمِ یک مقدار بینِ بارهای قابلِ فروش، به ترتیبِ FEFO.

    اگر موجودیِ قابلِ فروش کفاف ندهد، **هرچه هست** برمی‌گردد و تصمیمِ رد یا قبول
    با فراخوان است — این‌جا پیشنهاد می‌دهیم، گارد جای دیگری است.
    """
    rows = (
        db.query(StockBatch)
        .filter(StockBatch.item_id == item.id, StockBatch.warehouse_id == warehouse_id)
        .all()
    )
    if not rows:
        return []
    nums = numbers(db, rows, {item.id: item}, on)
    plan: list[tuple[StockBatch, Decimal]] = []
    remaining = Decimal(qty)
    for batch in fefo_order(rows):
        if remaining <= 0:
            break
        take = min(nums[batch.id]["sellable_qty"], remaining)
        if take <= 0:
            continue
        plan.append((batch, take))
        remaining -= take
    return plan


def assert_allocation(
    db: Session, item: "Item", warehouse_id: UUID, allocations: list[tuple[UUID, Decimal]], on: date
) -> None:
    """تخصیصِ صریحِ کاربر را می‌سنجد — **داخلِ قفلِ کالا** صدا زده می‌شود.

    §۱۱ می‌گوید کاربر باید بتواند FEFO را نقض کند، پس بارِ نزدیک‌تر به انقضا
    اجباری نیست. ولی سه چیز اجباری است: بار مالِ همین کالا و همین انبار باشد،
    منعقد/مردود/بسته نباشد، و مقدارش را داشته باشد.
    """
    if not allocations:
        return
    ids = [bid for bid, _ in allocations]
    rows = db.query(StockBatch).filter(StockBatch.id.in_(ids)).all()
    by_id = {b.id: b for b in rows}
    nums = numbers(db, rows, {item.id: item}, on)

    wanted: dict[UUID, Decimal] = {}
    for bid, take in allocations:
        wanted[bid] = wanted.get(bid, Decimal(0)) + Decimal(take)

    for bid, take in wanted.items():
        batch = by_id.get(bid)
        if batch is None or batch.item_id != item.id or batch.warehouse_id != warehouse_id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"بارِ انتخاب‌شده به «{item.name}» در این انبار تعلق ندارد",
            )
        if batch.hold_status != "none":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"بارِ «{batch.batch_number}» {HOLD_STATUS_LABELS[batch.hold_status]} است و از آن خروج ثبت نمی‌شود",
            )
        if batch.qc_status == "failed":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"بارِ «{batch.batch_number}» در کنترلِ کیفیت مردود شده و فروختنی نیست",
            )
        if batch.is_closed:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"بارِ «{batch.batch_number}» بسته شده است؛ بارِ دیگری انتخاب کنید",
            )
        available = nums[bid]["available_qty"]
        if take > available:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"موجودیِ بارِ «{batch.batch_number}» کافی نیست "
                f"(موجود: {available.normalize():f}، درخواستی: {Decimal(take).normalize():f})",
            )


def plan_outflow(
    db: Session,
    item: "Item",
    warehouse_id: UUID,
    qty: Decimal,
    on: date,
    *,
    wanted: list[tuple[UUID, Decimal]] | None = None,
) -> list[tuple[UUID, Decimal]]:
    """تخصیصِ نهاییِ یک خروج: یا همان چیزی که کاربر گفته، یا پیشنهادِ FEFO.

    **کالای بی‌ردیابی هیچ‌وقت به این‌جا نمی‌رسد** و تخصیصش خالی می‌ماند — همان
    «پیش‌فرض = رفتارِ دیروز». برای کالای ردیابی‌شده اگر FEFO هم کفاف ندهد، خطای
    فارسی می‌دهد تا کاربر بداند کدام بار کم آورد، نه فقط «موجودی کافی نیست».
    """
    if not item.is_batch_tracked:
        return []
    if wanted:
        assert_allocation(db, item, warehouse_id, wanted, on)
        return [(bid, Decimal(take)) for bid, take in wanted]

    plan = suggest_fefo(db, item, warehouse_id, qty, on)
    covered = sum((take for _, take in plan), Decimal(0))
    if covered < qty:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"موجودیِ قابلِ فروشِ «{item.name}» در بارهای این انبار کافی نیست "
            f"(قابلِ فروش: {covered.normalize():f}، درخواستی: {Decimal(qty).normalize():f}). "
            "بارِ منقضی، مسدود یا در انتظارِ کنترلِ کیفیت در این عدد شمرده نمی‌شود.",
        )
    return [(batch.id, take) for batch, take in plan]


def mirror_batch(db: Session, batch_id: UUID, to_warehouse_id: UUID, user) -> StockBatch:
    """بارِ آینه‌ی یک بار در انبارِ مقصد — ساخته می‌شود اگر نباشد.

    شناسنامه‌ی بار (شماره، انقضا، تاریخِ تولید، بهای واحد، تأمین‌کننده) کپی می‌شود
    چون **همان کالای فیزیکی** است که جابه‌جا شده، نه یک بارِ تازه. مقدار کپی
    نمی‌شود: آن از دفتر مشتق می‌گردد.

    `location_id` عمداً کپی **نمی‌شود** — قفسه‌ی انبارِ مبدأ در انبارِ مقصد وجود
    ندارد و کپی‌کردنش یعنی ارجاع به جایی که نیست.

    ایده‌آمپوتنت: انتقالِ دوم از همان بار به همان انبار، بارِ سومی نمی‌سازد.
    """
    source = db.get(StockBatch, batch_id)
    if source is None:  # pragma: no cover - فراخوان همیشه بارِ معتبر می‌دهد
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "بارِ مبدأ پیدا نشد")

    existing = (
        db.query(StockBatch)
        .filter(
            StockBatch.parent_batch_id == source.id,
            StockBatch.warehouse_id == to_warehouse_id,
        )
        .first()
    )
    if existing is not None:
        return existing

    mirror = StockBatch(
        item_id=source.item_id,
        warehouse_id=to_warehouse_id,
        batch_number=source.batch_number,
        expiry_date=source.expiry_date,
        production_date=source.production_date,
        unit_cost=source.unit_cost,
        consumer_price=source.consumer_price,
        supplier_batch_code=source.supplier_batch_code,
        supplier_id=source.supplier_id,
        qc_status=source.qc_status,
        #: مقدار از دفتر می‌آید؛ این ستون فقط برای بارهای پیش از ردیابی معنا دارد.
        qty=Decimal(0),
        received_qty=Decimal(0),
        source_type="transfer_in",
        source_id=None,
        received_date=source.received_date,
        parent_batch_id=source.id,
        notes=f"آینه‌ی بارِ «{source.batch_number}» از انتقالِ بینِ انبار",
        created_by_id=user.id,
    )
    db.add(mirror)
    db.flush()
    return mirror


def align_stock_to_batch(
    db: Session,
    item: "Item",
    warehouse_id: UUID,
    *,
    batch_number: str,
    user,
    on: date,
    expiry_date: date | None = None,
    production_date: date | None = None,
) -> StockBatch:
    """موجودیِ بی‌برچسبِ یک کالا را روی یک بارِ اول‌دوره می‌نشاند — **جمعِ صفر**.

    این راهِ عبورِ گاردِ «ردیابیِ بار» است. بدونِ آن، کالایی که سال‌ها موجودی
    داشته هرگز نمی‌توانست ردیابی بگیرد و پیامِ خطا به مسیری اشاره می‌کرد که وجود
    ندارد.

    دو حرکتِ هم‌تاریخ نوشته می‌شود:

        −X  بی‌برچسب        (موجودیِ قدیمیِ ناشناس بیرون می‌رود)
        +X  روی بارِ تازه    (همان کالا، حالا با هویت)

    موجودیِ کالا **تکان نمی‌خورد** چون جمعشان صفر است. میانگینِ موزون هم تکان
    نمی‌خورد و این تصادفی نیست: `batch_opening` در `AVERAGE_INFLOWS` ثبت شده، پس
    ورودی با همان میانگینِ جاری ارزش‌گذاری می‌شود نه با عددی که ما حساب کرده‌ایم.

    و چون سندِ واقعی است نه جادو، در کاردکس دیده می‌شود و ابطال هم دارد.
    """
    from app.services.inventory import lock_items

    number = (batch_number or "").strip()
    if not number:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "شماره‌ی بار نمی‌تواند خالی باشد")

    lock_items(db, [item.id])
    untagged = untagged_on_hand(db, item.id, warehouse_id)
    if untagged <= 0:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"«{item.name}» در این انبار موجودیِ بدونِ بار ندارد؛ چیزی برای انتساب نیست.",
        )

    unit_cost = Decimal(item.average_cost or 0)
    batch = StockBatch(
        item_id=item.id,
        warehouse_id=warehouse_id,
        batch_number=number,
        expiry_date=expiry_date,
        production_date=production_date,
        qty=untagged,
        received_qty=untagged,
        unit_cost=unit_cost,
        source_type=BATCH_OPENING,
        source_id=None,
        received_date=on,
        notes="انتسابِ موجودیِ موجود به بار (اول دوره)",
        created_by_id=user.id,
    )
    db.add(batch)
    db.flush()

    moves = [
        StockLedger(
            item_id=item.id, warehouse_id=warehouse_id, qty=-untagged, unit_cost=unit_cost,
            entry_date=on, source_type=BATCH_OPENING, source_id=batch.id, batch_id=None,
        ),
        StockLedger(
            item_id=item.id, warehouse_id=warehouse_id, qty=untagged, unit_cost=unit_cost,
            entry_date=on, source_type=BATCH_OPENING, source_id=batch.id, batch_id=batch.id,
        ),
    ]
    for move in moves:
        db.add(move)
    from app.services import valuation

    valuation.settle_posting(db, moves)
    db.flush()
    return batch
