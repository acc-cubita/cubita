from uuid import UUID

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.deps import require_permission
from app.models.counters import DOC_JOURNAL_ENTRY
from app.services.numbering import next_document_number
from app.models.accounting import JournalEntry, JournalLine
from app.models.user import User
from app.pagination import Page, PageParams, paginate
from app.schemas.accounting import JournalEntryIn, JournalEntryOut, SubNumberIn
from app.schemas.voiding import VoidIn, VoidOut
from app.services.analytics import resolve_analytic_id
from app.services.cost_centers import resolve_cost_center_id
from app.services.period_close import assert_period_open
from app.services.voiding import void_journal_entry

router = APIRouter(prefix="/api/journal-entries", tags=["journal"])


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
    return Page(items=items, next_cursor=next_cursor)


@router.post("", response_model=JournalEntryOut, status_code=201)
def create_entry(
    data: JournalEntryIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("accounting", "create")),
):
    assert_period_open(db, data.entry_date)
    cost_center_id = resolve_cost_center_id(db, data.cost_center_id)
    entry_analytic_id = resolve_analytic_id(db, data.analytic_id)

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
        lines=[
            JournalLine(
                account_id=line.account_id,
                cost_center_id=cost_center_id,
                # تفصیلیِ ردیف بر تفصیلیِ سند مقدم است: سطحِ ریزتر همیشه برنده.
                analytic_id=resolve_analytic_id(db, line.analytic_id) or entry_analytic_id,
                debit=line.debit,
                credit=line.credit,
                description=line.description,
                currency_code=line.currency_code,
                fx_amount=line.fx_amount,
                fx_rate=line.fx_rate,
            )
            for line in data.lines
        ],
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
