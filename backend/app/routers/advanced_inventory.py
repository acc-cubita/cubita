from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_permission
from app.models.advanced_inventory import PriceList, PriceListItem, StockBatch
from app.models.user import User
from app.schemas.advanced_inventory import (
    PriceListIn,
    PriceListItemOut,
    PriceListOut,
    PriceListUpdateIn,
    SetPricesIn,
    StockBatchIn,
    StockBatchOut,
)

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


# ── بچ / تاریخِ انقضا ───────────────────────────────────
@router.get("/stock-batches/expiring", response_model=list[StockBatchOut])
def expiring_batches(
    days: int = Query(30, ge=0),
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "view")),
):
    cutoff = date.today() + timedelta(days=days)
    return (
        db.query(StockBatch)
        .filter(StockBatch.expiry_date.isnot(None), StockBatch.expiry_date <= cutoff)
        .order_by(StockBatch.expiry_date)
        .all()
    )


@router.get("/stock-batches", response_model=list[StockBatchOut])
def list_stock_batches(
    item_id: UUID | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "view")),
):
    q = db.query(StockBatch)
    if item_id:
        q = q.filter(StockBatch.item_id == item_id)
    return q.order_by(StockBatch.expiry_date.is_(None), StockBatch.expiry_date).all()


@router.post("/stock-batches", response_model=StockBatchOut, status_code=201)
def create_stock_batch(
    data: StockBatchIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("inventory", "create")),
):
    batch = StockBatch(**data.model_dump(), created_by_id=user.id)
    db.add(batch)
    db.flush()
    db.refresh(batch)
    return batch


@router.delete("/stock-batches/{batch_id}", status_code=204)
def delete_stock_batch(
    batch_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("inventory", "delete")),
):
    batch = db.get(StockBatch, batch_id)
    if batch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "بچ یافت نشد")
    db.delete(batch)
