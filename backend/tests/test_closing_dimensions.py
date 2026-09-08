"""اختتامیه و افتتاحیه باید بُعدهای مانده را از سالی به سالِ بعد ببرند.

`_permanent_balances` فقط روی `Account.id` گروه می‌شد. یعنی «دریافتنیِ تجاری» با
سه مشتری یک ردیف می‌شد و سالِ جدید با حسابی باز می‌شد که صد میلیون مانده دارد و
**دفترِ تفصیلی‌اش خالی است** — جمع درست، تفکیک غلط، و چون سند ویرایشِ ردیف ندارد،
برای همیشه. همان باگی که در `fx_revaluation_preview` پیدا شد.

باگِ دوم مستقل بود و بی‌صداتر: **اختتامیه خودش را گارد می‌کند، افتتاحیه نه.** بعد
از اختتامیه همه‌ی مانده‌ها صفرند پس اختتامیه‌ی دوم خودبه‌خود رد می‌شود؛ ولی
افتتاحیه از *سندِ* اختتامیه ساخته می‌شود و آن سند سرِ جایش می‌ماند، پس اجرای دوم
هر مانده‌ی ابتدای دوره را دو برابر می‌کرد بدونِ اینکه چیزی صدا کند.
"""
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.accounting import Account, JournalEntry, JournalLine
from app.models.analytic import AnalyticAccount
from app.models.cost_center import CostCenter
from app.models.tenant import Tenant
from app.services import accounting_ops as ops
from app.services import chart_codes as cc
from app.services.common import get_account, make_journal_entry
from app.tenant_context import session_tenant

CLOSE = date(2026, 12, 29)
OPEN = date(2026, 12, 30)


def _set_mode(db, mode: str) -> None:
    db.get(Tenant, session_tenant(db)).tafsili_enforcement = mode
    db.flush()


def _analytic(db, user, code: str, name: str) -> AnalyticAccount:
    row = AnalyticAccount(code=code, name=name, created_by_id=user.id)
    db.add(row)
    db.flush()
    return row


def _center(db, user, name: str) -> CostCenter:
    row = CostCenter(code="", name=name, kind="project", created_by_id=user.id)
    db.add(row)
    db.flush()
    return row


def _capital(db) -> Account:
    return db.query(Account).filter(Account.code == "3101").one()


def _books(db, user, lines: list[JournalLine], total: int) -> None:
    """دفترِ کوچکی که فقط حساب‌های دائمی دارد، با طرفِ سرمایه‌ی متوازن‌کننده."""
    make_journal_entry(
        db,
        date(2026, 3, 1),
        "آورده‌ی سرمایه",
        "manual",
        user,
        [*lines, JournalLine(account_id=_capital(db).id, debit=0, credit=Decimal(total))],
    )


def _receivable(db) -> Account:
    account = get_account(db, cc.CASH)
    account.accepts_tafsili = True
    db.flush()
    return account


def _lines_of(db, entry_id, account_id) -> list[JournalLine]:
    entry = db.get(JournalEntry, entry_id)
    return [line for line in entry.lines if line.account_id == account_id]


# ── بُعدها از سال عبور می‌کنند ────────────────────────────────────────────────


def test_closing_keeps_each_analytic_separate(db, user):
    """**قیدِ اصلی.** سه مشتری سه مانده‌اند، نه یک کاسه‌ی صد میلیونی."""
    account = _receivable(db)
    alpha = _analytic(db, user, "A1", "شرکت آلفا")
    beta = _analytic(db, user, "B1", "شرکت بتا")
    _books(
        db,
        user,
        [
            JournalLine(account_id=account.id, debit=Decimal(20), credit=0, analytic_id=alpha.id),
            JournalLine(account_id=account.id, debit=Decimal(30), credit=0, analytic_id=beta.id),
        ],
        50,
    )

    out = ops.issue_closing_entry(db, user, CLOSE, "")
    lines = _lines_of(db, out["entry_id"], account.id)
    assert len(lines) == 2
    assert {line.analytic_id for line in lines} == {alpha.id, beta.id}
    #: اختتامیه برعکسِ مانده می‌زند تا صفر شود.
    assert {Decimal(line.credit) for line in lines} == {Decimal(20), Decimal(30)}


def test_opening_brings_the_same_analytics_back(db, user):
    """سالِ جدید باید با همان تفکیکی باز شود که سالِ قبل با آن بسته شد."""
    account = _receivable(db)
    alpha = _analytic(db, user, "A1", "شرکت آلفا")
    beta = _analytic(db, user, "B1", "شرکت بتا")
    _books(
        db,
        user,
        [
            JournalLine(account_id=account.id, debit=Decimal(20), credit=0, analytic_id=alpha.id),
            JournalLine(account_id=account.id, debit=Decimal(30), credit=0, analytic_id=beta.id),
        ],
        50,
    )
    ops.issue_closing_entry(db, user, CLOSE, "")

    out = ops.issue_opening_entry(db, user, OPEN, CLOSE, "")
    lines = _lines_of(db, out["entry_id"], account.id)
    by_analytic = {line.analytic_id: Decimal(line.debit) for line in lines}
    assert by_analytic == {alpha.id: Decimal(20), beta.id: Decimal(30)}


def test_the_cost_center_survives_too(db, user):
    """فقط تفصیلی کافی نیست — گزارشِ فیلترشده بر مرکز همان ناسازگاری را می‌داد.

    حساب عمداً تفصیلی‌پذیر **نیست**: این تست دربارهٔ مرکز هزینه است و اگر حساب
    تفصیلی می‌خواست، ردیفِ بی‌تفصیلی در حالتِ پیش‌فرض («ترکیبی») اصلاً ثبت نمی‌شد.
    """
    account = get_account(db, cc.CASH)
    center = _center(db, user, "دفتر مرکزی")
    _books(
        db,
        user,
        [JournalLine(account_id=account.id, debit=Decimal(40), credit=0, cost_center_id=center.id)],
        40,
    )
    ops.issue_closing_entry(db, user, CLOSE, "")

    out = ops.issue_opening_entry(db, user, OPEN, CLOSE, "")
    line = _lines_of(db, out["entry_id"], account.id)[0]
    assert line.cost_center_id == center.id


def test_a_balance_without_dimensions_is_still_one_line(db, user):
    """رگرسیون: نبودِ بُعد نباید چیزی را عوض کند."""
    cash = get_account(db, cc.CASH)
    _books(db, user, [JournalLine(account_id=cash.id, debit=Decimal(9_000), credit=0)], 9_000)

    out = ops.issue_closing_entry(db, user, CLOSE, "")
    lines = _lines_of(db, out["entry_id"], cash.id)
    assert len(lines) == 1
    assert lines[0].analytic_id is None and lines[0].cost_center_id is None


def test_strict_mode_no_longer_blocks_closing(db, user):
    """**رگرسیونِ همان تله.** پیش از این `strict` کلِ اختتامیه را رد می‌کرد."""
    account = _receivable(db)
    alpha = _analytic(db, user, "A1", "شرکت آلفا")
    _books(
        db,
        user,
        [JournalLine(account_id=account.id, debit=Decimal(20), credit=0, analytic_id=alpha.id)],
        20,
    )
    _set_mode(db, "strict")

    out = ops.issue_closing_entry(db, user, CLOSE, "")
    assert out["line_count"] >= 2


# ── افتتاحیه‌ی تکراری ────────────────────────────────────────────────────────


def test_a_second_opening_is_refused(db, user):
    """**باگِ خاموش.** اجرای دوم هر مانده‌ی ابتدای دوره را دو برابر می‌کرد."""
    cash = get_account(db, cc.CASH)
    _books(db, user, [JournalLine(account_id=cash.id, debit=Decimal(9_000), credit=0)], 9_000)
    ops.issue_closing_entry(db, user, CLOSE, "")
    first = ops.issue_opening_entry(db, user, OPEN, CLOSE, "")

    with pytest.raises(HTTPException) as err:
        ops.issue_opening_entry(db, user, OPEN, CLOSE, "")
    assert err.value.status_code == 409
    #: پیام باید بگوید کجا را نگاه کند، نه فقط «تکراری است».
    assert str(first["number"]) in err.value.detail


def test_the_opening_points_at_its_closing(db, user):
    """§۹ — «این مانده‌ی ابتدای دوره از کجا آمد؟» باید یک کوئریِ ساده باشد."""
    cash = get_account(db, cc.CASH)
    _books(db, user, [JournalLine(account_id=cash.id, debit=Decimal(9_000), credit=0)], 9_000)
    closing = ops.issue_closing_entry(db, user, CLOSE, "")
    opening = ops.issue_opening_entry(db, user, OPEN, CLOSE, "")

    entry = db.get(JournalEntry, opening["entry_id"])
    assert entry.reverses_entry_id == closing["entry_id"]


def test_voiding_the_opening_frees_the_way(db, user):
    """گارد فقط سندِ *باطل‌نشده* را می‌بیند — وگرنه اشتباه برای همیشه قفل می‌شد."""
    cash = get_account(db, cc.CASH)
    _books(db, user, [JournalLine(account_id=cash.id, debit=Decimal(9_000), credit=0)], 9_000)
    ops.issue_closing_entry(db, user, CLOSE, "")
    first = ops.issue_opening_entry(db, user, OPEN, CLOSE, "")

    db.get(JournalEntry, first["entry_id"]).voided_at = date(2026, 12, 31)
    db.flush()

    again = ops.issue_opening_entry(db, user, OPEN, CLOSE, "")
    assert again["entry_id"] != first["entry_id"]
