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
    MissingTafsiliOut,
    NatureViolationOut,
    SalesDashboardOut,
    SeasonalReportOut,
    TrialBalanceRowOut,
    VatReportOut,
)
from app.services import cost_centers as cost_centers_service
from app.services import reports as reports_service
from app.services.reports import ReportFilters
from app.services import tafsili as tafsili_service

router = APIRouter(prefix="/api/reports", tags=["reports"])


#: فیلترهای مشترکِ هر سه خانواده‌ی گزارش. یک `Depends` به‌جای تکرارِ نه پارامتر در
#: هر نقطه — و مهم‌تر: یک *معنا*، تا تراز و دفتر نتوانند از هم جدا بیفتند.
def report_filters(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    entry_from: int | None = Query(None, description="از شماره سند"),
    entry_to: int | None = Query(None, description="تا شماره سند"),
    status_filter: str | None = Query(None, alias="status", description="temporary | permanent"),
    source_type: str | None = Query(None),
    cost_center_id: UUID | None = Query(None),
    analytic_id: UUID | None = Query(None),
    include_system_entries: bool = Query(
        True, description="افتتاحیه، اختتامیه و بستنِ سود و زیان وارد محاسبه شوند"
    ),
) -> ReportFilters:
    return ReportFilters(
        date_from=date_from,
        date_to=date_to,
        entry_from=entry_from,
        entry_to=entry_to,
        status=status_filter,
        source_type=source_type,
        cost_center_id=cost_center_id,
        analytic_id=analytic_id,
        include_system_entries=include_system_entries,
    )


@router.get("/general-ledger", response_model=GeneralLedgerOut)
def analytic_ledger(
    filters: ReportFilters = Depends(report_filters),
    account_id: UUID | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    """دفتر بدونِ حسابِ اجباری — یعنی **دفترِ تفصیلی**: گردشِ یک تفصیلی در همه‌ی حساب‌ها."""
    return reports_service.get_general_ledger(
        db, account_id, filters.date_from, filters.date_to, filters
    )


@router.get("/general-ledger/{account_id}", response_model=GeneralLedgerOut)
def general_ledger(
    account_id: UUID,
    filters: ReportFilters = Depends(report_filters),
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    return reports_service.get_general_ledger(
        db, account_id, filters.date_from, filters.date_to, filters
    )


@router.get("/trial-balance", response_model=list[TrialBalanceRowOut])
def trial_balance(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: Session = Depends(get_db),
    management_only: bool = Query(
        False,
        description="فقط حساب‌هایی که «نمایش در گزارشات مدیریتی» دارند",
    ),
    _=Depends(require_permission("accounting", "view")),
):
    return reports_service.get_trial_balance(db, date_from, date_to, management_only)


@router.get("/nature-violations", response_model=list[NatureViolationOut])
def nature_violations(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: Session = Depends(get_db),
    controlled_only: bool = Query(
        False,
        description="فقط حساب‌هایی که «کنترل ماهیت طی دوره» دارند",
    ),
    _=Depends(require_permission("accounting", "view")),
):
    """حساب‌هایی که مانده‌شان خلافِ ماهیتشان است — گزارش، نه گارد."""
    return reports_service.get_nature_violations(db, date_from, date_to, controlled_only)


@router.get("/missing-tafsili", response_model=list[MissingTafsiliOut])
def missing_tafsili(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    """ردیف‌های بدونِ تفصیلی روی حساب‌های تفصیلی‌پذیر — سوراخِ گزارشِ تفصیلی.

    مستقل از سطحِ اجبار کار می‌کند. در «شناور» تنها چیزی است که این ردیف‌ها را نشان
    می‌دهد؛ در «ترکیبی» ردیف‌های ماژول‌ها را که از گارد رد شده‌اند می‌آورد؛ در
    «اجباری» باید تقریباً خالی باشد و هرچه در آن هست مالِ پیش از سخت‌گیری است.
    """
    return tafsili_service.find_missing_tafsili(db, date_from, date_to)


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


@router.get("/seasonal", response_model=SeasonalReportOut)
def seasonal_report(
    year: int = Query(..., ge=1300, le=1500),
    quarter: int = Query(0, ge=0, le=4),
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    return reports_service.get_seasonal_report(db, year, quarter)


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
    return cost_centers_service.get_report(db, date_from, date_to)


@router.get("/aging", response_model=AgingReportOut)
def aging_report(
    kind: str = Query("receivable"),
    as_of: date | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    return reports_service.get_aging(db, kind, as_of)


@router.get("/dashboard", response_model=SalesDashboardOut)
def sales_dashboard(
    months: int = Query(12, ge=1, le=36),
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    return reports_service.get_sales_dashboard(db, months)


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
