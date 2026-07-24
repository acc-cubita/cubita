from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_permission
from app.models.user import User
from app.schemas.cost_center import CostCenterIn, CostCenterOut
from app.services import cost_centers as service

router = APIRouter(prefix="/api/cost-centers", tags=["cost-centers"])


@router.get("", response_model=list[CostCenterOut])
def list_cost_centers(
    include_inactive: bool = Query(True),
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    return service.list_cost_centers(db, include_inactive=include_inactive)


@router.post("", response_model=CostCenterOut, status_code=201)
def create_cost_center(
    data: CostCenterIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("accounting", "create")),
):
    return service.create_cost_center(db, data, user)


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
