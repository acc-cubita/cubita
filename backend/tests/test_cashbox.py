"""صندوق: موجودیتِ عملیاتی، و مانده‌ای که ذخیره نمی‌شود.

تا پیش از این «صندوق» موجودیت نبود — `grep -rn "cashbox" backend/app/` صفر نتیجه
می‌داد. تنها تعریفش یک `if method == "cash": return get_account(cc.CASH)` بود،
یعنی صندوق *همان* حسابِ معین بود و بیش از یکی نمی‌شد داشت.

دو قیدِ اصلیِ این فایل:

* **مانده مشتق است، از دفتر.** نه ستونی که به‌روز شود، نه جمعِ تراکنش‌های خزانه.
  پس هر مسیری که به نقد دست بزند شمرده می‌شود و صندوق نمی‌تواند با تراز واگرا شود.
* **موجودیِ اولیه با مانده‌ی جاری قاطی نمی‌شود.** یکی ابتدای دوره است و دیگری
  نتیجه‌ی هرچه بعدش افتاده — همان تفکیکی که جلوی مغایرت را می‌گیرد.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.jalali import persian_year_end, persian_year_start
from app.models.accounting import JournalLine
from app.models.analytic import AnalyticAccount
from app.models.cashbox import Cashbox
from app.models.inventory import Contact
from app.schemas.fiscal_year import FiscalYearIn
from app.schemas.treasury import TreasuryTransactionIn
from app.services import cashboxes as svc
from app.services import chart_codes as cc
from app.services import fiscal_year as fy
from app.services import treasury as treasury_svc
from app.services.common import get_account, make_journal_entry

TODAY = date(2026, 6, 1)


def _two_years(db) -> None:
    """سالِ ۱۴۰۴ و ۱۴۰۵ — دومی جاری.

    موجودیِ اولیه از گردشِ *پیش از* شروعِ سال می‌آید، و آن گردش باید خودش در یک
    سالِ مالیِ تعریف‌شده بنشیند، وگرنه ثبتش رد می‌شود.
    """
    fy.create_year(
        db, FiscalYearIn(title="۱۴۰۴", start_date=persian_year_start(1404),
                         end_date=persian_year_end(1404), activate=False)
    )
    fy.create_year(
        db, FiscalYearIn(title="۱۴۰۵", start_date=persian_year_start(1405),
                         end_date=persian_year_end(1405), activate=True)
    )


def _contact(db, name="مشتری") -> Contact:
    row = Contact(name=name, type="customer")
    db.add(row)
    db.flush()
    return row


def _analytic(db, user, code, name) -> AnalyticAccount:
    row = AnalyticAccount(code=code, name=name, created_by_id=user.id)
    db.add(row)
    db.flush()
    return row


def _box(db, user, name, code, **kw) -> Cashbox:
    """صندوقِ تفصیلی‌دار — حالتِ عادیِ صندوقِ دوم به بعد."""
    return svc.create_cashbox(
        db, {"name": name, "analytic_id": _analytic(db, user, code, name).id, **kw}
    )


def _receive(db, user, amount, *, box=None, day=TODAY, contact=None):
    return treasury_svc.create_receipt(
        db,
        TreasuryTransactionIn(
            transaction_date=day,
            contact_id=(contact or _contact(db)).id,
            amount=Decimal(amount),
            method="cash",
            cashbox_id=box.id if box else None,
        ),
        user,
    )


def _pay(db, user, amount, *, box=None, day=TODAY):
    return treasury_svc.create_payment(
        db,
        TreasuryTransactionIn(
            transaction_date=day,
            contact_id=_contact(db, "تأمین‌کننده").id,
            amount=Decimal(amount),
            method="cash",
            cashbox_id=box.id if box else None,
        ),
        user,
    )


# ── چند صندوق، چند مانده ────────────────────────────────────────────────────


def test_two_cashboxes_keep_separate_balances(db, user):
    """**قیدِ اصلی.** پیش از این بیش از یک صندوق ممکن نبود."""
    main = svc.get_or_create_default(db)
    branch = _box(db, user, "صندوق شعبه", "C-2")

    _receive(db, user, 20_000_000, box=main)
    _receive(db, user, 5_000_000, box=branch)

    assert svc.balance(db, main) == Decimal(20_000_000)
    assert svc.balance(db, branch) == Decimal(5_000_000)


def test_the_cashboxes_sum_to_the_cash_account(db, user):
    """**قیدِ تطبیق.** جمعِ صندوق‌ها باید با مانده‌ی حسابِ صندوق در دفتر یکی باشد.

    اگر مانده جایی ذخیره می‌شد، این‌جا اولین جایی بود که واگرا می‌شد.
    """
    main = svc.get_or_create_default(db)
    branch = _box(db, user, "صندوق شعبه", "C-2")
    _receive(db, user, 12_000_000, box=main)
    _receive(db, user, 8_000_000, box=branch)
    _pay(db, user, 3_000_000, box=branch)

    cash_id = get_account(db, cc.CASH).id
    rows = db.query(JournalLine).filter(JournalLine.account_id == cash_id).all()
    ledger = sum((Decimal(r.debit) - Decimal(r.credit) for r in rows), Decimal(0))

    assert svc.balance(db, main) + svc.balance(db, branch) == ledger


def test_a_payment_lowers_the_right_cashbox(db, user):
    main = svc.get_or_create_default(db)
    branch = _box(db, user, "صندوق شعبه", "C-2")
    _receive(db, user, 10_000_000, box=branch)
    _pay(db, user, 4_000_000, box=branch)

    assert svc.balance(db, branch) == Decimal(6_000_000)
    assert svc.balance(db, main) == 0, "صندوقِ دیگر نباید تکان بخورد"


# ── مانده مشتق است، نه ذخیره ────────────────────────────────────────────────


def test_a_manual_entry_moves_the_cashbox_balance(db, user):
    """**اثباتِ مشتق‌بودن.** سندِ دستی هیچ‌وقت از مسیرِ خزانه رد نمی‌شود؛ اگر مانده
    ذخیره شده بود، این‌جا دیده نمی‌شد."""
    branch = _box(db, user, "صندوق شعبه", "C-2")
    cash = get_account(db, cc.CASH)
    equity = get_account(db, cc.RETAINED_EARNINGS)
    make_journal_entry(
        db, TODAY, "واریزِ دستی", "manual", user,
        [
            JournalLine(account_id=cash.id, analytic_id=branch.analytic_id,
                        debit=Decimal(7_000_000), credit=0),
            JournalLine(account_id=equity.id, debit=0, credit=Decimal(7_000_000)),
        ],
    )

    assert svc.balance(db, branch) == Decimal(7_000_000)


def test_the_balance_respects_a_date(db, user):
    branch = _box(db, user, "صندوق شعبه", "C-2")
    _receive(db, user, 5_000_000, box=branch, day=TODAY)
    _receive(db, user, 9_000_000, box=branch, day=TODAY + timedelta(days=10))

    assert svc.balance(db, branch, as_of=TODAY) == Decimal(5_000_000)
    assert svc.balance(db, branch) == Decimal(14_000_000)


# ── موجودیِ اولیه در برابر مانده‌ی جاری (§۱۲ §۱۳) ───────────────────────────


def test_opening_balance_is_the_balance_at_the_year_start(db, user):
    """**قیدِ کلیدیِ کاربر.** این دو نباید قاطی شوند."""
    #: سالِ قبل هم لازم است: وقتی سالِ مالی تعریف شده باشد، سندی خارج از هر سال
    #: پذیرفته نمی‌شود — و موجودیِ اولیه ذاتاً از سالِ قبل می‌آید.
    _two_years(db)
    branch = _box(db, user, "صندوق شعبه", "C-2")
    #: پیش از شروعِ سال — این موجودیِ اولیه است.
    _receive(db, user, 6_000_000, box=branch, day=persian_year_start(1405) - timedelta(days=5))
    #: داخلِ سال — این گردشِ دوره است.
    _receive(db, user, 4_000_000, box=branch, day=persian_year_start(1405) + timedelta(days=5))

    assert svc.opening_balance(db, branch) == Decimal(6_000_000)
    assert svc.balance(db, branch) == Decimal(10_000_000)


def test_the_opening_balance_moves_with_the_fiscal_year(db, user):
    """**§۱۲.** موجودیِ اولیه ویژگیِ ابدیِ صندوق نیست."""
    branch = _box(db, user, "صندوق شعبه", "C-2")
    _receive(db, user, 3_000_000, box=branch, day=persian_year_start(1405) - timedelta(days=1))

    fy.create_year(
        db, FiscalYearIn(title="۱۴۰۵", start_date=persian_year_start(1405),
                         end_date=persian_year_end(1405), activate=True)
    )
    assert svc.opening_balance(db, branch) == Decimal(3_000_000)

    #: سالِ بعد، همان پول دیگر «گردشِ پیش از دوره» است — ولی موجودیِ اولیه‌ی
    #: ۱۴۰۶ شاملِ گردشِ ۱۴۰۵ هم می‌شود.
    _receive(db, user, 5_000_000, box=branch, day=persian_year_start(1405) + timedelta(days=10))
    fy.create_year(
        db, FiscalYearIn(title="۱۴۰۶", start_date=persian_year_start(1406),
                         end_date=persian_year_end(1406), activate=True)
    )
    assert svc.opening_balance(db, branch) == Decimal(8_000_000)


def test_without_a_fiscal_year_the_opening_balance_is_zero(db, user):
    """دوره‌ای در کار نیست، پس «ابتدای دوره» معنایی ندارد."""
    branch = _box(db, user, "صندوق شعبه", "C-2")
    _receive(db, user, 2_000_000, box=branch)
    assert svc.opening_balance(db, branch) == 0


# ── گاردها ──────────────────────────────────────────────────────────────────


def test_an_operation_before_the_opening_date_is_rejected(db, user):
    """**§۱۴.** صندوق آن روز اصلاً وجود نداشته."""
    branch = _box(db, user, "صندوق شعبه", "C-2", opening_date=TODAY)

    with pytest.raises(HTTPException) as err:
        _receive(db, user, 1_000_000, box=branch, day=TODAY - timedelta(days=1))
    assert err.value.status_code == 400


def test_an_inactive_cashbox_is_not_selectable(db, user):
    """**§۱۶.** برای عملیاتِ تازه نه — ولی سوابقش می‌ماند."""
    branch = _box(db, user, "صندوق شعبه", "C-2")
    _receive(db, user, 5_000_000, box=branch)
    svc.update_cashbox(db, branch.id, {"is_active": False})

    with pytest.raises(HTTPException):
        _receive(db, user, 1_000_000, box=branch)

    assert svc.balance(db, branch) == Decimal(5_000_000), "سابقه باید بماند"


def test_a_used_cashbox_cannot_be_deleted(db, user):
    """**§۱۷.** حذفِ فیزیکی تاریخچه‌ی مالی را بی‌صاحب می‌کند."""
    branch = _box(db, user, "صندوق شعبه", "C-2")
    _receive(db, user, 5_000_000, box=branch)

    with pytest.raises(HTTPException) as err:
        svc.delete_cashbox(db, branch.id)
    assert "غیرفعال" in str(err.value.detail)


def test_an_unused_cashbox_can_be_deleted(db, user):
    branch = _box(db, user, "صندوقِ بی‌استفاده", "C-9")
    svc.delete_cashbox(db, branch.id)
    assert db.get(Cashbox, branch.id) is None


def test_one_analytic_cannot_serve_two_cashboxes(db, user):
    """وگرنه مانده‌ی دو صندوق یک عدد می‌شد."""
    shared = _analytic(db, user, "C-X", "مشترک")
    svc.create_cashbox(db, {"name": "اولی", "analytic_id": shared.id})

    with pytest.raises(HTTPException):
        svc.create_cashbox(db, {"name": "دومی", "analytic_id": shared.id})


def test_a_second_cashbox_needs_an_analytic(db, user):
    """بدونِ تفصیلی، صندوقِ دوم مانده‌ی جدا ندارد."""
    svc.get_or_create_default(db)
    with pytest.raises(HTTPException) as err:
        svc.create_cashbox(db, {"name": "بی‌تفصیلی"})
    assert "تفصیلی" in str(err.value.detail)


# ── داده‌ی مستقر نباید بشکند ────────────────────────────────────────────────


def test_a_cash_receipt_without_a_cashbox_still_works(db, user):
    """**رگرسیونِ کلیدی.** APIهای موجود `cashbox_id` نمی‌فرستند."""
    txn = _receive(db, user, 8_000_000)

    default = svc.get_or_create_default(db)
    assert txn.cashbox_id == default.id
    assert svc.balance(db, default) == Decimal(8_000_000)


def test_the_default_cashbox_owns_untagged_cash(db, user):
    """صندوقِ پیش‌فرض تفصیلی ندارد، پس ردیف‌های بی‌تفصیلیِ امروز مالِ اوست —
    و همین است که backfill را لازم نمی‌کند."""
    cash = get_account(db, cc.CASH)
    equity = get_account(db, cc.RETAINED_EARNINGS)
    make_journal_entry(
        db, TODAY, "نقدِ قدیمیِ بی‌تفصیلی", "manual", user,
        [
            JournalLine(account_id=cash.id, debit=Decimal(15_000_000), credit=0),
            JournalLine(account_id=equity.id, debit=0, credit=Decimal(15_000_000)),
        ],
    )

    default = svc.get_or_create_default(db)
    assert default.analytic_id is None
    assert svc.balance(db, default) == Decimal(15_000_000)


# ── فهرست ───────────────────────────────────────────────────────────────────


def test_the_list_shows_both_balances_separately(db, user):
    """**§۱۸.** فهرست هر دو عدد را دارد و قاطی‌شان نمی‌کند."""
    _two_years(db)
    branch = _box(db, user, "صندوق شعبه", "C-2")
    _receive(db, user, 6_000_000, box=branch, day=persian_year_start(1405) - timedelta(days=3))
    _receive(db, user, 4_000_000, box=branch, day=persian_year_start(1405) + timedelta(days=3))

    row = next(r for r in svc.list_cashboxes(db) if r["id"] == branch.id)
    assert row["opening_balance"] == Decimal(6_000_000)
    assert row["balance"] == Decimal(10_000_000)
    assert row["analytic_code"] == "C-2"


def test_a_foreign_currency_cashbox_keeps_its_own_currency(db, user):
    """**§۲۱.** ارزها جمع نمی‌شوند — فهرست هم جمعِ کل نمی‌دهد."""
    _box(db, user, "صندوق دلاری", "C-USD", currency_code="USD")
    rows = svc.list_cashboxes(db)
    codes = {r["currency_code"] for r in rows}
    assert "USD" in codes
