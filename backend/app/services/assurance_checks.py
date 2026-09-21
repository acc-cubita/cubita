"""بررسی‌های خانواده‌ی «حسابرسی» — همان موتور، مخاطبِ دیگر.

این فایل هیچ موتورِ دومی نمی‌سازد: کمک‌تابع‌های `integrity.py` را می‌خوانَد و
ردیف‌هایی با **دقیقاً همان شکل** می‌سازد، فقط با `family="assurance"` تا در
صفحه‌ی «بررسی یکپارچگی»ِ حسابدار ظاهر نشوند. جدا بودنِ فایل فقط برای خوانایی
است — نُه بررسیِ دفتر و دوازده بررسیِ حسابرسی در یک فایلِ هزارخطی گم می‌شدند.

**تفاوتِ دو خانواده در سؤالی است که می‌پرسند.** خانواده‌ی `ledger` می‌پرسد
«آیا این دفتر با خودش سازگار است؟» — پاسخِ منفی یعنی گزارش‌ها دروغ می‌گویند.
خانواده‌ی `assurance` می‌پرسد «آیا این دفتر نشانه‌ی کنترلِ داخلیِ ضعیف دارد؟» —
پاسخِ مثبت لزوماً یعنی خطا نیست، یعنی **جای نگاه‌کردن**. به همین دلیل بیشترشان
`warning`اند و توضیحشان صریح می‌گوید چه چیزی را اثبات **نمی‌کند**.

**زمان.** `created_at` در پایگاه‌داده UTC است و «ساعتِ غیرکاری» با ساعتِ تهران
معنا دارد، پس هر جا زمانِ ثبت سنجیده می‌شود از `timezone('Asia/Tehran', …)`
استفاده می‌شود، نه از تفریقِ خام.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date as date_
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import Date, cast, func
from sqlalchemy.orm import Session

from app.models.accounting import Account, JournalEntry, JournalLine
from app.models.inventory import Contact
from app.models.invoices import PurchaseInvoice
from app.models.period_close import FiscalPeriodClose
from app.models.user import User
from app.services.integrity import (
    FAMILY_ASSURANCE,
    MAX_ROW_LIMIT,
    _check,
    _filtered_lines,
    _row,
)
from app.services.reports import SYSTEM_SOURCE_TYPES, ReportFilters

#: منطقه‌ی زمانیِ کسب‌وکار. تنها جایی که کوبیتا زمانِ ذخیره‌شده را «ساعتِ روز»
#: تفسیر می‌کند همین‌جاست؛ بقیه‌ی برنامه با تاریخِ جلالی کار می‌کند نه ساعت.
TEHRAN_TZ = "Asia/Tehran"

#: ساعتِ کاریِ فراخ. هدف پیداکردنِ ثبتِ ساعتِ سه بامداد است، نه سخت‌گیری روی
#: حسابداری که هفت‌ونیم شروع می‌کند.
WORK_HOUR_FROM = 6
WORK_HOUR_TO = 21

#: تعطیلیِ هفتگی در تقویمِ پستگرس: ۵ = جمعه (`dow`: ۰ یکشنبه).
WEEKEND_DOW = 5

#: فاصله‌ای که فراتر از آن، «تاریخِ سند» دیگر تأخیرِ عادیِ ثبت نیست.
BACKDATE_DAYS = 30

#: سندِ موقتی که بیش از این بماند، عملاً فراموش شده است.
STALE_TEMPORARY_DAYS = 90

#: ابطال در این فاصله از ثبت، یعنی «اشتباهِ لحظه‌ی ثبت» نه تصمیمِ حسابداری.
QUICK_VOID_MINUTES = 10

#: آستانه‌ی جهشِ هزینه نسبت به دوره‌ی قبل.
DEVIATION_PCT = 50


def _fa(value) -> str:
    from app.services.printing import fa_number

    return fa_number(value)


def _day(value: date_ | None) -> str:
    from app.services.printing import format_jalali

    return format_jalali(value)


def _entry_scope(db: Session, filters: ReportFilters):
    """سندهای درونِ بازه — پایه‌ی بررسی‌هایی که سطحشان سند است نه ردیف.

    از `_filtered_lines` استفاده نمی‌کند چون آن‌جا واحدِ شمارش «ردیف» است و
    سندِ ده‌ردیفی ده بار شمرده می‌شد.
    """
    query = db.query(JournalEntry)
    if filters.date_from is not None:
        query = query.filter(JournalEntry.entry_date >= filters.date_from)
    if filters.date_to is not None:
        query = query.filter(JournalEntry.entry_date <= filters.date_to)
    if filters.status:
        query = query.filter(JournalEntry.status == filters.status)
    return query


def _purchase_scope(db: Session, filters: ReportFilters):
    query = db.query(PurchaseInvoice).filter(PurchaseInvoice.voided_at.is_(None))
    if filters.date_from is not None:
        query = query.filter(PurchaseInvoice.invoice_date >= filters.date_from)
    if filters.date_to is not None:
        query = query.filter(PurchaseInvoice.invoice_date <= filters.date_to)
    return query


def _contact_names(db: Session, ids: list) -> dict:
    clean = [i for i in ids if i is not None]
    if not clean:
        return {}
    rows = db.query(Contact.id, Contact.name).filter(Contact.id.in_(clean)).all()
    return {row.id: row.name for row in rows}


def _user_names(db: Session, ids: list) -> dict:
    clean = [i for i in ids if i is not None]
    if not clean:
        return {}
    rows = db.query(User.id, User.name, User.email).filter(User.id.in_(clean)).all()
    return {row.id: row.name or row.email for row in rows}


# ── خرید: مدرکِ طرفِ مقابل ────────────────────────────────────────────────────


def _duplicate_supplier_invoice(db: Session, filters: ReportFilters) -> dict:
    """یک شماره‌ی فاکتورِ فروشنده که دو بار ثبت شده.

    **چرا پایگاه‌داده جلویش را نمی‌گیرد:** `supplier_invoice_number` عمداً قیدِ
    یکتا ندارد — شماره‌ی سندِ *فروشنده* است و کوبیتا نمی‌تواند تضمین کند دو
    تأمین‌کننده شماره‌ی یکسان ندهند. ولی یک شماره از **یک** تأمین‌کننده، دو بار،
    یعنی یا پرداختِ دوباره یا هزینه‌ی دوباره.
    """
    groups = (
        _purchase_scope(db, filters)
        .filter(PurchaseInvoice.supplier_invoice_number != "")
        .with_entities(
            PurchaseInvoice.contact_id,
            PurchaseInvoice.supplier_invoice_number,
            func.count().label("n"),
            func.sum(PurchaseInvoice.total_amount).label("total"),
        )
        .group_by(PurchaseInvoice.contact_id, PurchaseInvoice.supplier_invoice_number)
        .having(func.count() > 1)
        .order_by(func.count().desc())
        .limit(MAX_ROW_LIMIT)
        .all()
    )
    names = _contact_names(db, [g.contact_id for g in groups])
    rows = [
        _row(
            f"شماره‌ی «{g.supplier_invoice_number}»",
            f"{names.get(g.contact_id, 'بدونِ طرف‌حساب')} — {_fa(g.n)} فاکتور با همین شماره",
            difference=Decimal(g.total or 0),
        )
        for g in groups
    ]
    return _check(
        "duplicate_supplier_invoice",
        "فاکتورهای خریدِ تکراری",
        "یک شماره‌ی فاکتور از یک تأمین‌کننده که بیش از یک بار ثبت شده — نشانه‌ی ثبت یا پرداختِ دوباره.",
        "error",
        rows,
        len(rows),
        family=FAMILY_ASSURANCE,
    )


def _duplicate_purchase_amount(db: Session, filters: ReportFilters) -> dict:
    """خریدهای هم‌مبلغ از یک تأمین‌کننده در یک روز — حالتِ «شماره‌ای در کار نیست»."""
    groups = (
        _purchase_scope(db, filters)
        .filter(PurchaseInvoice.total_amount > 0)
        .with_entities(
            PurchaseInvoice.contact_id,
            PurchaseInvoice.invoice_date,
            PurchaseInvoice.total_amount,
            func.count().label("n"),
        )
        .group_by(
            PurchaseInvoice.contact_id,
            PurchaseInvoice.invoice_date,
            PurchaseInvoice.total_amount,
        )
        .having(func.count() > 1)
        .order_by(func.count().desc())
        .limit(MAX_ROW_LIMIT)
        .all()
    )
    names = _contact_names(db, [g.contact_id for g in groups])
    rows = [
        _row(
            names.get(g.contact_id, "بدونِ طرف‌حساب"),
            f"{_day(g.invoice_date)} — {_fa(g.n)} فاکتور با مبلغِ یکسان",
            difference=Decimal(g.total_amount or 0),
        )
        for g in groups
    ]
    return _check(
        "duplicate_purchase_amount",
        "خریدهای هم‌مبلغِ هم‌روز",
        "چند فاکتورِ خرید از یک تأمین‌کننده، در یک روز و با مبلغِ دقیقاً یکسان. می‌تواند درست باشد، ولی ارزشِ نگاه‌کردن دارد.",
        "warning",
        rows,
        len(rows),
        family=FAMILY_ASSURANCE,
    )


def _missing_supplier_reference(db: Session, filters: ReportFilters) -> dict:
    """خریدِ بدونِ شماره‌ی مدرکِ فروشنده.

    نزدیک‌ترین چیزی که امروز می‌شود به «سندِ بدونِ پیوست» گفت: کوبیتا هنوز
    پیوستِ فایل ندارد، ولی خریدی که هیچ ارجاعی به مدرکِ طرفِ مقابل ندارد، همان
    نگرانی را با ستونی که وجود دارد بیان می‌کند.
    """
    query = _purchase_scope(db, filters).filter(PurchaseInvoice.supplier_invoice_number == "")
    total = query.count()
    records = query.order_by(PurchaseInvoice.invoice_date.desc()).limit(MAX_ROW_LIMIT).all()
    names = _contact_names(db, [r.contact_id for r in records])
    rows = [
        _row(
            f"فاکتور خرید {_fa(r.number)}",
            f"{_day(r.invoice_date)} — {names.get(r.contact_id, 'بدونِ طرف‌حساب')}",
            difference=Decimal(r.total_amount or 0),
        )
        for r in records
    ]
    return _check(
        "missing_supplier_reference",
        "فاکتور خرید بدونِ شماره‌ی فروشنده",
        "خریدی که به هیچ مدرکِ طرفِ مقابل ارجاع نمی‌دهد. نبودنِ شماره خطا نیست، ولی مستندسازی را ضعیف می‌کند.",
        "warning",
        rows,
        total,
        family=FAMILY_ASSURANCE,
    )


def _undocumented_manual_entries(db: Session, filters: ReportFilters) -> dict:
    """سندِ دستیِ بی‌شرح — تنها چیزی که می‌گفت چرا ثبت شده، خالی است."""
    query = _entry_scope(db, filters).filter(
        JournalEntry.source_type == "manual",
        JournalEntry.voided_at.is_(None),
        func.coalesce(func.trim(JournalEntry.description), "") == "",
    )
    total = query.count()
    records = query.order_by(JournalEntry.entry_date.desc()).limit(MAX_ROW_LIMIT).all()
    rows = [
        _row(
            f"سند {_fa(r.number)}",
            f"{_day(r.entry_date)} — بدونِ شرح",
            entry_id=r.id,
        )
        for r in records
    ]
    return _check(
        "undocumented_manual_entries",
        "سندِ دستیِ بی‌شرح",
        "سندی که کاربر دستی ساخته و هیچ توضیحی ندارد؛ شش ماه بعد هیچ‌کس نمی‌داند بابتِ چه بوده.",
        "warning",
        rows,
        total,
        family=FAMILY_ASSURANCE,
    )


# ── زمانِ ثبت ────────────────────────────────────────────────────────────────


def _local_created(column=JournalEntry.created_at):
    """لحظه‌ی ثبت به وقتِ تهران — `created_at` در پایگاه‌داده UTC است."""
    return func.timezone(TEHRAN_TZ, column)


def _backdated_entries(db: Session, filters: ReportFilters) -> dict:
    """تاریخِ سند خیلی عقب‌تر از لحظه‌ی ثبتش.

    افتتاحیه و اختتامیه و سندهای معکوس **عمداً** عقب‌دار ثبت می‌شوند، پس کنار
    گذاشته می‌شوند؛ بدونِ این استثنا، هر شرکتی در اولین ماهِ کارش این بررسی را
    پر از ردیف می‌دید و بعد یاد می‌گرفت نادیده‌اش بگیرد.
    """
    delta = cast(_local_created(), Date) - JournalEntry.entry_date
    query = _entry_scope(db, filters).filter(
        JournalEntry.voided_at.is_(None),
        JournalEntry.reverses_entry_id.is_(None),
        JournalEntry.source_type.notin_(tuple(SYSTEM_SOURCE_TYPES)),
        delta > BACKDATE_DAYS,
    )
    total = query.count()
    records = (
        query.with_entities(
            JournalEntry.id,
            JournalEntry.number,
            JournalEntry.entry_date,
            delta.label("gap"),
        )
        .order_by(delta.desc())
        .limit(MAX_ROW_LIMIT)
        .all()
    )
    rows = [
        _row(
            f"سند {_fa(r.number)}",
            f"تاریخِ سند {_day(r.entry_date)} — {_fa(r.gap)} روز پس از آن ثبت شده",
            entry_id=r.id,
        )
        for r in records
    ]
    return _check(
        "backdated_entries",
        "سند با تاریخِ عقب‌افتاده",
        f"سندی که بیش از {_fa(BACKDATE_DAYS)} روز پس از تاریخِ خودش ثبت شده. افتتاحیه، اختتامیه و سندهای معکوس شمرده نمی‌شوند.",
        "warning",
        rows,
        total,
        family=FAMILY_ASSURANCE,
    )


def _off_hours_entries(db: Session, filters: ReportFilters) -> dict:
    """ثبت در ساعتِ غیرکاری یا روزِ تعطیل، **گروه‌بندی‌شده بر اساسِ کاربر**.

    ردیف‌به‌ردیف نشان‌دادنش یعنی چهارده ردیفِ تکراری که همه یک حرف می‌زنند؛
    آنچه حسابرس می‌خواهد بداند این است که *چه کسی* عادتِ ثبتِ نیمه‌شب دارد.
    """
    hour = func.extract("hour", _local_created())
    dow = func.extract("dow", _local_created())
    groups = (
        _entry_scope(db, filters)
        .filter(
            JournalEntry.voided_at.is_(None),
            JournalEntry.source_type.notin_(tuple(SYSTEM_SOURCE_TYPES)),
            (hour < WORK_HOUR_FROM) | (hour > WORK_HOUR_TO) | (dow == WEEKEND_DOW),
        )
        .with_entities(
            JournalEntry.created_by_id,
            func.count().label("n"),
            func.min(hour).label("lo"),
            func.max(hour).label("hi"),
        )
        .group_by(JournalEntry.created_by_id)
        .order_by(func.count().desc())
        .limit(MAX_ROW_LIMIT)
        .all()
    )
    names = _user_names(db, [g.created_by_id for g in groups])
    rows = [
        _row(
            names.get(g.created_by_id, "کاربرِ حذف‌شده"),
            f"{_fa(g.n)} سند خارج از ساعتِ کاری یا در روزِ تعطیل — بینِ ساعتِ {_fa(int(g.lo))} و {_fa(int(g.hi))}",
        )
        for g in groups
    ]
    return _check(
        "off_hours_entries",
        "ثبت خارج از ساعتِ کاری",
        f"سندهایی که پیش از ساعتِ {_fa(WORK_HOUR_FROM)}، پس از {_fa(WORK_HOUR_TO)} یا در روزِ جمعه ثبت شده‌اند (به وقتِ تهران). به‌خودی‌خود ایراد نیست؛ الگویش مهم است.",
        "warning",
        rows,
        len(rows),
        family=FAMILY_ASSURANCE,
    )


def _void_soon_after_create(db: Session, filters: ReportFilters) -> dict:
    """سندی که چند دقیقه پس از ثبت باطل شده — نشانه‌ی ثبتِ آزمایشی روی دفترِ واقعی."""
    gap = JournalEntry.voided_at - JournalEntry.created_at
    query = _entry_scope(db, filters).filter(
        JournalEntry.voided_at.isnot(None),
        gap < timedelta(minutes=QUICK_VOID_MINUTES),
    )
    total = query.count()
    records = (
        query.with_entities(JournalEntry.id, JournalEntry.number, JournalEntry.entry_date)
        .order_by(JournalEntry.entry_date.desc())
        .limit(MAX_ROW_LIMIT)
        .all()
    )
    rows = [
        _row(
            f"سند {_fa(r.number)}",
            f"{_day(r.entry_date)} — کمتر از {_fa(QUICK_VOID_MINUTES)} دقیقه پس از ثبت باطل شده",
            entry_id=r.id,
        )
        for r in records
    ]
    return _check(
        "void_soon_after_create",
        "ابطالِ سریع پس از ثبت",
        "سندی که تقریباً بلافاصله باطل شده. معمولاً یعنی روی دفترِ واقعی آزمایش شده است.",
        "warning",
        rows,
        total,
        family=FAMILY_ASSURANCE,
    )


# ── انضباطِ دفتر ─────────────────────────────────────────────────────────────


def _out_of_sequence_numbers(db: Session, filters: ReportFilters) -> dict:
    """شماره‌ی سند با ترتیبِ تاریخ نمی‌خواند.

    **ترتیبِ درست را خودش تعریف نمی‌کند:** همان نقشه‌ای را می‌خواند که عملیاتِ
    «شماره‌گذاری مجدد» برای *اصلاح* می‌سازد (`accounting_ops._renumber_plan` —
    تاریخ، بعد لحظه‌ی ثبت، فقط اسنادِ موقت). دو تعریفِ جدا از «ترتیبِ درست» دیر
    یا زود دو جواب می‌دهند.

    `preview_renumber` عمداً استفاده **نشد**: آن تابع شماره‌ی شروع می‌گیرد و هر
    سندی را که با شمارشِ تازه جور نباشد «تغییرکرده» می‌نامد — یعنی دفتری که از
    ۱۰۰ شماره خورده، تک‌تکِ سندهایش این‌جا هشدار می‌شد. آنچه اهمیت دارد **وارونگی**
    است: سندی که تاریخش جلوتر است ولی شماره‌اش عقب‌تر.
    """
    from app.services import accounting_ops

    try:
        entries = accounting_ops._renumber_plan(db, filters.date_from, filters.date_to)
    except Exception:  # noqa: BLE001 — بازه‌ی نامعتبر نباید کلِ گزارش را بشکند
        entries = []

    rows: list[dict] = []
    total = 0
    peak: int | None = None
    peak_entry: JournalEntry | None = None
    for entry in entries:
        if peak is not None and entry.number < peak:
            total += 1
            if len(rows) < MAX_ROW_LIMIT:
                rows.append(
                    _row(
                        f"سند {_fa(entry.number)}",
                        f"{_day(entry.entry_date)} — پس از سندِ {_fa(peak)}"
                        f" با تاریخِ {_day(peak_entry.entry_date if peak_entry else None)} آمده",
                        entry_id=entry.id,
                    )
                )
        elif peak is None or entry.number > peak:
            peak, peak_entry = entry.number, entry
    return _check(
        "out_of_sequence_numbers",
        "شماره‌ی سند با تاریخ نمی‌خواند",
        "سندی که تاریخش جلوتر از سندِ قبلی است ولی شماره‌ی کوچک‌تری دارد. فقط اسنادِ موقت سنجیده می‌شوند، چون شماره‌ی سندِ دائم جابه‌جا نمی‌شود.",
        "warning",
        rows,
        total,
        family=FAMILY_ASSURANCE,
    )


def _long_lived_temporary(db: Session, filters: ReportFilters) -> dict:
    """سندِ موقتی که ماه‌هاست موقت مانده."""
    cutoff = (filters.date_to or date_.today()) - timedelta(days=STALE_TEMPORARY_DAYS)
    query = _entry_scope(db, filters).filter(
        JournalEntry.status == "temporary",
        JournalEntry.voided_at.is_(None),
        JournalEntry.entry_date < cutoff,
    )
    total = query.count()
    records = (
        query.with_entities(JournalEntry.id, JournalEntry.number, JournalEntry.entry_date)
        .order_by(JournalEntry.entry_date)
        .limit(MAX_ROW_LIMIT)
        .all()
    )
    rows = [
        _row(f"سند {_fa(r.number)}", f"{_day(r.entry_date)} — هنوز موقت است", entry_id=r.id)
        for r in records
    ]
    return _check(
        "long_lived_temporary",
        "سندهای موقتِ کهنه",
        f"سندهایی که بیش از {_fa(STALE_TEMPORARY_DAYS)} روز موقت مانده‌اند. سندِ موقت در دفترِ قانونی جایی ندارد.",
        "warning",
        rows,
        total,
        family=FAMILY_ASSURANCE,
    )


def _entries_before_period_close(db: Session, filters: ReportFilters) -> dict:
    """سندی با تاریخِ پیش از آخرین بستنِ دوره که **پس از** آن ثبت شده.

    دوره‌ی بسته یعنی اعداد اعلام‌شده‌اند. سندی که بعداً داخلِ همان بازه بنشیند،
    گزارشِ اعلام‌شده را بی‌صدا عوض می‌کند — دقیقاً همان چیزی که حسابرس دنبالش است.
    """
    last = (
        db.query(FiscalPeriodClose)
        .order_by(FiscalPeriodClose.closing_date.desc())
        .first()
    )
    if last is None:
        return _check(
            "entries_before_period_close",
            "سند با تاریخِ پیش از بستنِ دوره",
            "دوره‌ای بسته نشده است، پس این بررسی موضوعیت ندارد.",
            "error",
            [],
            0,
            family=FAMILY_ASSURANCE,
        )

    query = _entry_scope(db, filters).filter(
        JournalEntry.entry_date <= last.closing_date,
        JournalEntry.created_at > last.created_at,
        JournalEntry.voided_at.is_(None),
        JournalEntry.id != last.journal_entry_id,
    )
    total = query.count()
    records = (
        query.with_entities(JournalEntry.id, JournalEntry.number, JournalEntry.entry_date)
        .order_by(JournalEntry.entry_date.desc())
        .limit(MAX_ROW_LIMIT)
        .all()
    )
    rows = [
        _row(
            f"سند {_fa(r.number)}",
            f"{_day(r.entry_date)} — پس از بستنِ دوره‌ی {_day(last.closing_date)} ثبت شده",
            entry_id=r.id,
        )
        for r in records
    ]
    return _check(
        "entries_before_period_close",
        "سند با تاریخِ پیش از بستنِ دوره",
        "سندی که تاریخش داخلِ دوره‌ی بسته‌شده است ولی پس از بستن ثبت شده — یعنی عددی که قبلاً اعلام شده، عوض شده است.",
        "error",
        rows,
        total,
        family=FAMILY_ASSURANCE,
    )


def _same_actor_create_and_finalize(db: Session, filters: ReportFilters) -> dict:
    """یک نفر هم سند را ثبت کرده و هم دائمش کرده — تفکیکِ وظایف برقرار نیست."""
    groups = (
        _entry_scope(db, filters)
        .filter(
            JournalEntry.finalized_at.isnot(None),
            JournalEntry.finalized_by_id.isnot(None),
            JournalEntry.created_by_id == JournalEntry.finalized_by_id,
            JournalEntry.voided_at.is_(None),
            JournalEntry.source_type.notin_(tuple(SYSTEM_SOURCE_TYPES)),
        )
        .with_entities(JournalEntry.created_by_id, func.count().label("n"))
        .group_by(JournalEntry.created_by_id)
        .order_by(func.count().desc())
        .limit(MAX_ROW_LIMIT)
        .all()
    )
    names = _user_names(db, [g.created_by_id for g in groups])
    rows = [
        _row(
            names.get(g.created_by_id, "کاربرِ حذف‌شده"),
            f"{_fa(g.n)} سند را خودش ثبت و خودش دائم کرده است",
        )
        for g in groups
    ]
    return _check(
        "same_actor_create_and_finalize",
        "ثبت و نهایی‌سازی توسطِ یک نفر",
        "در کسب‌وکارِ کوچک طبیعی است، ولی یعنی هیچ چشمِ دومی سند را ندیده — همان چیزی که کنترلِ داخلی می‌خواهد.",
        "warning",
        rows,
        len(rows),
        family=FAMILY_ASSURANCE,
    )


# ── تحلیلِ دوره‌ای ────────────────────────────────────────────────────────────


def _expense_totals(db: Session, filters: ReportFilters, date_from, date_to) -> dict:
    """جمعِ هزینه‌ی هر حسابِ سطحِ آخر در یک بازه.

    روی `_filtered_lines` با `include_system_entries=False` سوار است، نه روی
    `_leaf_account_totals`: آن تابع `ReportFilters` نمی‌گیرد، پس سندِ بستنِ دوره
    را نمی‌شود کنار گذاشت — و اختتامیه کلِ هزینه‌ی سال را یک‌جا می‌زند و مقایسه را
    بی‌معنا می‌کند.
    """
    scope = replace(
        filters, date_from=date_from, date_to=date_to, include_system_entries=False
    )
    rows = (
        _filtered_lines(db, scope)
        .join(Account, JournalLine.account_id == Account.id)
        .filter(Account.type == "expense", Account.is_group.is_(False))
        .with_entities(
            Account.id,
            Account.code,
            Account.name,
            (func.coalesce(func.sum(JournalLine.debit), 0) - func.coalesce(func.sum(JournalLine.credit), 0)).label("net"),
        )
        .group_by(Account.id, Account.code, Account.name)
        .all()
    )
    return {r.id: r for r in rows}


def _expense_period_deviation(db: Session, filters: ReportFilters) -> dict:
    """جهشِ هزینه نسبت به دوره‌ی قبل، با همان طولِ بازه."""
    if filters.date_from is None or filters.date_to is None:
        return _check(
            "expense_period_deviation",
            "جهشِ هزینه نسبت به دوره‌ی قبل",
            "برای این بررسی باید بازه‌ی تاریخ مشخص باشد.",
            "warning",
            [],
            0,
            family=FAMILY_ASSURANCE,
        )

    span = (filters.date_to - filters.date_from).days + 1
    prev_to = filters.date_from - timedelta(days=1)
    prev_from = prev_to - timedelta(days=span - 1)

    current = _expense_totals(db, filters, filters.date_from, filters.date_to)
    previous = _expense_totals(db, filters, prev_from, prev_to)

    rows: list[dict] = []
    for account_id, now in current.items():
        before = previous.get(account_id)
        base = Decimal(before.net) if before is not None else Decimal(0)
        value = Decimal(now.net)
        if base <= 0:
            #: حسابی که دوره‌ی قبل اصلاً گردش نداشته، «جهش» ندارد — تازه است.
            #: گزارش‌کردنش یعنی هر حسابِ نوی هر ماه یک هشدار بسازد.
            continue
        variance = value - base
        variance_pct = (variance / base) * 100
        if abs(variance_pct) < DEVIATION_PCT:
            continue
        direction = "افزایش" if variance > 0 else "کاهش"
        rows.append(
            _row(
                f"{now.code} — {now.name}",
                f"{direction}ِ {_fa(abs(round(variance_pct)))}٪ نسبت به {_day(prev_from)} تا {_day(prev_to)}"
                f" (از {_fa(base)} به {_fa(value)})",
                difference=variance,
                account_id=account_id,
            )
        )
    rows.sort(key=lambda r: abs(r["difference"]), reverse=True)
    return _check(
        "expense_period_deviation",
        "جهشِ هزینه نسبت به دوره‌ی قبل",
        f"حساب‌های هزینه‌ای که بیش از {_fa(DEVIATION_PCT)}٪ نسبت به دوره‌ی قبل (با همان طول) تغییر کرده‌اند. اسنادِ بستنِ دوره شمرده نمی‌شوند.",
        "warning",
        rows,
        len(rows),
        family=FAMILY_ASSURANCE,
    )


def build(db: Session, filters: ReportFilters) -> list[dict]:
    """همه‌ی بررسی‌های خانواده‌ی حسابرسی، به ترتیبِ اهمیت.

    ترتیب عمدی است: دو بررسیِ «خطا» اول می‌آیند، بعد مستندسازی، بعد زمانِ ثبت،
    بعد انضباطِ دفتر و آخر تحلیلِ دوره‌ای.
    """
    return [
        _duplicate_supplier_invoice(db, filters),
        _entries_before_period_close(db, filters),
        _duplicate_purchase_amount(db, filters),
        _missing_supplier_reference(db, filters),
        _undocumented_manual_entries(db, filters),
        _backdated_entries(db, filters),
        _off_hours_entries(db, filters),
        _void_soon_after_create(db, filters),
        _out_of_sequence_numbers(db, filters),
        _long_lived_temporary(db, filters),
        _same_actor_create_and_finalize(db, filters),
        _expense_period_deviation(db, filters),
    ]
