"""بستنِ سود و زیان: ابعادِ ردیف، و جداشدنِ بستن از قفل.

دو اشکال را نگه می‌دارد که هر دو بی‌صدا بودند.

**یک.** سندِ بستن ابعادِ ردیف را دور می‌انداخت. مانده از `_leaf_account_totals`
می‌آمد که فقط روی `Account.id` گروه می‌کند، پس «فروش داخلی / شرکت آلفا» و «فروش
داخلی / شرکت بتا» یک عدد می‌شدند. در `hybrid` حساب صفر می‌شد و دفترِ تفصیلی
مانده‌دار می‌ماند — و چون درآمد و هزینه به سالِ بعد منتقل نمی‌شوند، آن مانده
**هیچ‌وقت** بسته نمی‌شد. در `strict` بدتر: `make_journal_entry` سندِ بی‌تفصیلی را رد
می‌کرد و بستنِ دوره **اصلاً انجام نمی‌شد**.

**دو.** یک دکمه هم سند را می‌زد، هم دوره را قفل می‌کرد، هم اسنادِ موقت را دائم
می‌کرد. و قفل برگشت ندارد — نه حذفی هست نه بازگشایی. حالا دو گام است و گامِ اول
سندِ موقتِ عادی می‌سازد.
"""
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.accounting import Account, JournalEntry, JournalLine
from app.models.analytic import AnalyticAccount
from app.models.cost_center import CostCenter
from app.models.tenant import Tenant
from app.schemas.period_close import FiscalPeriodCloseIn
from app.services import accounting_ops as ops
from app.services import chart_codes as cc
from app.services.common import get_account, make_journal_entry
from app.services.period_close import assert_period_open, close_period
from app.services.reports import get_income_statement
from app.tenant_context import session_tenant

DAY = date(2026, 3, 10)
CLOSING = date(2026, 3, 20)
LATER = date(2026, 3, 25)


def _set_mode(db, mode: str) -> None:
    db.get(Tenant, session_tenant(db)).tafsili_enforcement = mode
    db.flush()


def _analytic(db, user, code: str, name: str) -> AnalyticAccount:
    row = AnalyticAccount(code=code, name=name, created_by_id=user.id)
    db.add(row)
    db.flush()
    return row


def _center(db, user, code: str, name: str) -> CostCenter:
    row = CostCenter(code=code, name=name, created_by_id=user.id)
    db.add(row)
    db.flush()
    return row


def _revenue(db, *, tafsili: bool = False) -> Account:
    account = get_account(db, cc.SALES_REVENUE)
    account.accepts_tafsili = tafsili
    db.flush()
    return account


def _sell(db, user, amount: int, *, analytic=None, center=None, when=DAY) -> JournalEntry:
    """درآمد: نقد بدهکار، فروش بستانکار — با بُعدهای دلخواه روی ردیفِ درآمد."""
    cash = get_account(db, cc.CASH)
    revenue = get_account(db, cc.SALES_REVENUE)
    return make_journal_entry(
        db, when, "فروش آزمون", "manual", user,
        [
            JournalLine(account_id=cash.id, debit=Decimal(amount), credit=0),
            JournalLine(
                account_id=revenue.id,
                analytic_id=analytic.id if analytic else None,
                cost_center_id=center.id if center else None,
                debit=0,
                credit=Decimal(amount),
            ),
        ],
    )


def _spend(db, user, amount: int, *, analytic=None, when=DAY) -> JournalEntry:
    cash = get_account(db, cc.CASH)
    cogs = get_account(db, cc.COGS)
    return make_journal_entry(
        db, when, "هزینه آزمون", "manual", user,
        [
            JournalLine(
                account_id=cogs.id,
                analytic_id=analytic.id if analytic else None,
                debit=Decimal(amount),
                credit=0,
            ),
            JournalLine(account_id=cash.id, debit=0, credit=Decimal(amount)),
        ],
    )


def _closing_entry(db, out: dict) -> JournalEntry:
    return db.get(JournalEntry, out["entry_id"])


def _balance_of(db, account, analytic_id, as_of=CLOSING) -> Decimal:
    for acc, aid, _center, raw in ops.pnl_balances(db, None, as_of):
        if acc.id == account.id and aid == analytic_id:
            return raw
    return Decimal(0)


# ── قیدِ اصلی: تفصیلی روی ردیفِ سند می‌نشیند ────────────────────────────────


def test_the_closing_line_carries_the_analytic(db, user):
    """**قیدِ §۲۶.** پیش از این ردیف بی‌تفصیلی ساخته می‌شد."""
    _set_mode(db, "hybrid")
    revenue = _revenue(db, tafsili=True)
    alpha = _analytic(db, user, "A1", "شرکت آلفا")
    _sell(db, user, 8_000_000, analytic=alpha)

    entry = _closing_entry(db, ops.issue_pnl_close(db, user, CLOSING))
    line = next(line for line in entry.lines if line.account_id == revenue.id)

    assert line.analytic_id == alpha.id, "تفصیلی باید روی ردیفِ سندِ بستن بیاید"
    assert Decimal(line.debit) == Decimal(8_000_000)


def test_the_analytic_ledger_actually_closes(db, user):
    """**مهم‌ترین رگرسیون.** حساب صفر می‌شد ولی تفصیلی مانده‌دار می‌ماند — و چون
    درآمد به سالِ بعد نمی‌رود، هیچ‌وقت بسته نمی‌شد."""
    _set_mode(db, "hybrid")
    revenue = _revenue(db, tafsili=True)
    alpha = _analytic(db, user, "A1", "شرکت آلفا")
    _sell(db, user, 8_000_000, analytic=alpha)

    ops.issue_pnl_close(db, user, CLOSING)
    db.flush()

    assert _balance_of(db, revenue, alpha.id) == 0, "دفترِ تفصیلی هم باید صفر شود"


def test_two_analytics_get_two_separate_lines(db, user):
    """یک‌کاسه‌شدن یعنی جمع درست و تفکیک غلط."""
    _set_mode(db, "hybrid")
    revenue = _revenue(db, tafsili=True)
    alpha = _analytic(db, user, "A1", "شرکت آلفا")
    beta = _analytic(db, user, "B1", "شرکت بتا")
    _sell(db, user, 5_000_000, analytic=alpha)
    _sell(db, user, 3_000_000, analytic=beta)

    entry = _closing_entry(db, ops.issue_pnl_close(db, user, CLOSING))
    revenue_lines = [line for line in entry.lines if line.account_id == revenue.id]

    assert len(revenue_lines) == 2
    assert {line.analytic_id for line in revenue_lines} == {alpha.id, beta.id}
    assert {Decimal(line.debit) for line in revenue_lines} == {
        Decimal(5_000_000),
        Decimal(3_000_000),
    }


def test_the_cost_center_is_carried_too(db, user):
    _set_mode(db, "hybrid")
    revenue = _revenue(db)
    branch = _center(db, user, "C1", "شعبه‌ی مرکزی")
    _sell(db, user, 4_000_000, center=branch)

    entry = _closing_entry(db, ops.issue_pnl_close(db, user, CLOSING))
    line = next(line for line in entry.lines if line.account_id == revenue.id)

    assert line.cost_center_id == branch.id


def test_strict_mode_no_longer_blocks_closing(db, user):
    """**رگرسیونِ حالتِ `strict`.** تا امروز بستن در این حالت کاملاً مسدود بود و
    کاربر پیامی می‌گرفت که هیچ کاری نمی‌توانست برایش بکند."""
    _set_mode(db, "hybrid")
    _revenue(db, tafsili=True)
    alpha = _analytic(db, user, "A1", "شرکت آلفا")
    _sell(db, user, 6_000_000, analytic=alpha)
    _set_mode(db, "strict")

    out = ops.issue_pnl_close(db, user, CLOSING)  # نباید خطا بدهد
    assert out["line_count"] >= 2


# ── حساب‌داریِ سند ─────────────────────────────────────────────────────────


def test_the_entry_is_balanced_and_zeroes_the_statement(db, user):
    _set_mode(db, "hybrid")
    _revenue(db, tafsili=True)
    alpha = _analytic(db, user, "A1", "شرکت آلفا")
    _sell(db, user, 8_000_000, analytic=alpha)
    _spend(db, user, 3_000_000)

    entry = _closing_entry(db, ops.issue_pnl_close(db, user, CLOSING))
    db.flush()

    assert sum((Decimal(line.debit) for line in entry.lines), Decimal(0)) == sum(
        (Decimal(line.credit) for line in entry.lines), Decimal(0)
    )
    after = get_income_statement(db, None, CLOSING)
    assert Decimal(after["total_income"]) == 0
    assert Decimal(after["total_expenses"]) == 0


def test_the_net_result_reaches_retained_earnings(db, user):
    _set_mode(db, "hybrid")
    _revenue(db)
    _sell(db, user, 8_000_000)
    _spend(db, user, 3_000_000)

    out = ops.issue_pnl_close(db, user, CLOSING)
    entry = _closing_entry(db, out)
    retained = get_account(db, cc.RETAINED_EARNINGS)
    line = next(line for line in entry.lines if line.account_id == retained.id)

    assert Decimal(out["net_profit"]) == Decimal(5_000_000)
    assert Decimal(line.credit) == Decimal(5_000_000)


def test_a_loss_reverses_the_destination_side(db, user):
    _set_mode(db, "hybrid")
    _revenue(db)
    _sell(db, user, 2_000_000)
    _spend(db, user, 9_000_000)

    entry = _closing_entry(db, ops.issue_pnl_close(db, user, CLOSING))
    retained = get_account(db, cc.RETAINED_EARNINGS)
    line = next(line for line in entry.lines if line.account_id == retained.id)

    assert Decimal(line.debit) == Decimal(7_000_000), "زیان باید بدهکارِ سود انباشته شود"


def test_the_preview_matches_what_gets_issued(db, user):
    """پیش‌نمایش و صدور یک محاسبه‌اند، نه دو تا."""
    _set_mode(db, "hybrid")
    _revenue(db, tafsili=True)
    alpha = _analytic(db, user, "A1", "شرکت آلفا")
    _sell(db, user, 8_000_000, analytic=alpha)
    _spend(db, user, 3_000_000)

    preview = ops.pnl_close_preview(db, CLOSING)
    assert preview["difference"] == 0, "اختلافِ سند باید صفر باشد"
    assert preview["already_closed"] is False
    assert preview["destination_account_code"] == get_account(db, cc.RETAINED_EARNINGS).code

    out = ops.issue_pnl_close(db, user, CLOSING)
    assert out["line_count"] == len(preview["rows"]) + 1  # ردیف‌ها + خطِ مقصد
    assert Decimal(out["net_profit"]) == Decimal(preview["net_profit"])


def test_a_zero_balance_account_makes_no_line(db, user):
    """**§۲۵.** ردیفِ بی‌اثر ساخته نمی‌شود."""
    _set_mode(db, "hybrid")
    _revenue(db)
    _sell(db, user, 4_000_000)
    # برگشتِ کامل: همان سند، وارونه. مانده‌ی فروش صفر می‌شود.
    cash = get_account(db, cc.CASH)
    revenue = get_account(db, cc.SALES_REVENUE)
    make_journal_entry(
        db, DAY, "برگشت از فروش", "manual", user,
        [
            JournalLine(account_id=revenue.id, debit=Decimal(4_000_000), credit=0),
            JournalLine(account_id=cash.id, debit=0, credit=Decimal(4_000_000)),
        ],
    )
    _spend(db, user, 1_000_000)

    rows = ops.pnl_close_preview(db, CLOSING)["rows"]
    revenue_id = get_account(db, cc.SALES_REVENUE).id
    assert not any(r["account_id"] == revenue_id for r in rows)


# ── گامِ اول جدا از گامِ دوم ───────────────────────────────────────────────


def test_closing_alone_does_not_lock_the_period(db, user):
    """**قیدِ §۱۵.** پیش از این، بستن یعنی قفلِ برگشت‌ناپذیر."""
    _set_mode(db, "hybrid")
    _revenue(db)
    _sell(db, user, 5_000_000)

    ops.issue_pnl_close(db, user, CLOSING)
    db.flush()

    assert_period_open(db, DAY)  # نباید خطا بدهد — دوره هنوز باز است


def test_the_issued_entry_is_temporary(db, user):
    """سند چرخه‌ی عمرِ عادی را طی می‌کند: موقت → بررسی → دائم."""
    _set_mode(db, "hybrid")
    _revenue(db)
    _sell(db, user, 5_000_000)

    entry = _closing_entry(db, ops.issue_pnl_close(db, user, CLOSING))
    assert entry.status == "temporary"


def test_locking_after_closing_does_not_issue_a_second_entry(db, user):
    """**قیدِ اصلیِ گامِ دوم.** وگرنه سود دو بار به سود انباشته می‌رفت."""
    _set_mode(db, "hybrid")
    _revenue(db)
    _sell(db, user, 8_000_000)
    _spend(db, user, 3_000_000)

    first = ops.issue_pnl_close(db, user, CLOSING)
    db.flush()
    close = close_period(db, FiscalPeriodCloseIn(closing_date=CLOSING, notes=""), user)

    assert close.journal_entry_id == first["entry_id"], "باید همان سند را بردارد"
    assert (
        db.query(JournalEntry).filter(JournalEntry.source_type == "period_close").count() == 1
    )
    assert Decimal(close.net_profit) == Decimal(5_000_000), "سود از خودِ سند خوانده می‌شود"


def test_locking_without_closing_still_works(db, user):
    """رفتارِ «یک دکمه» برای کسی که مستقیم قفل می‌کند نباید عوض شود."""
    _set_mode(db, "hybrid")
    _revenue(db)
    _sell(db, user, 6_000_000)

    close = close_period(db, FiscalPeriodCloseIn(closing_date=CLOSING, notes=""), user)

    assert close.journal_entry_id is not None
    assert Decimal(close.net_profit) == Decimal(6_000_000)
    with pytest.raises(HTTPException):
        assert_period_open(db, DAY)  # حالا قفل است


def test_the_lock_finalizes_the_closing_entry(db, user):
    """سندِ موقتِ گامِ اول با قفلِ دوره دائم می‌شود."""
    _set_mode(db, "hybrid")
    _revenue(db)
    _sell(db, user, 6_000_000)
    entry_id = ops.issue_pnl_close(db, user, CLOSING)["entry_id"]
    db.flush()

    close_period(db, FiscalPeriodCloseIn(closing_date=CLOSING, notes=""), user)
    db.flush()

    assert db.get(JournalEntry, entry_id).status == "permanent"


# ── دوباره‌بستن ───────────────────────────────────────────────────────────


def test_closing_twice_with_no_new_activity_is_rejected(db, user):
    """**§۲۰.** سندِ بستنِ قبلی داخلِ همان بازه است و مانده را صفر کرده، پس
    ردیفی نمی‌ماند و خودبه‌خود رد می‌شود — بدونِ نیاز به گاردِ جدا."""
    _set_mode(db, "hybrid")
    _revenue(db)
    _sell(db, user, 5_000_000)
    ops.issue_pnl_close(db, user, CLOSING)
    db.flush()

    with pytest.raises(HTTPException) as err:
        ops.issue_pnl_close(db, user, CLOSING)
    assert err.value.status_code == 400


def test_closing_after_new_activity_closes_only_the_difference(db, user):
    """**§۲۱.** اگر بعد از بستن سندی اضافه شود، بستنِ بعدی فقط همان را می‌بندد."""
    _set_mode(db, "hybrid")
    _revenue(db)
    _sell(db, user, 5_000_000)
    ops.issue_pnl_close(db, user, CLOSING)
    db.flush()

    _sell(db, user, 2_000_000, when=LATER)
    out = ops.issue_pnl_close(db, user, LATER)

    assert Decimal(out["net_profit"]) == Decimal(2_000_000), "فقط تفاوت، نه کلِ دوره"


def test_no_activity_at_all_is_rejected(db, user):
    with pytest.raises(HTTPException) as err:
        ops.issue_pnl_close(db, user, CLOSING)
    assert "هیچ فعالیت" in str(err.value.detail)


def test_a_closed_period_rejects_a_new_closing(db, user):
    """**§۱۹.** این عملیات راهِ دورزدنِ قفلِ دوره نیست."""
    _set_mode(db, "hybrid")
    _revenue(db)
    _sell(db, user, 5_000_000)
    close_period(db, FiscalPeriodCloseIn(closing_date=CLOSING, notes=""), user)

    with pytest.raises(HTTPException):
        ops.issue_pnl_close(db, user, CLOSING)


# ── افتتاحیه‌ی سال هم همین اشکال را داشت ──────────────────────────────────


def test_carry_forward_keeps_the_analytic(db, user):
    """نمونه‌ی پنجمِ همان اشکال: `carry_forward` هم بُعدها را دور می‌انداخت."""
    from app.jalali import persian_year_end, persian_year_start
    from app.schemas.fiscal_year import FiscalYearIn
    from app.services import fiscal_year as fy

    _set_mode(db, "hybrid")
    old = fy.create_year(
        db, FiscalYearIn(title="۱۴۰۴", start_date=persian_year_start(1404),
                         end_date=persian_year_end(1404), activate=True)
    )
    new = fy.create_year(
        db, FiscalYearIn(title="۱۴۰۵", start_date=persian_year_start(1405),
                         end_date=persian_year_end(1405), activate=False)
    )

    receivable = get_account(db, cc.ACCOUNTS_RECEIVABLE)
    receivable.accepts_tafsili = True
    alpha = _analytic(db, user, "A1", "شرکت آلفا")
    revenue = get_account(db, cc.SALES_REVENUE)
    make_journal_entry(
        db, persian_year_start(1404), "فروش نسیه", "manual", user,
        [
            JournalLine(account_id=receivable.id, analytic_id=alpha.id,
                        debit=Decimal(9_000_000), credit=0),
            JournalLine(account_id=revenue.id, debit=0, credit=Decimal(9_000_000)),
        ],
    )
    fy.close_year(db, old.id, user)

    entry = db.get(JournalEntry, fy.carry_forward(db, new.id, user)["journal_entry_id"])
    line = next(line for line in entry.lines if line.account_id == receivable.id)

    assert line.analytic_id == alpha.id, "تفصیلی باید به سالِ بعد منتقل شود"
    assert Decimal(line.debit) == Decimal(9_000_000)
