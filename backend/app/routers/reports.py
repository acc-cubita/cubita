from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from uuid import UUID

from app.database import get_db
from app.deps import require_permission
from app.schemas.cost_center import CostCenterReportOut
from app.schemas.reports import (
    AgingReportOut,
    BalanceSheetOut,
    CashFlowOut,
    ContactStatementOut,
    GeneralLedgerOut,
    IncomeStatementOut,
    InventoryReportOut,
    KardexReportOut,
    TrialBalanceRowOut,
    VatReportOut,
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


@router.get("/vat", response_model=VatReportOut)
def vat_report(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    return reports_service.get_vat_report(db, date_from, date_to)


@router.get("/cash-flow", response_model=CashFlowOut)
def cash_flow(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    return reports_service.get_cash_flow(db, date_from, date_to)


@router.get("/cost-center", response_model=CostCenterReportOut)
def cost_center_report(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    return reports_service.get_cost_center_report(db, date_from, date_to)


@router.get("/aging", response_model=AgingReportOut)
def aging_report(
    kind: str = Query("receivable"),
    as_of: date | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    return reports_service.get_aging(db, kind, as_of)


@router.get("/inventory", response_model=InventoryReportOut)
def inventory_report(
    warehouse_id: UUID | None = Query(None),
    as_of: date | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    return reports_service.get_inventory_report(db, warehouse_id, as_of)


@router.get("/kardex/{item_id}", response_model=KardexReportOut)
def kardex(
    item_id: UUID,
    warehouse_id: UUID | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    return reports_service.get_kardex(db, item_id, warehouse_id, date_from, date_to)


@router.get("/contact-statement/{contact_id}", response_model=ContactStatementOut)
def contact_statement(
    contact_id: UUID,
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    return reports_service.get_contact_statement(db, contact_id, date_from, date_to)
