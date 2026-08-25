"""سالِ مالی: تعریفِ دوره، انتقالِ مانده (افتتاحیه)، و بستنِ سال (اختتامیه).

سه قانون که همه‌ی این ماژول را می‌سازند:

۱. **بازه‌ها هم‌پوشانی ندارند.** یک تاریخ نباید در دو سالِ مالی باشد، وگرنه معلوم
   نیست سند به کدام دوره تعلق دارد.
۲. **حداکثر یک سالِ جاری.** «جاری» یعنی پیش‌فرضِ فرم‌ها و مرجعِ گزارش‌های دوره‌ای.
۳. **به‌محضِ تعریفِ اولین سالِ مالی، تاریخِ اسناد محدود می‌شود** به بازه‌های تعریف‌شده‌ی
   باز. تا وقتی هیچ سالی تعریف نشده، رفتارِ سیستم مثلِ قبل است — پس حساب‌های موجود
   با ارتقا چیزی از دست نمی‌دهند.

بستنِ سال عمداً روی «بستنِ دوره»‌ی موجود سوار می‌شود (`services/period_close`) نه
موازیِ آن، تا قفلِ تاریخی یکی بماند و دو منبعِ حقیقت نداشته باشیم.
"""
from datetime import date, timedelta
from decimal import Decimal

from fastapi import HTTPException, status as http_status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.jalali import gregorian_to_jalali, persian_year_end, persian_year_start
from app.models.accounting import JournalEntry, JournalLine
from app.models.fiscal_year import STATUS_CLOSED, STATUS_OPEN, FiscalYear
from app.models.user import User
from app.schemas.fiscal_year import FiscalYearIn, FiscalYearUpdate
from app.services.common import make_journal_entry
from app.services.reports import CREDIT_NORMAL_TYPES, get_income_statement, get_trial_balance

#: بلندترین دوره‌ی مالیِ پذیرفتنی. سالِ مالی معمولاً ۱۲ ماه است، ولی اولین دوره‌ی یک
#: شرکتِ تازه می‌تواند تا ۱۸ ماه باشد؛ بیشتر از آن قطعاً اشتباهِ ورودی است.
MAX_YEAR_DAYS = 550

#: حساب‌های دائمی — همان‌هایی که مانده‌شان به سالِ بعد منتقل می‌شود.
PERMANENT_TYPES = ("asset", "liability", "equity")


# ── خواندن ────────────────────────────────────────────────────────────────────


def list_years(db: Session) -> list[FiscalYear]:
    return db.query(FiscalYear).order_by(FiscalYear.start_date.desc()).all()


def get_active_year(db: Session) -> FiscalYear | None:
    return db.query(FiscalYear).filter(FiscalYear.is_active.is_(True)).first()


def _get(db: Session, year_id) -> FiscalYear:
    year = db.get(FiscalYear, year_id)
    if year is None:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, "سال مالی پیدا نشد")
    return year


def entry_count(db: Session, year: FiscalYear) -> int:
    """شمارِ اسنادِ حسابداریِ داخلِ بازه — سالی که سند دارد نه حذف می‌شود نه بازه‌اش تغییر."""
    return (
        db.query(func.count(JournalEntry.id))
        .filter(JournalEntry.entry_date >= year.start_date, JournalEntry.entry_date <= year.end_date)
        .scalar()
        or 0
    )


def suggest_next(db: Session) -> dict:
    """بازه‌ی سالِ مالیِ بعدی را بر پایه‌ی تقویمِ شمسی پیشنهاد می‌دهد.

    سالِ مالیِ استانداردِ ایران از ۱ فروردین تا ۲۹/۳۰ اسفند است؛ طولِ اسفند به کبیسه
    بستگی دارد، پس تاریخِ پایان محاسبه می‌شود نه حدس‌زده.
    """
    last = db.query(FiscalYear).order_by(FiscalYear.end_date.desc()).first()
    if last is not None:
        jy = gregorian_to_jalali(last.end_date + timedelta(days=1))[0]
    else:
        jy = gregorian_to_jalali(date.today())[0]
    start, end = persian_year_start(jy), persian_year_end(jy)
    return {
        "jalali_year": jy,
        "title": f"سال مالی {jy}",
        "start_date": start,
        "end_date": end,
        "days": (end - start).days + 1,
        "is_leap": (end - start).days + 1 == 366,
    }


# ── اعتبارسنجی ────────────────────────────────────────────────────────────────


def _validate_range(db: Session, start: date, end: date, exclude_id=None) -> None:
    if end <= start:
        raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "تاریخ پایان باید بعد از تاریخ شروع باشد")
    days = (end - start).days + 1
    if days > MAX_YEAR_DAYS:
        raise HTTPException(
            http_status.HTTP_400_BAD_REQUEST,
            f"طول دوره {days} روز است؛ سال مالی نمی‌تواند بیش از {MAX_YEAR_DAYS} روز باشد",
        )
    query = db.query(FiscalYear).filter(FiscalYear.start_date <= end, FiscalYear.end_date >= start)
    if exclude_id is not None:
        query = query.filter(FiscalYear.id != exclude_id)
    clash = query.first()
    if clash is not None:
        raise HTTPException(
            http_status.HTTP_400_BAD_REQUEST,
            f"این بازه با «{clash.title}» ({clash.start_date} تا {clash.end_date}) هم‌پوشانی دارد",
        )


def assert_within_fiscal_year(db: Session, entry_date: date) -> None:
    """تاریخِ سند باید در یک سالِ مالیِ **باز** باشد.

    از `assert_period_open` صدا زده می‌شود، یعنی سرِ راهِ هر عملیاتی که سند می‌سازد.
    اگر هنوز هیچ سالِ مالی‌ای تعریف نشده باشد کاری نمی‌کند — این تنها راهِ سازگاری با
    حساب‌هایی است که پیش از این قابلیت کار می‌کردند.
    """
    years = db.query(FiscalYear).all()
    if not years:
        return
    match = next((y for y in years if y.start_date <= entry_date <= y.end_date), None)
    if match is None:
        raise HTTPException(
            http_status.HTTP_400_BAD_REQUEST,
            f"تاریخ {entry_date} در هیچ سال مالی تعریف‌شده‌ای نیست؛ ابتدا سال مالی مربوطه را بسازید",
        )
    if match.status == STATUS_CLOSED:
        raise HTTPException(
            http_status.HTTP_400_BAD_REQUEST,
            f"سال مالی «{match.title}» بسته شده؛ ثبت سند با تاریخ {entry_date} مجاز نیست",
        )


# ── نوشتن ─────────────────────────────────────────────────────────────────────


def create_year(db: Session, data: FiscalYearIn) -> FiscalYear:
    _validate_range(db, data.start_date, data.end_date)
    if db.query(FiscalYear).filter(FiscalYear.title == data.title).first():
        raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "سال مالی با این نام از قبل هست")

    first_ever = db.query(FiscalYear).count() == 0
    year = FiscalYear(
        title=data.title,
        start_date=data.start_date,
        end_date=data.end_date,
        notes=data.notes,
        status=STATUS_OPEN,
        # اولین سالِ مالی ناچار جاری است، وگرنه هیچ سالِ جاری‌ای نداریم.
        is_active=first_ever or data.activate,
    )
    db.add(year)
    db.flush()
    if year.is_active:
        _make_only_active(db, year)
    db.refresh(year)
    return year


def _make_only_active(db: Session, year: FiscalYear) -> None:
    # عمداً شیء‌به‌شیء و نه UPDATE گروهی: به‌روزرسانیِ گروهی نقشه‌ی هویتِ session را
    # کهنه می‌گذارد و نوشتنِ بعدی روی همان ردیف بی‌صدا نادیده گرفته می‌شود.
    others = (
        db.query(FiscalYear)
        .filter(FiscalYear.id != year.id, FiscalYear.is_active.is_(True))
        .all()
    )
    for other in others:
        other.is_active = False
    year.is_active = True
    db.flush()


def update_year(db: Session, year_id, data: FiscalYearUpdate) -> FiscalYear:
    year = _get(db, year_id)
    if year.status == STATUS_CLOSED:
        raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "سال مالی بسته‌شده قابل ویرایش نیست")

    start = data.start_date or year.start_date
    end = data.end_date or year.end_date
    if (start, end) != (year.start_date, year.end_date):
        # جابه‌جاییِ بازه‌ی سالی که سند دارد یعنی اسناد ناگهان بیرون از دوره می‌افتند.
        if entry_count(db, year) > 0:
            raise HTTPException(
                http_status.HTTP_400_BAD_REQUEST,
                "این سال مالی سند حسابداری دارد؛ بازه‌ی آن دیگر قابل تغییر نیست",
            )
        _validate_range(db, start, end, exclude_id=year.id)
        year.start_date, year.end_date = start, end

    if data.title is not None and data.title != year.title:
        if db.query(FiscalYear).filter(FiscalYear.title == data.title, FiscalYear.id != year.id).first():
            raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "سال مالی با این نام از قبل هست")
        year.title = data.title
    if data.notes is not None:
        year.notes = data.notes

    db.flush()
    db.refresh(year)
    return year


def activate_year(db: Session, year_id) -> FiscalYear:
    year = _get(db, year_id)
    if year.status == STATUS_CLOSED:
        raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "سال مالی بسته‌شده نمی‌تواند سال جاری باشد")
    _make_only_active(db, year)
    db.refresh(year)
    return year


def delete_year(db: Session, year_id) -> None:
    year = _get(db, year_id)
    if year.status == STATUS_CLOSED:
        raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "سال مالی بسته‌شده قابل حذف نیست")
    if entry_count(db, year) > 0:
        raise HTTPException(
            http_status.HTTP_400_BAD_REQUEST, "این سال مالی سند حسابداری دارد و قابل حذف نیست"
        )
    was_active = year.is_active
    db.delete(year)
    db.flush()
    if was_active:
        # نباید بدونِ سالِ جاری بمانیم: تازه‌ترین سالِ بازِ باقی‌مانده جانشین می‌شود.
        fallback = (
            db.query(FiscalYear)
            .filter(FiscalYear.status == STATUS_OPEN)
            .order_by(FiscalYear.start_date.desc())
            .first()
        )
        if fallback is not None:
            fallback.is_active = True
            db.flush()


# ── افتتاحیه: انتقالِ مانده از سالِ قبل ────────────────────────────────────────


def _previous_year(db: Session, year: FiscalYear) -> FiscalYear | None:
    return (
        db.query(FiscalYear)
        .filter(FiscalYear.end_date < year.start_date)
        .order_by(FiscalYear.end_date.desc())
        .first()
    )


def carry_forward(db: Session, year_id, user: User) -> dict:
    """مانده‌ی حساب‌های دائمیِ سالِ قبل را در یک سندِ افتتاحیه به این سال می‌آورد."""
    year = _get(db, year_id)
    if year.status == STATUS_CLOSED:
        raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "سال مالی بسته‌شده افتتاحیه نمی‌گیرد")
    if year.opening_entry_id is not None:
        raise HTTPException(http_status.HTTP_409_CONFLICT, "سند افتتاحیه‌ی این سال از قبل ثبت شده است")

    prev = _previous_year(db, year)
    if prev is None:
        raise HTTPException(
            http_status.HTTP_400_BAD_REQUEST,
            "سال مالی قبلی تعریف نشده؛ برای اولین دوره از «راه‌اندازی» مانده‌های اول دوره را وارد کنید",
        )
    if prev.status != STATUS_CLOSED:
        # پیش از بستن، سود/زیانِ سالِ قبل هنوز به سودِ انباشته منتقل نشده و مانده‌های
        # دائمی تراز نمی‌شوند؛ سندِ افتتاحیه‌ی نامتوازن بدتر از نبودنش است.
        raise HTTPException(
            http_status.HTTP_400_BAD_REQUEST,
            f"ابتدا «{prev.title}» را ببندید تا مانده‌های پایان دوره قطعی شود",
        )

    rows = [r for r in get_trial_balance(db, None, prev.end_date) if r["account_type"] in PERMANENT_TYPES]
    lines: list[JournalLine] = []
    for row in rows:
        balance = Decimal(row["balance"])
        if balance == 0:
            continue
        credit_normal = row["account_type"] in CREDIT_NORMAL_TYPES
        # مانده‌ی منفی یعنی حساب خلافِ ماهیتش مانده دارد؛ همان‌طور و در سمتِ مقابل منتقل می‌شود.
        if (balance > 0) == credit_normal:
            debit, credit = Decimal(0), abs(balance)
        else:
            debit, credit = abs(balance), Decimal(0)
        lines.append(
            JournalLine(
                account_id=row["account_id"],
                debit=debit,
                credit=credit,
                description=f"انتقال مانده از {prev.title}",
            )
        )

    if not lines:
        raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "سال قبل هیچ مانده‌ی دائمی برای انتقال ندارد")

    diff = sum(line.debit for line in lines) - sum(line.credit for line in lines)
    if diff != 0:
        # به‌جای ثبتِ سندِ ناتراز، صریح می‌گوییم دفاتر تراز نیست.
        raise HTTPException(
            http_status.HTTP_400_BAD_REQUEST,
            f"مانده‌های پایان «{prev.title}» تراز نیست (اختلاف {diff}) — ابتدا دفاتر را بررسی کنید",
        )

    entry = make_journal_entry(
        db,
        year.start_date,
        f"سند افتتاحیه {year.title} — انتقال مانده از {prev.title}",
        "opening",
        user,
        lines,
    )
    year.opening_entry_id = entry.id
    db.flush()
    return {
        "journal_entry_id": entry.id,
        "line_count": len(lines),
        "total": sum(line.debit for line in lines),
    }


# ── اختتامیه: بستنِ سال ───────────────────────────────────────────────────────


def close_year(db: Session, year_id, user: User) -> FiscalYear:
    """سال را می‌بندد: سندِ بستنِ حساب‌های موقت + قفلِ تاریخیِ دوره.

    از `close_period` استفاده می‌کند تا قفلِ تاریخی همان مکانیزمِ همیشگی بماند.
    """
    from app.schemas.period_close import FiscalPeriodCloseIn
    from app.services.period_close import close_period

    year = _get(db, year_id)
    if year.status == STATUS_CLOSED:
        raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "این سال مالی از قبل بسته شده است")

    earlier_open = (
        db.query(FiscalYear)
        .filter(FiscalYear.end_date < year.start_date, FiscalYear.status == STATUS_OPEN)
        .order_by(FiscalYear.start_date)
        .first()
    )
    if earlier_open is not None:
        raise HTTPException(
            http_status.HTTP_400_BAD_REQUEST,
            f"ابتدا سال مالی قدیمی‌تر «{earlier_open.title}» را ببندید",
        )

    statement = get_income_statement(db, year.start_date, year.end_date)
    has_activity = any(row["balance"] != 0 for row in statement["income"] + statement["expenses"])
    if has_activity:
        close = close_period(
            db,
            FiscalPeriodCloseIn(closing_date=year.end_date, notes=f"بستن {year.title}"),
            user,
        )
        year.closing_entry_id = close.journal_entry_id

    year.status = STATUS_CLOSED
    year.closed_at = func.now()
    year.closed_by_id = user.id
    if year.is_active:
        # سالِ بسته نمی‌تواند جاری بماند؛ اگر سالِ بازِ بعدی هست، جاری می‌شود.
        year.is_active = False
        nxt = (
            db.query(FiscalYear)
            .filter(FiscalYear.start_date > year.end_date, FiscalYear.status == STATUS_OPEN)
            .order_by(FiscalYear.start_date)
            .first()
        )
        if nxt is not None:
            nxt.is_active = True
    db.flush()
    db.refresh(year)
    return year
