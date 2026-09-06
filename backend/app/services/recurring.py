"""اسناد تکرارشونده — قالب‌های سندِ دوره‌ای و تولیدِ بر اساس تقاضا.

هیچ زمان‌بندِ پس‌زمینه‌ای در کار نیست: کاربر (یا فراخوانیِ خودکارِ کلاینت هنگام ورود)
اندپوینت «تولید سررسیدها» را می‌زند و همه‌ی سررسیدهای گذشته تا امروز ساخته می‌شوند.
درستی‌اش به `next_run_date`ِ ذخیره‌شده وابسته است: هر سند که ساخته شود این تاریخ جلو
می‌رود، پس اجرای دوباره چیزی را دوباره نمی‌سازد. سررسیدی که در دوره‌ی مالیِ بسته بیفتد
رد می‌شود (ساخته نمی‌شود) ولی تاریخ باز هم جلو می‌رود تا قالب گیر نکند.
"""
import calendar
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.accounting import JournalLine
from app.models.recurring import RECURRING_FREQUENCIES, RecurringJournalEntry, RecurringJournalLine
from app.models.user import User
from app.schemas.recurring import RecurringEntryIn
from app.services.common import make_journal_entry
from app.services.cost_centers import resolve_cost_center_id
from app.services.period_close import get_latest_close_date

#: سقفِ ایمنی برای جلوگیری از حلقه‌ی بی‌پایان اگر منطقِ پیش‌روی تاریخ روزی بشکند.
_MAX_OCCURRENCES = 500


def _add_months(d: date, months: int) -> date:
    """`months` ماه به تاریخ اضافه می‌کند و روز را به آخرین روزِ ماهِ مقصد می‌چسباند.

    مثلاً ۳۱ فروردین + ۱ ماه = ۳۱ اردیبهشت نیست اگر آن ماه ۳۰ روز باشد؛ روی تقویمِ
    میلادیِ زیرین هم ۳۱ ژانویه + ۱ ماه = ۲۸/۲۹ فوریه. بدون این، پرش از ماه رخ می‌داد.
    """
    total = d.month - 1 + months
    year = d.year + total // 12
    month = total % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(d.day, last_day))


def _advance(d: date, frequency: str, interval: int) -> date:
    if frequency == "weekly":
        return d + timedelta(weeks=interval)
    if frequency == "monthly":
        return _add_months(d, interval)
    if frequency == "yearly":
        return _add_months(d, 12 * interval)
    raise HTTPException(status.HTTP_400_BAD_REQUEST, "تناوب نامعتبر است")


def _get_template(db: Session, template_id: UUID) -> RecurringJournalEntry:
    tpl = db.get(RecurringJournalEntry, template_id)
    if tpl is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "قالبِ سند تکرارشونده یافت نشد")
    return tpl


def _apply(tpl: RecurringJournalEntry, data: RecurringEntryIn, db: Session) -> None:
    # اعتبارِ مرکز هزینه یک‌بار همین‌جا سنجیده می‌شود (نه در هر تولید).
    tpl.title = data.title.strip()
    tpl.description = data.description
    tpl.frequency = data.frequency
    tpl.interval = data.interval
    tpl.start_date = data.start_date
    tpl.end_date = data.end_date
    #: `current` تا ویرایشِ قالبی که مرکزش بعداً بسته شده ممکن بماند — کاربر
    #: نباید برای عوض‌کردنِ عنوان مجبور به عوض‌کردنِ مرکز شود.
    tpl.cost_center_id = resolve_cost_center_id(db, data.cost_center_id, current=tpl.cost_center_id)
    # تا وقتی هنوز اجرا نشده، سررسیدِ بعدی همان شروع است؛ بعد از اولین اجرا دست نمی‌خورد
    # تا ویرایشِ قالب سندهای گذشته را دوباره نسازد.
    if tpl.last_run_date is None:
        tpl.next_run_date = data.start_date
    tpl.lines = [
        RecurringJournalLine(
            account_id=line.account_id,
            debit=line.debit,
            credit=line.credit,
            description=line.description,
        )
        for line in data.lines
    ]


def create_template(db: Session, data: RecurringEntryIn, user: User) -> RecurringJournalEntry:
    tpl = RecurringJournalEntry(
        start_date=data.start_date,
        next_run_date=data.start_date,
        is_active=True,
        created_by_id=user.id,
    )
    _apply(tpl, data, db)
    db.add(tpl)
    db.flush()
    db.refresh(tpl)
    return tpl


def update_template(db: Session, template_id: UUID, data: RecurringEntryIn) -> RecurringJournalEntry:
    tpl = _get_template(db, template_id)
    _apply(tpl, data, db)
    db.flush()
    db.refresh(tpl)
    return tpl


def set_active(db: Session, template_id: UUID, is_active: bool) -> RecurringJournalEntry:
    tpl = _get_template(db, template_id)
    tpl.is_active = is_active
    db.flush()
    db.refresh(tpl)
    return tpl


def delete_template(db: Session, template_id: UUID) -> None:
    # سندهای *تولیدشده* اسنادِ واقعی و ثبت‌شده‌اند و دست‌نخورده می‌مانند؛ فقط قالب حذف می‌شود.
    tpl = _get_template(db, template_id)
    db.delete(tpl)
    db.flush()


def _generate_one(db: Session, tpl: RecurringJournalEntry, user: User, as_of: date, latest_close: date | None) -> list:
    """همه‌ی سررسیدهای سررسیدشده‌ی یک قالب را تا `as_of` می‌سازد و تاریخ‌ها را جلو می‌برد."""
    generated = []
    skipped = 0
    guard = 0
    while tpl.is_active and tpl.next_run_date <= as_of:
        guard += 1
        if guard > _MAX_OCCURRENCES:
            break
        run_date = tpl.next_run_date
        if tpl.end_date is not None and run_date > tpl.end_date:
            tpl.is_active = False  # به پایان رسید
            break

        if latest_close is not None and run_date <= latest_close:
            # سررسید در دوره‌ی بسته — ساخته نمی‌شود ولی تاریخ جلو می‌رود تا گیر نکند.
            skipped += 1
        else:
            lines = [
                JournalLine(
                    account_id=line.account_id,
                    cost_center_id=tpl.cost_center_id,
                    debit=line.debit,
                    credit=line.credit,
                    description=line.description,
                )
                for line in tpl.lines
            ]
            entry = make_journal_entry(
                db, run_date, tpl.description or tpl.title, "recurring", user, lines
            )
            generated.append({"id": entry.id, "number": entry.number, "entry_date": run_date, "title": tpl.title})

        tpl.last_run_date = run_date
        tpl.next_run_date = _advance(run_date, tpl.frequency, tpl.interval)
        # اگر با پیش‌روی از پایان گذشت، قالب را تمام‌شده علامت بزن.
        if tpl.end_date is not None and tpl.next_run_date > tpl.end_date:
            tpl.is_active = False

    return [generated, skipped]


def run_due(db: Session, user: User, as_of: date | None = None) -> dict:
    """همه‌ی قالب‌های فعالِ سررسیدشده را تولید می‌کند."""
    as_of = as_of or date.today()
    latest_close = get_latest_close_date(db)
    all_generated = []
    total_skipped = 0
    templates = db.query(RecurringJournalEntry).filter(RecurringJournalEntry.is_active.is_(True)).all()
    for tpl in templates:
        if tpl.next_run_date > as_of:
            continue
        generated, skipped = _generate_one(db, tpl, user, as_of, latest_close)
        all_generated.extend(generated)
        total_skipped += skipped
    db.flush()
    return {"generated": len(all_generated), "skipped": total_skipped, "entries": all_generated}


def run_one(db: Session, template_id: UUID, user: User, as_of: date | None = None) -> dict:
    """یک قالبِ مشخص را تولید می‌کند (دکمه‌ی «تولید همین حالا»)."""
    as_of = as_of or date.today()
    tpl = _get_template(db, template_id)
    if not tpl.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "قالبِ غیرفعال قابل تولید نیست")
    generated, skipped = _generate_one(db, tpl, user, as_of, get_latest_close_date(db))
    db.flush()
    return {"generated": len(generated), "skipped": skipped, "entries": generated}


# --- سریال‌سازی -------------------------------------------------------------------


def _serialize(tpl: RecurringJournalEntry, today: date | None = None) -> dict:
    today = today or date.today()
    amount = sum((Decimal(l.debit) for l in tpl.lines), Decimal(0))
    return {
        "id": tpl.id,
        "title": tpl.title,
        "description": tpl.description,
        "frequency": tpl.frequency,
        "interval": tpl.interval,
        "start_date": tpl.start_date,
        "end_date": tpl.end_date,
        "next_run_date": tpl.next_run_date,
        "last_run_date": tpl.last_run_date,
        "is_active": tpl.is_active,
        "cost_center_id": tpl.cost_center_id,
        "created_at": tpl.created_at,
        "is_due": tpl.is_active and tpl.next_run_date <= today,
        "amount": amount,
        "lines": [
            {
                "id": l.id,
                "account_id": l.account_id,
                "account_code": l.account.code,
                "account_name": l.account.name,
                "debit": Decimal(l.debit),
                "credit": Decimal(l.credit),
                "description": l.description,
            }
            for l in tpl.lines
        ],
    }


def serialize(tpl: RecurringJournalEntry) -> dict:
    return _serialize(tpl)


def list_templates(db: Session) -> list[dict]:
    today = date.today()
    rows = db.query(RecurringJournalEntry).order_by(RecurringJournalEntry.created_at.desc()).all()
    return [_serialize(t, today) for t in rows]


def get_template_detail(db: Session, template_id: UUID) -> dict:
    return _serialize(_get_template(db, template_id))
