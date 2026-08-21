from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_permission
from app.models.advanced_inventory import PriceList, PriceListItem, StockBatch, StockBatchSerial
from app.models.inventory import Contact, StockAdjustment
from app.models.user import User
from app.schemas.advanced_inventory import (
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
    pl = db.get(PriceList, list_id)
    if pl is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "لیستِ قیمت یافت نشد")
    # مشتری‌هایی که این لیست را پیش‌فرض دارند رها می‌شوند (به قیمتِ پایه)، وگرنه قیدِ FK
    # حذف را با ۵۰۰ می‌شکند. اجزای لیست خودشان با ondelete CASCADE پاک می‌شوند.
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


@router.put("/price-lists/{list_id}/items", response_model=list[PriceListItemOut])
def set_price_list_items(
    list_id: UUID,
    data: SetPricesIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "update")),
):
    """قیمت‌های لیست را یک‌جا جایگزین می‌کند (کالاهای نیامده حذف می‌شوند)."""
    pl = db.get(PriceList, list_id)
    if pl is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "لیستِ قیمت یافت نشد")
    pl.items.clear()
    db.flush()
    seen: set[UUID] = set()
    for row in data.items:
        if row.item_id in seen:
            continue
        seen.add(row.item_id)
        pl.items.append(PriceListItem(item_id=row.item_id, price=row.price))
    db.flush()
    return db.query(PriceListItem).filter(PriceListItem.price_list_id == list_id).all()


# ── بچ / بارِ ورودی / سریالِ کارتن ──────────────────────────
def _decorate_batches(db: Session, batches: list[StockBatch]) -> list[StockBatch]:
    """defect_qty (received − remaining) و serial_count را روی هر بار می‌نشاند."""
    if not batches:
        return batches
    ids = [b.id for b in batches]
    counts = dict(
        db.query(StockBatchSerial.batch_id, func.count(StockBatchSerial.id))
        .filter(StockBatchSerial.batch_id.in_(ids))
        .group_by(StockBatchSerial.batch_id)
        .all()
    )
    for b in batches:
        b.defect_qty = (b.received_qty or 0) - (b.qty or 0)
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
    _=Depends(require_permission("inventory", "update")),
):
    """سریالِ کارتن به یک بار اضافه می‌کند — فهرستِ دستی یا تولیدِ توالیِ خودکار.

    تکراری‌ها (چه در ورودی، چه با سریال‌های موجودِ همین بار) بی‌صدا رد می‌شوند تا
    اپراتور بتواند چند بار «افزودن» بزند بدونِ خطا.
    """
    _get_batch_or_404(db, batch_id)

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
            for serial in wanted:
                if serial in existing or serial in seen:
                    continue
                seen.add(serial)
                db.add(StockBatchSerial(batch_id=batch_id, serial=serial))
            db.flush()
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
    adjustment = post_stock_adjustment(
        db,
        StockAdjustmentIn(
            item_id=batch.item_id,
            warehouse_id=batch.warehouse_id,
            qty_diff=-data.qty,
            reason=reason_text,
            adjustment_date=data.adjustment_date,
        ),
        user,
    )
    adjustment.batch_id = batch.id
    batch.qty = (batch.qty or 0) - data.qty
    db.flush()
    db.refresh(batch)
    return _decorate_batches(db, [batch])[0]
