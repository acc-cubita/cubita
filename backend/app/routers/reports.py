from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from uuid import UUID

from app.database import get_db
from app.deps import Principal, get_principal, require_permission
from app.pagination import MAX_LIMIT
from app.schemas.cost_center import CostCenterReportOut
from app.schemas.reports import (
    InventoryBreakdownOut,
    PreinvoiceProgressOut,
    SalesByCustomerOut,
    SalesByItemOut,
    SalesByWarehouseOut,
    SalesDocumentOut,
    SalesLineOut,
    SalesReviewSummaryOut,
    CounterpartyEventDetailOut,
    CounterpartyEventOut,
    CounterpartySummaryOut,
    AgingReportOut,
    BalanceSheetOut,
    CashFlowOut,
    EquityStatementOut,
    ContactStatementOut,
    GeneralLedgerOut,
    IncomeStatementOut,
    IntegrityReportOut,
    InventoryReportOut,
    KardexReportOut,
    MissingTafsiliOut,
    NatureViolationOut,
    SalesDashboardOut,
    SeasonalReportOut,
    TrialBalanceRowOut,
    VatReportOut,
)
from app.services import counterparty as counterparty_service
from app.services import inventory_analytics
from app.services import sales_review as sales_review_service
from app.services import cost_centers as cost_centers_service
from app.services import integrity as integrity_service
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
    limit: int | None = Query(None, ge=1, le=MAX_LIMIT, description="بی‌آن، همه‌ی ردیف‌ها"),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    """دفتر بدونِ حسابِ اجباری — یعنی **دفترِ تفصیلی**: گردشِ یک تفصیلی در همه‌ی حساب‌ها."""
    return reports_service.get_general_ledger(
        db, account_id, filters.date_from, filters.date_to, filters, limit=limit, offset=offset
    )


@router.get("/general-ledger/{account_id}", response_model=GeneralLedgerOut)
def general_ledger(
    account_id: UUID,
    filters: ReportFilters = Depends(report_filters),
    limit: int | None = Query(None, ge=1, le=MAX_LIMIT, description="بی‌آن، همه‌ی ردیف‌ها"),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    """دفترِ یک حساب با مانده‌ی در حال اجرا. `limit`/`offset` اختیاری‌اند و مانده‌ی
    برش همان مانده‌ی دفترِ کامل است (نگاه کنید به `get_general_ledger`)."""
    return reports_service.get_general_ledger(
        db, account_id, filters.date_from, filters.date_to, filters, limit=limit, offset=offset
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


@router.get("/integrity", response_model=IntegrityReportOut)
def integrity_check(
    filters: ReportFilters = Depends(report_filters),
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    """بررسیِ یکپارچگیِ دفتر — گزارش، نه گارد.

    همان `report_filters` بقیه‌ی گزارش‌ها را می‌گیرد تا بشود دامنه‌ی بررسی را با
    همان زبانِ آشنا محدود کرد؛ بدونِ فیلتر، کلِ دفتر سنجیده می‌شود.
    """
    return integrity_service.run_integrity_check(db, filters)


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


@router.get("/equity-statement", response_model=EquityStatementOut)
def equity_statement(
    date_to: date = Query(...),
    date_from: date | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    """صورت تغییرات در حقوق صاحبان سهام — چهارمین صورتِ الزامی.

    `date_to` اجباری است چون «مانده‌ی پایان دوره» بی تاریخِ پایان معنا ندارد.
    `date_from` خالی یعنی از ابتدای دفتر.
    """
    return reports_service.get_equity_statement(db, date_from, date_to)


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


#: **مقدار و مبلغ دو مجوزِ متفاوت‌اند.**
#:
#: تا امروز هر گزارشِ انبار `accounting.view` می‌خواست و نتیجه‌اش در **هر دو
#: جهت** غلط بود: انباردار — که مجوزِ `inventory` دارد و نه `accounting` — اصلاً
#: موجودیِ انبارش را نمی‌دید، و هر کسی که می‌دید بهای تمام‌شده را هم می‌دید.
#:
#: راهِ درست دو اندپوینت نیست (همان داده، دو نما)؛ یک اندپوینت است با مبالغِ
#: **پوشیده** برای کسی که مجوزِ بها ندارد.
MONEY_MODULE, MONEY_ACTION = "accounting", "view"

#: نامِ فیلدهایی که «بها» حساب می‌شوند و بی مجوزِ حسابداری `None` می‌شوند.
#: دقیقاً همان نام‌هایی که در `schemas/reports.py` تهی‌پذیر شده‌اند. اگر نامی
#: این‌جا باشد و آن‌جا نه، پاسخ در اعتبارسنجی می‌شکند — که بهتر از لو رفتنِ بهاست.
_MONEY_FIELDS = frozenset({
    "opening_value", "in_value", "out_value", "book_value", "unit_cost", "stock_value",
    "recorded_unit_cost", "value_in", "value_out", "balance_value", "average_cost",
    "closing_value", "total_value", "total_value_in", "total_value_out",
    "total_opening_value", "total_in_value", "total_out_value", "total_book_value",
    "net_value",
})


def _redact_money(payload, allowed: bool):
    """مبالغ را `None` می‌کند وقتی کاربر مجوزِ بها ندارد.

    `None` است نه صفر — صفر یک عددِ واقعی است و «اجازه نداری ببینی» نیست. همان
    تمایزی که گزارشِ مبلغی بینِ «بی‌بها» و «بهای صفر» می‌گذارد.
    """
    if allowed:
        return payload
    if isinstance(payload, dict):
        return {
            key: (None if key in _MONEY_FIELDS else _redact_money(value, allowed))
            for key, value in payload.items()
        }
    if isinstance(payload, list):
        return [_redact_money(row, allowed) for row in payload]
    return payload


@router.get("/inventory", response_model=InventoryReportOut)
def inventory_report(
    warehouse_id: UUID | None = Query(None),
    as_of: date | None = Query(None),
    date_from: date | None = Query(None),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
    _=Depends(require_permission("inventory", "view")),
):
    """مرورِ موجودی — مقدار برای انباردار، مبلغ فقط با مجوزِ حسابداری."""
    return _redact_money(
        reports_service.get_inventory_report(db, warehouse_id, as_of, date_from),
        principal.has_permission(MONEY_MODULE, MONEY_ACTION),
    )


@router.get("/kardex/{item_id}", response_model=KardexReportOut)
def kardex(
    item_id: UUID,
    warehouse_id: UUID | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
    _=Depends(require_permission("inventory", "view")),
):
    return _redact_money(
        reports_service.get_kardex(db, item_id, warehouse_id, date_from, date_to),
        principal.has_permission(MONEY_MODULE, MONEY_ACTION),
    )


@router.get("/inventory-breakdown", response_model=InventoryBreakdownOut)
def inventory_breakdown(
    dimension: str = Query(..., description="supplier | customer | purpose"),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    warehouse_id: UUID | None = Query(None),
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
    _=Depends(require_permission("inventory", "view")),
):
    """گردشِ انبار از زاویه‌ی تأمین‌کننده، مشتری یا هدفِ حرکت.

    دفترِ دومی در کار نیست: همان `valuation.replay`ِ کاردکس، فقط با کلیدِ
    جمع‌زدنِ دیگر. پس عددها با کاردکس می‌خوانند یا هر دو باگ دارند.
    """
    if dimension not in inventory_analytics.DIMENSIONS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"بُعدِ گزارش باید یکی از {', '.join(inventory_analytics.DIMENSIONS)} باشد",
        )
    return _redact_money(
        inventory_analytics.breakdown(
            db,
            dimension=dimension,
            date_from=date_from,
            date_to=date_to,
            warehouse_id=warehouse_id,
        ),
        principal.has_permission(MONEY_MODULE, MONEY_ACTION),
    )


@router.get("/contact-statement/{contact_id}", response_model=ContactStatementOut)
def contact_statement(
    contact_id: UUID,
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    return reports_service.get_contact_statement(db, contact_id, date_from, date_to)


# ───────────────────── مرور جامع طرف حساب ─────────────────────
#
# سه اندپوینت برای سه دانه‌بندی. عمداً یکی نشده‌اند: یک پاسخِ واحد که هر سه را
# با هم بدهد، رابط را وادار می‌کند اقلام را جمع بزند تا خلاصه دربیاورد — و
# همان‌جاست که یک مبلغ چند بار شمرده می‌شود.
#
# هر سه `accounting.view` می‌خواهند، چون هر سه مانده‌ی حساب‌های دریافتنی و
# پرداختنی را نشان می‌دهند — همان چیزی که کارتِ حساب هم می‌خواهد.


@router.get("/counterparty/{contact_id}/summary", response_model=CounterpartySummaryOut)
def counterparty_summary(
    contact_id: UUID,
    as_of: date | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    """خلاصه‌ی نقش‌محورِ یک طرف حساب — و تطبیقش با دفتر."""
    return counterparty_service.position_summary(db, contact_id, as_of=as_of)


@router.get("/counterparty/{contact_id}/events", response_model=list[CounterpartyEventOut])
def counterparty_events(
    contact_id: UUID,
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    role: str | None = Query(None, description="customer | supplier"),
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    """خطِ زمانیِ رویدادها با ماندهٔ در حالِ اجرا.

    مانده از **کلِ تاریخ** ساخته می‌شود و بعد بازه بریده می‌شود، وگرنه ردیفِ اولِ
    بازه از صفر شروع می‌کرد.
    """
    return counterparty_service.events(
        db, contact_id, date_from=date_from, date_to=date_to, role=role
    )


@router.get(
    "/counterparty/{contact_id}/events/{source_type}/{source_id}/lines",
    response_model=CounterpartyEventDetailOut,
)
def counterparty_event_lines(
    contact_id: UUID,
    source_type: str,
    source_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    """اقلامِ یک رویداد — ردیف‌های کالا و ردیف‌های دفتر، هرکدام با برچسبِ نوعش.

    `contact_id` در مسیر می‌ماند تا آدرس خودش بگوید از کجای گزارش آمده، و
    drill-downِ برعکس هم ممکن باشد.
    """
    return counterparty_service.event_lines(db, source_type, source_id)


# ───────────────────── مرور فروش ─────────────────────
#
# شش نما، شش اندپوینت. یکی نشده‌اند چون دانه‌بندی‌شان فرق دارد و یک پاسخِ واحد
# رابط را وادار می‌کرد از یکی، دیگری را بسازد — همان‌جا که یک مبلغ دو بار
# شمرده می‌شود.
#
# `accounting.view` نمی‌خواهند: این‌ها فروش‌اند نه دفتر. همان مجوزِ `sales.view`
# که فهرستِ فاکتورها دارد.


def _sales_scope(
    date_from: date | None,
    date_to: date | None,
    contact_id: UUID | None,
    item_id: UUID | None,
    sale_type_id: UUID | None,
    warehouse_id: UUID | None,
) -> sales_review_service.Scope:
    return sales_review_service.Scope(
        date_from=date_from,
        date_to=date_to,
        contact_id=contact_id,
        item_id=item_id,
        sale_type_id=sale_type_id,
        warehouse_id=warehouse_id,
    )


_sales_view = require_permission("sales", "view")


@router.get("/sales-review/summary", response_model=SalesReviewSummaryOut)
def sales_review_summary(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    contact_id: UUID | None = Query(None),
    item_id: UUID | None = Query(None),
    sale_type_id: UUID | None = Query(None),
    warehouse_id: UUID | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(_sales_view),
):
    """شاخص‌های بازه — از دانه‌بندیِ سند، نه از جمعِ نمایی دیگر."""
    return sales_review_service.summary(
        db, _sales_scope(date_from, date_to, contact_id, item_id, sale_type_id, warehouse_id)
    )


@router.get("/sales-review/items", response_model=list[SalesByItemOut])
def sales_review_items(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    contact_id: UUID | None = Query(None),
    item_id: UUID | None = Query(None),
    sale_type_id: UUID | None = Query(None),
    warehouse_id: UUID | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(_sales_view),
):
    """نمای کالا — فروش، برگشت، و تحققِ فیزیکی کنارِ هم."""
    return sales_review_service.by_item(
        db, _sales_scope(date_from, date_to, contact_id, item_id, sale_type_id, warehouse_id)
    )


@router.get("/sales-review/customers", response_model=list[SalesByCustomerOut])
def sales_review_customers(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    contact_id: UUID | None = Query(None),
    item_id: UUID | None = Query(None),
    sale_type_id: UUID | None = Query(None),
    warehouse_id: UUID | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(_sales_view),
):
    """نمای مشتری — فروشِ همین بازه. **مانده‌ی طرف حساب نیست.**"""
    return sales_review_service.by_customer(
        db, _sales_scope(date_from, date_to, contact_id, item_id, sale_type_id, warehouse_id)
    )


@router.get("/sales-review/warehouses", response_model=list[SalesByWarehouseOut])
def sales_review_warehouses(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    contact_id: UUID | None = Query(None),
    item_id: UUID | None = Query(None),
    sale_type_id: UUID | None = Query(None),
    warehouse_id: UUID | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(_sales_view),
):
    """نمای انبار — تحققِ فیزیکی. **دفترِ موجودی نیست.**"""
    return sales_review_service.by_warehouse(
        db, _sales_scope(date_from, date_to, contact_id, item_id, sale_type_id, warehouse_id)
    )


@router.get("/sales-review/documents", response_model=list[SalesDocumentOut])
def sales_review_documents(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    contact_id: UUID | None = Query(None),
    item_id: UUID | None = Query(None),
    sale_type_id: UUID | None = Query(None),
    warehouse_id: UUID | None = Query(None),
    voided: bool = Query(False, description="فقط فاکتورهای ابطالی"),
    db: Session = Depends(get_db),
    _=Depends(_sales_view),
):
    """نمای اسنادِ فروش — یک ردیف برای هر سند.

    `voided=true` نمای **فاکتورهای ابطالی** را می‌دهد: آن‌ها در هیچ نمای دیگری
    شمرده نمی‌شوند، ولی تاریخ پاک نمی‌شود.
    """
    scope = _sales_scope(date_from, date_to, contact_id, item_id, sale_type_id, warehouse_id)
    if voided:
        return sales_review_service.voided_documents(db, scope)
    return sales_review_service.documents(db, scope)


@router.get("/sales-review/lines", response_model=list[SalesLineOut])
def sales_review_lines(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    contact_id: UUID | None = Query(None),
    item_id: UUID | None = Query(None),
    sale_type_id: UUID | None = Query(None),
    warehouse_id: UUID | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(_sales_view),
):
    """نمای اقلامِ فروش — ریزترین دانه‌بندی. با نمای اسناد **جمع نمی‌شود**."""
    return sales_review_service.lines(
        db, _sales_scope(date_from, date_to, contact_id, item_id, sale_type_id, warehouse_id)
    )


@router.get("/sales-review/preinvoices", response_model=list[PreinvoiceProgressOut])
def sales_review_preinvoices(
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    contact_id: UUID | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(_sales_view),
):
    """پیشرفتِ پیش‌فاکتور — پیشنهادشده، فاکتورشده، خارج‌شده."""
    return sales_review_service.preinvoices(
        db, _sales_scope(date_from, date_to, contact_id, None, None, None)
    )
