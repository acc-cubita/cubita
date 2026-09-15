"""تنخواه: صندوق به‌عنوان موجودیت، و استردادِ مانده.

**چه کم بود.** `PettyCashTransaction` یک جدولِ تخت بود با دو نوع
(`charge`, `expense`) و docstringش می‌گفت «یک صندوق تنخواه واحد». سه پیامد:

۱. **تنخواه‌دار جایی ثبت نمی‌شد.** عوض‌شدنش هیچ ردی نداشت، چون صندوقی به‌عنوان
   موجودیت وجود نداشت که تاریخچه داشته باشد (قاعده ۶۳).
۲. **استردادِ ماندهٔ تنخواه هیچ مسیری نداشت.** تنها راهش ثبتِ یک «هزینه»ی جعلی
   بود — و دفتر آن را هزینه می‌دید، پس هم سود و زیان غلط می‌شد و هم گزارشِ
   تنخواه (قاعده ۶۴).
۳. هیچ پیوندی به مدرکِ پشتوانه (قاعده ۶۵).
"""
from datetime import date
from decimal import Decimal

from app.models.accounting import Account
from app.models.banking import PettyCashFund, PettyCashTransaction
from app.schemas.banking import PettyCashChargeIn, PettyCashExpenseIn, PettyCashReturnIn
from app.services import chart_codes as cc
from app.services.banking import (
    create_petty_cash_charge,
    create_petty_cash_expense,
    create_petty_cash_return,
    get_petty_cash_balance,
)
from app.services.common import get_account

import pytest
from fastapi import HTTPException

TODAY = date(2026, 3, 15)


def _leaf(db, exclude_role=None) -> Account:
    q = db.query(Account).filter(Account.is_group.is_(False))
    if exclude_role:
        q = q.filter(Account.system_role.isnot(None) | Account.system_role.is_(None))
    return q.first()


def _fund(db, **kw) -> PettyCashFund:
    kw.setdefault("name", f"تنخواه {len(db.query(PettyCashFund).all())}")
    row = PettyCashFund(**kw)
    db.add(row)
    db.flush()
    return row


def _charge(db, user, amount=10_000_000, **kw):
    return create_petty_cash_charge(
        db,
        PettyCashChargeIn(
            transaction_date=TODAY,
            amount=Decimal(amount),
            source_account_id=get_account(db, cc.CASH).id,
            **kw,
        ),
        user,
    )


# ─────────── صندوق به‌عنوان موجودیت ───────────


def test_a_fund_keeps_its_identity_when_the_custodian_changes(db, user):
    """**قاعده ۶۳.** تعویضِ تنخواه‌دار نباید هویت یا تاریخچه‌ی صندوق را بازنویسی کند."""
    from app.models.inventory import Contact

    first = Contact(name="تنخواه‌دار اول", type="customer")
    second = Contact(name="تنخواه‌دار دوم", type="customer")
    db.add_all([first, second])
    db.flush()

    fund = _fund(db, custodian_contact_id=first.id)
    txn = _charge(db, user, fund_id=fund.id)
    fund_id, txn_id = fund.id, txn.id

    fund.custodian_contact_id = second.id
    db.flush()

    assert fund.id == fund_id, "*** هویتِ صندوق عوض شد ***"
    assert db.get(PettyCashTransaction, txn_id).fund_id == fund_id


def test_a_transaction_lands_on_its_fund(db, user):
    fund = _fund(db)
    assert _charge(db, user, fund_id=fund.id).fund_id == fund.id


def test_the_single_active_fund_is_used_when_none_is_given(db, user):
    """رابطِ مستقر `fund_id` نمی‌فرستد؛ اجباری‌کردنش آن را می‌شکست."""
    fund = _fund(db)
    assert _charge(db, user).fund_id == fund.id


def test_two_active_funds_force_an_explicit_choice(db, user):
    """**حدس‌زدن یعنی پول از صندوقِ اشتباه کم شود.**"""
    _fund(db, name="تنخواه دفتر")
    _fund(db, name="تنخواه انبار")

    with pytest.raises(HTTPException) as err:
        _charge(db, user)
    assert err.value.status_code == 400
    assert "کدام صندوق" in err.value.detail


def test_an_inactive_fund_is_refused(db, user):
    fund = _fund(db, is_active=False)
    with pytest.raises(HTTPException) as err:
        _charge(db, user, fund_id=fund.id)
    assert err.value.status_code == 409


# ─────────── استردادِ مانده ───────────


def test_returning_the_balance_is_not_an_expense(db, user):
    """**هسته‌ی این فصل.**

    استرداد باید حسابِ مقصد را بدهکار کند و تنخواه را بستانکار — دقیقاً معکوسِ
    شارژ. اگر هزینه ثبت می‌شد، سود و زیان به همان اندازه غلط می‌شد.
    """
    fund = _fund(db)
    _charge(db, user, amount=10_000_000, fund_id=fund.id)

    destination = get_account(db, cc.CASH)
    txn = create_petty_cash_return(
        db,
        PettyCashReturnIn(
            transaction_date=TODAY,
            amount=Decimal(4_000_000),
            destination_account_id=destination.id,
            fund_id=fund.id,
        ),
        user,
    )
    assert txn.type == "return_balance"

    from app.models.accounting import JournalEntry

    entry = db.get(JournalEntry, txn.journal_entry_id)
    debited = [line for line in entry.lines if line.debit]
    credited = [line for line in entry.lines if line.credit]
    assert debited[0].account_id == destination.id
    assert credited[0].account_id == get_account(db, cc.PETTY_CASH).id, (
        "*** استرداد، تنخواه را بستانکار نکرد ***"
    )


def test_the_balance_drops_after_a_return(db, user):
    """**تله‌ای که نزدیک بود جا بماند.**

    `get_petty_cash_balance` فقط `charge` و `expense` را می‌شمرد. با نوعِ سوم،
    پولی که برگشته بود همچنان در تنخواه شمرده می‌شد.
    """
    fund = _fund(db)
    before = get_petty_cash_balance(db)
    _charge(db, user, amount=10_000_000, fund_id=fund.id)
    assert get_petty_cash_balance(db) == before + 10_000_000

    create_petty_cash_return(
        db,
        PettyCashReturnIn(
            transaction_date=TODAY,
            amount=Decimal(4_000_000),
            destination_account_id=get_account(db, cc.CASH).id,
            fund_id=fund.id,
        ),
        user,
    )
    assert get_petty_cash_balance(db) == before + 6_000_000, (
        "*** استرداد از ماندهٔ تنخواه کم نشد ***"
    )


def test_returning_more_than_the_balance_is_refused(db, user):
    """دارایی‌ای با ماندهٔ منفی هیچ معنای حسابداری ندارد."""
    fund = _fund(db)
    balance = get_petty_cash_balance(db)

    with pytest.raises(HTTPException) as err:
        create_petty_cash_return(
            db,
            PettyCashReturnIn(
                transaction_date=TODAY,
                amount=Decimal(balance) + Decimal(1_000_000),
                destination_account_id=get_account(db, cc.CASH).id,
                fund_id=fund.id,
            ),
            user,
        )
    assert err.value.status_code == 400
    assert "کافی نیست" in err.value.detail


def test_the_balance_is_per_fund_when_asked(db, user):
    office = _fund(db, name="تنخواه دفتر")
    store = _fund(db, name="تنخواه انبار")
    _charge(db, user, amount=7_000_000, fund_id=office.id)
    _charge(db, user, amount=3_000_000, fund_id=store.id)

    assert get_petty_cash_balance(db, office.id) == 7_000_000
    assert get_petty_cash_balance(db, store.id) == 3_000_000


# ─────────── مدرکِ پشتوانه ───────────


def test_an_expense_can_carry_its_evidence(db, user):
    """قاعده ۶۵ — تا امروز فقط یک شرحِ متنی بود."""
    fund = _fund(db)
    _charge(db, user, amount=5_000_000, fund_id=fund.id)
    txn = create_petty_cash_expense(
        db,
        PettyCashExpenseIn(
            transaction_date=TODAY,
            amount=Decimal(1_000_000),
            expense_account_id=get_account(db, cc.BANK_FEE).id,
            evidence_ref="فاکتور ۱۲۳۴",
            fund_id=fund.id,
        ),
        user,
    )
    assert txn.evidence_ref == "فاکتور ۱۲۳۴"


def test_evidence_is_optional_and_defaults_to_blank(db, user):
    """خالی یعنی «مدرکی ثبت نشده» — گزارش‌شدنی، برخلافِ امروز که جایی نداشت."""
    fund = _fund(db)
    assert _charge(db, user, fund_id=fund.id).evidence_ref == ""
