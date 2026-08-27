from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_permission
from app.models.user import User
from app.schemas.budgeting import BudgetLineIn, BudgetLineOut, BudgetReportOut
from app.services import budgeting as budgeting_service

router = APIRouter(prefix="/api/budgets", tags=["budgets"])


@router.get("", response_model=list[BudgetLineOut])
def list_budget_lines(
    cost_center_id: UUID | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    return budgeting_service.list_budget_lines(db, cost_center_id=cost_center_id)


@router.get("/report", response_model=BudgetReportOut)
def budget_report(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    cost_center_id: UUID | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    return budgeting_service.get_budget_report(db, date_from, date_to, cost_center_id)


@router.post("", response_model=BudgetLineOut, status_code=201)
def create_budget_line(
    data: BudgetLineIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("accounting", "create")),
):
    return budgeting_service.create_budget_line(db, data, user)


@router.put("/{line_id}", response_model=BudgetLineOut)
def update_budget_line(
    line_id: UUID,
    data: BudgetLineIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "update")),
):
    return budgeting_service.update_budget_line(db, line_id, data)


@router.delete("/{line_id}", status_code=204)
def delete_budget_line(
    line_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "delete")),
):
    budgeting_service.delete_budget_line(db, line_id)
