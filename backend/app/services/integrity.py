"""بررسیِ یکپارچگیِ دفتر — **گزارش است، نه گارد**.

همان تصمیمی که `get_nature_violations` گرفت، به همان دلیل: چیزی این‌جا مسدود
نمی‌شود. کاری که می‌شود این است که ناسازگاری‌ها **پیدا و نشان داده** شوند تا
حسابدار خودش قضاوت کند و سرِ فرصت اصلاح کند. سندِ نامتوازن را نمی‌شود با نبستنِ
راهِ ثبت درست کرد؛ آن سند از قبل ثبت شده است.

**چرا اصلاً لازم است.** کوبیتا سند را از سی‌وهفت نقطه می‌سازد. اعتبارسنجیِ توازن
در `schemas/accounting.py` است — یعنی فقط سرِ راهِ سندِ *دستی*. سرویس‌ها ردیف را
مستقیم می‌سازند و از آن اعتبارسنج رد نمی‌شوند؛ یک اشتباه در هرکدام، سندی می‌سازد
که هیچ‌جا صدا نمی‌کند. تنها راهِ دیدنش خواندنِ خودِ دفتر است.

**دو مسیرِ مستقل، عمداً.** بررسیِ `trial_vs_ledger` همان عددی را که «گزارش ترازها»
با `GROUP BY` در پایگاه‌داده می‌گیرد، با عددی که «مرور حساب» ردیف‌به‌ردیف در
پایتون جمع می‌زند مقایسه می‌کند. اگر این دو یکی نباشند، یکی از دو گزارش دروغ
می‌گوید و تا امروز راهی برای فهمیدنش نبود. همان قیدی که `get_balances` در
مستنداتش نوشته: «با یک فیلتر، تراز و مرور حساب و دفتر باید یک عدد بدهند».
"""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.accounting import Account, JournalEntry, JournalLine
from app.services.accounting_ops import get_balances
from app.services.reports import (
    SYSTEM_SOURCE_TYPES,
    ReportFilters,
    apply_report_filters,
    get_general_ledger,
)

#: سقفِ ردیف‌های هر بررسی. گزارشِ یکپارچگی برای *دیدنِ* اشکال است نه صادر کردنش؛
#: اگر هزار سندِ نامتوازن هست، دیدنِ پنجاه‌تای اول همان تصمیم را می‌سازد و
#: شمارشِ کامل هم کنارش هست. بدونِ سقف، یک دفترِ خرابْ صفحه را از کار می‌انداخت.
ROW_LIMIT = 50


def _row(
    label: str,
    detail: str,
    *,
    debit: Decimal = Decimal(0),
    credit: Decimal = Decimal(0),
    difference: Decimal = Decimal(0),
    entry_id: UUID | None = None,
    account_id: UUID | None = None,
) -> dict:
    """ردیفِ یکنواختِ هر بررسی — تا یک جدول در رابط، همه را نشان بدهد.

    `entry_id` و `account_id` برای drill-down‌اند: هر ردیف باید بتواند کاربر را به
    خودِ سند یا خودِ دفترِ حساب ببرد. گزارشی که می‌گوید «اشکالی هست» ولی نمی‌گوید
    کجا، کارِ حسابدار را بیشتر می‌کند نه کمتر.
    """
    return {
        "label": label,
        "detail": detail,
        "debit": debit,
        "credit": credit,
        "difference": difference,
        "entry_id": entry_id,
        "account_id": account_id,
    }


def _check(key: str, title: str, description: str, severity: str, rows: list[dict], total: int) -> dict:
    return {
        "key": key,
        "title": title,
        "description": description,
        "severity": severity,
        "ok": total == 0,
        "count": total,
        "rows": rows[:ROW_LIMIT],
        "truncated": total > ROW_LIMIT,
    }


def _filtered_lines(db: Session, filters: ReportFilters):
    """کوئریِ پایه‌ی هر بررسی: ردیف‌های سند با فیلترهای گزارش **و** بازه‌ی تاریخ.

    تاریخ این‌جا اعمال می‌شود چون `apply_report_filters` عمداً تاریخ را جا
    می‌گذارد (`get_balances` بازه را دو تکه می‌کند و آن‌جا مزاحم می‌شد). بررسیِ
    یکپارچگی تکه‌بندی ندارد و یک بازه‌ی ساده می‌خواهد.
    """
    query = db.query(JournalLine).join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
    query = apply_report_filters(db, query, filters)
    if filters.date_from is not None:
        query = query.filter(JournalEntry.entry_date >= filters.date_from)
    if filters.date_to is not None:
        query = query.filter(JournalEntry.entry_date <= filters.date_to)
    return query


def _unbalanced_entries(db: Session, filters: ReportFilters) -> dict:
    """سندهایی که جمعِ بدهکار و بستانکارشان یکی نیست.

    ستونِ اصلیِ دوقلمی. اگر این بررسی ردیف بدهد، هیچ گزارشِ مالیِ دیگری قابلِ
    اتکا نیست — پس اول از همه می‌آید.
    """
    totals = (
        _filtered_lines(db, filters)
        .with_entities(
            JournalEntry.id,
            JournalEntry.number,
            JournalEntry.entry_date,
            JournalEntry.description,
            func.coalesce(func.sum(JournalLine.debit), 0),
            func.coalesce(func.sum(JournalLine.credit), 0),
        )
        .group_by(JournalEntry.id, JournalEntry.number, JournalEntry.entry_date, JournalEntry.description)
        .having(func.coalesce(func.sum(JournalLine.debit), 0) != func.coalesce(func.sum(JournalLine.credit), 0))
        .order_by(JournalEntry.number)
        .all()
    )
    rows = [
        _row(
            f"سند {number}",
            description or "",
            debit=Decimal(debit),
            credit=Decimal(credit),
            difference=Decimal(debit) - Decimal(credit),
            entry_id=entry_id,
        )
        for entry_id, number, _entry_date, description, debit, credit in totals
    ]
    return _check(
        "unbalanced_entries",
        "سندهای نامتوازن",
        "سندی که جمعِ بدهکار و بستانکارش یکی نیست. اعتبارسنجیِ توازن فقط روی سندِ "
        "دستی است؛ سندی که یک سرویس ساخته از آن رد نمی‌شود.",
        "error",
        rows,
        len(totals),
    )


def _empty_entries(db: Session, filters: ReportFilters) -> dict:
    """سندهای بی‌ردیف.

    سندِ بدونِ ردیف «متوازن» است (صفر برابرِ صفر) پس بررسیِ توازن نمی‌بیندش، ولی
    یک شماره‌ی سندِ سوخته است که هیچ رویدادی را ثبت نکرده. خطای مالی نیست —
    برای همین هشدار است نه خطا — ولی معمولاً نشانه‌ی نیمه‌کاره ماندنِ یک عملیات است.

    **تنها بررسی‌ای که فیلترهای سطحِ *ردیف* را نمی‌گیرد**، و ناچار: سندِ بی‌ردیف
    مرکز هزینه و تفصیلی ندارد، پس هر فیلترِ بُعدی همیشه از قلمش می‌انداخت و این
    بررسی دقیقاً وقتی کور می‌شد که کاربر دامنه را باریک کرده. فیلترهای سطحِ
    *سند* (شماره، وضعیت، منشأ، بازه) اما اعمال می‌شوند تا دامنه با بقیه‌ی
    بررسی‌ها یکی بماند.
    """
    query = (
        db.query(JournalEntry.id, JournalEntry.number, JournalEntry.description)
        .outerjoin(JournalLine, JournalLine.entry_id == JournalEntry.id)
        .group_by(JournalEntry.id, JournalEntry.number, JournalEntry.description)
        .having(func.count(JournalLine.id) == 0)
    )
    if filters.entry_from is not None:
        query = query.filter(JournalEntry.number >= filters.entry_from)
    if filters.entry_to is not None:
        query = query.filter(JournalEntry.number <= filters.entry_to)
    if filters.status in ("temporary", "permanent"):
        query = query.filter(JournalEntry.status == filters.status)
    if filters.source_type:
        query = query.filter(JournalEntry.source_type == filters.source_type)
    if not filters.include_system_entries:
        query = query.filter(
            or_(
                JournalEntry.source_type.is_(None),
                JournalEntry.source_type.notin_(tuple(SYSTEM_SOURCE_TYPES)),
            )
        )
    if filters.date_from is not None:
        query = query.filter(JournalEntry.entry_date >= filters.date_from)
    if filters.date_to is not None:
        query = query.filter(JournalEntry.entry_date <= filters.date_to)

    rows_raw = query.order_by(JournalEntry.number).all()
    rows = [
        _row(f"سند {number}", description or "بدونِ شرح", entry_id=entry_id)
        for entry_id, number, description in rows_raw
    ]
    return _check(
        "empty_entries",
        "سندهای بی‌ردیف",
        "سندی که هیچ ردیفی ندارد. چون صفر با صفر متوازن است، بررسیِ توازن آن را نمی‌بیند.",
        "warning",
        rows,
        len(rows_raw),
    )


def _lines_on_group_accounts(db: Session, filters: ReportFilters) -> dict:
    """ردیف‌هایی که روی حسابِ **گروه** نشسته‌اند.

    این بی‌صداترین اشکالِ ممکن است: `get_balances` فقط حساب‌های
    `is_group = False` را می‌آورد، پس مبلغی که روی یک سرفصل نشسته باشد **از تراز
    ناپدید می‌شود** در حالی که دفتر همچنان متوازن است. یعنی جمعِ ستون‌های تراز با
    هم نمی‌خوانند و هیچ‌جا نمی‌گوید چرا.

    ثبتِ سندِ دستی روی سرفصل امروز مسدود نیست. طبقِ «گزارش، نه گارد» این‌جا هم
    مسدود نمی‌شود — نشان داده می‌شود.
    """
    totals = (
        _filtered_lines(db, filters)
        .join(Account, JournalLine.account_id == Account.id)
        .with_entities(
            Account.id,
            Account.code,
            Account.name,
            func.count(JournalLine.id),
            func.coalesce(func.sum(JournalLine.debit), 0),
            func.coalesce(func.sum(JournalLine.credit), 0),
        )
        .filter(Account.is_group.is_(True))
        .group_by(Account.id, Account.code, Account.name)
        .order_by(Account.code)
        .all()
    )
    rows = [
        _row(
            f"{code} — {name}",
            f"{count} ردیفِ سند روی سرفصل",
            debit=Decimal(debit),
            credit=Decimal(credit),
            difference=Decimal(debit) - Decimal(credit),
            account_id=account_id,
        )
        for account_id, code, name, count, debit, credit in totals
    ]
    return _check(
        "group_account_lines",
        "سند روی سرفصل",
        "ردیفِ سندی که به‌جای حسابِ سطحِ آخر، روی یک سرفصل نشسته. این مبلغ از "
        "«گزارش ترازها» حذف می‌شود و جمعِ تراز را به‌هم می‌زند.",
        "error",
        rows,
        len(totals),
    )


def _leaves_with_children(db: Session) -> dict:
    """حسابی که سطحِ آخر علامت خورده ولی زیرحساب دارد.

    آینه‌ی بررسیِ قبلی. تراز چنین حسابی را **هم خودش** می‌آورد **هم فرزندانش** —
    و «مرور حساب» که زیرشاخه را جمع می‌زند، مبلغ را دو بار می‌شمارد.

    این تنها بررسیِ ساختاریِ این گزارش است: به تاریخ و فیلتر کاری ندارد، چون
    اشکال در *چارت* است نه در دفتر.
    """
    child = db.query(Account.parent_id, func.count(Account.id).label("kids")).group_by(Account.parent_id).subquery()
    rows_raw = (
        db.query(Account.id, Account.code, Account.name, child.c.kids)
        .join(child, child.c.parent_id == Account.id)
        .filter(Account.is_group.is_(False))
        .order_by(Account.code)
        .all()
    )
    rows = [
        _row(f"{code} — {name}", f"{kids} زیرحساب دارد ولی سطحِ آخر علامت خورده", account_id=account_id)
        for account_id, code, name, kids in rows_raw
    ]
    return _check(
        "leaf_with_children",
        "حسابِ سطحِ آخر با زیرحساب",
        "حسابی که «سرفصل» نیست ولی زیرحساب دارد. مانده‌اش هم مستقیم و هم از راهِ "
        "زیرشاخه شمرده می‌شود.",
        "error",
        rows,
        len(rows_raw),
    )


def _trial_vs_ledger(db: Session, filters: ReportFilters) -> dict:
    """همان حساب، از دو مسیرِ مستقل — و باید یک عدد بدهند.

    مسیرِ اول «گزارش ترازها» است: `get_balances` با `GROUP BY` در پایگاه‌داده جمع
    می‌زند و بازه را به دو تکه‌ی «پیش از دوره» و «داخلِ دوره» می‌شکند. مسیرِ دوم
    «مرور حساب» است: `get_general_ledger` ردیف‌ها را به ترتیبِ تاریخ می‌خواند و
    مانده را در پایتون جلو می‌برد.

    دو پیاده‌سازیِ متفاوتِ یک تعریف. تا وقتی جوابشان یکی است، هر دو گزارش قابلِ
    اتکایند؛ اولین جایی که واگرا شوند، این بررسی می‌گویدش.

    **هزینه‌اش را می‌پذیریم:** به‌ازای هر حسابِ دارای گردش یک بار دفتر خوانده
    می‌شود. این گزارش تشخیصی است و با دستِ کاربر اجرا می‌شود، نه در بارگذاریِ
    صفحه؛ و مقایسه‌ای که خودش را دوباره پیاده کند، چیزی را که باید بسنجد نمی‌سنجد.
    """
    rows = []
    balances = get_balances(db, filters.date_from, filters.date_to, filters)
    for entry in balances:
        ledger = get_general_ledger(
            db, entry["account_id"], filters.date_from, filters.date_to, filters
        )
        diff = Decimal(entry["balance"]) - Decimal(ledger["closing_balance"])
        if diff == 0:
            continue
        rows.append(
            _row(
                f"{entry['account_code']} — {entry['account_name']}",
                f"تراز {entry['balance']}، دفتر {ledger['closing_balance']}",
                debit=Decimal(entry["balance"]),
                credit=Decimal(ledger["closing_balance"]),
                difference=diff,
                account_id=entry["account_id"],
            )
        )
    return _check(
        "trial_vs_ledger",
        "اختلافِ تراز و دفتر",
        "مانده‌ی حساب از «گزارش ترازها» با مانده‌ی همان حساب در «مرور حساب» یکی "
        "نیست. این دو با دو محاسبه‌ی مستقل به‌دست می‌آیند و باید همیشه بخوانند.",
        "error",
        rows,
        len(rows),
    )


def run_integrity_check(db: Session, filters: ReportFilters | None = None) -> dict:
    """همه‌ی بررسی‌ها، با جمعِ کلِ دفتر به‌عنوانِ سرخطِ گزارش.

    `total_debit` و `total_credit` جدا از بررسی‌ها و با یک کوئریِ ساده گرفته
    می‌شوند: این تنها عددی است که حسابدار در یک نگاه می‌خواهد، و مستقل بودنش از
    بقیه‌ی محاسبات خودش یک سنجه است.
    """
    filters = filters or ReportFilters()

    total_debit, total_credit = (
        _filtered_lines(db, filters)
        .with_entities(
            func.coalesce(func.sum(JournalLine.debit), 0),
            func.coalesce(func.sum(JournalLine.credit), 0),
        )
        .one()
    )
    total_debit, total_credit = Decimal(total_debit), Decimal(total_credit)

    checks = [
        _unbalanced_entries(db, filters),
        _lines_on_group_accounts(db, filters),
        _leaves_with_children(db),
        _trial_vs_ledger(db, filters),
        _empty_entries(db, filters),
    ]
    return {
        "date_from": filters.date_from,
        "date_to": filters.date_to,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "difference": total_debit - total_credit,
        #: «سالم» یعنی هیچ بررسیِ *خطا*یی ردیف ندارد. هشدار سلامتِ دفتر را زیر
        #: سؤال نمی‌برد، پس نتیجه را قرمز نمی‌کند — ولی دیده می‌شود.
        "ok": all(c["ok"] for c in checks if c["severity"] == "error") and total_debit == total_credit,
        "checks": checks,
    }
