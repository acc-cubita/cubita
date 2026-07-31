from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_permission
from app.models.user import User
from app.schemas.installments import InstallmentPayIn, InstallmentPlanIn, InstallmentPlanOut
from app.services import installments as svc

router = APIRouter(prefix="/api/installment-plans", tags=["installments"])


@router.get("", response_model=list[InstallmentPlanOut])
def list_plans(db: Session = Depends(get_db), _=Depends(require_permission("invoices", "view"))):
    return svc.list_plans(db)


@router.get("/{plan_id}", response_model=InstallmentPlanOut)
def get_plan(plan_id: UUID, db: Session = Depends(get_db), _=Depends(require_permission("invoices", "view"))):
    return svc.get_plan(db, plan_id)


@router.post("", response_model=InstallmentPlanOut, status_code=201)
def create_plan(
    data: InstallmentPlanIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("invoices", "create")),
):
    return svc.create_plan(db, data, user)


@router.post("/{plan_id}/installments/{installment_id}/pay", response_model=InstallmentPlanOut)
def pay_installment(
    plan_id: UUID,
    installment_id: UUID,
    data: InstallmentPayIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("invoices", "create")),
):
    return svc.pay_installment(db, plan_id, installment_id, data, user)


@router.post("/{plan_id}/cancel", response_model=InstallmentPlanOut)
def cancel_plan(
    plan_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("invoices", "update")),
):
    return svc.cancel_plan(db, plan_id)
