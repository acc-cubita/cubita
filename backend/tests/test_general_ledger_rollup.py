"""دفتر کل — گردشِ یک سرفصل با همه‌ی زیرحساب‌هایش.

«گزارش دفتر» تا امروز دو تب داشت: روزنامه و معین. رگِ میانیِ حسابداری — **دفتر
کل** — نبود، چون `get_general_ledger` روی `account_id == ...` فیلتر می‌کرد و
ردیفِ سند هرگز به سرفصل نمی‌چسبد. یعنی برای دیدنِ گردشِ «دارایی‌های جاری» باید
تک‌تکِ زیرحساب‌ها جدا باز می‌شدند.

**دوباره‌شماری ممکن نیست** و این تضمینِ کلِ ماجراست: `routers/accounts.py` اجازه
نمی‌دهد حسابی هم ردیفِ مستقیم داشته باشد هم فرزند. پس هر حساب یا برگ است یا
سرفصل، و جمعِ زیرشاخه هیچ مبلغی را دو بار نمی‌شمارد.
"""
from datetime import date
from decimal import Decimal

from app.models.accounting import Account, JournalLine
from app.services import chart_codes as cc
from app.services.common import get_account, make_journal_entry
from app.services.reports import get_general_ledger

#: «۱۱ دارایی‌های جاری» — سرفصلِ سطحِ کل که صندوق و بانک زیرش هستند.
CURRENT_ASSETS = "11"


def _account(db, code: str) -> Account:
    return db.query(Account).filter(Account.code == code).one()


def _post(db, user, *, day: int, account_id, amount: int, note: str = "آزمون"):
    equity = get_account(db, cc.RETAINED_EARNINGS)
    return make_journal_entry(
        db,
        date(2026, 6, day),
        note,
        "manual",
        user,
        [
            JournalLine(account_id=account_id, debit=Decimal(amount), credit=0, description=note),
            JournalLine(account_id=equity.id, debit=0, credit=Decimal(amount)),
        ],
    )


# ── رول‌آپ ───────────────────────────────────────────────────────────────────


def test_a_heading_shows_the_movement_of_every_account_beneath_it(db, user):
    """**قیدِ اصلی.** سرفصل تا امروز دفترِ خالی می‌داد."""
    cash = _account(db, "1101")
    bank = _account(db, "1102")
    _post(db, user, day=1, account_id=cash.id, amount=100)
    _post(db, user, day=2, account_id=bank.id, amount=250)
    db.flush()

    book = get_general_ledger(db, _account(db, CURRENT_ASSETS).id, None, None)
    mine = [line for line in book["lines"] if line["account_code"] in {"1101", "1102"}]
    assert len(mine) == 2
    assert {line["account_code"] for line in mine} == {"1101", "1102"}


def test_each_row_names_the_sub_account_it_came_from(db, user):
    """بدونِ این ستون، دفترِ کل فهرستی از مبالغِ بی‌صاحب است."""
    cash = _account(db, "1101")
    _post(db, user, day=1, account_id=cash.id, amount=100, note="دریافتِ نقدی")
    db.flush()

    book = get_general_ledger(db, _account(db, CURRENT_ASSETS).id, None, None)
    row = next(line for line in book["lines"] if line["description"] == "دریافتِ نقدی")
    assert row["account_code"] == "1101"
    assert row["account_name"] == cash.name


def test_the_closing_balance_equals_the_sum_of_the_leaves(db, user):
    """جمعِ سرفصل باید دقیقاً جمعِ برگ‌هایش باشد — نه کمتر، نه دو برابر."""
    cash = _account(db, "1101")
    bank = _account(db, "1102")
    _post(db, user, day=1, account_id=cash.id, amount=100)
    _post(db, user, day=2, account_id=bank.id, amount=250)
    db.flush()

    heading = get_general_ledger(db, _account(db, CURRENT_ASSETS).id, None, None)
    leaves = sum(
        Decimal(get_general_ledger(db, _account(db, code).id, None, None)["closing_balance"])
        for code in ("1101", "1102", "1103", "1104", "1105", "1106", "1107", "1111")
    )
    assert Decimal(heading["closing_balance"]) == leaves


def test_the_opening_balance_rolls_up_too(db, user):
    """مانده‌ی پیش از بازه هم باید از همه‌ی زیرحساب‌ها بیاید، نه فقط یکی."""
    cash = _account(db, "1101")
    bank = _account(db, "1102")
    _post(db, user, day=1, account_id=cash.id, amount=100)
    _post(db, user, day=2, account_id=bank.id, amount=250)
    _post(db, user, day=20, account_id=cash.id, amount=7)
    db.flush()

    book = get_general_ledger(db, _account(db, CURRENT_ASSETS).id, date(2026, 6, 10), None)
    assert Decimal(book["opening_balance"]) == Decimal(350)
    assert all(line["entry_date"] >= date(2026, 6, 10) for line in book["lines"])


def test_two_sub_accounts_in_one_entry_stay_two_rows(db, user):
    """دفتر ردیف‌ها را ادغام نمی‌کند؛ هر ردیفِ سند ردیفِ خودش را دارد."""
    cash = _account(db, "1101")
    bank = _account(db, "1102")
    equity = get_account(db, cc.RETAINED_EARNINGS)
    make_journal_entry(
        db,
        date(2026, 6, 3),
        "دو زیرحساب در یک سند",
        "manual",
        user,
        [
            JournalLine(account_id=cash.id, debit=Decimal(40), credit=0),
            JournalLine(account_id=bank.id, debit=Decimal(60), credit=0),
            JournalLine(account_id=equity.id, debit=0, credit=Decimal(100)),
        ],
    )
    db.flush()

    book = get_general_ledger(db, _account(db, CURRENT_ASSETS).id, None, None)
    rows = [line for line in book["lines"] if line["account_code"] in {"1101", "1102"}]
    assert len(rows) == 2
    #: مانده‌ی در حال اجرا باید پشتِ سرِ هم جمع شود، نه اینکه هر ردیف از نو شروع کند.
    assert Decimal(rows[-1]["balance"]) == Decimal(100)


# ── چیزی که نباید عوض شود ────────────────────────────────────────────────────


def test_a_leaf_account_behaves_exactly_as_before(db, user):
    """**رگرسیون.** حسابِ برگ نواده ندارد، پس دفترش مو‌به‌مو همان قبل است."""
    cash = _account(db, "1101")
    bank = _account(db, "1102")
    _post(db, user, day=1, account_id=cash.id, amount=100)
    _post(db, user, day=2, account_id=bank.id, amount=250)
    db.flush()

    book = get_general_ledger(db, cash.id, None, None)
    assert {line["account_code"] for line in book["lines"]} == {"1101"}
    assert Decimal(book["closing_balance"]) == Decimal(100)


def test_a_voided_entry_and_its_reversal_both_remain(db, user):
    """**رگرسیون.** دفتر باید نشان دهد اشتباه رخ داد و بعد اصلاح شد.

    همان موضعِ دفترِ روزنامه و `get_legal_book`؛ رول‌آپ نباید بی‌سروصدا فیلترش کند.
    """
    from app.services.voiding import void_journal_entry

    cash = _account(db, "1101")
    entry = _post(db, user, day=1, account_id=cash.id, amount=100)
    db.flush()
    void_journal_entry(db, entry.id, reason="آزمون", user=user, void_date=date(2026, 6, 5))
    db.flush()

    book = get_general_ledger(db, _account(db, CURRENT_ASSETS).id, None, None)
    cash_rows = [line for line in book["lines"] if line["account_code"] == "1101"]
    assert len(cash_rows) == 2  # اصل و معکوسش
    assert sum(Decimal(r["debit"]) - Decimal(r["credit"]) for r in cash_rows) == 0
