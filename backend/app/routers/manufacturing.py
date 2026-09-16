from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_module, require_permission
from app.models.inventory import Item
from app.models.invoices import WarehouseIssue, WarehouseReceipt
from app.models.manufacturing import Bom, BomLine, ProductionOrder, ProductionPlan
from app.models.user import User
from app.pagination import Page, PageParams, paginate
from app.schemas.invoices import WarehouseIssueOut, WarehouseReceiptOut
from app.schemas.manufacturing import (
    BomIn,
    BomOut,
    BomUpdateIn,
    ProductionCostCalcIn,
    ProductionMaterialIssueIn,
    ProductionOrderIn,
    ProductionOrderOut,
    ProductionPlanIn,
    ProductionPlanOut,
    ProductionPlanStatusIn,
    ProductionReceiptIn,
)
from app.services import manufacturing as service
from app.services.idempotency import idempotent

router = APIRouter(
    prefix="/api",
    tags=["manufacturing"],
    dependencies=[Depends(require_module("manufacturing"))],
)


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


# ── سفارشِ تولید (برنامه) ────────────────────────────────
@router.get("/production-plans", response_model=Page[ProductionPlanOut])
def list_production_plans(
    db: Session = Depends(get_db),
    params: PageParams = Depends(),
    status_: str | None = Query(None, alias="status"),
    _=Depends(require_permission("manufacturing", "view")),
):
    query = db.query(ProductionPlan)
    if status_:
        query = query.filter(ProductionPlan.status == status_)
    rows, next_cursor = paginate(query, [ProductionPlan.created_at, ProductionPlan.number], params)
    return Page(items=rows, next_cursor=next_cursor)


@router.post("/production-plans", response_model=ProductionPlanOut, status_code=201)
def create_production_plan(
    data: ProductionPlanIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("manufacturing", "create")),
):
    """**idempotent** — دوکلیک نباید دو سفارش با یک شماره بسازد."""
    return idempotent(
        db, request, user, operation="create_production_plan", payload=data,
        run=lambda: service.create_production_plan(db, data, user),
        replay=lambda pid: db.get(ProductionPlan, pid),
    )


@router.patch("/production-plans/{plan_id}/status", response_model=ProductionPlanOut)
def change_production_plan_status(
    plan_id: UUID,
    data: ProductionPlanStatusIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("manufacturing", "update")),
):
    return service.change_production_plan_status(db, plan_id, data.status, user)


# ── تحویلِ مواد به تولید / رسیدِ محصول از تولید ──────────
@router.post("/production-plans/{plan_id}/issue-materials", response_model=WarehouseIssueOut, status_code=201)
def issue_materials_to_production(
    plan_id: UUID,
    data: ProductionMaterialIssueIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("manufacturing", "create")),
):
    """**idempotent** — دوکلیک نباید مواد را دوبار تحویل بدهد."""
    return idempotent(
        db, request, user, operation="issue_materials_to_production", payload=data,
        run=lambda: service.issue_materials_to_production(db, plan_id, data, user),
        replay=lambda iid: db.get(WarehouseIssue, iid),
    )


@router.post("/production-plans/{plan_id}/receive-output", response_model=WarehouseReceiptOut, status_code=201)
def receive_production_output(
    plan_id: UUID,
    data: ProductionReceiptIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("manufacturing", "create")),
):
    """**idempotent** — دوکلیک نباید محصول را دوبار وارد انبار کند."""
    return idempotent(
        db, request, user, operation="receive_production_output", payload=data,
        run=lambda: service.receive_production_output(db, plan_id, data, user),
        replay=lambda rid: db.get(WarehouseReceipt, rid),
    )


@router.post("/production-plans/{plan_id}/calculate-cost", response_model=ProductionPlanOut, status_code=201)
def calculate_production_cost(
    plan_id: UUID,
    data: ProductionCostCalcIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("manufacturing", "create")),
):
    """**idempotent** — دوکلیک نباید دستمزد/سربار را دوبار روی بها بنشاند."""
    return idempotent(
        db, request, user, operation="calculate_production_cost", payload=data,
        run=lambda: service.calculate_production_cost(db, plan_id, data, user),
        replay=lambda pid: db.get(ProductionPlan, pid),
    )


# ── سندِ تولید (اجرا) ────────────────────────────────────
@router.get("/production-orders", response_model=Page[ProductionOrderOut])
def list_production_orders(
    db: Session = Depends(get_db),
    params: PageParams = Depends(),
    _=Depends(require_permission("manufacturing", "view")),
):
    query = db.query(ProductionOrder)
    rows, next_cursor = paginate(query, [ProductionOrder.created_at, ProductionOrder.number], params)
    return Page(items=rows, next_cursor=next_cursor)


@router.post("/production-orders", response_model=ProductionOrderOut, status_code=201)
def create_production_order(
    data: ProductionOrderIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("manufacturing", "create")),
):
    """**idempotent** — دوکلیک نباید مواد را دوبار مصرف کند."""
    return idempotent(
        db, request, user, operation="create_production_order", payload=data,
        run=lambda: service.post_production_order(db, data, user),
        replay=lambda oid: db.get(ProductionOrder, oid),
    )
