from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_permission
from app.models.inventory import Item
from app.models.manufacturing import Bom, BomLine, ProductionOrder
from app.models.user import User
from app.schemas.manufacturing import (
    BomIn,
    BomOut,
    BomUpdateIn,
    ProductionOrderIn,
    ProductionOrderOut,
)
from app.services import manufacturing as service

router = APIRouter(prefix="/api", tags=["manufacturing"])


# ── فرمولِ ساخت (BOM) ───────────────────────────────────
@router.get("/boms", response_model=list[BomOut])
def list_boms(db: Session = Depends(get_db), _=Depends(require_permission("manufacturing", "view"))):
    return db.query(Bom).order_by(Bom.created_at.desc()).all()


@router.post("/boms", response_model=BomOut, status_code=201)
def create_bom(
    data: BomIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("manufacturing", "create")),
):
    finished = db.get(Item, data.finished_item_id)
    if finished is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "محصولِ نهایی یافت نشد")
    if finished.is_service:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "محصولِ خدماتی فرمولِ ساخت ندارد")
    if any(line.component_item_id == data.finished_item_id for line in data.lines):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "محصولِ نهایی نمی‌تواند جزءِ خودش باشد")

    bom = Bom(
        finished_item_id=data.finished_item_id,
        name=data.name,
        yield_qty=data.yield_qty,
        notes=data.notes,
        created_by_id=user.id,
        lines=[BomLine(component_item_id=line.component_item_id, qty=line.qty) for line in data.lines],
    )
    db.add(bom)
    db.flush()
    db.refresh(bom)
    return bom


@router.patch("/boms/{bom_id}", response_model=BomOut)
def update_bom(
    bom_id: UUID,
    data: BomUpdateIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("manufacturing", "update")),
):
    bom = db.get(Bom, bom_id)
    if bom is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "فرمولِ ساخت یافت نشد")

    patch = data.model_dump(exclude_unset=True)
    lines = patch.pop("lines", None)
    for key, value in patch.items():
        setattr(bom, key, value)

    if lines is not None:
        if not lines:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "فرمول باید حداقل یک جزء داشته باشد")
        if any(line["component_item_id"] == bom.finished_item_id for line in lines):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "محصولِ نهایی نمی‌تواند جزءِ خودش باشد")
        bom.lines.clear()
        db.flush()
        for line in lines:
            bom.lines.append(BomLine(component_item_id=line["component_item_id"], qty=line["qty"]))

    db.flush()
    db.refresh(bom)
    return bom


@router.delete("/boms/{bom_id}", status_code=204)
def delete_bom(
    bom_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("manufacturing", "delete")),
):
    bom = db.get(Bom, bom_id)
    if bom is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "فرمولِ ساخت یافت نشد")
    db.delete(bom)


# ── سفارشِ تولید ────────────────────────────────────────
@router.get("/production-orders", response_model=list[ProductionOrderOut])
def list_production_orders(db: Session = Depends(get_db), _=Depends(require_permission("manufacturing", "view"))):
    return db.query(ProductionOrder).order_by(ProductionOrder.created_at.desc()).all()


@router.post("/production-orders", response_model=ProductionOrderOut, status_code=201)
def create_production_order(
    data: ProductionOrderIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("manufacturing", "create")),
):
    return service.post_production_order(db, data, user)
