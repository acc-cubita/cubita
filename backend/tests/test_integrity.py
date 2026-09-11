"""بررسیِ یکپارچگیِ دفتر — §۲۷.

**قیدِ اصلی:** بررسی باید چیزی را پیدا کند که هیچ گاردِ دیگری نمی‌بیند. برای همین
هر تستِ این فایل اول ثابت می‌کند که اشکال واقعاً بی‌صداست (تراز و دفتر با هم
نمی‌خوانند، یا مبلغی از تراز غیب می‌شود) و بعد که بررسی می‌بیندش.

**انزوا با شماره‌ی سند، نه تاریخ.** این گزارش دامنه‌ی حساب ندارد — کلِ مستأجر را
می‌سنجد. چون تست‌های `client` در همان مستأجر کامیت می‌کنند، شمارشِ مطلق فقط در
اجرای تنها درست می‌ماند. پس هر تست بازه‌ی `entry_from/entry_to` خودش را می‌گذارد و
فقط اسنادِ خودش را می‌بیند.
"""
import itertools
from datetime import date
from decimal import Decimal

from app.models.accounting import Account, JournalEntry, JournalLine
from app.models.analytic import AnalyticAccount
from app.services import accounting_ops as ops
from app.services import chart_codes as cc
from app.services.common import get_account, make_journal_entry, next_journal_number, number_lines
from app.services.integrity import ROW_LIMIT, run_integrity_check
from app.services.reports import ReportFilters, get_general_ledger

WHEN = date(2026, 4, 12)

_SEQ = itertools.count(1)


def _account(db, kind: str = "asset", *, is_group: bool = False, parent=None) -> Account:
    """حسابِ تازه‌ی اختصاصیِ همین تست، با کدِ یکتا."""
    row = Account(
        code=f"G{next(_SEQ):04d}",
        name=f"حسابِ آزمون {next(_SEQ)}",
        type=kind,
        is_group=is_group,
        parent_id=parent.id if parent is not None else get_account(db, cc.CASH).parent_id,
    )
    db.add(row)
    db.flush()
    return row


def _balanced(db, user, amount, *, account=None, analytic=None, source="manual"):
    target = account if account is not None else _account(db)
    other = get_account(db, cc.RETAINED_EARNINGS)
    return make_journal_entry(
        db, WHEN, "آزمون", source, user,
        [
            JournalLine(
                account_id=target.id,
                analytic_id=analytic.id if analytic else None,
                debit=Decimal(amount),
                credit=0,
            ),
            JournalLine(account_id=other.id, debit=0, credit=Decimal(amount)),
        ],
    )


def _raw_entry(db, user, lines, *, source="manual") -> JournalEntry:
    """سند را بدونِ گذشتن از هیچ اعتبارسنجی می‌سازد.

    عمداً `make_journal_entry` صدا زده نمی‌شود: نکته‌ی همین گزارش این است که
    سرویس‌ها ردیف را مستقیم می‌سازند و از اعتبارسنجِ توازنِ `schemas` رد نمی‌شوند.
    """
    entry = JournalEntry(
        number=next_journal_number(db),
        entry_date=WHEN,
        description="آزمون",
        source_type=source,
        created_by_id=user.id,
        lines=number_lines(lines),
    )
    db.add(entry)
    db.flush()
    return entry


def _scope(*entries) -> ReportFilters:
    numbers = [e.number for e in entries]
    return ReportFilters(entry_from=min(numbers), entry_to=max(numbers))


def _check(report, key) -> dict:
    return next(c for c in report["checks"] if c["key"] == key)


# ── دفترِ سالم ────────────────────────────────────────────────────────────────


def test_healthy_books_pass_every_check(db, user):
    entry = _balanced(db, user, 500_000)
    report = run_integrity_check(db, _scope(entry))

    assert report["ok"] is True
    assert report["total_debit"] == report["total_credit"] == Decimal(500_000)
    assert report["difference"] == 0
    assert all(c["ok"] for c in report["checks"]), [c["key"] for c in report["checks"] if not c["ok"]]


def test_default_chart_is_structurally_sound(db, user):
    """چارتِ پیش‌فرض نباید حسابِ سطحِ آخرِ دارای زیرحساب داشته باشد.

    این بررسی به فیلتر کاری ندارد، پس همیشه کلِ چارت را می‌سنجد — و همین یعنی
    اگر روزی قالبِ چارت خراب ساخته شود، این تست می‌گویدش.
    """
    get_account(db, cc.CASH)  # چارت را lazy می‌سازد
    report = run_integrity_check(db, ReportFilters(entry_from=0, entry_to=0))
    assert _check(report, "leaf_with_children")["ok"] is True


# ── سندِ نامتوازن ─────────────────────────────────────────────────────────────


def test_unbalanced_entry_is_found(db, user):
    target, other = _account(db), get_account(db, cc.RETAINED_EARNINGS)
    entry = _raw_entry(db, user, [
        JournalLine(account_id=target.id, debit=Decimal(700), credit=0),
        JournalLine(account_id=other.id, debit=0, credit=Decimal(400)),
    ])

    report = run_integrity_check(db, _scope(entry))
    check = _check(report, "unbalanced_entries")

    assert check["ok"] is False
    assert check["severity"] == "error"
    assert [r["entry_id"] for r in check["rows"]] == [entry.id]
    assert check["rows"][0]["difference"] == Decimal(300)
    assert report["ok"] is False


def test_unbalanced_entry_moves_the_headline_totals(db, user):
    """سرخطِ گزارش هم باید بگوید دفتر ناتراز است، مستقل از بررسیِ سندبه‌سند."""
    target, other = _account(db), get_account(db, cc.RETAINED_EARNINGS)
    entry = _raw_entry(db, user, [
        JournalLine(account_id=target.id, debit=Decimal(700), credit=0),
        JournalLine(account_id=other.id, debit=0, credit=Decimal(400)),
    ])

    report = run_integrity_check(db, _scope(entry))
    assert report["total_debit"] == Decimal(700)
    assert report["total_credit"] == Decimal(400)
    assert report["difference"] == Decimal(300)


def test_balanced_entry_outside_the_scope_is_not_reported(db, user):
    """فیلتر واقعاً محدود می‌کند — سندِ خرابِ بیرونِ بازه نباید بیاید."""
    target, other = _account(db), get_account(db, cc.RETAINED_EARNINGS)
    bad = _raw_entry(db, user, [
        JournalLine(account_id=target.id, debit=Decimal(700), credit=0),
        JournalLine(account_id=other.id, debit=0, credit=Decimal(400)),
    ])
    good = _balanced(db, user, 100)

    report = run_integrity_check(db, _scope(good))
    assert _check(report, "unbalanced_entries")["ok"] is True
    assert bad.number < good.number


# ── سند روی سرفصل ────────────────────────────────────────────────────────────


def test_line_on_group_account_vanishes_from_the_trial_balance(db, user):
    """اول ثابت کن اشکال بی‌صداست، بعد که بررسی می‌بیندش.

    این مهم‌ترین تستِ فایل است: مبلغی که روی سرفصل بنشیند از تراز حذف می‌شود
    (چون تراز فقط `is_group = False` را می‌آورد) در حالی که خودِ دفتر متوازن
    است. یعنی جمعِ ستون‌های تراز با هم نمی‌خوانند و تا امروز هیچ‌جا نمی‌گفت چرا.
    """
    group = _account(db, is_group=True)
    other = get_account(db, cc.RETAINED_EARNINGS)
    entry = _raw_entry(db, user, [
        JournalLine(account_id=group.id, debit=Decimal(900), credit=0),
        JournalLine(account_id=other.id, debit=0, credit=Decimal(900)),
    ])
    filters = _scope(entry)

    balances = ops.get_balances(db, filters=filters)
    assert group.id not in {r["account_id"] for r in balances}
    debit = sum((r["closing_debit"] for r in balances), Decimal(0))
    credit = sum((r["closing_credit"] for r in balances), Decimal(0))
    assert debit != credit  # ← تراز ناتراز است، و دفتر سالم

    report = run_integrity_check(db, filters)
    check = _check(report, "group_account_lines")
    assert check["ok"] is False
    assert [r["account_id"] for r in check["rows"]] == [group.id]
    assert check["rows"][0]["debit"] == Decimal(900)
    assert report["ok"] is False


def test_group_account_lines_do_not_break_the_ledger(db, user):
    """دفترِ خودِ سرفصل مبلغ را دارد — پس واقعاً فقط تراز است که آن را نمی‌بیند."""
    group = _account(db, is_group=True)
    other = get_account(db, cc.RETAINED_EARNINGS)
    entry = _raw_entry(db, user, [
        JournalLine(account_id=group.id, debit=Decimal(900), credit=0),
        JournalLine(account_id=other.id, debit=0, credit=Decimal(900)),
    ])

    ledger = get_general_ledger(db, group.id, None, None, _scope(entry))
    assert ledger["closing_balance"] == Decimal(900)


# ── حسابِ سطحِ آخر با زیرحساب ─────────────────────────────────────────────────


def test_leaf_with_children_is_found(db, user):
    parent = _account(db)  # is_group = False
    _account(db, parent=parent)
    _account(db, parent=parent)

    report = run_integrity_check(db, ReportFilters(entry_from=0, entry_to=0))
    check = _check(report, "leaf_with_children")

    assert check["ok"] is False
    assert parent.id in {r["account_id"] for r in check["rows"]}
    assert "۲" in check["rows"][0]["detail"] or "2" in check["rows"][0]["detail"]


def test_leaf_with_children_ignores_the_date_filter(db, user):
    """اشکالِ ساختاری است نه دوره‌ای — بازه نباید پنهانش کند."""
    parent = _account(db)
    _account(db, parent=parent)

    narrow = run_integrity_check(db, ReportFilters(date_from=WHEN, date_to=WHEN))
    assert parent.id in {r["account_id"] for r in _check(narrow, "leaf_with_children")["rows"]}


def test_group_account_with_children_is_correct(db, user):
    """سرفصلی که زیرحساب دارد سالم است — این حالتِ *درست* است."""
    parent = _account(db, is_group=True)
    _account(db, parent=parent)

    report = run_integrity_check(db, ReportFilters(entry_from=0, entry_to=0))
    assert parent.id not in {r["account_id"] for r in _check(report, "leaf_with_children")["rows"]}


# ── سندِ بی‌ردیف ─────────────────────────────────────────────────────────────


def test_empty_entry_is_a_warning_not_an_error(db, user):
    """صفر با صفر متوازن است، پس بررسیِ توازن نمی‌بیندش — ولی سلامتِ دفتر هم
    زیر سؤال نیست، چون هیچ مبلغی جابه‌جا نشده."""
    entry = _raw_entry(db, user, [])
    report = run_integrity_check(db, _scope(entry))

    check = _check(report, "empty_entries")
    assert check["severity"] == "warning"
    assert [r["entry_id"] for r in check["rows"]] == [entry.id]
    assert _check(report, "unbalanced_entries")["ok"] is True
    assert report["ok"] is True  # ← هشدار نتیجه را قرمز نمی‌کند


# ── تراز در برابرِ دفتر ───────────────────────────────────────────────────────


def test_trial_and_ledger_agree_on_healthy_data(db, user):
    for amount in (100, 250, 375):
        last = _balanced(db, user, amount)
    first = last.number - 2
    report = run_integrity_check(db, ReportFilters(entry_from=first, entry_to=last.number))
    assert _check(report, "trial_vs_ledger")["ok"] is True


def test_trial_and_ledger_agree_under_a_dimension_filter(db, user):
    """قیدِ §۲۶ زیرِ فیلتر هم برقرار است — همان چیزی که دو مسیر را به هم می‌دوزد."""
    analytic = AnalyticAccount(code=f"A{next(_SEQ):04d}", name="آزمون", created_by_id=user.id)
    db.add(analytic)
    db.flush()
    tagged = _balanced(db, user, 400, analytic=analytic)
    plain = _balanced(db, user, 900)

    filters = ReportFilters(
        entry_from=min(tagged.number, plain.number),
        entry_to=max(tagged.number, plain.number),
        analytic_id=analytic.id,
    )
    report = run_integrity_check(db, filters)
    assert _check(report, "trial_vs_ledger")["ok"] is True
    assert report["total_debit"] == Decimal(400)  # فیلتر واقعاً اعمال شده


def test_trial_and_ledger_agree_across_a_period_split(db, user):
    """`get_balances` بازه را به «پیش از دوره» و «داخلِ دوره» می‌شکند و دفتر
    نمی‌شکند؛ خطای مرزِ روز دقیقاً همین‌جا خودش را نشان می‌دهد."""
    account = _account(db)
    before = _balanced(db, user, 300, account=account)
    inside = _balanced(db, user, 700, account=account)

    filters = ReportFilters(
        date_from=WHEN,
        date_to=WHEN,
        entry_from=before.number,
        entry_to=inside.number,
    )
    report = run_integrity_check(db, filters)
    assert _check(report, "trial_vs_ledger")["ok"] is True


# ── سقفِ ردیف ────────────────────────────────────────────────────────────────


def test_rows_are_capped_but_the_count_is_complete(db, user):
    entries = [
        _raw_entry(db, user, [JournalLine(account_id=_account(db).id, debit=Decimal(10), credit=0)])
        for _ in range(ROW_LIMIT + 3)
    ]
    check = _check(run_integrity_check(db, _scope(*entries)), "unbalanced_entries")

    assert check["count"] == ROW_LIMIT + 3
    assert len(check["rows"]) == ROW_LIMIT
    assert check["truncated"] is True


# ── دامنه ────────────────────────────────────────────────────────────────────


def test_system_entries_can_be_excluded(db, user):
    """همان دامنه‌ی بقیه‌ی گزارش‌ها: افتتاحیه و اختتامیه قابلِ کنار گذاشتن‌اند."""
    target, other = _account(db), get_account(db, cc.RETAINED_EARNINGS)
    entry = _raw_entry(db, user, [
        JournalLine(account_id=target.id, debit=Decimal(700), credit=0),
        JournalLine(account_id=other.id, debit=0, credit=Decimal(400)),
    ], source="opening")

    scope = _scope(entry)
    assert _check(run_integrity_check(db, scope), "unbalanced_entries")["ok"] is False

    without = ReportFilters(
        entry_from=scope.entry_from, entry_to=scope.entry_to, include_system_entries=False
    )
    assert _check(run_integrity_check(db, without), "unbalanced_entries")["ok"] is True


def test_empty_filters_scan_the_whole_ledger(db, user):
    """بدونِ فیلتر، بررسی کلِ دفتر را می‌بیند — پیش‌فرض نباید چیزی را پنهان کند."""
    target, other = _account(db), get_account(db, cc.RETAINED_EARNINGS)
    entry = _raw_entry(db, user, [
        JournalLine(account_id=target.id, debit=Decimal(700), credit=0),
        JournalLine(account_id=other.id, debit=0, credit=Decimal(400)),
    ])

    check = _check(run_integrity_check(db), "unbalanced_entries")
    assert entry.id in {r["entry_id"] for r in check["rows"]} or check["truncated"]


# ── رگرسیونِ میان‌بُرِ دفترِ برگ ───────────────────────────────────────────────


def test_group_ledger_still_includes_descendants(db, user):
    """میان‌بُرِ «حسابِ برگ نواده ندارد» نباید دفترِ سرفصل را خالی کند."""
    parent = _account(db, is_group=True)
    child = _account(db, parent=parent)
    entry = _balanced(db, user, 550, account=child)

    ledger = get_general_ledger(db, parent.id, None, None, _scope(entry))
    assert ledger["closing_balance"] == Decimal(550)
    assert [line["account_code"] for line in ledger["lines"]] == [child.code]


def test_leaf_ledger_holds_only_its_own_lines(db, user):
    account = _account(db)
    entry = _balanced(db, user, 120, account=account)
    other = _balanced(db, user, 480)

    ledger = get_general_ledger(db, account.id, None, None, _scope(entry, other))
    assert ledger["closing_balance"] == Decimal(120)
    assert len(ledger["lines"]) == 1


# ── مسیر ────────────────────────────────────────────────────────────────────


def test_endpoint_serialises_the_whole_report(client, db, user):
    """سریال‌سازی از راهِ Pydantic — Decimal و UUID هر دو باید سالم رد شوند."""
    target, other = _account(db), get_account(db, cc.RETAINED_EARNINGS)
    entry = _raw_entry(db, user, [
        JournalLine(account_id=target.id, debit=Decimal(700), credit=0),
        JournalLine(account_id=other.id, debit=0, credit=Decimal(400)),
    ])
    db.commit()

    body = client.get(f"/api/reports/integrity?entry_from={entry.number}&entry_to={entry.number}").json()

    assert body["ok"] is False
    assert body["total_debit"] == "700.00" or Decimal(body["total_debit"]) == 700
    keys = {c["key"] for c in body["checks"]}
    assert keys == {
        "unbalanced_entries",
        "group_account_lines",
        "leaf_with_children",
        "trial_vs_ledger",
        "empty_entries",
        "over_allocated",
        "unsettleable_balance",
    }
    found = next(c for c in body["checks"] if c["key"] == "unbalanced_entries")
    assert found["rows"][0]["entry_id"] == str(entry.id)
