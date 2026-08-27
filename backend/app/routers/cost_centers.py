from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_permission
from app.models.user import User
from app.schemas.budgeting import BudgetLineIn, BudgetLineOut
from app.schemas.cost_center import (
    CostCenterAnalysisOut,
    CostCenterIn,
    CostCenterLedgerRow,
    CostCenterOut,
    CostCenterReportOut,
)
from app.services import budgeting as budgeting_service
from app.services import cost_centers as service

router = APIRouter(prefix="/api/cost-centers", tags=["cost-centers"])


@router.get("", response_model=list[CostCenterOut])
def list_cost_centers(
    include_inactive: bool = Query(True),
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    return service.list_cost_centers(db, include_inactive=include_inactive)


@router.get("/report", response_model=CostCenterReportOut)
def cost_center_report(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    """همان گزارشِ `/api/reports/cost-center` — اینجا هم هست تا صفحه‌ی مرکزِ هزینه
    برای مقایسه‌ی مراکز به روترِ گزارش‌ها وابسته نباشد."""
    return service.get_report(db, date_from, date_to)


@router.post("", response_model=CostCenterOut, status_code=201)
def create_cost_center(
    data: CostCenterIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("accounting", "create")),
):
    return service.create_cost_center(db, data, user)


@router.get("/{cost_center_id}", response_model=CostCenterOut)
def get_cost_center(
    cost_center_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    return service.get_cost_center_out(db, cost_center_id)


@router.get("/{cost_center_id}/analysis", response_model=CostCenterAnalysisOut)
def cost_center_analysis(
    cost_center_id: UUID,
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    include_children: bool = Query(True),
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    return service.get_analysis(
        db, cost_center_id, date_from, date_to, include_children=include_children
    )


@router.get("/{cost_center_id}/ledger", response_model=list[CostCenterLedgerRow])
def cost_center_ledger(
    cost_center_id: UUID,
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    include_children: bool = Query(True),
    limit: int = Query(50, ge=1, le=service.LEDGER_MAX_LIMIT),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    return service.get_ledger(
        db,
        cost_center_id,
        date_from,
        date_to,
        include_children=include_children,
        limit=limit,
        offset=offset,
    )


@router.get("/{cost_center_id}/budget", response_model=list[BudgetLineOut])
def cost_center_budget(
    cost_center_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    """ردیف‌های بودجه‌ی همین مرکز — همان جدولِ بودجه‌ی سراسری، فیلترشده روی مرکز."""
    service.get_cost_center(db, cost_center_id)
    return budgeting_service.list_budget_lines(db, cost_center_id=cost_center_id)


@router.post("/{cost_center_id}/budget", response_model=BudgetLineOut, status_code=201)
def set_cost_center_budget(
    cost_center_id: UUID,
    data: BudgetLineIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("accounting", "create")),
):
    service.get_cost_center(db, cost_center_id)
    # مرکزِ مسیر بر بدنه اولویت دارد: آدرس صریح‌تر از بدنه است و اجازه نمی‌دهد
    # ردیفِ بودجه اشتباهی زیرِ مرکزِ دیگری بنشیند.
    return budgeting_service.create_budget_line(
        db, data.model_copy(update={"cost_center_id": cost_center_id}), user
    )


@router.put("/{cost_center_id}", response_model=CostCenterOut)
def update_cost_center(
    cost_center_id: UUID,
    data: CostCenterIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "update")),
):
    return service.update_cost_center(db, cost_center_id, data)


@router.delete("/{cost_center_id}", status_code=204)
def delete_cost_center(
    cost_center_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "delete")),
):
    service.delete_cost_center(db, cost_center_id)
