"""حسابِ بانکی — تفصیلی، مانده‌ی مشتق، بلوکه و گاردها.

**قیدِ اصلی (§۲۵):** جمعِ مانده‌ی حساب‌های بانکی باید با مانده‌ی معینِ بانک در دفتر
یکی باشد. اگر واگرا شوند یعنی جایی پول را دو بار شمرده‌ایم یا گم کرده‌ایم — و
همان تستی است که برای صندوق هم نوشته شد.

**چرا حسابِ معینِ اختصاصی:** فیکسچرِ `db` برمی‌گردد ولی تست‌های `client` در همان
مستأجر کامیت می‌کنند، پس ادعای مطلق روی معینِ مشترکِ بانک به ترتیبِ اجرا وابسته
می‌شود. هر تست معینِ خودش را می‌سازد تا عددهایش مالِ خودش باشند.
"""
import itertools
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.accounting import Account, JournalLine
from app.models.analytic import AnalyticAccount
from app.models.banking import BankAccount
from app.models.fiscal_year import FiscalYear
from app.services import bank_accounts as svc
from app.services import chart_codes as cc
from app.services.common import get_account, make_journal_entry

WHEN = date(1405, 3, 10)

_SEQ = itertools.count(1)


@pytest.fixture
def gl(db) -> Account:
    """معینِ بانکیِ اختصاصیِ همین تست — زیرِ همان سرفصلی که معینِ بانک هست."""
    row = Account(
        code=f"B{next(_SEQ):04d}",
        name=f"بانکِ آزمون {next(_SEQ)}",
        type="asset",
        is_group=False,
        parent_id=get_account(db, cc.BANK).parent_id,
    )
    db.add(row)
    db.flush()
    return row


def _analytic(db, user) -> AnalyticAccount:
    row = AnalyticAccount(code=f"BA{next(_SEQ):04d}", name=f"تفصیلی {next(_SEQ)}", created_by_id=user.id)
    db.add(row)
    db.flush()
    return row


def _account(db, gl, *, analytic=None, **kw) -> BankAccount:
    acct = BankAccount(
        name=kw.pop("name", f"حساب {next(_SEQ)}"),
        gl_account_id=gl.id,
        analytic_id=analytic.id if analytic else None,
        **kw,
    )
    db.add(acct)
    db.flush()
    db.refresh(acct)
    return acct


def _post(db, user, gl, amount, *, analytic=None, when=WHEN):
    """بانک بدهکار در برابرِ سودِ انباشته — طرفِ مقابل فقط سند را متوازن می‌کند."""
    other = get_account(db, cc.RETAINED_EARNINGS)
    return make_journal_entry(
        db, when, "آزمون", "manual", user,
        [
            JournalLine(
                account_id=gl.id,
                analytic_id=analytic.id if analytic else None,
                debit=Decimal(amount),
                credit=0,
            ),
            JournalLine(account_id=other.id, debit=0, credit=Decimal(amount)),
        ],
    )


# ── مانده مشتق است ───────────────────────────────────────────────────────────


def test_balance_comes_from_the_ledger_not_a_column(db, user, gl):
    """سندِ دستی روی همان تفصیلی مانده را عوض می‌کند — یعنی ذخیره‌شده نیست."""
    an = _analytic(db, user)
    acct = _account(db, gl, analytic=an)
    assert svc.balance(db, acct) == 0

    _post(db, user, gl, 5_000_000, analytic=an)
    assert svc.balance(db, acct) == Decimal(5_000_000)


def test_two_accounts_keep_separate_balances(db, user, gl):
    a, b = _analytic(db, user), _analytic(db, user)
    first, second = _account(db, gl, analytic=a), _account(db, gl, analytic=b)

    _post(db, user, gl, 300, analytic=a)
    _post(db, user, gl, 700, analytic=b)

    assert svc.balance(db, first) == Decimal(300)
    assert svc.balance(db, second) == Decimal(700)


def test_sum_of_accounts_equals_the_gl_balance(db, user, gl):
    """**قیدِ §۲۵.** هر ریالی که روی معینِ بانک نشسته باید در مانده‌ی یکی از
    حساب‌ها دیده شود — نه بیشتر، نه کمتر."""
    a, b = _analytic(db, user), _analytic(db, user)
    untagged = _account(db, gl)  # حسابِ اول، بی‌تفصیلی
    first, second = _account(db, gl, analytic=a), _account(db, gl, analytic=b)

    _post(db, user, gl, 1_000, analytic=a)
    _post(db, user, gl, 2_500, analytic=b)
    _post(db, user, gl, 400)  # تفکیک‌نشده

    ledger = (
        db.query(JournalLine).filter(JournalLine.account_id == gl.id).all()
    )
    gl_total = sum((Decimal(x.debit) - Decimal(x.credit) for x in ledger), Decimal(0))
    accounts_total = sum(
        (svc.balance(db, acct) for acct in (untagged, first, second)), Decimal(0)
    )
    assert accounts_total == gl_total == Decimal(3_900)


def test_untagged_account_reads_the_null_analytic_rows(db, user, gl):
    """حسابِ بی‌تفصیلی همان گردشِ امروزِ دفتر را می‌خواند — همین است که مهاجرت را
    بی‌نیاز از backfill می‌کند. `= NULL` هرگز درست نیست، پس اگر برابریِ NULL-امن
    نبود این عدد صفر می‌ماند."""
    acct = _account(db, gl)
    _post(db, user, gl, 850)
    assert svc.balance(db, acct) == Decimal(850)


def test_tagged_account_does_not_see_untagged_money(db, user, gl):
    an = _analytic(db, user)
    tagged = _account(db, gl, analytic=an)
    _post(db, user, gl, 900)  # بی‌تفصیلی
    assert svc.balance(db, tagged) == 0


# ── بلوکه با مانده قاطی نمی‌شود ───────────────────────────────────────────────


def test_blocked_amount_never_moves_the_balance(db, user, gl):
    """**قیدِ صریحِ §۱۸.** بلوکه رویدادِ حسابداری نیست: نه سند می‌زند نه مانده را
    عوض می‌کند. فقط «قابل استفاده» را کم می‌کند."""
    acct = _account(db, gl, analytic=_analytic(db, user))
    _post(db, user, gl, 100, analytic=db.get(AnalyticAccount, acct.analytic_id))

    before = svc.balance(db, acct)
    svc.update_bank_account(db, acct.id, {"blocked_amount": Decimal(30)})
    db.refresh(acct)

    assert svc.balance(db, acct) == before == Decimal(100)
    assert svc.available_balance(db, acct) == Decimal(70)


def test_blocked_amount_leaves_no_journal_line(db, user, gl):
    acct = _account(db, gl, analytic=_analytic(db, user))
    before = db.query(JournalLine).filter(JournalLine.account_id == gl.id).count()
    svc.update_bank_account(db, acct.id, {"blocked_amount": Decimal(5_000)})
    after = db.query(JournalLine).filter(JournalLine.account_id == gl.id).count()
    assert before == after == 0


def test_available_balance_may_go_negative(db, user, gl):
    """بانک می‌تواند بیش از موجودی بلوکه کند — واقعیت است، نه خطای ورودِ داده."""
    acct = _account(db, gl, analytic=_analytic(db, user), blocked_amount=Decimal(500))
    assert svc.available_balance(db, acct) == Decimal(-500)


# ── موجودیِ اولیه ────────────────────────────────────────────────────────────


def test_opening_balance_is_the_position_at_year_start(db, user, gl):
    """§۱۲ — مانده در ابتدای سالِ مالی، نه یک عددِ ابدی."""
    db.add(FiscalYear(title="۱۴۰۵", start_date=date(1405, 1, 1), end_date=date(1405, 12, 29), is_active=True))
    db.flush()

    an = _analytic(db, user)
    acct = _account(db, gl, analytic=an)
    _post(db, user, gl, 600, analytic=an, when=date(1404, 11, 5))  # سالِ قبل
    _post(db, user, gl, 250, analytic=an, when=WHEN)               # امسال

    assert svc.opening_balance(db, acct) == Decimal(600)
    assert svc.balance(db, acct) == Decimal(850)


def test_opening_and_current_balance_are_two_numbers(db, user, gl):
    """§۱۳ — ثبتِ تراکنشِ تازه فقط مانده‌ی جاری را تکان می‌دهد."""
    db.add(FiscalYear(title="۱۴۰۵", start_date=date(1405, 1, 1), end_date=date(1405, 12, 29), is_active=True))
    db.flush()
    an = _analytic(db, user)
    acct = _account(db, gl, analytic=an)
    _post(db, user, gl, 400, analytic=an, when=date(1404, 10, 1))

    opening_before = svc.opening_balance(db, acct)
    _post(db, user, gl, 90, analytic=an, when=WHEN)

    assert svc.opening_balance(db, acct) == opening_before == Decimal(400)
    assert svc.balance(db, acct) == Decimal(490)


# ── گاردها ───────────────────────────────────────────────────────────────────


def test_inactive_account_is_refused_for_new_operations(db, user, gl):
    """§۲۲ — سابقه می‌ماند، فقط عملیاتِ تازه بسته می‌شود."""
    acct = _account(db, gl, analytic=_analytic(db, user), is_active=False)
    with pytest.raises(HTTPException) as err:
        svc.assert_usable(db, acct, WHEN)
    assert err.value.status_code == 400
    assert "غیرفعال" in err.value.detail


def test_operation_before_opening_date_is_refused(db, user, gl):
    """§۱۵ — و پیام باید خودِ تاریخ را بگوید."""
    acct = _account(db, gl, analytic=_analytic(db, user), opening_date=date(1405, 5, 1))
    with pytest.raises(HTTPException) as err:
        svc.assert_usable(db, acct, date(1405, 4, 20))
    assert err.value.status_code == 400
    assert "1405-05-01" in err.value.detail


def test_account_without_opening_date_has_no_date_guard(db, user, gl):
    """حساب‌های موجود `opening_date` ندارند و نباید ناگهان بسته شوند."""
    acct = _account(db, gl, analytic=_analytic(db, user))
    svc.assert_usable(db, acct, date(1400, 1, 1))  # نباید خطا بدهد


def test_one_analytic_serves_one_account(db, user, gl):
    an = _analytic(db, user)
    _account(db, gl, analytic=an)
    with pytest.raises(HTTPException) as err:
        svc.create_bank_account(db, {"name": "دومی", "gl_account_id": gl.id, "analytic_id": an.id})
    assert "تعلق دارد" in err.value.detail


def test_analytic_cannot_be_shared_with_a_cashbox(db, user, gl):
    """صندوق و حسابِ بانکی روی یک جدولِ تفصیلی می‌نشینند؛ تفصیلیِ مشترک یعنی یک
    پول که دو موجودیت ادعایش می‌کنند."""
    from app.models.cashbox import Cashbox

    an = _analytic(db, user)
    db.add(Cashbox(name="صندوقِ آزمون", analytic_id=an.id))
    db.flush()
    with pytest.raises(HTTPException) as err:
        svc.create_bank_account(db, {"name": "بانکی", "gl_account_id": gl.id, "analytic_id": an.id})
    assert "صندوق" in err.value.detail


def test_only_the_first_account_may_be_untagged(db, user, gl):
    """حسابِ دومِ بی‌تفصیلی عیناً همان مانده‌ی اولی را می‌خواند — پس رد می‌شود."""
    _account(db, gl)
    with pytest.raises(HTTPException) as err:
        svc.create_bank_account(db, {"name": "دومی", "gl_account_id": gl.id, "analytic_id": None})
    assert "تفصیلی" in err.value.detail


# ── §۳۱ تغییرِ تفصیلی ────────────────────────────────────────────────────────


def test_changing_analytic_of_a_used_account_is_refused(db, user, gl):
    """اگر اجازه داده می‌شد، مانده بی‌صدا به مجموعه‌ی دیگری از ردیف‌ها می‌پرید."""
    an = _analytic(db, user)
    acct = _account(db, gl, analytic=an)
    _post(db, user, gl, 1_200, analytic=an)

    with pytest.raises(HTTPException) as err:
        svc.update_bank_account(db, acct.id, {"analytic_id": _analytic(db, user).id})
    assert err.value.status_code == 409
    assert "انتقال مانده به حساب دیگر" in err.value.detail


def test_changing_analytic_of_an_unused_account_is_allowed(db, user, gl):
    acct = _account(db, gl, analytic=_analytic(db, user))
    fresh = _analytic(db, user)
    svc.update_bank_account(db, acct.id, {"analytic_id": fresh.id})
    db.refresh(acct)
    assert acct.analytic_id == fresh.id


def test_other_fields_of_a_used_account_stay_editable(db, user, gl):
    """گارد فقط روی تفصیلی است — اسم و شبا و بلوکه باید عوض شوند."""
    an = _analytic(db, user)
    acct = _account(db, gl, analytic=an)
    _post(db, user, gl, 100, analytic=an)
    svc.update_bank_account(db, acct.id, {"name": "نامِ تازه", "blocked_amount": Decimal(10)})
    db.refresh(acct)
    assert acct.name == "نامِ تازه"


# ── حذف ──────────────────────────────────────────────────────────────────────


def test_unused_account_can_be_deleted(db, user, gl):
    acct = _account(db, gl, analytic=_analytic(db, user))
    svc.delete_bank_account(db, acct.id)
    assert db.get(BankAccount, acct.id) is None


def test_account_with_ledger_history_is_not_deleted(db, user, gl):
    """§۲۳ — حذفش یعنی شکستنِ چک و کارت‌خوان و مغایرت. به‌جایش غیرفعال."""
    an = _analytic(db, user)
    acct = _account(db, gl, analytic=an)
    _post(db, user, gl, 50, analytic=an)
    with pytest.raises(HTTPException) as err:
        svc.delete_bank_account(db, acct.id)
    assert "غیرفعالش کنید" in err.value.detail


# ── ارز ──────────────────────────────────────────────────────────────────────


def test_currency_accounts_are_listed_separately(db, user, gl):
    """§۲۱ — فهرست جمعِ کل نمی‌دهد، چون دلار و ریال جمع‌شدنی نیستند."""
    _account(db, gl, analytic=_analytic(db, user), currency_code="USD")
    rows = svc.list_bank_accounts(db)
    assert {r["currency_code"] for r in rows} >= {"IRR", "USD"}
    assert not any(r.get("total") for r in rows)
