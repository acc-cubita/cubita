"""فیلترهای مشترکِ گزارش‌ها — و قیدی که همه‌شان را به هم می‌دوزد.

تحلیل §۲۶ می‌گوید اگر تراز بگوید «بانک ۹۵ میلیون»، مرور حساب و دفتر هم باید همان
را بگویند؛ هر اختلافی اشکالِ جدیِ حسابداری است. کوبیتا از قبل یک هسته داشت
(`get_balances`) ولی آن هسته **فقط تاریخ می‌فهمید** — محدوده‌ی شماره‌ی سند،
موقت/دائم، منشأ، مرکز هزینه و تفصیلی در هیچ گزارشی نبودند، با آن‌که فهرستِ اسناد
همه‌شان را داشت.

خطرِ افزودنِ فیلتر به دو موتور این است که از هم جدا بیفتند. برای همین `ReportFilters`
یکی است و هر دو از `apply_report_filters` می‌گذرند — و مهم‌ترین تستِ این فایل همان
تطبیقِ تراز و دفتر است، نه تکِ فیلترها.

**قیدِ دوم:** پیش‌فرضِ هر فیلترِ تازه «چیزی عوض نمی‌شود» است.

**چرا حسابِ اختصاصی و نه `cc.CASH`:** فیکسچرِ `db` برمی‌گردد، ولی تست‌هایی که از
`client` استفاده می‌کنند در همان مستأجر **کامیت** می‌کنند. پس مانده‌ی مطلقِ یک حسابِ
مشترک به ترتیبِ اجرا وابسته می‌شود — تنها در اجرای کاملِ مجموعه، نه به‌تنهایی. هر تست
حسابِ خودش را می‌سازد تا عددهایش مالِ خودش باشند.
"""
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

import itertools

from app.models.accounting import Account, JournalLine
from app.models.analytic import AnalyticAccount
from app.models.cost_center import CostCenter
from app.services import accounting_ops as ops
from app.services import chart_codes as cc
from app.services import reports
from app.services.common import get_account, make_journal_entry
from app.services.reports import ReportFilters, get_general_ledger

EARLY = date(2026, 1, 10)
MID = date(2026, 3, 15)
LATE = date(2026, 6, 20)


_SEQ = itertools.count(1)


def _account(db, kind: str = "asset") -> Account:
    """یک حسابِ برگِ تازه زیرِ سرفصلِ صندوق — اختصاصیِ همین تست.

    کد یکتاست تا اجراهای پشتِ سرِ هم به هم نخورند.
    """
    parent = get_account(db, cc.CASH).parent_id
    row = Account(
        code=f"T{next(_SEQ):04d}",
        name=f"حسابِ آزمون {next(_SEQ)}",
        type=kind,
        is_group=False,
        parent_id=parent,
    )
    db.add(row)
    db.flush()
    return row


def _post(db, user, when, amount, *, account=None, source="manual", analytic=None, center=None,
          fx=None, tracking=None, status=None):
    """حسابِ آزمون بدهکار در برابرِ سودِ انباشته بستانکار، با هر بُعدی که تست بخواهد.

    طرفِ بستانکار عمداً حسابِ مشترک است و هرگز ادعایی رویش نمی‌شود؛ فقط سند را
    متوازن می‌کند.
    """
    target = account if account is not None else _account(db)
    revenue = get_account(db, cc.RETAINED_EARNINGS)
    line = JournalLine(
        account_id=target.id,
        analytic_id=analytic.id if analytic else None,
        cost_center_id=center.id if center else None,
        debit=Decimal(amount),
        credit=0,
    )
    if fx:
        line.currency_code, line.fx_amount, line.fx_rate = fx
    if tracking:
        line.tracking_no, line.tracking_date = tracking
    entry = make_journal_entry(
        db, when, "آزمون", source, user,
        [line, JournalLine(account_id=revenue.id, debit=0, credit=Decimal(amount))],
    )
    if status:
        entry.status = status
    db.flush()
    entry.target_account = target  # راحتیِ تست، نه ستونِ مدل
    return entry


def _analytic(db, user, code, name):
    row = AnalyticAccount(code=code, name=name, created_by_id=user.id)
    db.add(row)
    db.flush()
    return row


def _center(db, user, code, name, parent=None):
    row = CostCenter(code=code, name=name, created_by_id=user.id,
                     parent_id=parent.id if parent else None)
    db.add(row)
    db.flush()
    return row


def _row(db, account, filters=None, **kw):
    rows = ops.get_balances(db, filters=filters or ReportFilters(), **kw)
    return next((r for r in rows if r["account_id"] == account.id), None)


def _balance(db, account, filters=None) -> Decimal:
    row = _row(db, account, filters)
    return Decimal(row["balance"]) if row else Decimal(0)


# ── قیدِ اصلی: گزارش‌ها باید با هم بخوانند (§۲۶) ────────────────────────────


def test_the_trial_balance_and_the_ledger_agree(db, user):
    """**مهم‌ترین تستِ این فایل.** دو مسیرِ مستقل: تجمیعِ گروهی در برابر ردیف‌به‌ردیف."""
    acc = _account(db)
    _post(db, user, EARLY, 20_000_000, account=acc)
    _post(db, user, MID, 40_000_000, account=acc)

    balance = _balance(db, acc)
    ledger = get_general_ledger(db, acc.id)

    assert balance == Decimal(ledger["closing_balance"]) == Decimal(60_000_000)


def test_they_still_agree_under_a_filter(db, user):
    """اگر فیلتر فقط به یکی از دو موتور می‌رسید، این‌جا لو می‌رفت."""
    acc = _account(db)
    _post(db, user, EARLY, 20_000_000, account=acc)
    _post(db, user, MID, 40_000_000, account=acc, status="permanent")

    filters = ReportFilters(status="permanent")

    assert _balance(db, acc, filters) == Decimal(
        get_general_ledger(db, acc.id, None, None, filters)["closing_balance"]
    ) == Decimal(40_000_000)


def test_a_group_rollup_matches_the_sum_of_its_leaves(db, user):
    """§۲۷ «والد = جمعِ فرزندان» — تجمیعِ درختیِ دفتر در برابر جمعِ ردیف‌های تراز."""
    acc = _account(db)
    _post(db, user, MID, 15_000_000, account=acc)
    parent_id = acc.parent_id
    assert parent_id, "حسابِ آزمون باید سرفصل داشته باشد"

    leaves = reports.descendant_account_ids(db, parent_id)
    from_balances = sum(
        (Decimal(r["closing_debit"]) - Decimal(r["closing_credit"])
         for r in ops.get_balances(db) if r["account_id"] in leaves),
        Decimal(0),
    )
    from_ledger = Decimal(get_general_ledger(db, parent_id)["closing_balance"])

    assert from_balances == from_ledger


# ── پیش‌فرض‌ها هیچ‌چیز را عوض نمی‌کنند ───────────────────────────────────────


def test_empty_filters_change_nothing(db, user):
    """**رگرسیونِ کلیدی.** هر پرچمِ تازه باید خاموش شروع شود."""
    _post(db, user, EARLY, 5_000_000)
    _post(db, user, MID, 7_000_000, source="opening")

    assert ops.get_balances(db) == ops.get_balances(db, filters=ReportFilters())


def test_system_entries_are_included_by_default(db, user):
    acc = _account(db)
    _post(db, user, MID, 7_000_000, account=acc, source="opening_entry")
    assert _balance(db, acc) == Decimal(7_000_000)


# ── تک‌تکِ فیلترها ──────────────────────────────────────────────────────────


def test_the_document_number_range_filters(db, user):
    """**§۸.** موتور دیگر فقط تاریخ‌محور نیست."""
    acc = _account(db)
    first = _post(db, user, EARLY, 10_000_000, account=acc)
    second = _post(db, user, MID, 25_000_000, account=acc)
    assert second.number > first.number

    assert _balance(db, acc, ReportFilters(entry_from=second.number)) == Decimal(25_000_000)
    assert _balance(db, acc, ReportFilters(entry_to=first.number)) == Decimal(10_000_000)


def test_the_status_filter_separates_temporary_from_permanent(db, user):
    """**§۳۰.** سندِ موقت نباید بی‌دلیل با سندِ رسمی یکی گرفته شود."""
    acc = _account(db)
    _post(db, user, EARLY, 3_000_000, account=acc)  # موقت
    _post(db, user, MID, 8_000_000, account=acc, status="permanent")

    assert _balance(db, acc, ReportFilters(status="permanent")) == Decimal(8_000_000)
    assert _balance(db, acc, ReportFilters(status="temporary")) == Decimal(3_000_000)


def test_the_source_filter_works(db, user):
    """**§۳۱.** مغایرت‌گیری بر اساسِ منشأ."""
    acc = _account(db)
    _post(db, user, EARLY, 4_000_000, account=acc)
    _post(db, user, MID, 9_000_000, account=acc, source="fx_revaluation")

    assert _balance(db, acc, ReportFilters(source_type="fx_revaluation")) == Decimal(9_000_000)


def test_excluding_system_entries_drops_exactly_them(db, user):
    """**§۹.** حسابدار می‌خواهد گردشِ عملیاتی را بدونِ افتتاحیه ببیند.

    «دقیقاً به‌اندازه‌ی سندِ سیستمی» — نه بیشتر و نه کمتر.
    """
    acc = _account(db)
    _post(db, user, EARLY, 12_000_000, account=acc, source="opening_entry")
    _post(db, user, MID, 30_000_000, account=acc)

    assert _balance(db, acc) == Decimal(42_000_000)
    assert _balance(db, acc, ReportFilters(include_system_entries=False)) == Decimal(30_000_000)


def test_a_manual_entry_survives_the_system_exclusion(db, user):
    """**رگرسیونِ معکوس:** صافی نباید سندِ عادی را هم بیندازد."""
    acc = _account(db)
    _post(db, user, MID, 6_000_000, account=acc)
    assert _balance(db, acc, ReportFilters(include_system_entries=False)) == Decimal(6_000_000)


def test_the_analytic_filter_works(db, user):
    """**§۲۹.**"""
    acc = _account(db)
    alpha = _analytic(db, user, "A1", "شرکت آلفا")
    _post(db, user, EARLY, 5_000_000, account=acc, analytic=alpha)
    _post(db, user, MID, 11_000_000, account=acc)

    assert _balance(db, acc, ReportFilters(analytic_id=alpha.id)) == Decimal(5_000_000)


def test_the_cost_center_filter_rolls_up_children(db, user):
    """**§۳۲.** گزارشِ «شعبه تهران» باید پروژه‌های زیرش را هم بیاورد."""
    acc = _account(db)
    branch = _center(db, user, "C1", "شعبه تهران")
    project = _center(db, user, "C2", "پروژه الف", parent=branch)
    _post(db, user, EARLY, 7_000_000, account=acc, center=branch)
    _post(db, user, MID, 13_000_000, account=acc, center=project)
    _post(db, user, LATE, 2_000_000, account=acc)  # بدونِ مرکز

    assert _balance(db, acc, ReportFilters(cost_center_id=branch.id)) == Decimal(20_000_000)
    assert _balance(db, acc, ReportFilters(cost_center_id=project.id)) == Decimal(13_000_000)


# ── بی‌گردش در برابر مانده‌ی صفر (§۱۸) ──────────────────────────────────────


def test_an_account_with_no_activity_is_absent_by_default(db, user):
    _post(db, user, MID, 1_000_000)
    idle = _account(db)  # ساخته می‌شود ولی هیچ سندی نمی‌خورد
    codes = {r["account_code"] for r in ops.get_balances(db)}
    assert idle.code not in codes


def test_zero_activity_accounts_can_be_included_and_are_marked(db, user):
    """**قیدِ §۱۸.** «بی‌گردش» و «گردشِ صفر» از نظر حسابداری یکی نیستند."""
    acc = _account(db)
    _post(db, user, MID, 9_000_000, account=acc)
    idle = _account(db)

    rows = {r["account_id"]: r for r in ops.get_balances(db, include_zero_activity=True)}

    assert rows[idle.id]["has_activity"] is False
    assert Decimal(rows[idle.id]["closing_debit"]) == 0
    assert rows[acc.id]["has_activity"] is True


def test_an_account_that_nets_to_zero_still_counts_as_active(db, user):
    """حسابی که صد میلیون بدهکار و صد میلیون بستانکار خورده، فعالیت داشته."""
    acc = _account(db)
    equity = get_account(db, cc.RETAINED_EARNINGS)
    make_journal_entry(db, MID, "رفت", "manual", user, [
        JournalLine(account_id=acc.id, debit=Decimal(5_000_000), credit=0),
        JournalLine(account_id=equity.id, debit=0, credit=Decimal(5_000_000)),
    ])
    make_journal_entry(db, LATE, "برگشت", "manual", user, [
        JournalLine(account_id=equity.id, debit=Decimal(5_000_000), credit=0),
        JournalLine(account_id=acc.id, debit=0, credit=Decimal(5_000_000)),
    ])

    row = _row(db, acc)
    assert row is not None and row["has_activity"] is True
    assert Decimal(row["closing_debit"]) == Decimal(row["closing_credit"]) == 0
    assert Decimal(row["period_debit"]) == Decimal(5_000_000), "گردش باید دیده شود"


# ── دفتر: ارز، پیگیری، تفصیلی (§۱۲ §۱۳ §۲۰ §۲۱) ────────────────────────────


def test_the_ledger_returns_currency_and_tracking(db, user):
    """هر دو از قبل روی ردیفِ سند بودند و هیچ گزارشی نشانشان نمی‌داد."""
    acc = _account(db)
    _post(db, user, MID, 8_400_000, account=acc,
          fx=("USD", Decimal(100), Decimal(84_000)),
          tracking=("HAV-125", date(2026, 3, 1)))

    line = get_general_ledger(db, acc.id)["lines"][0]

    assert line["currency_code"] == "USD"
    assert Decimal(line["fx_amount"]) == Decimal(100)
    assert line["tracking_no"] == "HAV-125"
    assert line["tracking_date"] == date(2026, 3, 1)


def test_the_ledger_totals_foreign_currency_per_currency(db, user):
    """**§۱۲.** دلار و یورو با هم جمع نمی‌شوند."""
    acc = _account(db)
    _post(db, user, EARLY, 8_400_000, account=acc, fx=("USD", Decimal(100), Decimal(84_000)))
    _post(db, user, MID, 4_200_000, account=acc, fx=("USD", Decimal(50), Decimal(84_000)))
    _post(db, user, LATE, 9_000_000, account=acc, fx=("EUR", Decimal(90), Decimal(100_000)))

    totals = {t["currency_code"]: Decimal(t["amount"])
              for t in get_general_ledger(db, acc.id)["fx_totals"]}

    assert totals == {"USD": Decimal(150), "EUR": Decimal(90)}


def test_the_analytic_ledger_needs_no_account(db, user):
    """**§۲۰ دفترِ تفصیلی.** گردشِ یک تفصیلی در همه‌ی حساب‌ها."""
    acc = _account(db)
    alpha = _analytic(db, user, "A1", "شرکت آلفا")
    _post(db, user, EARLY, 6_000_000, account=acc, analytic=alpha)
    _post(db, user, MID, 20_000_000, account=acc)  # بی‌تفصیلی — نباید بیاید

    ledger = get_general_ledger(db, None, None, None, ReportFilters(analytic_id=alpha.id))

    assert ledger["account_id"] is None
    assert len(ledger["lines"]) == 1
    assert Decimal(ledger["closing_balance"]) == Decimal(6_000_000)


def test_a_ledger_with_neither_account_nor_analytic_is_rejected(db, user):
    with pytest.raises(HTTPException) as err:
        get_general_ledger(db, None)
    assert err.value.status_code == 400


def test_the_running_balance_stays_correct_under_a_filter(db, user):
    """**§۲۲ §۲۳.** مانده‌ی در حال اجرا مشتق است؛ با فیلتر هم باید درست بماند."""
    acc = _account(db)
    _post(db, user, EARLY, 10_000_000, account=acc, source="opening_entry")
    _post(db, user, MID, 30_000_000, account=acc)
    _post(db, user, LATE, 5_000_000, account=acc)

    ledger = get_general_ledger(db, acc.id, None, None,
                                ReportFilters(include_system_entries=False))
    balances = [Decimal(line["balance"]) for line in ledger["lines"]]

    assert balances == [Decimal(30_000_000), Decimal(35_000_000)]
    assert Decimal(ledger["closing_balance"]) == Decimal(35_000_000)


def test_the_ledger_carries_status_and_origin_per_line(db, user):
    """§۱۰ — بدونِ بازکردنِ سند معلوم باشد این گردش موقت است یا دائم و از کجا آمد."""
    acc = _account(db)
    _post(db, user, MID, 3_000_000, account=acc, source="fx_revaluation", status="permanent")

    line = get_general_ledger(db, acc.id)["lines"][0]
    assert line["entry_status"] == "permanent"
    assert line["source_type"] == "fx_revaluation"
    assert line["line_id"] is not None
