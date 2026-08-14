from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_permission
from app.models.user import User
from app.schemas.payroll import (
    BenefitIssueOut,
    BenefitSettingsIn,
    BenefitSettingsOut,
    BenefitsReportOut,
    LeaveRecordIn,
    LeaveRecordOut,
)
from app.services import benefits as service

router = APIRouter(prefix="/api/payroll", tags=["benefits"])


@router.get("/benefits", response_model=BenefitsReportOut)
def benefits_report(
    year: int = Query(...),
    as_of: date | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_permission("payroll", "view")),
):
    return service.get_benefits_report(db, year, as_of)


@router.put("/benefit-settings", response_model=BenefitSettingsOut)
def set_benefit_settings(
    data: BenefitSettingsIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("payroll", "update")),
):
    return service.set_benefit_settings(db, data.year, data.min_base_wage, data.annual_leave_days)


@router.get("/leave", response_model=list[LeaveRecordOut])
def list_leave(
    employee_id: UUID | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_permission("payroll", "view")),
):
    return service.list_leave(db, employee_id)


@router.post("/leave", response_model=LeaveRecordOut, status_code=201)
def record_leave(
    data: LeaveRecordIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("payroll", "update")),
):
    return service.record_leave(db, data, user)


@router.post("/eidi", response_model=BenefitIssueOut)
def issue_eidi(
    year: int = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("payroll", "update")),
):
    return service.issue_eidi(db, year, user)


@router.post("/severance/{employee_id}", response_model=BenefitIssueOut)
def issue_severance(
    employee_id: UUID,
    as_of: date | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("payroll", "update")),
):
    return service.issue_severance(db, employee_id, user, as_of)


@router.post("/leave-payout/{employee_id}", response_model=BenefitIssueOut)
def issue_leave_payout(
    employee_id: UUID,
    year: int = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("payroll", "update")),
):
    return service.issue_leave_payout(db, employee_id, year, user)
