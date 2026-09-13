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
from app.models.inventory import Item, Warehouse
from app.services import chart_codes as cc
from app.services import valuation
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
    item_id: UUID | None = None,
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
        "item_id": item_id,
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


def _over_allocated_settlements(db: Session) -> dict:
    """تخصیص‌هایی که از مانده‌ی سندشان بیشترند (§۳۹ §۴۰).

    یعنی سندِ منبع **بعد از** تسویه کوچک یا باطل شده. چون تسویه سندِ حسابداری
    نمی‌زند، هیچ ترازی از این خرابی خبر نمی‌دهد و تنها جایی که دیده می‌شود همین
    بررسی است.

    فیلترِ تاریخ نمی‌گیرد — تخصیصِ نامعتبر مالِ یک دوره نیست؛ تا وقتی اصلاح نشود
    هست. همان استدلالِ `_leaves_with_children`.
    """
    from app.services.open_items import over_allocated

    rows = over_allocated(db)
    return _check(
        "over_allocated",
        "تخصیصِ بیش از مانده در تسویه",
        "این سندها بعد از تسویه تغییر کرده‌اند و تخصیصشان از مبلغشان بیشتر شده. "
        "تسویه‌ی مربوط را برگردانید و با مبلغِ درست دوباره ثبت کنید.",
        "error",
        [
            _row(
                f"{row['label']}",
                f"تخصیص‌یافته {row['allocated']:,} در برابرِ مانده‌ی {row['eligible']:,}",
                difference=row["excess"],
            )
            for row in rows
        ],
        len(rows),
    )


def _unsettleable_balance(db: Session) -> dict:
    """گردشِ معینِ طرف مقابل که هیچ سندِ قابلِ تسویه‌ای پشتش نیست.

    خطا نیست — دفتر سالم است و جمع‌ها می‌خوانند. ولی این بخش از ماندهٔ مشتری در
    «اقلامِ باز» دیده نمی‌شود و قابلِ تسویه هم نیست، پس کاربر باید بداند چقدر
    است و از کجا آمده: سندِ دستی روی دریافتنی/پرداختنی، ماندهٔ اول دوره، یا چکی
    که پیش از مهاجرتِ ۰۱۱۰ ثبت شده و رویدادی ندارد.
    """
    from app.services.open_items import counterparty_accounts, unattributed

    rows = []
    for account in counterparty_accounts(db):
        residual = unattributed(db, account.id)
        if residual != 0:
            rows.append(
                _row(
                    f"{account.code} — {account.name}",
                    "این مبلغ در دفتر هست ولی سندِ قابلِ تسویه‌ای ندارد "
                    "(سندِ دستی، ماندهٔ اول دوره، یا چکِ پیش از نسخه‌ی ۰۱۱۴)",
                    difference=residual,
                    account_id=account.id,
                )
            )
    return _check(
        "unsettleable_balance",
        "گردشِ بدونِ سندِ قابلِ تسویه",
        "بخشی از ماندهٔ این معین‌ها در «تسویه حساب طرف مقابل» دیده نمی‌شود. "
        "دفتر درست است؛ فقط این گردش‌ها لنگرِ سندی ندارند تا تخصیص بخورند.",
        "warning",
        rows,
        len(rows),
    )


#: پسوندِ توضیحِ بررسی‌های انبار وقتی دامنه باریک شده — تا «چیزی پیدا نکرد» با «اجرا نشد» یکی خوانده نشود.
_NARROWED = " (با فیلترِ شماره‌ی سند، وضعیت، منشأ، بُعد یا بدونِ اسنادِ سیستمی اجرا نمی‌شود.)"


def _ledger_wide(filters: ReportFilters) -> bool:
    """بررسی‌های انبار فقط روی کلِ دفتر معنا دارند.

    ارزشِ موجودی شماره‌ی سند، مرکز هزینه یا تفصیلی ندارد: با فیلترِ «سند ۱۲ تا ۱۲»
    مانده‌ی معینِ موجودی از یک سند می‌آمد و ارزشِ انبار از همه‌ی حرکات، و اختلافی
    ساخته می‌شد که هیچ معنایی ندارد. بازه‌ی تاریخ اما معنا دارد (ارزش تا پایانِ بازه).
    """
    return (
        filters.entry_from is None
        and filters.entry_to is None
        and filters.status is None
        and not filters.source_type
        and filters.cost_center_id is None
        and filters.analytic_id is None
        and filters.include_system_entries
    )


def _inventory_vs_ledger(db: Session, filters: ReportFilters) -> dict:
    """ارزشِ انبار در برابرِ مانده‌ی معینِ موجودی — یک عدد از دو دفترِ مستقل.

    مسیرِ اول دفترِ حسابداری است: مانده‌ی هر معینی که موجودیِ کالا رویش می‌نشیند
    (نقشِ «موجودی کالا» و هر معینی که به انباری نگاشت شده). مسیرِ دوم دفترِ موجودی
    است: ارزشِ کالای انبارهای همان معین، از بازپخشِ `valuation`. تا امروز گزارشِ
    ارزشِ موجودی در مستنداتش می‌گفت «باید با ماندهٔ حساب بخواند» و هیچ‌جا سنجیده
    نمی‌شد.

    اختلاف دو جزء دارد و جزئیات هر دو را جدا می‌گوید: **ارزش‌گذاریِ منقضی** (بهایی که
    اسناد نوشته‌اند با بازپخشِ زمانی نمی‌خواند) و **بقیه** — سندِ دستی روی معینِ
    موجودی، سندی بی‌حرکتِ انبار یا حرکتی بی‌سند.

    **هشدار است نه خطا:** دفتر متوازن است و گزارش‌های مالی با خودشان می‌خوانند؛ دو
    دفتر فقط از هم فاصله گرفته‌اند. فقط `date_to` را می‌گیرد — ارزشِ موجودی بُعدِ
    مرکز هزینه یا تفصیلی ندارد که فیلترهای دیگر رویش معنا داشته باشند.
    """
    from app.services.printing import fa_number

    key, title = "inventory_vs_ledger", "ارزشِ انبار در برابرِ دفتر"
    description = (
        "مانده‌ی معینِ موجودی با ارزشِ کالای انبارهایی که به آن نگاشت شده‌اند یکی نیست. "
        "«بدهکار» مانده‌ی دفتر است و «بستانکار» ارزشِ انبار."
    )
    if not _ledger_wide(filters):
        return _check(key, title, description + _NARROWED, "warning", [], 0)

    positions = valuation.positions(db, date_to=filters.date_to)
    by_warehouse: dict[UUID, list[Decimal]] = {}
    for position in positions.values():
        for warehouse_id, (_qty, value, book) in position.by_warehouse.items():
            slot = by_warehouse.setdefault(warehouse_id, [Decimal(0), Decimal(0)])
            slot[0] += value
            slot[1] += book

    mapping = dict(db.query(Warehouse.id, Warehouse.gl_account_id).all())
    default = db.query(Account.id).filter(Account.system_role == cc.INVENTORY).first()
    default_id = default[0] if default is not None else None

    per_account: dict[UUID, list[Decimal]] = {}
    for warehouse_id, (value, book) in by_warehouse.items():
        account_id = mapping.get(warehouse_id) or default_id
        if account_id is None:
            continue
        slot = per_account.setdefault(account_id, [Decimal(0), Decimal(0)])
        slot[0] += value
        slot[1] += book

    account_ids = set(per_account) | {gl for gl in mapping.values() if gl is not None}
    if default_id is not None:
        account_ids.add(default_id)

    rows = []
    if account_ids:
        ledger_query = (
            db.query(
                JournalLine.account_id,
                func.coalesce(func.sum(JournalLine.debit), 0) - func.coalesce(func.sum(JournalLine.credit), 0),
            )
            .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
            .filter(JournalLine.account_id.in_(account_ids))
        )
        if filters.date_to is not None:
            ledger_query = ledger_query.filter(JournalEntry.entry_date <= filters.date_to)
        ledger = {account_id: Decimal(balance) for account_id, balance in ledger_query.group_by(JournalLine.account_id).all()}

        for account in db.query(Account).filter(Account.id.in_(account_ids)).order_by(Account.code).all():
            balance = valuation.rial(ledger.get(account.id, Decimal(0)))
            value, book = (valuation.rial(amount) for amount in per_account.get(account.id, (Decimal(0), Decimal(0))))
            difference = balance - value
            if difference == 0:
                continue
            parts = []
            if book != value:
                parts.append(f"{fa_number(book - value)} از ارزش‌گذاریِ منقضی")
            if balance != book:
                parts.append(f"{fa_number(balance - book)} از سندِ بی‌حرکت یا حرکتِ بی‌سند روی این معین")
            rows.append(
                _row(
                    f"{account.code} — {account.name}",
                    f"مانده‌ی دفتر {fa_number(balance)}، ارزشِ انبار {fa_number(value)}"
                    + (" — " + "؛ ".join(parts) if parts else ""),
                    debit=balance,
                    credit=value,
                    difference=difference,
                    account_id=account.id,
                )
            )
    return _check(key, title, description, "warning", rows, len(rows))


def _stale_valuation(db: Session, filters: ReportFilters) -> dict:
    """کالاهایی که بهای ثبت‌شده‌ی حرکاتشان با بازپخشِ دفتر به ترتیبِ تاریخ نمی‌خواند.

    «منقضی» ذخیره نمی‌شود؛ هر بار از دفتر مشتق می‌شود (`valuation.stale_items`)، پس
    دفترِ پیش از این نسخه را هم می‌بیند و با اصلاحِ ارزش‌گذاری خودش پاک می‌شود. علت
    هم از دفتر می‌آید: سندی که بعداً با تاریخِ گذشته ثبت شده، یا ابطالی که سندِ
    پیش از آن حرکت را برداشته.
    """
    from app.services.printing import fa_number, format_jalali

    key, title = "stale_valuation", "ارزش‌گذاریِ منقضی"
    description = (
        "حرکتی که با میانگین ارزش‌گذاری شده و بهای ثبت‌شده‌اش با میانگینِ همان تاریخ نمی‌خواند — "
        "معمولاً چون سندی بعداً با تاریخِ گذشته ثبت یا باطل شده. سندِ حسابداریِ آن حرکات هنوز "
        "بهای کهنه را دارد؛ «اختلاف» اثرش بر ارزشِ موجودی است."
    )
    if not _ledger_wide(filters):
        return _check(key, title, description + _NARROWED, "warning", [], 0)

    found = valuation.stale_items(db, until=filters.date_to)
    items = (
        {item.id: item for item in db.query(Item).filter(Item.id.in_([entry["item_id"] for entry in found])).all()}
        if found
        else {}
    )
    numbers = valuation.document_numbers(
        db, [(source_type, source_id) for entry in found for _kind, source_type, source_id in entry["causes"]]
    )
    rows = []
    for entry in found:
        item = items.get(entry["item_id"])
        causes = []
        for kind, source_type, source_id in entry["causes"][:3]:
            label = valuation.document_label(source_type, numbers.get((source_type, source_id)))
            causes.append(f"ابطالِ {label}" if kind == "void" else f"{label} با تاریخِ گذشته")
        if len(entry["causes"]) > 3:
            causes.append(f"و {fa_number(len(entry['causes']) - 3)} سندِ دیگر")
        why = (
            "، ".join(causes)
            if causes
            else "بهای ثبت‌شده از همان روزِ ثبت با میانگینِ آن تاریخ نمی‌خوانده "
            "(دفترِ پیش از ترتیبِ تاریخی، یا انبارگردانی با بهای روزِ بازکردنِ جلسه)"
        )
        rows.append(
            _row(
                f"{item.sku} — {item.name}" if item is not None else str(entry["item_id"]),
                f"از {format_jalali(entry['from_date'])}، {fa_number(entry['count'])} حرکت با بهای کهنه — علت: {why}",
                difference=valuation.rial(entry["difference"]),
                item_id=entry["item_id"],
            )
        )
    return _check(key, title, description, "warning", rows, len(rows))


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
        _over_allocated_settlements(db),
        _unsettleable_balance(db),
        _inventory_vs_ledger(db, filters),
        _stale_valuation(db, filters),
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
