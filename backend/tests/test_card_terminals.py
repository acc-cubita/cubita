"""دستگاهِ کارت‌خوانِ بانکی — اتصال به تراکنش‌ها، موجودیِ عملیاتی و گاردها.

**قیدِ اصلی (§۱۳):** موجودیِ دستگاه با مانده‌ی حسابِ بانکی **یکی نیست و نباید
باشد**. رسیدِ کارتی از همان لحظه بانک را بدهکار می‌کند؛ موجودیِ دستگاه یعنی «چقدر
کشیده شده و PSP هنوز واریزش نکرده». اگر این دو را یکی می‌گرفتیم، همان پول دو بار
شمرده می‌شد.

**چرا دستگاهِ اختصاصی در هر تست:** فیکسچرِ `db` برمی‌گردد ولی تست‌های `client` در
همان مستأجر کامیت می‌کنند، پس شمارشِ مطلق روی داده‌ی مشترک به ترتیبِ اجرا وابسته
می‌شود.
"""
import itertools
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.banking import BankAccount
from app.models.pos_terminal import PosTerminal
from app.models.treasury import TreasuryTransaction
from app.schemas.treasury import CardPaymentIn
from app.services import bank_accounts
from app.services import card_terminals as svc
from app.services import chart_codes as cc
from app.services.common import get_account
from app.services.treasury import record_card_payment

WHEN = date(1405, 3, 10)

_SEQ = itertools.count(1)


def _bank(db, *, currency: str = "IRR") -> BankAccount:
    acct = BankAccount(
        name=f"بانکِ آزمون {next(_SEQ)}",
        gl_account_id=get_account(db, cc.BANK).id,
        currency_code=currency,
    )
    db.add(acct)
    db.flush()
    return acct


def _terminal(db, bank=None, **kw) -> PosTerminal:
    term = PosTerminal(
        label=kw.pop("label", f"کارتخوان {next(_SEQ)}"),
        bank_account_id=(bank or _bank(db)).id,
        **kw,
    )
    db.add(term)
    db.flush()
    db.refresh(term)
    return term


def _contact(db, user):
    from app.models.inventory import Contact

    row = Contact(name=f"مشتری {next(_SEQ)}")
    db.add(row)
    db.flush()
    return row


def _pay(db, user, term, amount, *, contact=None, ref=None):
    return record_card_payment(
        db,
        CardPaymentIn(
            transaction_date=WHEN,
            amount=Decimal(amount),
            pos_terminal_id=term.id,
            contact_id=(contact or _contact(db, user)).id,
            reference_no=ref or f"RRN{next(_SEQ):08d}",
        ),
        user,
    )


# ── موجودیِ دستگاه مانده‌ی بانک نیست ──────────────────────────────────────────


def test_terminal_balance_is_not_the_bank_balance(db, user):
    """**قیدِ §۱۳ — و از مهاجرتِ ۰۱۰۹ معنایش عوض شد.**

    نسخه‌ی قبلیِ این تست می‌گفت هر دو عدد ۱۰٬۰۰۰٬۰۰۰ می‌شوند و کنارش نوشته بود
    «عددها برابرند ولی معناشان یکی نیست». آن برابری خودش نشانه‌ی اشکال بود: پولی
    که شرکتِ پرداخت هنوز واریز نکرده در دفتر روی بانک نشسته بود.

    حالا موجودیِ دستگاه بالاست و بانک هنوز صفر — که همان چیزی است که واقعاً اتفاق
    افتاده.
    """
    bank = _bank(db)
    term = _terminal(db, bank)
    _pay(db, user, term, 10_000_000)

    assert svc.unsettled_balance(db, term) == Decimal(10_000_000)
    assert bank_accounts.balance(db, bank) == Decimal(0)


def test_settlement_moves_the_money_into_the_bank(db, user):
    """تسویه پول را از وجوهِ در راه به بانک می‌برد.

    پیش از ۰۱۰۹ این تست ادعا می‌کرد «بانک تکان نخورد» — چون ناخالص از اول آنجا
    بود. حالا تسویه همان کاری را می‌کند که اسمش می‌گوید.
    """
    from app.services import pos_settlements

    bank = _bank(db)
    term = _terminal(db, bank)
    _pay(db, user, term, 4_000_000)

    pos_settlements.create(
        db,
        user,
        pos_terminal_id=term.id,
        settlement_date=WHEN,
        settle_through=WHEN,
    )

    assert svc.unsettled_balance(db, term) == 0                    # ← دستگاه خالی شد
    assert bank_accounts.balance(db, bank) == Decimal(4_000_000)   # ← پول رسید


def test_balance_is_derived_not_stored(db, user):
    term = _terminal(db)
    assert svc.unsettled_balance(db, term) == 0
    _pay(db, user, term, 300)
    _pay(db, user, term, 700)
    assert svc.unsettled_balance(db, term) == Decimal(1_000)


def test_two_terminals_keep_separate_balances(db, user):
    bank = _bank(db)
    a, b = _terminal(db, bank), _terminal(db, bank)
    _pay(db, user, a, 500)
    _pay(db, user, b, 900)
    assert svc.unsettled_balance(db, a) == Decimal(500)
    assert svc.unsettled_balance(db, b) == Decimal(900)


# ── حساب از خودِ دستگاه می‌آید (§۴) ───────────────────────────────────────────


def test_card_payment_takes_the_bank_account_from_the_terminal(db, user):
    bank = _bank(db)
    term = _terminal(db, bank)
    txn = _pay(db, user, term, 250)

    assert txn.bank_account_id == bank.id
    assert txn.pos_terminal_id == term.id


def test_mismatched_bank_account_is_refused_not_silently_preferred(db, user):
    """اگر کلاینت حسابِ دیگری بفرستد، رد می‌شود — وگرنه کارمزد می‌توانست به
    حسابی بخورد که ناخالص آنجا نرفته بود."""
    term = _terminal(db)
    other = _bank(db)
    with pytest.raises(HTTPException) as err:
        record_card_payment(
            db,
            CardPaymentIn(
                transaction_date=WHEN,
                amount=Decimal(100),
                pos_terminal_id=term.id,
                bank_account_id=other.id,
                contact_id=_contact(db, user).id,
                reference_no=f"RRN{next(_SEQ):08d}",
            ),
            user,
        )
    assert err.value.status_code == 400
    assert "یکی نیست" in err.value.detail


def test_terminal_without_a_bank_account_is_refused(db, user):
    term = PosTerminal(label="بی‌حساب", bank_account_id=None)
    db.add(term)
    db.flush()
    with pytest.raises(HTTPException) as err:
        _pay(db, user, term, 100)
    assert "حسابِ بانکیِ تسویه ندارد" in err.value.detail


def test_legacy_card_payment_without_a_terminal_still_works(db, user):
    """**رگرسیون:** کلاینتِ قدیمی فقط حساب می‌فرستد — نباید بشکند."""
    bank = _bank(db)
    txn = record_card_payment(
        db,
        CardPaymentIn(
            transaction_date=WHEN,
            amount=Decimal(600),
            bank_account_id=bank.id,
            contact_id=_contact(db, user).id,
            reference_no=f"RRN{next(_SEQ):08d}",
        ),
        user,
    )
    assert txn.bank_account_id == bank.id
    assert txn.pos_terminal_id is None


def test_card_payment_with_neither_terminal_nor_account_is_refused(db, user):
    with pytest.raises(HTTPException) as err:
        record_card_payment(
            db,
            CardPaymentIn(
                transaction_date=WHEN,
                amount=Decimal(100),
                contact_id=_contact(db, user).id,
                reference_no=f"RRN{next(_SEQ):08d}",
            ),
            user,
        )
    assert err.value.status_code == 400


# ── رسیدهای قدیمی به شماره‌ی پایانه وصل می‌شوند ───────────────────────────────


def test_legacy_rows_are_matched_by_terminal_number(db, user):
    """رسیدی که کلیدِ خارجی ندارد ولی شماره‌اش می‌خواند، در موجودیِ دستگاه دیده
    می‌شود — همان تطبیقی که صفحه‌ی تسویه از قبل انجام می‌داد."""
    bank = _bank(db)
    term = _terminal(db, bank, terminal_no="TERM-77")
    legacy = record_card_payment(
        db,
        CardPaymentIn(
            transaction_date=WHEN,
            amount=Decimal(1_500),
            bank_account_id=bank.id,
            terminal_no="TERM-77",
            contact_id=_contact(db, user).id,
            reference_no=f"RRN{next(_SEQ):08d}",
        ),
        user,
    )
    assert legacy.pos_terminal_id is None
    assert svc.unsettled_balance(db, term) == Decimal(1_500)


def test_a_numberless_terminal_does_not_claim_numberless_rows(db, user):
    """دستگاهِ بی‌شماره نباید هر رسیدِ بی‌شماره‌ای را مالِ خود بداند."""
    bank = _bank(db)
    term = _terminal(db, bank)  # بدونِ terminal_no
    record_card_payment(
        db,
        CardPaymentIn(
            transaction_date=WHEN,
            amount=Decimal(800),
            bank_account_id=bank.id,
            contact_id=_contact(db, user).id,
            reference_no=f"RRN{next(_SEQ):08d}",
        ),
        user,
    )
    assert svc.unsettled_balance(db, term) == 0


# ── ارز (§۹) ─────────────────────────────────────────────────────────────────


def test_currency_mismatch_with_the_settlement_account_is_refused(db, user):
    usd = _bank(db, currency="USD")
    with pytest.raises(HTTPException) as err:
        svc.create_terminal(
            db, {"label": "ریالی", "currency_code": "IRR", "bank_account_id": usd.id}
        )
    assert err.value.status_code == 400
    assert "نمی‌خواند" in err.value.detail


def test_matching_currency_is_allowed(db, user):
    usd = _bank(db, currency="USD")
    term = svc.create_terminal(
        db, {"label": "دلاری", "currency_code": "USD", "bank_account_id": usd.id}
    )
    assert term.currency_code == "USD"


def test_changing_only_the_account_still_checks_currency(db, user):
    """قید روی *نتیجه* سنجیده می‌شود، نه روی چیزی که فرستاده شده."""
    term = _terminal(db, _bank(db))
    usd = _bank(db, currency="USD")
    with pytest.raises(HTTPException):
        svc.update_terminal(db, term.id, {"bank_account_id": usd.id})


# ── شماره‌ی پایانه ───────────────────────────────────────────────────────────


def test_terminal_number_is_unique_when_present(db, user):
    bank = _bank(db)
    svc.create_terminal(db, {"label": "اولی", "terminal_no": "T-1", "bank_account_id": bank.id})
    with pytest.raises(HTTPException) as err:
        svc.create_terminal(db, {"label": "دومی", "terminal_no": "T-1", "bank_account_id": bank.id})
    assert "تعلق دارد" in err.value.detail


def test_blank_terminal_numbers_do_not_collide(db, user):
    """دستگاه‌های تعریف‌شده‌ی پیش از این مهاجرت شماره ندارند."""
    bank = _bank(db)
    svc.create_terminal(db, {"label": "الف", "terminal_no": "", "bank_account_id": bank.id})
    svc.create_terminal(db, {"label": "ب", "terminal_no": "", "bank_account_id": bank.id})


# ── فعال/غیرفعال و حذف ───────────────────────────────────────────────────────


def test_inactive_terminal_is_refused_for_new_payments(db, user):
    term = _terminal(db, is_active=False)
    with pytest.raises(HTTPException) as err:
        svc.assert_usable(db, term)
    assert "غیرفعال" in err.value.detail


def test_editing_a_terminal_no_longer_reactivates_it(db, user):
    """**رگرسیون.** PATCH شِمای کامل می‌گرفت و پیش‌فرضِ `is_active=True` را
    می‌نشاند، پس ویرایشِ نامِ یک دستگاهِ غیرفعال بی‌صدا فعالش می‌کرد."""
    term = _terminal(db, is_active=False)
    svc.update_terminal(db, term.id, {"label": "نامِ تازه"})
    db.refresh(term)
    assert term.is_active is False
    assert term.label == "نامِ تازه"


def test_used_terminal_is_not_deleted(db, user):
    """§۲۱ — تا امروز حذف هیچ سنجشی نداشت و رکورد بی‌صدا می‌رفت."""
    term = _terminal(db)
    _pay(db, user, term, 100)
    with pytest.raises(HTTPException) as err:
        svc.delete_terminal(db, term.id)
    assert "غیرفعالش کنید" in err.value.detail


def test_unused_terminal_can_be_deleted(db, user):
    term = _terminal(db)
    svc.delete_terminal(db, term.id)
    assert db.get(PosTerminal, term.id) is None


def test_only_one_terminal_stays_default(db, user):
    bank = _bank(db)
    first = svc.create_terminal(db, {"label": "الف", "is_default": True, "bank_account_id": bank.id})
    svc.create_terminal(db, {"label": "ب", "is_default": True, "bank_account_id": bank.id})
    db.refresh(first)
    assert first.is_default is False


# ── فهرست ────────────────────────────────────────────────────────────────────


def test_list_can_be_filtered(db, user):
    bank = _bank(db)
    svc.create_terminal(db, {"label": "شعبه مرکزی", "terminal_no": "T-100", "bank_account_id": bank.id})
    svc.create_terminal(db, {"label": "شعبه دو", "terminal_no": "T-200", "bank_account_id": bank.id})

    assert len(svc.list_terminals(db, search="T-100")) == 1
    assert len(svc.list_terminals(db, search="مرکزی")) == 1
    assert len(svc.list_terminals(db, bank_account_id=bank.id)) >= 2


def test_list_row_carries_the_bank_name_and_balance(db, user):
    bank = _bank(db)
    term = _terminal(db, bank, terminal_no="T-55")
    _pay(db, user, term, 320)

    row = next(r for r in svc.list_terminals(db) if r["id"] == term.id)
    assert row["bank_account_name"] == bank.name
    assert row["unsettled_balance"] == Decimal(320)
    assert row["terminal_no"] == "T-55"
