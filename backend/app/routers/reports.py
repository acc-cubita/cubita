from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from uuid import UUID

from app.database import get_db
from app.deps import require_permission
from app.schemas.reports import (
    BalanceSheetOut,
    GeneralLedgerOut,
    IncomeStatementOut,
    TrialBalanceRowOut,
)
from app.services import reports as reports_service

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/general-ledger/{account_id}", response_model=GeneralLedgerOut)
def general_ledger(
    account_id: UUID,
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    return reports_service.get_general_ledger(db, account_id, date_from, date_to)


@router.get("/trial-balance", response_model=list[TrialBalanceRowOut])
def trial_balance(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    return reports_service.get_trial_balance(db, date_from, date_to)


@router.get("/income-statement", response_model=IncomeStatementOut)
def income_statement(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    return reports_service.get_income_statement(db, date_from, date_to)


@router.get("/balance-sheet", response_model=BalanceSheetOut)
def balance_sheet(
    as_of: date | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    return reports_service.get_balance_sheet(db, as_of or date.today())
