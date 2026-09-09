"""روترِ عملیاتِ حسابداری — همه زیرِ `/api/accounting`.

الگوی مشترکِ هر عملیاتِ سندساز: یک `GET .../preview` که *فقط* می‌خواند و یک `POST`
که صادر می‌کند. کاربر همیشه پیش از هر سندی، دقیقاً همان سند را می‌بیند.

مجوزها عمدی‌اند: خواندن با `view`، صدورِ سند با `create`، و عملیاتی که ساختارِ
موجود را دست می‌زند (بازشماره‌گذاری، ادغام، اصلاحِ طبقه‌بندی) با `update` — چون
اثرشان روی داده‌ی *موجود* است نه ساختِ چیزِ تازه.
"""
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_permission
from app.models.user import User
from app.schemas.accounting_ops import (
    AccountingOverviewOut,
    AnalyticIn,
    AnalyticOut,
    AnalyticUpdateIn,
    BalancedIssueOut,
    BalanceRowOut,
    CartableOut,
    ClosingPreviewOut,
    FinalizeIn,
    FinalizeOut,
    FxIssueOut,
    FxPreviewOut,
    IssueIn,
    LegalBookOut,
    MergeIn,
    MergeOut,
    OpeningIssueIn,
    OpeningPreviewOut,
    PnlIssueOut,
    PnlPreviewOut,
    ReclassIn,
    ReclassPreviewOut,
    ReclassSourceRowOut,
    ReclassifyIn,
    ReclassifyOut,
    RenumberIn,
    RenumberPreviewOut,
    RenumberResultOut,
)
from app.services import accounting_ops as ops
from app.routers.reports import report_filters
from app.services.reports import ReportFilters
from app.services import analytics as an

router = APIRouter(prefix="/api/accounting", tags=["accounting-ops"])


# ───────────────────────────── نمای کلی ─────────────────────────────


@router.get("/overview", response_model=AccountingOverviewOut)
def overview(db: Session = Depends(get_db), _=Depends(require_permission("accounting", "view"))):
    return ops.get_overview(db)


# ─────────────────── کارتابل و تبدیلِ موقت به دائم ───────────────────


@router.get("/cartable", response_model=CartableOut)
def cartable(
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    return ops.get_cartable(db, date_from, date_to)


@router.post("/entries/finalize", response_model=FinalizeOut)
def finalize(
    data: FinalizeIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("accounting", "update")),
):
    return ops.finalize_entries(
        db,
        user,
        date_from=data.date_from,
        date_to=data.date_to,
        #: خالی به None تبدیل نمی‌شود: سرویس بینِ «انتخاب نکردم» و «انتخابم
        #: خالی بود» فرق می‌گذارد و دومی خطاست، نه «فیلتری نیست».
        entry_ids=data.entry_ids,
        source_type=data.source_type,
    )


# ─────────────────── بازشماره‌گذاری و ادغامِ اسناد ───────────────────


@router.get("/entries/renumber/preview", response_model=RenumberPreviewOut)
def renumber_preview(
    date_from: date | None = None,
    date_to: date | None = None,
    start_number: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    return ops.preview_renumber(db, date_from, date_to, start_number)


@router.post("/entries/renumber", response_model=RenumberResultOut)
def renumber(
    data: RenumberIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("accounting", "update")),
):
    return ops.renumber_entries(
        db, user, data.date_from, data.date_to, data.start_number, data.entry_ids
    )


@router.post("/entries/merge", response_model=MergeOut)
def merge(
    data: MergeIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("accounting", "update")),
):
    return ops.merge_entries(db, user, data.entry_ids, data.description)


# ──────────────────────────── تسعیرِ ارز ─────────────────────────────


@router.get("/fx-revaluation/preview", response_model=FxPreviewOut)
def fx_preview(
    as_of: date,
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    return ops.fx_revaluation_preview(db, as_of)


@router.post("/fx-revaluation", response_model=FxIssueOut)
def fx_issue(
    data: IssueIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("accounting", "create")),
):
    return ops.issue_fx_revaluation(db, user, data.as_of, data.description)


# ────────────── سود و زیان، اختتامیه و افتتاحیه ──────────────────────


@router.get("/pnl-close/preview", response_model=PnlPreviewOut)
def pnl_preview(
    date_to: date,
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    """پیش‌نمایشِ «بستنِ حساب‌های سود و زیان» — همان ردیف‌هایی که صدور خواهد زد."""
    return ops.pnl_close_preview(db, date_to)


@router.post("/pnl-close", response_model=PnlIssueOut)
def pnl_issue(
    data: IssueIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("accounting", "create")),
):
    """**گامِ اول**: سندِ بستن را می‌زند و بس — دوره قفل نمی‌شود.

    قفلِ دوره گامِ دومِ جداست (`POST /api/fiscal-period-closes`) چون برگشت ندارد:
    نه حذفی هست نه بازگشایی. پیش از آن، این دو یک دکمه بودند و کاربر سندی را
    تأیید می‌کرد که هنوز ندیده بود.

    هر دو مسیر از `issue_pnl_close` رد می‌شوند، پس یک *پیاده‌سازی* بیشتر نیست.
    """
    return ops.issue_pnl_close(db, user, data.as_of, data.description)


@router.get("/closing-entry/preview", response_model=ClosingPreviewOut)
def closing_preview(
    as_of: date,
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    return ops.closing_entry_preview(db, as_of)


@router.post("/closing-entry", response_model=BalancedIssueOut)
def closing_issue(
    data: IssueIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("accounting", "create")),
):
    return ops.issue_closing_entry(db, user, data.as_of, data.description)


@router.get("/opening-entry/preview", response_model=OpeningPreviewOut)
def opening_preview(
    as_of: date,
    source_date: date,
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    return ops.opening_entry_preview(db, as_of, source_date)


@router.post("/opening-entry", response_model=BalancedIssueOut)
def opening_issue(
    data: OpeningIssueIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("accounting", "create")),
):
    return ops.issue_opening_entry(db, user, data.as_of, data.source_date, data.description)


# ────────────────────────── ترازها و دفاتر ──────────────────────────


@router.get("/balances", response_model=list[BalanceRowOut])
def balances(
    filters: ReportFilters = Depends(report_filters),
    include_zero_activity: bool = False,
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    """پایه‌ی «گزارش ترازها»، «مرور حساب‌ها» و «صدور سند کل».

    فیلترها همان‌هایی‌اند که دفتر می‌گیرد (`report_filters`) — عمداً، تا هر سه
    گزارش با یک فیلتر یک عدد بدهند.
    """
    return ops.get_balances(
        db, filters.date_from, filters.date_to, filters, include_zero_activity
    )


@router.get("/legal-book", response_model=LegalBookOut)
def legal_book(
    date_from: date,
    date_to: date,
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    return ops.get_legal_book(db, date_from, date_to)


# ─────────────────── اصلاحِ طبقه‌بندیِ حساب‌ها ────────────────────────


@router.post("/accounts/reclassify", response_model=ReclassifyOut)
def reclassify(
    data: ReclassifyIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "update")),
):
    return ops.reclassify_accounts(db, [i.model_dump() for i in data.items])


# ────────────────────────── تفصیلیِ سایر ────────────────────────────


@router.get("/analytics", response_model=list[AnalyticOut])
def list_analytics(
    include_inactive: bool = True,
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    return an.list_analytics(db, include_inactive=include_inactive)


@router.post("/analytics", response_model=AnalyticOut, status_code=201)
def create_analytic(
    data: AnalyticIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("accounting", "create")),
):
    return an.create_analytic(db, data, user)


@router.patch("/analytics/{analytic_id}", response_model=AnalyticOut)
def update_analytic(
    analytic_id: UUID,
    data: AnalyticUpdateIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "update")),
):
    return an.update_analytic(db, analytic_id, data)


@router.delete("/analytics/{analytic_id}", status_code=204)
def delete_analytic(
    analytic_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "delete")),
):
    an.delete_analytic(db, analytic_id)


# ──────────────── اصلاحِ طبقه‌بندیِ مانده ────────────────
#
# با «جابه‌جایی حساب در درختواره» (`/accounts/reclassify`) یکی نیست: آن یکی
# `parent_id`ِ حساب را عوض می‌کند و گزارشِ گذشته را هم تغییر می‌دهد؛ این یکی
# تاریخ را دست نمی‌زند و فقط یک سندِ متوازنِ تاریخ‌دار می‌سازد.


@router.get("/balance-reclass/sources", response_model=list[ReclassSourceRowOut])
def reclass_sources(
    as_of: date,
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    return ops.reclass_sources(db, as_of)


@router.post("/balance-reclass/preview", response_model=ReclassPreviewOut)
def reclass_preview(
    data: ReclassIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    return ops.reclass_preview(
        db,
        data.as_of,
        [s.model_dump() for s in data.sources],
        data.dest_account_id,
        data.dest_analytic_id,
    )


@router.post("/balance-reclass", response_model=BalancedIssueOut)
def reclass_issue(
    data: ReclassIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("accounting", "create")),
):
    return ops.issue_reclass(
        db,
        user,
        data.as_of,
        [s.model_dump() for s in data.sources],
        data.dest_account_id,
        data.dest_analytic_id,
        data.description,
    )
