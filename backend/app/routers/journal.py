from uuid import UUID

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from sqlalchemy import or_
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
from app.schemas.accounting import EntrySourceOut, JournalEntryIn, JournalEntryOut, SubNumberIn
from app.schemas.voiding import VoidIn, VoidOut
from app.services import entry_source
from app.services.analytics import resolve_analytic_id
from app.services.cost_centers import resolve_cost_center_id
from app.services.period_close import assert_period_open
from app.services import tafsili
from app.services.voiding import void_journal_entry

router = APIRouter(prefix="/api/journal-entries", tags=["journal"])


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
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "این حساب‌ها پیگیری نمی‌پذیرند؛ از ویرایشِ حساب گزینه‌ی «پیگیری» را "
            f"روشن کنید: {'، '.join(names)}",
        )


@router.get("", response_model=Page[JournalEntryOut])
def list_entries(
    date_from: date | None = None,
    date_to: date | None = None,
    status_filter: str | None = Query(None, alias="status"),
    source_type: str | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
    params: PageParams = Depends(),
    _=Depends(require_permission("accounting", "view")),
):
    """فهرستِ اسناد با فیلترهای اختیاری.

    فیلترها سمتِ سرورند نه کلاینت: صفحه‌ی «سند حسابداری»، کارتابل، ادغام و دفترِ
    روزنامه همگی زیرمجموعه‌ای از همین فهرست را می‌خواهند، و کشیدنِ کلِ دفتر برای
    فیلترکردنِ آن در مرورگر با هر کسب‌وکارِ چندساله از کار می‌افتاد.
    """
    query = db.query(JournalEntry).options(selectinload(JournalEntry.lines))
    if date_from is not None:
        query = query.filter(JournalEntry.entry_date >= date_from)
    if date_to is not None:
        query = query.filter(JournalEntry.entry_date <= date_to)
    if status_filter in ("temporary", "permanent"):
        query = query.filter(JournalEntry.status == status_filter)
    if source_type:
        query = query.filter(JournalEntry.source_type == source_type)
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
    _assert_tracking_allowed(db, data.lines)

    # تفصیلیِ ردیف بر تفصیلیِ سند مقدم است: سطحِ ریزتر همیشه برنده. یک‌بار این‌جا
    # حل می‌شود تا هم گاردِ زیر و هم ساختِ ردیف‌ها از یک مقدار بخوانند — وگرنه
    # گارد چیزی را می‌سنجید که با آنچه ذخیره می‌شود یکی نیست.
    line_analytics = [
        resolve_analytic_id(db, line.analytic_id) or entry_analytic_id for line in data.lines
    ]
    #: مرکزِ هزینه هم همان قاعده: ردیف بر سند مقدم است. هر مرکزِ ردیف جداگانه
    #: اعتبارسنجی می‌شود (نامعتبر یا غیرفعال → ۴۰۰)، دقیقاً مثلِ مرکزِ سند.
    line_centers = [resolve_cost_center_id(db, line.cost_center_id) or cost_center_id for line in data.lines]
    tafsili.assert_lines_have_tafsili(
        db,
        [(line.account_id, analytic) for line, analytic in zip(data.lines, line_analytics)],
        source_type="manual",
    )

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
