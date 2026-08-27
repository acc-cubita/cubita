from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_permission
from app.models.user import User
from app.schemas.installments import (
    EarlySettlementOut,
    InstallmentPayIn,
    InstallmentPlanIn,
    InstallmentPlanOut,
    InstallmentSettleIn,
    InstallmentSummaryOut,
    RescheduleIn,
)
from app.services import installments as svc

router = APIRouter(prefix="/api/installment-plans", tags=["installments"])


@router.get("", response_model=list[InstallmentPlanOut])
def list_plans(db: Session = Depends(get_db), _=Depends(require_permission("invoices", "view"))):
    return svc.list_plans(db)


@router.get("/summary", response_model=InstallmentSummaryOut)
def summary(db: Session = Depends(get_db), _=Depends(require_permission("invoices", "view"))):
    return svc.get_summary(db)


@router.get("/{plan_id}", response_model=InstallmentPlanOut)
def get_plan(plan_id: UUID, db: Session = Depends(get_db), _=Depends(require_permission("invoices", "view"))):
    return svc.get_plan(db, plan_id)


@router.get("/{plan_id}/early-settlement", response_model=EarlySettlementOut)
def early_settlement_quote(
    plan_id: UUID,
    discount: Decimal = Query(Decimal(0)),
    db: Session = Depends(get_db),
    _=Depends(require_permission("invoices", "view")),
):
    """مبلغِ تسویه‌ی یک‌جا با تخفیفِ اختیاری — فقط محاسبه، بدونِ ثبت."""
    return svc.early_settlement_quote(db, plan_id, discount)


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


@router.post("/{plan_id}/settle", response_model=InstallmentPlanOut)
def settle_amount(
    plan_id: UUID,
    data: InstallmentSettleIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("invoices", "create")),
):
    """یک فیش، چند قسط: مبلغ از قدیمی‌ترین قسطِ باز به بعد تسهیم می‌شود."""
    return svc.settle_amount(db, plan_id, data, user)


@router.post("/{plan_id}/reschedule", response_model=InstallmentPlanOut)
def reschedule(
    plan_id: UUID,
    data: RescheduleIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("invoices", "update")),
):
    return svc.reschedule(db, plan_id, data, user)


@router.post("/{plan_id}/cancel", response_model=InstallmentPlanOut)
def cancel_plan(
    plan_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("invoices", "update")),
):
    return svc.cancel_plan(db, plan_id)
