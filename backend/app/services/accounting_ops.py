"""عملیاتِ دفترداریِ ماژولِ حسابداری — کارهایی که *روی* اسناد انجام می‌شوند، نه ثبتِ تازه.

ثبتِ سند در `routers/journal.py` است و ساختِ سندِ خودکار در سرویسِ هر ماژول. اینجا
جای هجده عملیاتی است که دفتردار پس از ثبت انجام می‌دهد: مرتب‌کردن، قطعی‌کردن،
تسعیر، بستنِ سال. سه قاعده بر همه‌شان حاکم است و هر تابعی که اضافه شود باید هر سه
را رعایت کند:

۱. **دفتر هرگز پاک نمی‌شود.** تنها استثنا سندِ *موقتِ دستی* است: موقت یعنی هنوز
   قطعی نشده و کاربر خودش ثبتش کرده — پس ادغام می‌تواند اصل‌ها را حذف کند. سندِ
   دائم یا سندی که یک ماژولِ دیگر ساخته، فقط با معکوس برمی‌گردد.

۲. **هیچ عملیاتی مانده‌ی حساب را عوض نمی‌کند مگر عمداً.** بازشماره‌گذاری و ادغام
   و دائم‌کردن، صفر اثرِ مالی دارند؛ تسعیر و اختتامیه/افتتاحیه عمداً سند می‌زنند و
   پیش از صدور، پیش‌نمایشِ دقیقِ همان سند را برمی‌گردانند.

۳. **دوره‌ی بسته دست‌نخوردنی است.** هر عملیاتی که سند بسازد یا شماره/وضعیتِ سندی را
   عوض کند، اول `assert_period_open` را روی تاریخِ هدف صدا می‌زند.
"""
from datetime import date as date_
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session, selectinload

from app import audit
from app.models.accounting import Account, JournalEntry, JournalLine
from app.models.analytic import AnalyticAccount
from app.models.cost_center import CostCenter
from app.models.counters import DOC_JOURNAL_ENTRY
from app.models.currency import ExchangeRate
from app.models.user import User
from app.services import chart_codes as cc
from app.services.common import get_or_create_account, make_journal_entry
from app.services.period_close import assert_period_open, get_latest_close_date
from app.services.reports import _signed_balance, descendant_account_ids

#: نوعِ حساب‌هایی که مانده‌شان از سالی به سالِ بعد منتقل می‌شود (حساب‌های دائمی).
#: درآمد و هزینه اینجا نیستند چون پیش از اختتامیه با «بستن سود و زیان» صفر شده‌اند.
PERMANENT_TYPES = ("asset", "liability", "equity")

#: سقفِ ردیف‌های برگشتی در فهرست‌های پیش‌نمایش. عملیاتِ دسته‌ای می‌تواند هزاران سند
#: را لمس کند ولی کاربر هرگز هزاران ردیف را نمی‌خواند؛ *شمارش* کامل برمی‌گردد و
#: فقط نمونه محدود می‌شود.
PREVIEW_LIMIT = 200


# ───────────────────────────── کمکی‌های مشترک ─────────────────────────────


def _entry_out(entry: JournalEntry, names: dict[UUID, str] | None = None) -> dict:
    """شکلِ خلاصه‌ی سند برای فهرست‌های عملیات (بدونِ بارِ کاملِ ردیف‌ها مگر لازم باشد)."""
    total = sum((Decimal(line.debit) for line in entry.lines), Decimal(0))
    return {
        "id": entry.id,
        "number": entry.number,
        "atf_number": entry.atf_number,
        "sub_number": entry.sub_number,
        "entry_date": entry.entry_date,
        "description": entry.description,
        "source_type": entry.source_type,
        "status": entry.status,
        "voided_at": entry.voided_at,
        "total": total,
        "line_count": len(entry.lines),
        "accounts": (
            [names.get(line.account_id, "") for line in entry.lines][:6] if names is not None else []
        ),
    }


def _account_names(db: Session) -> dict[UUID, str]:
    return {a.id: f"{a.code} — {a.name}" for a in db.query(Account).all()}


def _live_entries(db: Session):
    """اسنادِ باطل‌نشده. هر عملیاتِ دسته‌ای باید باطل‌ها را رد کند: سندِ باطل و معکوسش
    جمعشان صفر است و دست‌بردن در آن جفت، ردِ حسابرسی را می‌شکند."""
    return db.query(JournalEntry).filter(JournalEntry.voided_at.is_(None))


def _assert_range(date_from: date_ | None, date_to: date_ | None) -> None:
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "تاریخِ شروع بعد از تاریخِ پایان است")


# ───────────────────────── ۱) نمای کلیِ ماژول ─────────────────────────────


def get_overview(db: Session) -> dict:
    """آمارِ سرصفحه‌ی ماژول — همان چند عددی که دفتردار پیش از هر عملیات می‌خواهد بداند."""
    rows = (
        db.query(JournalEntry.status, func.count(JournalEntry.id))
        .filter(JournalEntry.voided_at.is_(None))
        .group_by(JournalEntry.status)
        .all()
    )
    by_status = {s: int(n) for s, n in rows}
    accounts = db.query(Account.is_group, func.count(Account.id)).group_by(Account.is_group).all()
    by_group = {bool(g): int(n) for g, n in accounts}
    last_number = db.query(func.max(JournalEntry.number)).scalar()
    oldest_temp = (
        db.query(func.min(JournalEntry.entry_date))
        .filter(JournalEntry.status == "temporary", JournalEntry.voided_at.is_(None))
        .scalar()
    )
    return {
        "temporary_count": by_status.get("temporary", 0),
        "permanent_count": by_status.get("permanent", 0),
        "voided_count": int(
            db.query(func.count(JournalEntry.id)).filter(JournalEntry.voided_at.isnot(None)).scalar() or 0
        ),
        "account_count": by_group.get(False, 0),
        "group_count": by_group.get(True, 0),
        "last_number": int(last_number) if last_number is not None else None,
        "oldest_temporary_date": oldest_temp,
        "last_close_date": get_latest_close_date(db),
    }


# ─────────────────── ۲) کارتابل و تبدیلِ موقت به دائم ─────────────────────


def get_cartable(db: Session, date_from: date_ | None, date_to: date_ | None) -> dict:
    """کارتابلِ صدورِ سند: هرچه هنوز *موقت* است، دسته‌بندی‌شده بر اساسِ منشأ.

    دفتردار با این کارتابل تصمیم می‌گیرد کدام سند آماده‌ی دائم‌شدن است. گروه‌بندی بر
    اساسِ `source_type` است چون تصمیم معمولاً دسته‌ای گرفته می‌شود («همه‌ی سندهای
    فاکتورِ فروشِ این ماه درست‌اند») نه سند‌به‌سند.
    """
    _assert_range(date_from, date_to)
    query = _live_entries(db).filter(JournalEntry.status == "temporary")
    if date_from:
        query = query.filter(JournalEntry.entry_date >= date_from)
    if date_to:
        query = query.filter(JournalEntry.entry_date <= date_to)

    entries = (
        query.options(selectinload(JournalEntry.lines))
        .order_by(JournalEntry.entry_date, JournalEntry.number)
        .limit(PREVIEW_LIMIT)
        .all()
    )
    names = _account_names(db)

    groups: dict[str, dict] = {}
    for src, count, total in (
        query.join(JournalLine, JournalLine.entry_id == JournalEntry.id)
        .with_entities(
            JournalEntry.source_type,
            func.count(func.distinct(JournalEntry.id)),
            func.coalesce(func.sum(JournalLine.debit), 0),
        )
        .group_by(JournalEntry.source_type)
        .all()
    ):
        groups[src] = {"source_type": src, "count": int(count), "total": Decimal(total)}

    return {
        "total_count": int(query.with_entities(func.count(JournalEntry.id)).scalar() or 0),
        "groups": sorted(groups.values(), key=lambda g: -g["count"]),
        "entries": [_entry_out(e, names) for e in entries],
    }


def finalize_entries(
    db: Session,
    user: User,
    *,
    date_from: date_ | None = None,
    date_to: date_ | None = None,
    entry_ids: list[UUID] | None = None,
    source_type: str | None = None,
) -> dict:
    """تبدیلِ اسنادِ موقت به دائم — دسته‌ای یا موردی.

    دائم‌کردن هیچ اثرِ مالی ندارد؛ فقط سند را از دسترسِ عملیاتی مثلِ ادغام و
    بازشماره‌گذاری بیرون می‌برد. یک‌طرفه است: راهِ برگشتی عمداً وجود ندارد، چون
    «دائم» یعنی امضاشده و برگرداندنش همان چیزی است که این وضعیت باید جلویش را بگیرد.
    """
    _assert_range(date_from, date_to)

    #: فهرستِ **خالی** یعنی «کاربر چیزی انتخاب نکرد»، نه «فیلتری در کار نیست».
    #: با شرطِ truthy به فیلترِ تاریخ می‌افتاد و اگر بازه هم خالی بود **همه‌ی دفتر**
    #: دائم می‌شد — یک‌طرفه و بی‌راهِ برگشت.
    if entry_ids is not None and not entry_ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "سندی انتخاب نشده است")

    #: **گاردِ واقعیِ همان قاعده‌ای که docstringِ `FinalizeIn` از روزِ اول ادعا می‌کرد.**
    #: تا امروز هیچ‌چیز اعمالش نمی‌کرد و بدنه‌ی خالیِ `{}` همه‌ی اسنادِ موقتِ
    #: کسب‌وکار را برای همیشه دائم می‌کرد.
    if entry_ids is None and not (date_from or date_to or source_type):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "دستِ‌کم یک فیلتر لازم است — بازه، منشأ، یا انتخابِ صریحِ اسناد. "
            "دائم‌کردنِ همه‌ی اسنادِ موقت یک‌طرفه است و باید صریح خواسته شود.",
        )

    query = _live_entries(db).filter(JournalEntry.status == "temporary")
    #: انتخابِ دستی **جایگزینِ** بازه است نه افزوده بر آن — همان قاعده‌ی
    #: `_renumber_scope`. پیش از این هر دو اعمال می‌شدند، پس کاربری که چند سند تیک
    #: زده و بازه‌اش روی «امسال» مانده بی‌صدا زیرمجموعه‌ای از انتخابش را دائم می‌کرد.
    if entry_ids is not None:
        query = query.filter(JournalEntry.id.in_(entry_ids))
    else:
        if date_from:
            query = query.filter(JournalEntry.entry_date >= date_from)
        if date_to:
            query = query.filter(JournalEntry.entry_date <= date_to)
        if source_type:
            query = query.filter(JournalEntry.source_type == source_type)

    entries = query.all()
    if not entries:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "هیچ سندِ موقتی با این شرایط پیدا نشد")

    now = datetime.now(timezone.utc)
    for entry in entries:
        entry.status = "permanent"
        entry.finalized_at = now
        entry.finalized_by_id = user.id
    db.flush()
    return {
        "count": len(entries),
        "first_date": min(e.entry_date for e in entries),
        "last_date": max(e.entry_date for e in entries),
    }


# ─────────────────────── ۳) بازشماره‌گذاریِ اسناد ─────────────────────────


def _renumber_scope(
    db: Session,
    date_from: date_ | None,
    date_to: date_ | None,
    entry_ids: list[UUID] | None = None,
):
    """محدوده‌ی عملیات: یا فهرستِ صریحِ اسناد، یا بازه‌ی تاریخ.

    انتخابِ دستی **جایگزینِ** بازه است نه افزوده بر آن. اگر هر دو اعمال می‌شدند،
    کاربری که چند سند را تیک زده و بازه‌اش روی «این ماه» مانده بی‌صدا زیرمجموعه‌ای
    از انتخابش را می‌گرفت — و پیش‌نمایش هم همان کمتر را نشان می‌داد، پس اشتباه
    شبیهِ درست به نظر می‌رسید.

    **انتخاب بر اساسِ محدوده‌ی شماره عمداً نیست.** کلِ کارِ این عملیات درست‌کردنِ
    شماره‌هایی است که با تاریخ نمی‌خوانند؛ فیلترکردن بر همان شماره‌های به‌هم‌ریخته
    یعنی تکیه بر چیزی که خودش خراب است — همان دلیلی که `_renumber_plan` با
    `created_at` مرتب می‌کند نه با `number`.
    """
    query = _live_entries(db)
    #: `is not None` و نه صرفاً truthy: فهرستِ **خالی** یعنی «کاربر چیزی انتخاب
    #: نکرد»، نه «فیلتری در کار نیست». با شرطِ truthy، انتخابِ خالی به فیلترِ
    #: تاریخ می‌افتاد و اگر بازه هم خالی بود **کلِ دفتر** بازشماری می‌شد.
    if entry_ids is not None:
        return query.filter(JournalEntry.id.in_(entry_ids))
    if date_from:
        query = query.filter(JournalEntry.entry_date >= date_from)
    if date_to:
        query = query.filter(JournalEntry.entry_date <= date_to)
    return query


def _renumber_plan(
    db: Session,
    date_from: date_ | None,
    date_to: date_ | None,
    entry_ids: list[UUID] | None = None,
) -> list[JournalEntry]:
    """اسنادِ *موقتِ* بازه به ترتیبی که باید شماره بگیرند: تاریخ، بعد لحظه‌ی ثبت.

    دو تصمیم:

    * **فقط موقت.** سندِ دائم شماره‌ی امضاشده دارد و ارجاعاتِ بیرونی (چاپ، اظهارنامه،
      دفترِ قانونی) رویش نشسته‌اند. اگر اینجا فیلتر نمی‌شد، پیش‌نمایش نقشه‌ای نشان
      می‌داد که اجرا حتماً ردش می‌کرد — بدترین حالت: کاربر تصمیمی می‌گرفت که
      نمی‌توانست اجرا کند.
    * **مرتب‌سازیِ ثانویه با `created_at` نه `number`.** کلِ کارِ این عملیات
      درست‌کردنِ شماره‌هایی است که با تاریخ نمی‌خوانند، پس تکیه بر شماره‌ی فعلی همان
      بی‌نظمی را بازتولید می‌کرد.
    """
    return (
        _renumber_scope(db, date_from, date_to, entry_ids)
        .filter(JournalEntry.status == "temporary")
        .order_by(JournalEntry.entry_date, JournalEntry.created_at, JournalEntry.id)
        .all()
    )


def _permanent_in_range(
    db: Session,
    date_from: date_ | None,
    date_to: date_ | None,
    entry_ids: list[UUID] | None = None,
) -> int:
    """چند سندِ دائم در بازه هست — فقط برای توضیحِ اینکه چرا نقشه کوچک‌تر از بازه است."""
    return int(
        _renumber_scope(db, date_from, date_to, entry_ids)
        .filter(JournalEntry.status == "permanent")
        .with_entities(func.count(JournalEntry.id))
        .scalar()
        or 0
    )


def preview_renumber(
    db: Session,
    date_from: date_ | None,
    date_to: date_ | None,
    start_number: int,
    entry_ids: list[UUID] | None = None,
) -> dict:
    _assert_range(date_from, date_to)
    entries = _renumber_plan(db, date_from, date_to, entry_ids)
    names = _account_names(db)
    rows = []
    for offset, entry in enumerate(entries):
        new_number = start_number + offset
        rows.append(
            {
                "id": entry.id,
                "entry_date": entry.entry_date,
                "description": entry.description,
                "atf_number": entry.atf_number,
                "old_number": entry.number,
                "new_number": new_number,
                "changed": entry.number != new_number,
                "status": entry.status,
                "source_type": entry.source_type,
                "accounts": [names.get(line.account_id, "") for line in entry.lines][:4],
            }
        )
    return {
        "count": len(rows),
        "changed_count": sum(1 for r in rows if r["changed"]),
        "skipped_permanent": _permanent_in_range(db, date_from, date_to, entry_ids),
        "rows": rows[:PREVIEW_LIMIT],
        "truncated": len(rows) > PREVIEW_LIMIT,
    }


def renumber_entries(
    db: Session,
    user: User,
    date_from: date_ | None,
    date_to: date_ | None,
    start_number: int,
    entry_ids: list[UUID] | None = None,
) -> dict:
    """شماره‌ی اسنادِ بازه را از نو و به‌ترتیبِ تاریخ می‌دهد.

    دو نکته‌ی اجرایی که بدونشان کار نمی‌کند:

    * **دو مرحله‌ای.** قیدِ یکتای (مستأجر، شماره) اجازه نمی‌دهد سندی موقتاً شماره‌ی
      سندِ دیگری را بگیرد. پس اول همه به شماره‌ی منفی می‌روند (فضای خالیِ تضمینی) و
      بعد شماره‌ی نهایی می‌نشیند.
    * **شمارنده هم جابه‌جا می‌شود.** اگر `document_counters` عقب بماند، سندِ بعدی
      شماره‌ی تکراری می‌گیرد و ثبتش با خطای قید شکست می‌خورد.
    """
    _assert_range(date_from, date_to)
    if start_number < 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "شماره‌ی شروع باید دستِ‌کم ۱ باشد")

    entries = _renumber_plan(db, date_from, date_to, entry_ids)
    if not entries:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "در این بازه سندِ موقتی برای شماره‌گذاری نیست"
        )
    assert_period_open(db, min(e.entry_date for e in entries))

    # بیرونِ محدوده‌ی هدف چه شماره‌هایی گرفته‌اند — تا شماره‌ی تازه رویشان نیفتد.
    target_ids = {e.id for e in entries}
    taken = {
        int(n)
        for (n,) in db.query(JournalEntry.number)
        .filter(JournalEntry.number.isnot(None), JournalEntry.id.notin_(target_ids))
        .all()
        if n is not None
    }
    clash = [start_number + i for i in range(len(entries)) if start_number + i in taken]
    if clash:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"شماره‌ی {clash[0]} پیش‌تر به سندی بیرونِ این بازه داده شده؛ شماره‌ی شروعِ دیگری انتخاب کنید",
        )

    #: شماره‌های اصلی پیش از دست‌زدن نگه داشته می‌شوند — بعد از پاسِ منفی دیگر
    #: از خودِ شیء درنمی‌آیند، و همین‌ها `from`ِ رکوردِ حسابرسی‌اند.
    original = {entry.id: entry.number for entry in entries}

    #: ثبتِ خودکار برای این دو flush خاموش است: مرحله‌ی منفی یک ترفندِ پیاده‌سازی
    #: است نه واقعیتِ کسب‌وکاری، و رکوردش می‌گفت «سند شماره -۱ ویرایش شد».
    #: رکوردِ درست پایین‌تر و یک‌بار نوشته می‌شود. شرح در `audit.suppressed`.
    with audit.suppressed(db):
        for i, entry in enumerate(entries):
            entry.number = -(i + 1)
        db.flush()
        for offset, entry in enumerate(entries):
            entry.number = start_number + offset
        db.flush()

    changed = 0
    for entry in entries:
        was, now = original[entry.id], entry.number
        if was == now:
            continue  # شماره‌اش عوض نشده؛ رویدادی رخ نداده که ثبت شود
        changed += 1
        audit.record_change(
            db,
            entry,
            {"number": {"from": was, "to": now}},
            f"شماره‌ی سند از {was if was is not None else '—'} به {now} تغییر کرد (بازشماره‌گذاری)",
        )

    _sync_counter(db)
    return {
        "count": len(entries),
        "changed_count": changed,
        "first_number": start_number,
        "last_number": start_number + len(entries) - 1,
    }


def _sync_counter(db: Session) -> None:
    """شمارنده‌ی سند را روی بزرگ‌ترین شماره‌ی موجود می‌نشاند (هرگز عقب نمی‌برد)."""
    from sqlalchemy import text

    from app.tenant_context import require_session_tenant

    highest = db.query(func.max(JournalEntry.number)).scalar() or 0
    db.execute(
        text(
            "UPDATE document_counters SET last_number = GREATEST(last_number, :n) "
            "WHERE tenant_id = :tenant_id AND doc_type = :doc_type"
        ),
        {
            "n": int(highest),
            "tenant_id": str(require_session_tenant(db)),
            "doc_type": DOC_JOURNAL_ENTRY,
        },
    )


# ───────────────────────────── ۴) ادغامِ اسناد ─────────────────────────────


def merge_entries(db: Session, user: User, entry_ids: list[UUID], description: str) -> dict:
    """چند سندِ موقتِ هم‌تاریخ را در یک سند جمع می‌کند.

    محدودیت‌ها عمدی‌اند: فقط **موقت** (دائم امضاشده است)، فقط **دستی** (سندی که یک
    ماژول ساخته به فاکتور/فیشِ خودش گره خورده و بی‌آن سند، آن مدرک بی‌ردِ حسابداری
    می‌ماند)، و فقط **هم‌تاریخ** (سندِ ادغامی یک تاریخ بیشتر ندارد؛ ادغامِ دو تاریخ
    یعنی جابه‌جاکردنِ رویداد در زمان).

    اصل‌ها *حذف* می‌شوند نه باطل: سندِ موقت هنوز قطعی نشده و معکوس‌زدنِ آن، دفتر را
    از سه سندِ بی‌فایده پر می‌کرد به‌جای یکی.
    """
    if len(entry_ids) < 2:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "برای ادغام دستِ‌کم دو سند لازم است")

    entries = (
        _live_entries(db)
        .options(selectinload(JournalEntry.lines))
        .filter(JournalEntry.id.in_(entry_ids))
        .all()
    )
    if len(entries) != len(set(entry_ids)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "بعضی از اسنادِ انتخابی پیدا نشدند یا باطل‌اند")

    bad_status = [e for e in entries if e.status != "temporary"]
    if bad_status:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"سندِ شماره {bad_status[0].number} دائم است؛ فقط اسنادِ موقت ادغام می‌شوند",
        )
    bad_source = [e for e in entries if e.source_type != "manual"]
    if bad_source:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"سندِ شماره {bad_source[0].number} را ماژولِ «{bad_source[0].source_type}» ساخته؛ "
            "فقط سندِ دستی ادغام می‌شود",
        )
    dates = {e.entry_date for e in entries}
    if len(dates) > 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "همه‌ی اسنادِ انتخابی باید یک تاریخ داشته باشند")

    entry_date = dates.pop()
    assert_period_open(db, entry_date)

    lines = [
        JournalLine(
            account_id=line.account_id,
            cost_center_id=line.cost_center_id,
            analytic_id=line.analytic_id,
            debit=line.debit,
            credit=line.credit,
            description=line.description,
            currency_code=line.currency_code,
            fx_amount=line.fx_amount,
            fx_rate=line.fx_rate,
            tracking_no=line.tracking_no,
            tracking_date=line.tracking_date,
        )
        for entry in sorted(entries, key=lambda e: (e.number or 0))
        for line in entry.lines
    ]
    numbers = ", ".join(str(e.number) for e in sorted(entries, key=lambda e: (e.number or 0)))
    text_ = description.strip() or f"ادغامِ اسنادِ {numbers}"

    merged = make_journal_entry(db, entry_date, text_, "manual", user, lines)
    merged.status = "temporary"
    for entry in entries:
        db.delete(entry)
    db.flush()
    db.refresh(merged)
    return {
        "entry_id": merged.id,
        "number": merged.number,
        "line_count": len(lines),
        "merged_numbers": [e.number for e in entries],
    }


# ───────────────────────── ۵) تسعیرِ ارز ──────────────────────────────────


def _rate_on(db: Session, code: str, as_of: date_) -> tuple[Decimal, date_] | None:
    """آخرین نرخِ ثبت‌شده تا این تاریخ (نه نرخِ آینده) — همراهِ تاریخِ خودش.

    تاریخ هم برمی‌گردد چون «آخرین نرخ تا این تاریخ» می‌تواند ماه‌ها کهنه باشد و
    کاربر باید ببیندش. نرخِ نبود را حدس نمی‌زنیم؛ نرخِ کهنه را هم نباید بی‌صدا
    به‌جای نرخِ روز جا بزنیم.
    """
    row = (
        db.query(ExchangeRate)
        .filter(ExchangeRate.currency_code == code, ExchangeRate.rate_date <= as_of)
        .order_by(ExchangeRate.rate_date.desc())
        .first()
    )
    return (Decimal(str(row.rate)), row.rate_date) if row else None


def fx_revaluation_preview(db: Session, as_of: date_) -> dict:
    """مانده‌ی ارزیِ هر حساب را با نرخِ روز می‌سنجد و اختلافِ ریالی را نشان می‌دهد.

    منطق: هر ردیفِ ارزی دو عدد دارد — مبلغِ ارزی و معادلِ ریالیِ *لحظه‌ی ثبت*. جمعِ
    علامت‌دارِ اولی می‌شود «موجودیِ ارزی» و جمعِ علامت‌دارِ دومی «ارزشِ دفتری». ارزشِ
    امروز = موجودیِ ارزی × نرخِ امروز. تفاوتِ این دو، سود/زیانِ تحقق‌نیافته‌ی تسعیر است.
    """
    rows = (
        db.query(
            JournalLine.account_id,
            #: گروه‌بندی روی هر سه بُعدی که ردیفِ سند حمل می‌کند، نه فقط حساب.
            #: یک «دریافتنیِ ارزی» با سه مشتری سه مانده‌ی جداست؛ اگر یک‌کاسه شود،
            #: ردیفِ تسعیر بی‌تفصیلی می‌نشیند و دفترِ تفصیلی از حساب جدا می‌افتد —
            #: جمعِ حساب درست، تفکیکش غلط، و چون سند ویرایشِ ردیف ندارد، برای همیشه.
            JournalLine.analytic_id,
            JournalLine.cost_center_id,
            JournalLine.currency_code,
            func.coalesce(func.sum(JournalLine.debit), 0),
            func.coalesce(func.sum(JournalLine.credit), 0),
            func.coalesce(
                func.sum(
                    case(
                        (JournalLine.debit > 0, JournalLine.fx_amount),
                        else_=-JournalLine.fx_amount,
                    )
                ),
                0,
            ),
        )
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .filter(
            JournalLine.currency_code.isnot(None),
            JournalLine.fx_amount.isnot(None),
            JournalEntry.entry_date <= as_of,
            JournalEntry.voided_at.is_(None),
        )
        .group_by(
            JournalLine.account_id,
            JournalLine.analytic_id,
            JournalLine.cost_center_id,
            JournalLine.currency_code,
        )
        .all()
    )

    accounts = {a.id: a for a in db.query(Account).all()}
    analytics = {a.id: a for a in db.query(AnalyticAccount).all()}
    centers = {c.id: c for c in db.query(CostCenter).all()}
    missing_rates: set[str] = set()
    items = []
    total_diff = Decimal(0)
    for account_id, analytic_id, cost_center_id, code, debit, credit, fx_net in rows:
        account = accounts.get(account_id)
        if account is None:
            continue
        #: «تسعیر پذیر» انصراف است نه انتخاب. هر حسابی که ردیفِ ارزی دارد به‌طورِ
        #: طبیعی تسعیر می‌شود؛ تنها راهِ کنارگذاشتنش این است که کاربر صریحاً آن را
        #: «ارزی» علامت بزند و «تسعیرپذیر» را بردارد — یعنی «می‌دانم ارزی است،
        #: تسعیرش نکن» (تنخواهِ ارزیِ بسته، حسابِ واسطِ ارزی). اگر انتخاب بود،
        #: پیش‌فرضِ خاموشِ مهاجرتِ ۰۰۸۸ این صفحه را یک‌شبه خالی می‌کرد.
        if account.is_fx and not account.fx_revaluable:
            continue
        fx_balance = Decimal(fx_net or 0)
        book_value = Decimal(debit) - Decimal(credit)  # مانده‌ی ریالیِ خام (بدهکار مثبت)
        found = _rate_on(db, code, as_of)
        if found is None:
            missing_rates.add(code)
            continue
        rate, rate_date = found
        market_value = (fx_balance * rate).quantize(Decimal(1))
        diff = market_value - book_value
        if fx_balance == 0 and diff == 0:
            continue
        total_diff += diff
        analytic = analytics.get(analytic_id) if analytic_id else None
        center = centers.get(cost_center_id) if cost_center_id else None
        items.append(
            {
                "account_id": account.id,
                "account_code": account.code,
                "account_name": account.name,
                "analytic_id": analytic_id,
                "analytic_code": analytic.code if analytic else None,
                "analytic_name": analytic.name if analytic else None,
                "cost_center_id": cost_center_id,
                "cost_center_name": center.name if center else None,
                "currency_code": code,
                "fx_balance": fx_balance,
                "rate": rate,
                #: تاریخِ خودِ نرخ، نه تاریخِ تسعیر. وقتی این دو یکی نیستند یعنی
                #: نرخِ روز ثبت نشده و کهنه‌ترین موجود به کار رفته — که کاربر باید
                #: ببیندش، نه اینکه پشتِ عددِ نرخ پنهان بماند.
                "rate_date": rate_date,
                "book_value": book_value,
                "market_value": market_value,
                "difference": diff,
            }
        )

    items.sort(
        key=lambda r: (
            r["currency_code"],
            r["account_code"],
            r["analytic_code"] or "",
            r["cost_center_name"] or "",
        )
    )
    return {
        "as_of": as_of,
        "items": items,
        "total_difference": total_diff,
        "missing_rates": sorted(missing_rates),
    }


def issue_fx_revaluation(db: Session, user: User, as_of: date_, description: str) -> dict:
    """سندِ تسعیر را از روی همان پیش‌نمایش صادر می‌کند."""
    assert_period_open(db, as_of)
    preview = fx_revaluation_preview(db, as_of)
    items = [i for i in preview["items"] if i["difference"] != 0]
    if not items:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "اختلافِ تسعیری برای این تاریخ وجود ندارد")

    gain = get_or_create_account(
        db, cc.FX_GAIN, code=cc.DEFAULT_CODE_BY_ROLE[cc.FX_GAIN], name="سود تسعیر ارز",
        acc_type="income", parent_code="4",
    )
    loss = get_or_create_account(
        db, cc.FX_LOSS, code=cc.DEFAULT_CODE_BY_ROLE[cc.FX_LOSS], name="زیان تسعیر ارز",
        acc_type="expense", parent_code="5",
    )

    lines: list[JournalLine] = []
    net = Decimal(0)
    for item in items:
        diff = Decimal(item["difference"])
        net += diff
        #: تفصیلی در شرح هم می‌آید، وگرنه چند ردیفِ تسعیرِ یک حساب در چاپ و در
        #: دفترِ کل از هم قابلِ تشخیص نیستند.
        label = f"تسعیرِ {item['currency_code']} — {item['account_name']}"
        if item["analytic_name"]:
            label += f" / {item['analytic_name']}"
        # اختلافِ مثبت یعنی معادلِ ریالیِ دارایی بیشتر شده → حساب بدهکار می‌شود.
        lines.append(
            JournalLine(
                account_id=item["account_id"],
                #: هر دو بُعد عیناً از مانده‌ای که تسعیر می‌شود کپی می‌شوند. ردیفی
                #: که ابعادش را دور بیندازد، اثرِ مالی را جایی می‌نشاند که مانده‌اش
                #: از آن‌جا نیامده است.
                analytic_id=item["analytic_id"],
                cost_center_id=item["cost_center_id"],
                debit=diff if diff > 0 else 0,
                credit=-diff if diff < 0 else 0,
                description=label,
                currency_code=item["currency_code"],
                # صفر، نه None: این ردیف ارزش *ریالیِ* حساب را اصلاح می‌کند بدونِ آنکه
                # یک واحد ارز جابه‌جا شود. None بودنش ردیف را از محاسبه‌ی بعدی حذف
                # می‌کرد و تسعیر هر بار همان اختلاف را دوباره پیشنهاد می‌داد.
                fx_amount=Decimal(0),
                fx_rate=item["rate"],
            )
        )
    if net > 0:
        lines.append(JournalLine(account_id=gain.id, debit=0, credit=net, description="سود تسعیر ارز"))
    else:
        lines.append(JournalLine(account_id=loss.id, debit=-net, credit=0, description="زیان تسعیر ارز"))

    entry = make_journal_entry(
        db, as_of, description.strip() or f"سند تسعیر ارز تا {as_of}", "fx_revaluation", user, lines
    )
    db.flush()
    return {"entry_id": entry.id, "number": entry.number, "net_difference": net, "line_count": len(lines)}


# ──────────────── ۶) بستنِ سود و زیان / اختتامیه / افتتاحیه ────────────────


def pnl_close_preview(db: Session, date_to: date_) -> dict:
    """پیش‌نمایشِ سندی که «بستنِ دوره» خواهد زد — بدونِ زدنش.

    عمداً همان تابعِ صورتِ سود و زیانِ سرویسِ گزارش را صدا می‌زند که خودِ بستن هم صدا
    می‌زند؛ اگر پیش‌نمایش منطقِ دوم می‌داشت، روزی از سندِ واقعی جدا می‌افتاد.
    """
    from app.services.reports import get_income_statement

    previous = get_latest_close_date(db)
    date_from = previous + timedelta(days=1) if previous else None
    statement = get_income_statement(db, date_from, date_to)
    rows = [
        {
            "account_id": r["account_id"],
            "account_code": r["account_code"],
            "account_name": r["account_name"],
            "side": "debit",
            "amount": r["balance"],
        }
        for r in statement["income"]
        if r["balance"] != 0
    ] + [
        {
            "account_id": r["account_id"],
            "account_code": r["account_code"],
            "account_name": r["account_name"],
            "side": "credit",
            "amount": r["balance"],
        }
        for r in statement["expenses"]
        if r["balance"] != 0
    ]
    return {
        "date_from": date_from,
        "date_to": date_to,
        "rows": rows,
        "total_income": statement["total_income"],
        "total_expenses": statement["total_expenses"],
        "net_profit": statement["net_profit"],
        "temporary_in_range": _temporary_count(db, date_from, date_to),
    }


def _temporary_count(db: Session, date_from: date_ | None, date_to: date_ | None) -> int:
    query = _live_entries(db).filter(JournalEntry.status == "temporary")
    if date_from:
        query = query.filter(JournalEntry.entry_date >= date_from)
    if date_to:
        query = query.filter(JournalEntry.entry_date <= date_to)
    return int(query.with_entities(func.count(JournalEntry.id)).scalar() or 0)


def _permanent_balances(
    db: Session, as_of: date_
) -> list[tuple[Account, UUID | None, UUID | None, Decimal]]:
    """مانده‌ی حساب‌های دائمی تا این تاریخ — بدونِ خودِ حساب‌های اختتامیه/افتتاحیه.

    آن دو حساب واسط‌اند و جمعشان در هر سندی صفر است؛ واردکردنشان در محاسبه یعنی
    اختتامیه‌ی امسال، اختتامیه‌ی پارسال را دوباره ببندد.

    **گروه‌بندی روی هر سه بُعدِ ردیف است، نه فقط حساب.** «دریافتنیِ تجاری» با سه
    مشتری سه مانده‌ی جداست؛ اگر یک‌کاسه شود، سالِ جدید با حسابی باز می‌شود که
    مانده دارد ولی دفترِ تفصیلی‌اش خالی است — جمع درست، تفکیک غلط، و چون سند
    ویرایشِ ردیف ندارد، برای همیشه. همان استدلالِ `fx_revaluation_preview`.
    """
    rows = (
        db.query(
            Account,
            JournalLine.analytic_id,
            JournalLine.cost_center_id,
            func.coalesce(func.sum(JournalLine.debit), 0),
            func.coalesce(func.sum(JournalLine.credit), 0),
        )
        .join(JournalLine, JournalLine.account_id == Account.id)
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .filter(
            Account.is_group.is_(False),
            Account.type.in_(PERMANENT_TYPES),
            or_(
                Account.system_role.is_(None),
                Account.system_role.notin_([cc.CLOSING_ACCOUNT, cc.OPENING_ACCOUNT]),
            ),
            JournalEntry.entry_date <= as_of,
        )
        .group_by(Account.id, JournalLine.analytic_id, JournalLine.cost_center_id)
        .all()
    )
    out: list[tuple[Account, UUID | None, UUID | None, Decimal]] = []
    for account, analytic_id, cost_center_id, debit, credit in rows:
        raw = Decimal(debit) - Decimal(credit)  # بدهکارِ خالص (مثبت = بدهکار)
        if raw != 0:
            out.append((account, analytic_id, cost_center_id, raw))
    return sorted(out, key=lambda r: (r[0].code, str(r[1] or ""), str(r[2] or "")))


def closing_entry_preview(db: Session, as_of: date_) -> dict:
    """سندِ اختتامیه: بستنِ همه‌ی حساب‌های دائمی در پایانِ سال."""
    balances = _permanent_balances(db, as_of)
    analytics = {a.id: a for a in db.query(AnalyticAccount).all()}
    centers = {c.id: c for c in db.query(CostCenter).all()}
    rows = []
    for a, analytic_id, cost_center_id, raw in balances:
        analytic = analytics.get(analytic_id) if analytic_id else None
        center = centers.get(cost_center_id) if cost_center_id else None
        rows.append(
            {
                "account_id": a.id,
                "account_code": a.code,
                "account_name": a.name,
                "account_type": a.type,
                #: بُعدها با مانده می‌آیند و روی ردیفِ سند می‌نشینند، وگرنه سالِ
                #: جدید تفکیکِ تفصیلیِ خودش را از دست می‌دهد.
                "analytic_id": analytic_id,
                "analytic_code": analytic.code if analytic else None,
                "analytic_name": analytic.name if analytic else None,
                "cost_center_id": cost_center_id,
                "cost_center_name": center.name if center else None,
                # اختتامیه هر حساب را *برعکسِ* مانده‌اش می‌زند تا صفر شود.
                "debit": -raw if raw < 0 else Decimal(0),
                "credit": raw if raw > 0 else Decimal(0),
                "balance": raw,
            }
        )
    total = sum((r["debit"] + r["credit"] for r in rows), Decimal(0))
    open_pnl = _open_pnl_total(db, as_of)
    return {
        "as_of": as_of,
        "rows": rows,
        "total": total,
        # اگر درآمد/هزینه هنوز باز است، اختتامیه زودهنگام است.
        "open_pnl_total": open_pnl,
        "temporary_count": _temporary_count(db, None, as_of),
    }


def _open_pnl_total(db: Session, as_of: date_) -> Decimal:
    rows = (
        db.query(Account.type, func.coalesce(func.sum(JournalLine.debit - JournalLine.credit), 0))
        .join(JournalLine, JournalLine.account_id == Account.id)
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .filter(Account.type.in_(("income", "expense")), JournalEntry.entry_date <= as_of)
        .group_by(Account.type)
        .all()
    )
    return sum((abs(Decimal(v)) for _, v in rows), Decimal(0))


def issue_closing_entry(db: Session, user: User, as_of: date_, description: str) -> dict:
    assert_period_open(db, as_of)
    preview = closing_entry_preview(db, as_of)
    if not preview["rows"]:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "هیچ حسابِ دائمیِ دارای مانده‌ای برای بستن نیست")
    if preview["open_pnl_total"] != 0:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "حساب‌های سود و زیان هنوز باز‌اند؛ اول «بستن حساب‌های سود و زیان» را انجام دهید",
        )

    closing = get_or_create_account(
        db, cc.CLOSING_ACCOUNT, code=cc.DEFAULT_CODE_BY_ROLE[cc.CLOSING_ACCOUNT],
        name="حساب اختتامیه", acc_type="equity", parent_code="3",
    )
    lines = [
        JournalLine(
            account_id=r["account_id"],
            #: بُعدها عیناً از مانده‌ای که بسته می‌شود کپی می‌شوند؛ ردیفی که
            #: دورشان بیندازد، دفترِ تفصیلیِ سالِ بعد را خالی تحویل می‌دهد.
            analytic_id=r["analytic_id"],
            cost_center_id=r["cost_center_id"],
            debit=r["debit"],
            credit=r["credit"],
            description=(
                f"بستنِ {r['account_name']}"
                + (f" / {r['analytic_name']}" if r["analytic_name"] else "")
            ),
        )
        for r in preview["rows"]
    ]
    total_debit = sum((Decimal(r["debit"]) for r in preview["rows"]), Decimal(0))
    total_credit = sum((Decimal(r["credit"]) for r in preview["rows"]), Decimal(0))
    # قیدِ پایگاه‌داده ردیفِ دوطرفه را نمی‌پذیرد، پس خطِ توازن باید *خالص* باشد نه
    # جمعِ دو طرف: یک ردیف با یک طرفِ پرشده به‌اندازه‌ی اختلاف.
    net = total_debit - total_credit
    lines.append(
        JournalLine(
            account_id=closing.id,
            debit=Decimal(0) if net > 0 else -net,
            credit=net if net > 0 else Decimal(0),
            description="حساب اختتامیه",
        )
    )
    entry = make_journal_entry(
        db, as_of, description.strip() or f"سند اختتامیه {as_of}", "closing_entry", user, lines
    )
    db.flush()
    return {"entry_id": entry.id, "number": entry.number, "line_count": len(lines), "total": total_debit + total_credit}


def _closing_entry_at(db: Session, source_date: date_) -> JournalEntry | None:
    return (
        db.query(JournalEntry)
        .options(selectinload(JournalEntry.lines))
        .filter(
            JournalEntry.source_type == "closing_entry",
            JournalEntry.entry_date == source_date,
            JournalEntry.voided_at.is_(None),
        )
        .order_by(JournalEntry.number.desc())
        .first()
    )


def opening_entry_preview(db: Session, as_of: date_, source_date: date_) -> dict:
    """سندِ افتتاحیه = **معکوسِ سندِ اختتامیه‌ی سالِ قبل**، نه یک محاسبه‌ی تازه.

    وسوسه‌ی طبیعی این است که مانده‌ها را دوباره از دفتر بخوانیم — ولی درست بعد از
    اختتامیه همه‌ی مانده‌ها صفرند (کارِ خودِ اختتامیه همین بود)، پس آن راه همیشه
    سندِ خالی می‌داد. مهم‌تر از آن: خواندنِ دوباره یعنی دو محاسبه‌ی مستقل که می‌توانند
    از هم جدا بیفتند. وارونه‌کردنِ همان سند، تضمین می‌کند سالِ جدید دقیقاً با همان
    مانده‌ای باز شود که سالِ قبل با آن بسته شد.
    """
    closing = _closing_entry_at(db, source_date)
    if closing is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"در تاریخ {source_date} سندِ اختتامیه‌ای پیدا نشد؛ اول اختتامیه را صادر کنید",
        )

    accounts = {a.id: a for a in db.query(Account).all()}
    analytics = {a.id: a for a in db.query(AnalyticAccount).all()}
    centers = {c.id: c for c in db.query(CostCenter).all()}
    closing_role_ids = {
        a.id for a in accounts.values() if a.system_role == cc.CLOSING_ACCOUNT
    }
    rows = []
    for line in closing.lines:
        if line.account_id in closing_role_ids:
            continue  # طرفِ واسطِ اختتامیه؛ جایش را حسابِ افتتاحیه می‌گیرد
        account = accounts.get(line.account_id)
        if account is None:
            continue
        debit = Decimal(line.credit)
        credit = Decimal(line.debit)
        analytic = analytics.get(line.analytic_id) if line.analytic_id else None
        center = centers.get(line.cost_center_id) if line.cost_center_id else None
        rows.append(
            {
                "account_id": account.id,
                "account_code": account.code,
                "account_name": account.name,
                "account_type": account.type,
                #: بُعدها از خودِ ردیفِ اختتامیه می‌آیند، نه از محاسبه‌ی تازه —
                #: همان دلیلی که کلِ افتتاحیه معکوسِ اختتامیه است.
                "analytic_id": line.analytic_id,
                "analytic_code": analytic.code if analytic else None,
                "analytic_name": analytic.name if analytic else None,
                "cost_center_id": line.cost_center_id,
                "cost_center_name": center.name if center else None,
                "debit": debit,
                "credit": credit,
                "balance": debit - credit,
            }
        )
    rows.sort(key=lambda r: (r["account_code"], r["analytic_code"] or "", r["cost_center_name"] or ""))
    return {
        "as_of": as_of,
        "source_date": source_date,
        "rows": rows,
        "closing_entry_id": closing.id,
        "closing_entry_number": closing.number,
        "total": sum((r["debit"] + r["credit"] for r in rows), Decimal(0)),
    }


def issue_opening_entry(
    db: Session, user: User, as_of: date_, source_date: date_, description: str
) -> dict:
    if source_date >= as_of:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "تاریخِ افتتاحیه باید بعد از تاریخِ اختتامیه‌ی سالِ قبل باشد"
        )
    assert_period_open(db, as_of)
    preview = opening_entry_preview(db, as_of, source_date)
    if not preview["rows"]:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "سندِ اختتامیه‌ی مبنا هیچ ردیفی ندارد")

    #: **اختتامیه خودش را گارد می‌کند، افتتاحیه نه.** بعد از اختتامیه همه‌ی
    #: مانده‌ها صفرند، پس اختتامیه‌ی دوم «حسابی برای بستن نیست» می‌گیرد. ولی
    #: افتتاحیه از *سندِ* اختتامیه ساخته می‌شود و آن سند سرِ جایش می‌ماند — پس
    #: اجرای دوم همان را دوباره وارونه می‌کند و **هر مانده‌ی ابتدای دوره دو برابر
    #: می‌شود**، بی‌صدا، چون سند متوازن است و هیچ گاردِ دیگری صدا نمی‌کند.
    #:
    #: مسدودکننده است نه هشدار: دوبرابرشدنِ خاموشِ ترازنامه همان‌قدر بنیادی است که
    #: گاردِ «سود و زیان هنوز باز است» چند خط بالاتر.
    existing = (
        db.query(JournalEntry)
        .filter(
            JournalEntry.source_type == "opening_entry",
            JournalEntry.reverses_entry_id == preview["closing_entry_id"],
            JournalEntry.voided_at.is_(None),
        )
        .first()
    )
    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"از روی این سندِ اختتامیه قبلاً افتتاحیه صادر شده (سند شماره "
            f"{existing.number}). برای صدورِ دوباره، اول همان را باطل کنید.",
        )

    opening = get_or_create_account(
        db, cc.OPENING_ACCOUNT, code=cc.DEFAULT_CODE_BY_ROLE[cc.OPENING_ACCOUNT],
        name="حساب افتتاحیه", acc_type="equity", parent_code="3",
    )
    lines = [
        JournalLine(
            account_id=r["account_id"],
            analytic_id=r["analytic_id"],
            cost_center_id=r["cost_center_id"],
            debit=r["debit"],
            credit=r["credit"],
            description=(
                f"افتتاحِ {r['account_name']}"
                + (f" / {r['analytic_name']}" if r["analytic_name"] else "")
            ),
        )
        for r in preview["rows"]
    ]
    total_debit = sum((Decimal(r["debit"]) for r in preview["rows"]), Decimal(0))
    total_credit = sum((Decimal(r["credit"]) for r in preview["rows"]), Decimal(0))
    net = total_debit - total_credit
    lines.append(
        JournalLine(
            account_id=opening.id,
            debit=Decimal(0) if net > 0 else -net,
            credit=net if net > 0 else Decimal(0),
            description="حساب افتتاحیه",
        )
    )
    entry = make_journal_entry(
        db, as_of, description.strip() or f"سند افتتاحیه {as_of}", "opening_entry", user, lines
    )
    #: پیوندِ صریحِ افتتاحیه به اختتامیه‌اش. ستونِ تازه لازم نیست: `reverses_entry_id`
    #: از قبل همین معنا را دارد و کامنتش می‌گوید «جمعشان همیشه صفر است» — که برای
    #: این جفت مو‌به‌مو صادق است. گاردِ بالا هم روی همین می‌نشیند.
    entry.reverses_entry_id = preview["closing_entry_id"]
    db.flush()
    return {
        "entry_id": entry.id,
        "number": entry.number,
        "line_count": len(lines),
        "total": total_debit + total_credit,
    }


# ─────────────────── ۷) ترازها، مرورِ حساب‌ها، دفاتر ───────────────────────


def get_balances(db: Session, date_from: date_ | None, date_to: date_ | None) -> list[dict]:
    """پایه‌ی «گزارش ترازها» و «مرور حساب‌ها» و «صدور سند کل» — هر سه از همین یک عدد ساخته می‌شوند.

    برای هر حسابِ سطحِ آخر شش عدد برمی‌گردد: گردشِ *قبل* از بازه (افتتاحیه)، گردشِ
    *داخلِ* بازه، و جمعشان (مانده‌ی پایانِ دوره). تراز دو/چهار/شش/هشت‌ستونی همگی
    نمایش‌های مختلفِ همین شش عددند، پس محاسبه یک‌بار اینجا انجام می‌شود نه در چهار جا.
    """
    _assert_range(date_from, date_to)

    def totals(upper: date_ | None, lower: date_ | None):
        query = (
            db.query(
                JournalLine.account_id,
                func.coalesce(func.sum(JournalLine.debit), 0),
                func.coalesce(func.sum(JournalLine.credit), 0),
            )
            .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
            .group_by(JournalLine.account_id)
        )
        if lower is not None:
            query = query.filter(JournalEntry.entry_date >= lower)
        if upper is not None:
            query = query.filter(JournalEntry.entry_date <= upper)
        return {aid: (Decimal(d), Decimal(c)) for aid, d, c in query.all()}

    opening = totals(date_from - timedelta(days=1), None) if date_from else {}
    period = totals(date_to, date_from)

    accounts = {a.id: a for a in db.query(Account).filter(Account.is_group.is_(False)).all()}
    rows = []
    for account_id in set(opening) | set(period):
        account = accounts.get(account_id)
        if account is None:
            continue
        od, oc = opening.get(account_id, (Decimal(0), Decimal(0)))
        pd_, pc = period.get(account_id, (Decimal(0), Decimal(0)))
        open_net = od - oc
        close_net = open_net + pd_ - pc
        rows.append(
            {
                "account_id": account.id,
                "account_code": account.code,
                "account_name": account.name,
                "account_type": account.type,
                "parent_id": account.parent_id,
                "opening_debit": open_net if open_net > 0 else Decimal(0),
                "opening_credit": -open_net if open_net < 0 else Decimal(0),
                "period_debit": pd_,
                "period_credit": pc,
                "closing_debit": close_net if close_net > 0 else Decimal(0),
                "closing_credit": -close_net if close_net < 0 else Decimal(0),
                "balance": _signed_balance(account.type, od + pd_, oc + pc),
            }
        )
    return sorted(rows, key=lambda r: r["account_code"])


def get_legal_book(db: Session, date_from: date_, date_to: date_) -> dict:
    """ردیف‌های دفترِ روزنامه به شکلی که دفاترِ قانونی/تجارتِ الکترونیک می‌خواهند.

    یک ردیف به‌ازای هر **ردیفِ سند** (نه هر سند)، با کد و نامِ حساب و شرح — همان
    چیدمانی که در دفترِ روزنامه‌ی رسمی نوشته می‌شود. اسنادِ باطل و معکوسشان هر دو
    می‌آیند: دفترِ قانونی باید نشان دهد اشتباه رخ داد و بعد اصلاح شد.
    """
    _assert_range(date_from, date_to)
    rows = (
        db.query(JournalEntry, JournalLine, Account)
        .join(JournalLine, JournalLine.entry_id == JournalEntry.id)
        .join(Account, JournalLine.account_id == Account.id)
        .filter(JournalEntry.entry_date >= date_from, JournalEntry.entry_date <= date_to)
        .order_by(JournalEntry.entry_date, JournalEntry.number, JournalLine.seq, JournalLine.id)
        .all()
    )
    out = []
    total_debit = Decimal(0)
    total_credit = Decimal(0)
    for entry, line, account in rows:
        total_debit += Decimal(line.debit)
        total_credit += Decimal(line.credit)
        out.append(
            {
                "entry_id": entry.id,
                "entry_number": entry.number,
                "entry_date": entry.entry_date,
                "status": entry.status,
                "voided": entry.voided_at is not None,
                "account_code": account.code,
                "account_name": account.name,
                "description": line.description or entry.description,
                "debit": Decimal(line.debit),
                "credit": Decimal(line.credit),
            }
        )
    return {
        "date_from": date_from,
        "date_to": date_to,
        "rows": out,
        "total_debit": total_debit,
        "total_credit": total_credit,
    }


# ───────────────────── ۸) اصلاحِ طبقه‌بندیِ حساب‌ها ────────────────────────


def reclassify_accounts(db: Session, items: list[dict]) -> dict:
    """جابه‌جاییِ دسته‌ایِ حساب‌ها زیرِ سرفصلِ درست (و در صورتِ نیاز، اصلاحِ نوع).

    سه گاردِ لازم:
      * سرفصلِ مقصد باید **گروه** باشد — حساب زیرِ حسابِ عادی معنا ندارد.
      * حرکت به زیرِ فرزندِ خودش حلقه می‌سازد و درخت را بی‌نهایت می‌کند.
      * نوعِ حساب باید با نوعِ سرفصلش بخواند، وگرنه ترازنامه و سود و زیان همان حساب
        را در دو جای متناقض نشان می‌دهند.
    """
    if not items:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "هیچ حسابی برای اصلاح انتخاب نشده")

    changed = []
    for item in items:
        account = db.get(Account, item["account_id"])
        if account is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "حساب یافت نشد")
        if account.system_role:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"حسابِ «{account.name}» نقشِ سیستمی دارد و طبقه‌بندی‌اش تغییر نمی‌کند",
            )

        new_parent_id = item.get("parent_id", account.parent_id)
        new_type = item.get("type") or account.type

        parent = None
        if new_parent_id is not None:
            parent = db.get(Account, new_parent_id)
            if parent is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "سرفصلِ مقصد یافت نشد")
            if not parent.is_group:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST, f"«{parent.name}» سرفصل نیست و نمی‌تواند زیرمجموعه بگیرد"
                )
            if parent.id in descendant_account_ids(db, account.id):
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST, "حساب را نمی‌توان زیرِ زیرمجموعه‌ی خودش برد"
                )
            if parent.type != new_type:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    f"نوعِ «{account.name}» با نوعِ سرفصلِ «{parent.name}» نمی‌خواند",
                )

        if account.parent_id != new_parent_id or account.type != new_type:
            changed.append(
                {
                    "account_id": account.id,
                    "account_code": account.code,
                    "account_name": account.name,
                    "old_parent_id": account.parent_id,
                    "new_parent_id": new_parent_id,
                    "old_type": account.type,
                    "new_type": new_type,
                }
            )
            account.parent_id = new_parent_id
            account.type = new_type
            # زیرمجموعه‌ها باید با والدشان هم‌نوع بمانند، وگرنه گارد بالا بارِ بعد
            # روی همان درخت شکست می‌خورد.
            if account.is_group:
                for child_id in descendant_account_ids(db, account.id) - {account.id}:
                    child = db.get(Account, child_id)
                    if child is not None:
                        child.type = new_type

    db.flush()
    return {"count": len(changed), "changed": changed}
