from uuid import UUID

from dataclasses import replace
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.deps import Principal, get_principal, require_permission
from app.models.counters import DOC_JOURNAL_ENTRY
from app.models.analytic import AnalyticAccount
from app.models.cost_center import CostCenter
from app.services.common import number_lines
from app.services.printing import render_journal_entry
from app.services.numbering import next_document_number
from app.models.accounting import Account, JournalEntry, JournalLine
from app.models.user import User
from app.pagination import Page, PageParams, paginate
from app.routers.reports import report_filters
from app.schemas.accounting import (
    EntrySourceOut,
    JournalEntryIn,
    JournalEntryOut,
    JournalListSummaryOut,
    SubNumberIn,
)
from app.schemas.voiding import VoidIn, VoidOut
from app.services import entry_source
from app.services.analytics import resolve_analytic_id
from app.services.cost_centers import resolve_cost_center_id
from app.services.period_close import assert_period_open
from app.services.reports import ReportFilters, apply_report_filters
from app.services import tafsili
from app.services.voiding import void_journal_entry

router = APIRouter(prefix="/api/journal-entries", tags=["journal"])


class JournalLineInputError(HTTPException):
    """متن قدیمیِ `detail` را نگه می‌دارد و جایگاهِ ردیف را جدا می‌افزاید.

    `HTTPException` است تا مثلِ هر خطای دیگرِ روتر **raise** شود و `get_db` تراکنش را
    rollback کند. پاسخِ پیش‌فرضِ FastAPI فقط `detail` را می‌نویسد، پس
    `journal_line_error_handler` همان پاسخ را با `line_errors` می‌سازد.
    """

    def __init__(self, status_code: int, detail: str, line_errors: list[dict]):
        super().__init__(status_code=status_code, detail=detail)
        self.line_errors = line_errors


async def journal_line_error_handler(request: Request, exc: JournalLineInputError) -> JSONResponse:
    """`{detail, line_errors}` — همان شکلی که کلاینت از #183 می‌خواند؛ `detail` همان متنِ قدیمی."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "line_errors": exc.line_errors},
        headers=exc.headers,
    )


def _assert_tracking_allowed(db: Session, lines) -> None:
    """پیگیری فقط روی حسابی که «پیگیری» دارد.

    رد کردن، نه دور ریختنِ خاموش: اگر کاربر شماره‌ی حواله‌ای وارد کرده و سرور آن را
    بی‌صدا نادیده می‌گرفت، سند ثبت می‌شد و آن ارجاع برای همیشه گم بود — و کسی هم
    نمی‌فهمید، چون هیچ خطایی نیامده بود.
    """
    wanted = {
        line.account_id for line in lines if line.tracking_no is not None or line.tracking_date is not None
    }
    if not wanted:
        return
    allowed = {
        row.id
        for row in db.query(Account.id).filter(
            Account.id.in_(wanted), Account.has_tracking.is_(True)
        )
    }
    missing = wanted - allowed
    if missing:
        names = [
            f"{a.code} {a.name}"
            for a in db.query(Account).filter(Account.id.in_(missing)).order_by(Account.code)
        ]
        invalid_lines = [
            {"index": index, "field": "tracking_no", "message": "این حساب پیگیری نمی‌پذیرد."}
            for index, line in enumerate(lines)
            if line.account_id in missing and (line.tracking_no is not None or line.tracking_date is not None)
        ]
        raise JournalLineInputError(
            status.HTTP_400_BAD_REQUEST,
            "این حساب‌ها پیگیری نمی‌پذیرند؛ از ویرایشِ حساب گزینه‌ی «پیگیری» را "
            f"روشن کنید: {'، '.join(names)}",
            invalid_lines,
        )


def _filtered_entries(
    db: Session,
    filters: ReportFilters,
    q: str | None,
    *,
    atf: int | None = None,
    sub: str | None = None,
    desc: str | None = None,
):
    """اسنادی که فهرست و جمعِ آن می‌بینند — **یک تعریف برای هر دو**.

    فیلترها همان `ReportFilters`ِ دفتر و تراز است و از همان `apply_report_filters` رد
    می‌شود، نه نسخه‌ی دومی از آن. سند وقتی می‌آید که **دست‌کم یکی** از ردیف‌هایش از
    فیلتر رد شود، چون مرکز هزینه و تفصیلی روی ردیف‌اند نه روی سند. دفتر روزنامه سند
    را کامل نشان می‌دهد، همان‌طور که ثبت شده.

    تاریخ جدا اعمال می‌شود، چون `apply_report_filters` عمداً تاریخ نمی‌گیرد.

    `atf`، `sub` و `desc` فیلترهای **ستونیِ** فهرستِ اسناد‌اند (سرستونِ جدول): هرکدام فقط
    ستونِ خودش را می‌گیرد و با بقیه «و» می‌شود. `q` همان جست‌وجوی سراسری است که در همه‌ی
    این ستون‌ها با «یا» می‌گردد. شماره‌ی سند فیلترِ ستونیِ جدا نمی‌خواهد:
    `entry_from = entry_to` همان است.
    """
    query = db.query(JournalEntry)
    if filters.date_from is not None:
        query = query.filter(JournalEntry.entry_date >= filters.date_from)
    if filters.date_to is not None:
        query = query.filter(JournalEntry.entry_date <= filters.date_to)
    #: بدونِ فیلترِ دیگری، کوئری همان است که پیش از این بود — زیرکوئریِ بی‌مصرف نمی‌خورد.
    if replace(filters, date_from=None, date_to=None) != ReportFilters():
        matching = apply_report_filters(
            db,
            select(JournalLine.entry_id).join(JournalEntry, JournalLine.entry_id == JournalEntry.id),
            filters,
        )
        query = query.filter(JournalEntry.id.in_(matching))
    if q:
        term = q.strip()
        # شماره فرعی هم متن است و هم چیزی که کاربر با آن دنبالِ سند می‌گردد، پس
        # مثلِ شرح جستجوی جزئی می‌شود؛ عطف و شماره‌ی سند عددی و دقیق‌اند.
        conditions = [
            JournalEntry.description.ilike(f"%{term}%"),
            JournalEntry.sub_number.ilike(f"%{term}%"),
        ]
        if term.isdigit():
            conditions.append(JournalEntry.number == int(term))
            conditions.append(JournalEntry.atf_number == int(term))
        query = query.filter(or_(*conditions))
    if atf is not None:
        query = query.filter(JournalEntry.atf_number == atf)
    if sub and sub.strip():
        query = query.filter(JournalEntry.sub_number.ilike(f"%{sub.strip()}%"))
    if desc and desc.strip():
        query = query.filter(JournalEntry.description.ilike(f"%{desc.strip()}%"))
    return query


@router.get("", response_model=Page[JournalEntryOut])
def list_entries(
    filters: ReportFilters = Depends(report_filters),
    q: str | None = None,
    atf: int | None = None,
    sub: str | None = None,
    desc: str | None = None,
    db: Session = Depends(get_db),
    params: PageParams = Depends(),
    _=Depends(require_permission("accounting", "view")),
):
    """فهرستِ اسناد با فیلترهای اختیاری.

    فیلترها سمتِ سرورند نه کلاینت: صفحه‌ی «سند حسابداری»، کارتابل، ادغام و دفترِ
    روزنامه همگی زیرمجموعه‌ای از همین فهرست را می‌خواهند، و کشیدنِ کلِ دفتر برای
    فیلترکردنِ آن در مرورگر با هر کسب‌وکارِ چندساله از کار می‌افتاد.

    فیلترها همان `report_filters`ِ دفتر و تراز است. پیش از این فقط تاریخ و وضعیت و
    منشأ را می‌شناخت، و دفتر روزنامه نمی‌توانست بر اساسِ شماره‌ی سند یا مرکز هزینه
    فیلتر کند.
    """
    query = _filtered_entries(db, filters, q, atf=atf, sub=sub, desc=desc).options(
        selectinload(JournalEntry.lines)
    )

    # (entry_date, number) یکتاست چون number از sequence می‌آید — کلید امن برای keyset
    items, next_cursor = paginate(
        query,
        [JournalEntry.entry_date, JournalEntry.number],
        params,
    )

    #: منبعِ هر سند **دسته‌ای** حل می‌شود: یک کوئری به‌ازای هر *نوعِ* منبع، نه
    #: به‌ازای هر سند. صفحه‌ی دویست‌تایی حداکثر به تعدادِ *نوع‌ها* کوئری می‌خورد.
    sources = entry_source.resolve_sources(db, items)
    rows = []
    for entry in items:
        row = JournalEntryOut.model_validate(entry)
        found = sources.get(entry.id)
        row.source = EntrySourceOut(**found) if found is not None else None
        rows.append(row)
    return Page(items=rows, next_cursor=next_cursor)


#: پیش از `/{entry_id}`، وگرنه «summary» به‌عنوانِ شناسه‌ی سند خوانده می‌شود و ۴۲۲ می‌گیرد.
@router.get("/summary", response_model=JournalListSummaryOut)
def list_summary(
    filters: ReportFilters = Depends(report_filters),
    q: str | None = None,
    atf: int | None = None,
    sub: str | None = None,
    desc: str | None = None,
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    """جمعِ کلِ همان دامنه‌ای که `list_entries` صفحه‌به‌صفحه می‌دهد.

    جمعِ ردیف‌ها فقط ردیف‌هایی را می‌شمارد که خودشان از فیلتر رد می‌شوند. سندی با یک
    ردیفِ «مرکز تهران» و یک ردیفِ «مرکز شیراز»، با فیلترِ تهران در فهرست می‌آید ولی
    فقط ردیفِ تهرانش در جمع است — همان عددی که دفتر و تراز با همان فیلتر می‌دهند.
    """
    entries = _filtered_entries(db, filters, q, atf=atf, sub=sub, desc=desc)
    entry_count = entries.count()
    lines = db.query(
        func.count(JournalLine.id),
        func.coalesce(func.sum(JournalLine.debit), 0),
        func.coalesce(func.sum(JournalLine.credit), 0),
    ).join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
    lines = lines.filter(JournalLine.entry_id.in_(entries.with_entities(JournalEntry.id).scalar_subquery()))
    line_count, debit, credit = apply_report_filters(db, lines, filters).one()
    return JournalListSummaryOut(
        entry_count=entry_count, line_count=line_count, total_debit=debit, total_credit=credit
    )


@router.get("/{entry_id}", response_model=JournalEntryOut)
def get_entry(
    entry_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    """یک سند با ردیف‌ها و منشأش.

    آخرین پله‌ی drill-down: از تراز به دفتر، از دفترِ حساب به همین‌جا. تا پیش از
    این تنها راهِ دیدنِ یک سند، یافتنش در *فهرست* بود — یعنی هر گزارشی ته‌اش
    بن‌بست می‌شد.
    """
    entry = (
        db.query(JournalEntry)
        .options(selectinload(JournalEntry.lines))
        .filter(JournalEntry.id == entry_id)
        .first()
    )
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سند یافت نشد")
    row = JournalEntryOut.model_validate(entry)
    found = entry_source.resolve_source(db, entry)
    row.source = EntrySourceOut(**found) if found is not None else None
    return row


@router.post("", response_model=JournalEntryOut, status_code=201)
def create_entry(
    data: JournalEntryIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("accounting", "create")),
):
    assert_period_open(db, data.entry_date)
    cost_center_id = resolve_cost_center_id(db, data.cost_center_id)
    entry_analytic_id = resolve_analytic_id(db, data.analytic_id)
    #: خطای ردیف **raise** می‌شود، نه return: `get_db` فقط وقتی rollback می‌کند که
    #: استثنا از روتر بیرون برود، و پاسخِ برگشتیِ ۴۰۰ یعنی commitِ همان تراکنش. امروز
    #: پیش از این گاردها چیزی نوشته نمی‌شود، ولی «خطا = rollback» قاعده‌ی کلِ پروژه
    #: است و نباید به ترتیبِ خط‌ها وابسته بماند. شکلِ پاسخ را
    #: `journal_line_error_handler` (ثبت در main.py) می‌سازد.
    _assert_tracking_allowed(db, data.lines)

    # تفصیلیِ ردیف بر تفصیلیِ سند مقدم است: سطحِ ریزتر همیشه برنده. یک‌بار این‌جا
    # حل می‌شود تا هم گاردِ زیر و هم ساختِ ردیف‌ها از یک مقدار بخوانند — وگرنه
    # گارد چیزی را می‌سنجید که با آنچه ذخیره می‌شود یکی نیست.
    line_analytics = []
    for index, line in enumerate(data.lines):
        try:
            line_analytics.append(resolve_analytic_id(db, line.analytic_id) or entry_analytic_id)
        except HTTPException as exc:
            raise JournalLineInputError(exc.status_code, str(exc.detail), [
                {"index": index, "field": "analytic_id", "message": str(exc.detail)},
            ]) from exc
    #: مرکزِ هزینه هم همان قاعده: ردیف بر سند مقدم است. هر مرکزِ ردیف جداگانه
    #: اعتبارسنجی می‌شود (نامعتبر یا غیرفعال → ۴۰۰)، دقیقاً مثلِ مرکزِ سند.
    line_centers = []
    for index, line in enumerate(data.lines):
        try:
            line_centers.append(resolve_cost_center_id(db, line.cost_center_id) or cost_center_id)
        except HTTPException as exc:
            raise JournalLineInputError(exc.status_code, str(exc.detail), [
                {"index": index, "field": "cost_center_id", "message": str(exc.detail)},
            ]) from exc
    try:
        tafsili.assert_lines_have_tafsili(
            db,
            [(line.account_id, analytic) for line, analytic in zip(data.lines, line_analytics)],
            source_type="manual",
        )
    except HTTPException as exc:
        missing_ids = {line.account_id for line, analytic in zip(data.lines, line_analytics) if analytic is None}
        required_ids = {
            row.id for row in db.query(Account.id).filter(
                Account.id.in_(missing_ids), Account.accepts_tafsili.is_(True)
            )
        }
        line_errors = [
            {"index": index, "field": "analytic_id", "message": "تفصیلیِ این ردیف الزامی است."}
            for index, (line, analytic) in enumerate(zip(data.lines, line_analytics))
            if analytic is None and line.account_id in required_ids
        ]
        if not line_errors:
            raise
        raise JournalLineInputError(exc.status_code, str(exc.detail), line_errors) from exc

    # شماره‌ی سند از یک sequence اتمیک پایگاه‌داده گرفته می‌شود تا زیر بار همزمان چند کاربر تصادم نکند
    number = next_document_number(db, DOC_JOURNAL_ENTRY)

    entry = JournalEntry(
        number=number,
        # عطف اینجا داده نمی‌شود: رویدادِ `_assign_atf_number` در سرویسِ شماره‌گذاری
        # پیش از فلاش رویش می‌نشیند، برای *همه‌ی* مسیرهای ساختِ سند نه فقط این یکی.
        sub_number=data.sub_number,
        entry_date=data.entry_date,
        description=data.description,
        source_type="manual",
        status=data.status,
        created_by_id=user.id,
        lines=number_lines([
            JournalLine(
                account_id=line.account_id,
                cost_center_id=center,
                analytic_id=analytic,
                debit=line.debit,
                credit=line.credit,
                description=line.description,
                currency_code=line.currency_code,
                fx_amount=line.fx_amount,
                fx_rate=line.fx_rate,
                tracking_no=line.tracking_no,
                tracking_date=line.tracking_date,
            )
            for line, analytic, center in zip(data.lines, line_analytics, line_centers)
        ]),
    )
    db.add(entry)
    db.flush()
    db.refresh(entry)
    return entry


@router.patch("/{entry_id}/sub-number", response_model=JournalEntryOut)
def set_sub_number(
    entry_id: UUID,
    data: SubNumberIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "update")),
):
    """اصلاحِ شماره فرعیِ یک سند.

    شماره فرعی ارجاعِ کاربر است نه واقعیتِ مالی، پس اصلاحش هیچ رقمی را جابه‌جا
    نمی‌کند. با این حال فقط روی سندِ **موقت** باز است: «دائم» در این برنامه یعنی
    امضاشده، و استثنا گذاشتن برای «فقط یک فیلدِ بی‌خطر» همان‌جایی است که این‌طور
    قاعده‌ها می‌شکنند. سندِ باطل هم دست‌نخوردنی است.
    """
    entry = db.query(JournalEntry).filter(JournalEntry.id == entry_id).first()
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سند پیدا نشد")
    if entry.voided_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "سندِ باطل‌شده ویرایش نمی‌شود")
    if entry.status != "temporary":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "سندِ دائم ویرایش نمی‌شود؛ شماره فرعی را پیش از دائم‌کردن ثبت کنید",
        )

    entry.sub_number = data.sub_number
    db.flush()
    db.refresh(entry)
    return entry


@router.post("/{entry_id}/void", response_model=VoidOut)
def void_entry(
    entry_id: UUID,
    data: VoidIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("accounting", "delete")),
):
    """ابطالِ سندِ دستی با ثبتِ سندِ معکوس.

    مجوز عمداً «delete» است (مثلِ ابطالِ فاکتور): اثرِ برگشت‌ناپذیرِ حسابداری دارد و
    نباید در اختیارِ نقشی باشد که فقط «update» دارد. فقط سندِ دستی؛ سندی که یک ماژول
    (فاکتور، حقوق، …) ساخته باید از راهِ ابطالِ همان منبع برگردد — سرویس این را گارد
    می‌کند و ۴۰۹ می‌دهد.
    """
    reversal = void_journal_entry(db, entry_id, reason=data.reason, user=user, void_date=data.void_date)
    return VoidOut(reversal_entry_id=reversal.id, reversal_entry_number=reversal.number)


@router.get("/{entry_id}/print", response_class=HTMLResponse)
def print_journal_entry(
    entry_id: UUID,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
    _=Depends(require_permission("accounting", "view")),
):
    """برگه‌ی چاپیِ سند حسابداری.

    مجوز «view» است نه «create»: چاپ خواندن است. همان مرزی که چاپِ فاکتور دارد.

    نام‌های حساب، تفصیلی و مرکز هزینه این‌جا با یک کوئریِ دسته‌ای گرفته می‌شوند نه
    یکی‌به‌ازای‌هر‌ردیف — سندِ بیست‌ردیفی وگرنه شصت رفت‌وبرگشت می‌زد.
    """
    entry = db.get(JournalEntry, entry_id)
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سند یافت نشد")

    accounts = {
        a.id: a
        for a in db.query(Account).filter(Account.id.in_({l.account_id for l in entry.lines})).all()
    }
    analytic_ids = {l.analytic_id for l in entry.lines if l.analytic_id}
    analytics = (
        {a.id: a.name for a in db.query(AnalyticAccount).filter(AnalyticAccount.id.in_(analytic_ids)).all()}
        if analytic_ids
        else {}
    )
    center_ids = {l.cost_center_id for l in entry.lines if l.cost_center_id}
    centers = (
        {c.id: c.name for c in db.query(CostCenter).filter(CostCenter.id.in_(center_ids)).all()}
        if center_ids
        else {}
    )

    html = render_journal_entry(
        business_name=principal.membership.tenant.name,
        number=entry.number,
        atf_number=entry.atf_number,
        sub_number=entry.sub_number or "",
        entry_date=entry.entry_date,
        status=entry.status,
        description=entry.description,
        source_label=entry_source.describe(entry_source.resolve_source(db, entry)),
        lines=[
            {
                "seq": line.seq,
                "account_code": accounts[line.account_id].code if line.account_id in accounts else "",
                "account_name": accounts[line.account_id].name if line.account_id in accounts else "",
                "analytic_name": analytics.get(line.analytic_id, ""),
                "cost_center_name": centers.get(line.cost_center_id, ""),
                "description": line.description,
                "tracking_no": line.tracking_no,
                "tracking_date": line.tracking_date,
                "debit": line.debit,
                "credit": line.credit,
            }
            for line in entry.lines
        ],
        voided_at=entry.voided_at,
        void_reason=entry.void_reason,
    )
    return HTMLResponse(content=html, headers={"Cache-Control": "no-store"})
