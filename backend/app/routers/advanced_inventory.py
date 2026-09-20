from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value

from app.database import get_db
from app.deps import require_permission
from app.models.advanced_inventory import PriceList, PriceListItem, StockBatch, StockBatchSerial
from app.models.inventory import Contact, Item, StockAdjustment, StockLedger
from app.models.user import User
from app.schemas.advanced_inventory import (
    BatchCloseIn,
    BatchSubstitutionIn,
    BatchHoldIn,
    BatchReconciliationOut,
    BatchTraceOut,
    PickingRowOut,
    SerialAssignIn,
    SerialAssignOut,
    SerialTraceOut,
    BatchAdjustIn,
    BatchSerialAddIn,
    BatchSerialOut,
    BatchSerialStatusIn,
    PriceListIn,
    PriceListItemOut,
    PriceListOut,
    PriceListUpdateIn,
    SetPricesIn,
    StockBatchIn,
    StockBatchOut,
)
from app.schemas.inventory import StockAdjustmentIn
from app.services import batches as batches_svc
from app.services import serials as serials_svc
from app.services.inventory import post_stock_adjustment

# نگاشتِ نوعِ تعدیلِ بار به متنِ فارسی (برای reasonِ سندِ حسابداری/تعدیل).
_ADJUST_REASON = {"shortage": "کسری", "defect": "معیوب", "wastage": "ضایعات"}

router = APIRouter(prefix="/api", tags=["advanced-inventory"])


# ── لیستِ قیمت ──────────────────────────────────────────
@router.get("/price-lists", response_model=list[PriceListOut])
def list_price_lists(db: Session = Depends(get_db), _=Depends(require_permission("inventory", "view"))):
    return db.query(PriceList).order_by(PriceList.created_at.desc()).all()


@router.post("/price-lists", response_model=PriceListOut, status_code=201)
def create_price_list(
    data: PriceListIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory", "create")),
):
    pl = PriceList(name=data.name, notes=data.notes, created_by_id=user.id)
    db.add(pl)
    db.flush()
    db.refresh(pl)
    return pl


@router.patch("/price-lists/{list_id}", response_model=PriceListOut)
def update_price_list(
    list_id: UUID,
    data: PriceListUpdateIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "update")),
):
    pl = db.get(PriceList, list_id)
    if pl is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "لیستِ قیمت یافت نشد")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(pl, key, value)
    db.flush()
    db.refresh(pl)
    return pl


@router.delete("/price-lists/{list_id}", status_code=204)
def delete_price_list(
    list_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "delete")),
):
    """اعلامیه‌ی ردیف‌دار **غیرفعال** می‌شود، حذف نمی‌شود (§۸۳ §۸۴).

    تا امروز این مسیر سخت‌حذف بود و ردیف‌هایش با `ondelete CASCADE` می‌رفتند.
    ولی فاکتورِ پارسال `price_rule_id` دارد و باید بتواند بگوید نرخش از کجا آمد؛
    حذفِ فیزیکیِ قاعده آن توضیح را برای همیشه از بین می‌برد. غیرفعال‌کردن هم
    همان کار را می‌کند — اعلامیه دیگر در حلِ قیمت شرکت نمی‌کند — بدونِ نابودکردنِ
    تاریخ. اعلامیه‌ی خالی چیزی برای از دست دادن ندارد، پس واقعاً حذف می‌شود.
    """
    pl = db.get(PriceList, list_id)
    if pl is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "لیستِ قیمت یافت نشد")
    has_rows = (
        db.query(PriceListItem.id).filter(PriceListItem.price_list_id == list_id).first() is not None
    )
    if has_rows:
        pl.is_active = False
        db.flush()
        return
    # مشتری‌هایی که این لیست را پیش‌فرض دارند رها می‌شوند (به قیمتِ پایه)، وگرنه قیدِ FK
    # حذف را با ۵۰۰ می‌شکند.
    db.query(Contact).filter(Contact.default_price_list_id == list_id).update(
        {Contact.default_price_list_id: None}, synchronize_session="evaluate"
    )
    db.delete(pl)


@router.get("/price-lists/{list_id}/items", response_model=list[PriceListItemOut])
def list_price_list_items(
    list_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "view")),
):
    pl = db.get(PriceList, list_id)
    if pl is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "لیستِ قیمت یافت نشد")
    return db.query(PriceListItem).filter(PriceListItem.price_list_id == list_id).all()


def _context_key(row) -> tuple:
    """کلیدِ یکتاییِ یک قاعده = **کلِ زمینه‌اش**، نه فقط کالا (§۳۴ §۳۸).

    یک کالا می‌تواند هم‌زمان قیمتِ عمده و خرده و صادراتی داشته باشد. همین تاپل
    است که ایندکسِ `uq_price_list_items_context` در دیتابیس نگه می‌دارد.
    """
    return (
        row.item_id,
        row.item_group_id,
        row.sale_type_id,
        row.unit_id,
        row.contact_group_id,
        row.currency_code,
    )


@router.put("/price-lists/{list_id}/items", response_model=list[PriceListItemOut])
def set_price_list_items(
    list_id: UUID,
    data: SetPricesIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "update")),
):
    """قاعده‌های فرستاده‌شده را **می‌نشاند یا به‌روز می‌کند** — چیزی را پاک نمی‌کند.

    **این مسیر تا امروز ماتریسِ قیمت را نابود می‌کرد.** اول `pl.items.clear()`
    می‌زد و بعد هرچه رسیده بود می‌نشاند؛ یعنی هر فرستنده‌ای که زمینه‌ها را
    نمی‌شناخت — و فرمِ «لیست قیمت»ِ انبار دقیقاً همین بود، چون ردیف‌ها را در یک
    نگاشتِ `item_id → price` می‌ریخت — با یک بار «ذخیره» **هر قیمتِ
    عمده/خرده/واحد/گروهِ مشتری و هر حدِ تغییرِ نرخِ آن اعلامیه را برای همیشه پاک
    می‌کرد.** بی‌صدا، بی‌خطا، و بی‌ردِ حسابرسی.

    پس «حذف با نیامدن» برداشته شد: حذفِ یک قاعده حالا مسیرِ صریحِ خودش را دارد
    (`DELETE .../items/{row_id}`). همین §۴۷ را هم آرام می‌کند — دو مدیرِ هم‌زمان
    دیگر کارِ هم را نمی‌بلعند، فقط ردیف‌های مشترک را بازنویسی می‌کنند.
    """
    pl = db.get(PriceList, list_id)
    if pl is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "لیستِ قیمت یافت نشد")

    existing = {
        _context_key(row): row
        for row in db.query(PriceListItem)
        .filter(PriceListItem.price_list_id == list_id)
        .order_by(PriceListItem.id)
        .with_for_update()
        .all()
    }

    seen: set[tuple] = set()
    for row in data.items:
        key = _context_key(row)
        if key in seen:
            continue
        seen.add(key)
        current = existing.get(key)
        if current is None:
            pl.items.append(PriceListItem(**row.model_dump()))
            continue
        for field, value in row.model_dump().items():
            setattr(current, field, value)
    db.flush()
    return db.query(PriceListItem).filter(PriceListItem.price_list_id == list_id).all()


@router.delete("/price-lists/{list_id}/items/{row_id}", status_code=204)
def delete_price_list_item(
    list_id: UUID,
    row_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "update")),
):
    """حذفِ یک قاعده‌ی قیمت — صریح، نه به‌عنوانِ عارضه‌ی جانبیِ یک ذخیره."""
    row = (
        db.query(PriceListItem)
        .filter(PriceListItem.id == row_id, PriceListItem.price_list_id == list_id)
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "قاعده‌ی قیمت یافت نشد")
    db.delete(row)


# ── بچ / بارِ ورودی / سریالِ کارتن ──────────────────────────
def _decorate_batches(db: Session, batches: list[StockBatch]) -> list[StockBatch]:
    """مانده‌ی مشتق‌شده، منشأش، کسری و شمارِ سریال را روی هر بار می‌نشاند.

    **مانده دیگر از ستون خوانده نمی‌شود.** `batches.qty_view` تصمیم می‌گیرد که
    عددِ این بار از دفتر می‌آید یا (برای بارهای پیش از ردیابی) از ستونِ قدیمی —
    و کدام را انتخاب کرده در `qty_source` صریح برمی‌گردد، تا رابط بتواند
    نشانه بگذارد به‌جای اینکه عددِ نامطمئن را مثلِ عددِ دقیق نشان دهد.
    """
    if not batches:
        return batches
    ids = [b.id for b in batches]
    counts = dict(
        db.query(StockBatchSerial.batch_id, func.count(StockBatchSerial.id))
        .filter(StockBatchSerial.batch_id.in_(ids))
        .group_by(StockBatchSerial.batch_id)
        .all()
    )
    view = batches_svc.qty_view(db, batches)
    defects = batches_svc.defect_qty(db, ids)
    #: کالاها یک‌جا خوانده می‌شوند چون «حداقلِ عمرِ مفیدِ فروش» روی کالاست، نه بار
    #: (§۲۹) — و بی آن `sellable` نمی‌تواند محاسبه شود.
    items = {
        i.id: i for i in db.query(Item).filter(Item.id.in_({b.item_id for b in batches})).all()
    }
    nums = batches_svc.numbers(db, batches, items, date.today())
    for b in batches:
        v = view[b.id]
        n = nums[b.id]
        b.physical_qty = n["physical_qty"]
        b.reserved_qty = n["reserved_qty"]
        b.available_qty = n["available_qty"]
        b.sellable_qty = n["sellable_qty"]
        b.days_to_expiry = n["days_to_expiry"]
        b.status = n["status"]
        #: **`set_committed_value` و نه انتساب ساده.** انتساب، صفت را کثیف
        #: علامت می‌زد و فلاشِ پایانِ درخواست عددِ مشتق را در ستونِ قدیمی
        #: می‌نوشت — یعنی یک درخواستِ `GET` بی‌صدا داده می‌نوشت و شاهدِ بارهای
        #: `legacy` را نابود می‌کرد. این تابع مقدار را «انگار از پایگاه‌داده
        #: خوانده شده» می‌نشاند، پس هرگز ذخیره نمی‌شود.
        set_committed_value(b, "qty", v["qty"])
        b.qty_source = v["qty_source"]
        b.ledger_qty = v["ledger_qty"]
        b.legacy_qty = v["legacy_qty"]
        b.defect_qty = defects.get(b.id, Decimal(0))
        b.serial_count = counts.get(b.id, 0)
    return batches


@router.get("/stock-batches/expiring", response_model=list[StockBatchOut])
def expiring_batches(
    days: int = Query(30, ge=0),
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "view")),
):
    cutoff = date.today() + timedelta(days=days)
    batches = (
        db.query(StockBatch)
        .filter(StockBatch.expiry_date.isnot(None), StockBatch.expiry_date <= cutoff)
        .order_by(StockBatch.expiry_date)
        .all()
    )
    return _decorate_batches(db, batches)


@router.get("/stock-batches/reconciliation", response_model=list[BatchReconciliationOut])
def batch_reconciliation(
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "view")),
):
    """بارهایی که مانده‌شان از دفترِ انبار درنمی‌آید.

    **گزارش است، نه خطا.** هیچ‌کدامِ این ردیف‌ها جلوی کاری را نمی‌گیرند؛ فقط
    می‌گویند عددِ کدام بار هنوز از ستونِ قدیمی می‌آید و چرا. بارهای تازه از
    همان اول از دفتر مشتق می‌شوند و این فهرست کوتاه‌تر و کوتاه‌تر می‌شود.
    """
    batches = db.query(StockBatch).order_by(StockBatch.received_date.desc()).all()
    return batches_svc.reconciliation(db, batches)


@router.get("/stock-batches/available", response_model=list[StockBatchOut])
def available_batches(
    item_id: UUID = Query(...),
    warehouse_id: UUID = Query(...),
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "view")),
):
    """بارهای **قابلِ فروشِ** یک کالا در یک انبار، به ترتیبِ FEFO (§۱۱).

    بارِ منقضی، مسدود، فراخوان‌شده، مردودِ کنترلِ کیفیت و بسته کنار گذاشته
    می‌شوند. بارِ بدونِ تاریخِ انقضا **آخر** می‌آید نه اول: «نمی‌دانم» نباید جلوی
    باری بیفتد که تاریخش دارد می‌گذرد.

    فرمِ خروجِ انبار این را می‌گیرد و پیش‌فرض را از رویش می‌چیند؛ کاربر می‌تواند
    نقضش کند، که خواسته‌ی صریحِ §۱۱ است.
    """
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "کالا یافت نشد")
    rows = (
        db.query(StockBatch)
        .filter(StockBatch.item_id == item_id, StockBatch.warehouse_id == warehouse_id)
        .all()
    )
    ordered = batches_svc.fefo_order(rows)
    decorated = _decorate_batches(db, ordered)
    return [b for b in decorated if b.sellable_qty > 0]


@router.get("/stock-batches", response_model=list[StockBatchOut])
def list_stock_batches(
    item_id: UUID | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "view")),
):
    q = db.query(StockBatch)
    if item_id:
        q = q.filter(StockBatch.item_id == item_id)
    # تازه‌ترین بارها بالا (received_date نزولی)، سپس انقضای نزدیک.
    batches = q.order_by(StockBatch.received_date.desc(), StockBatch.created_at.desc()).all()
    return _decorate_batches(db, batches)


@router.post("/stock-batches", response_model=StockBatchOut, status_code=201)
def create_stock_batch(
    data: StockBatchIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory", "create")),
):
    # بارِ دستی: مقدارِ اولیه = مقدارِ فعلی، منشأ = manual.
    batch = StockBatch(
        **data.model_dump(),
        received_qty=data.qty,
        source_type="manual",
        created_by_id=user.id,
    )
    db.add(batch)
    db.flush()
    db.refresh(batch)
    return _decorate_batches(db, [batch])[0]


@router.patch("/stock-batches/{batch_id}", response_model=StockBatchOut)
def update_stock_batch(
    batch_id: UUID,
    data: StockBatchIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "update")),
):
    """ویرایشِ شماره‌ی بار/انقضا/یادداشت (نه مقدار — مقدار با تعدیلِ کسری/معیوب کم می‌شود)."""
    batch = db.get(StockBatch, batch_id)
    if batch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "بار یافت نشد")
    batch.batch_number = data.batch_number
    batch.expiry_date = data.expiry_date
    batch.production_date = data.production_date
    batch.consumer_price = data.consumer_price
    batch.notes = data.notes
    db.flush()
    db.refresh(batch)
    return _decorate_batches(db, [batch])[0]


@router.delete("/stock-batches/{batch_id}", status_code=204)
def delete_stock_batch(
    batch_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "delete")),
):
    batch = db.get(StockBatch, batch_id)
    if batch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "بار یافت نشد")
    #: باری که در دفترِ انبار گردش دارد حذف نمی‌شود — حذفش یعنی پاک‌کردنِ
    #: تاریخچه‌ی حرکت. کلیدِ خارجی `RESTRICT` هم جلویش را می‌گیرد، ولی آن یک
    #: خطای خامِ ۵۰۰ می‌داد؛ این پیام می‌گوید به‌جایش چه کار کند.
    if db.query(StockLedger.id).filter(StockLedger.batch_id == batch_id).first() is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"بارِ «{batch.batch_number}» در دفترِ انبار گردش دارد و حذف نمی‌شود. "
            "اگر کارتان با آن تمام شده، به‌جای حذف آن را ببندید.",
        )
    db.delete(batch)


# ── سریالِ کارتن ────────────────────────────────────────
def _get_batch_or_404(db: Session, batch_id: UUID) -> StockBatch:
    batch = db.get(StockBatch, batch_id)
    if batch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "بار یافت نشد")
    return batch


@router.get("/stock-batches/{batch_id}/serials", response_model=list[BatchSerialOut])
def list_batch_serials(
    batch_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "view")),
):
    _get_batch_or_404(db, batch_id)
    return db.query(StockBatchSerial).filter(StockBatchSerial.batch_id == batch_id).order_by(StockBatchSerial.serial).all()


@router.post("/stock-batches/{batch_id}/serials", response_model=list[BatchSerialOut], status_code=201)
def add_batch_serials(
    batch_id: UUID,
    data: BatchSerialAddIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory", "update")),
):
    """سریالِ کارتن به یک بار اضافه می‌کند — فهرستِ دستی یا تولیدِ توالیِ خودکار.

    تکراری‌ها (چه در ورودی، چه با سریال‌های موجودِ همین بار) بی‌صدا رد می‌شوند تا
    اپراتور بتواند چند بار «افزودن» بزند بدونِ خطا.
    """
    batch = _get_batch_or_404(db, batch_id)

    wanted: list[str] = list(data.serials)
    # تولیدِ توالیِ خودکار وقتی سریال‌ها مرتب‌اند.
    if data.start is not None and data.count and data.count > 0:
        if data.count > 5000:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "تعدادِ سریالِ توالی بیش از حدِ مجاز است")
        for i in range(data.count):
            n = data.start + i
            wanted.append(f"{data.prefix}{str(n).zfill(data.pad) if data.pad else n}")

    if not wanted:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "سریالی برای افزودن داده نشد")

    existing = {
        s for (s,) in db.query(StockBatchSerial.serial).filter(StockBatchSerial.batch_id == batch_id).all()
    }
    seen: set[str] = set()
    try:
        # SAVEPOINT: اگر قیدِ یکتا (همزمانیِ نادر) شکست، فقط این بلوک برمی‌گردد نه زمینه‌ی RLS.
        with db.begin_nested():
            added: list[StockBatchSerial] = []
            for serial in wanted:
                if serial in existing or serial in seen:
                    continue
                seen.add(serial)
                row = StockBatchSerial(batch_id=batch_id, serial=serial)
                db.add(row)
                added.append(row)
            db.flush()
            #: **رویدادِ ورود همین‌جا ثبت می‌شود.** سریال بی رویداد یک بن‌بست
            #: است: می‌دانیم هست، نمی‌دانیم از کجا آمده. سندِ مبدأ را خودِ بچ
            #: می‌داند، پس حدسی در کار نیست.
            for row in added:
                serials_svc.record(
                    db,
                    row,
                    event_type="receipt",
                    source_type=batch.source_type or "",
                    source_id=batch.source_id,
                    entry_date=batch.received_date or date.today(),
                    user=user,
                )
    except IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "برخی سریال‌ها تکراری بودند؛ دوباره تلاش کنید")
    return db.query(StockBatchSerial).filter(StockBatchSerial.batch_id == batch_id).order_by(StockBatchSerial.serial).all()


@router.patch("/stock-batch-serials/{serial_id}", response_model=BatchSerialOut)
def update_batch_serial_status(
    serial_id: UUID,
    data: BatchSerialStatusIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "update")),
):
    """وضعیتِ یک سریالِ کارتن را ok/defect می‌کند (نشانه‌گذاریِ کارتنِ معیوب)."""
    s = db.get(StockBatchSerial, serial_id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سریال یافت نشد")
    s.status = data.status
    db.flush()
    db.refresh(s)
    return s


@router.delete("/stock-batch-serials/{serial_id}", status_code=204)
def delete_batch_serial(
    serial_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "update")),
):
    s = db.get(StockBatchSerial, serial_id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سریال یافت نشد")
    db.delete(s)


# ── تعدیلِ بار: کسری/معیوب/ضایعات ─────────────────────────
@router.post("/stock-batches/{batch_id}/adjust", response_model=StockBatchOut)
def adjust_batch(
    batch_id: UUID,
    data: BatchAdjustIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory", "update")),
):
    """کسری/معیوب/ضایعاتِ یک بار را ثبت می‌کند: از موجودی کم و به حسابداری (زیانِ مغایرت)
    ثبت می‌شود، و مقدارِ باقی‌مانده‌ی همین بار کاهش می‌یابد تا معلوم بماند کدام بار مشکل داشت."""
    batch = _get_batch_or_404(db, batch_id)
    if data.qty > batch.qty:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"مقدارِ {_ADJUST_REASON[data.reason]} نمی‌تواند از باقی‌مانده‌ی این بار ({batch.qty}) بیشتر باشد",
        )
    label = _ADJUST_REASON[data.reason]
    reason_text = f"{label}ِ بارِ «{batch.batch_number}»" + (f" — {data.notes}" if data.notes else "")
    post_stock_adjustment(
        db,
        StockAdjustmentIn(
            item_id=batch.item_id,
            warehouse_id=batch.warehouse_id,
            qty_diff=-data.qty,
            reason=reason_text,
            adjustment_date=data.adjustment_date,
            #: **حالا خودِ تعدیل بار را می‌شناسد.** تا امروز `batch_id` بعد از
            #: ثبت روی سند می‌نشست و حرکتِ دفتر بی‌برچسب می‌ماند؛ یعنی کسری از
            #: موجودیِ کالا کم می‌شد ولی از مانده‌ی بار نه.
            batch_id=batch.id,
        ),
        user,
    )
    #: ستونِ قدیمی همچنان نگهداری می‌شود: برای بارهای `legacy` هنوز **تنها**
    #: عددِ موجود است و تا وقتی گزارشِ مغایرت پاک نشده نباید کهنه شود.
    batch.qty = (batch.qty or 0) - data.qty
    db.flush()
    db.refresh(batch)
    return _decorate_batches(db, [batch])[0]


@router.get("/serials/search", response_model=list[SerialTraceOut])
def search_serials(
    serial: str | None = Query(None),
    item_id: UUID | None = Query(None),
    source_type: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "view")),
):
    """جست‌وجوی سریال — هر نتیجه با **کلِ تاریخچه‌اش**.

    پیش از این چنین چیزی ممکن نبود: سریال فقط به بچِ ورودش وصل بود و فروش
    لمسش نمی‌کرد، پس «به چه کسی فروخته شد؟» جوابی نداشت.

    فیلترها روی رویداد اعمال می‌شوند ولی تاریخچه‌ی برگردانده‌شده کامل است —
    وگرنه باز یک بن‌بستِ تازه ساخته‌ایم.
    """
    return serials_svc.search(
        db,
        serial=serial,
        item_id=item_id,
        source_type=source_type,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )


@router.post("/serials/assign", response_model=SerialAssignOut)
def assign_serials(
    data: SerialAssignIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory", "update")),
):
    """سریال‌های نام‌برده را به یک سند می‌چسباند.

    یکتاسازی از شکلِ داده می‌آید (ایندکسِ یکتای سریال+سند)، پس تلاشِ دوباره‌ی
    شبکه رویدادِ دوم نمی‌سازد و در `replayed` گزارش می‌شود.
    """
    return serials_svc.assign(
        db,
        serials=data.serials,
        item_id=data.item_id,
        source_type=data.source_type,
        source_id=data.source_id,
        entry_date=data.entry_date,
        event_type=data.event_type,
        user=user,
    )


# ── انسداد، فراخوان، بستن، ردیابی (§۱۵ §۱۶) ─────────────────────────
@router.post("/stock-batches/{batch_id}/hold", response_model=StockBatchOut)
def hold_batch(
    batch_id: UUID,
    data: BatchHoldIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory", "update")),
):
    """بار را مسدود یا فراخوان می‌کند (§۱۶).

    موجودیِ فیزیکی تکان نمی‌خورد — بار همان‌جاست، فقط از «قابلِ فروش» بیرون
    می‌رود و FEFO دیگر برش نمی‌دارد. برای همین هم انسداد سندِ انبار نمی‌خورد:
    چیزی جابه‌جا نشده.
    """
    batch = _get_batch_or_404(db, batch_id)
    batches_svc.set_hold(db, batch, hold_status=data.hold_status, reason=data.reason, user=user)
    db.refresh(batch)
    return _decorate_batches(db, [batch])[0]


@router.post("/stock-batches/{batch_id}/release", response_model=StockBatchOut)
def release_batch_hold(
    batch_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory", "update")),
):
    """انسداد یا فراخوان را برمی‌دارد — بار دوباره قابلِ فروش می‌شود."""
    batch = _get_batch_or_404(db, batch_id)
    batches_svc.set_hold(db, batch, hold_status="none", reason="", user=user)
    db.refresh(batch)
    return _decorate_batches(db, [batch])[0]


@router.post("/stock-batches/{batch_id}/close", response_model=StockBatchOut)
def close_batch(
    batch_id: UUID,
    data: BatchCloseIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory", "update")),
):
    """بار را می‌بندد یا باز می‌کند — تصمیم است، نه نتیجه‌ی عدد."""
    batch = _get_batch_or_404(db, batch_id)
    batches_svc.set_closed(db, batch, closed=data.is_closed, user=user)
    db.refresh(batch)
    return _decorate_batches(db, [batch])[0]


@router.get("/stock-batches/{batch_id}/trace", response_model=BatchTraceOut)
def trace_batch(
    batch_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "view")),
):
    """گزارشِ کاملِ یک بار: چه رسید، چه فروخته شد، به که، با کدام سند (§۱۵ §۱۶).

    همه‌چیز از دفترِ انبار مشتق می‌شود؛ هیچ شمارنده‌ای نگهداری نمی‌شود که بتواند
    عقب بیفتد.
    """
    return batches_svc.trace(db, _get_batch_or_404(db, batch_id))


@router.get("/warehouse-issues/{issue_id}/picking", response_model=list[PickingRowOut])
def picking_sheet(
    issue_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "view")),
):
    """برگه‌ی جمع‌آوری (§۱۲) — انباردار باید بداند کدام بار و کجا.

    همه‌ی داده از قبل در دفتر و روی بار هست؛ این مسیر فقط کنارِ هم می‌گذاردشان.
    """
    return batches_svc.picking_sheet(db, issue_id)


@router.post("/stock-batches/substitute", response_model=dict, status_code=201)
def substitute_batch(
    data: BatchSubstitutionIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory", "update")),
):
    """بارِ یک ردیفِ خروج را عوض می‌کند، با ردِ ممیزی (§۱۳).

    موجودیِ کالا تکان نمی‌خورد — فقط از یک بار به بارِ دیگر جابه‌جا می‌شود.
    """
    row = batches_svc.substitute(
        db,
        source_line_id=data.source_line_id,
        original_batch_id=data.original_batch_id,
        new_batch_id=data.new_batch_id,
        qty=data.qty,
        reason=data.reason,
        source_type="warehouse_issue",
        source_id=None,
        user=user,
    )
    return {"id": str(row.id), "qty": str(row.qty), "reason": row.reason}
