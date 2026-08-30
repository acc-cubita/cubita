"""عملیاتِ «دریافت و پرداخت»: دسته‌چک، استردادِ چک، تسویه‌ی کارتخوان.

سه قابلیتی که مهاجرتِ ۰۰۸۴ زیرساختشان را ساخت. هر تست یک قاعده‌ی رفتاری را می‌بندد،
نه صرفاً «کد اجرا شد».
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.accounting import Account
from app.models.banking import BankAccount, Check, Checkbook
from app.models.inventory import Contact
from app.models.treasury import TreasuryTransaction
from app.schemas.banking import CheckbookIn, CheckIn, PosSettlementIn
from app.services import banking as svc
from app.services import chart_codes as cc
from app.services.common import get_account

TODAY = date(2026, 6, 1)


def _bank(db, name="بانک تست") -> BankAccount:
    gl = get_account(db, cc.BANK)
    bank = BankAccount(name=name, bank_name="ملت", account_number="1", iban="IR1", gl_account_id=gl.id)
    db.add(bank)
    db.flush()
    return bank


def _contact(db, name="مشتری تست") -> Contact:
    contact = Contact(name=name, type="customer")
    db.add(contact)
    db.flush()
    return contact


def _book(db, user, bank, **kw) -> Checkbook:
    data = CheckbookIn(
        bank_account_id=bank.id,
        serial=kw.get("serial", "SR-1"),
        first_number=kw.get("first_number", "000101"),
        last_number=kw.get("last_number", "000110"),
        issue_date=TODAY,
    )
    return svc.create_checkbook(db, data, user)


# ── دسته چک ──────────────────────────────────────────────────────────────────


def test_checkbook_counts_leaves_from_the_range(db, user):
    """تعدادِ برگ از بازه‌ی شماره حساب می‌شود؛ کاربر نباید ریاضی کند."""
    book = _book(db, user, _bank(db))
    assert book.leaf_count == 10


def test_checkbook_rejects_duplicate_serial_on_same_account(db, user):
    bank = _bank(db)
    _book(db, user, bank, serial="SR-9")
    with pytest.raises(HTTPException) as e:
        _book(db, user, bank, serial="SR-9")
    assert e.value.status_code == 409


def test_next_number_walks_past_used_leaves(db, user):
    """شماره‌ی بعدی از بزرگ‌ترین شماره‌ی مصرف‌شده جلو می‌رود، نه از شمارِ برگ‌ها.

    اگر کاربر برگی را از وسط خرج کرده باشد، شمارشِ ساده شماره‌ی تکراری پیشنهاد می‌داد.
    """
    bank = _bank(db)
    book = _book(db, user, bank)
    assert svc.next_check_number(db, book.id) == "000101"

    svc.create_check(
        db,
        CheckIn(
            type="payable",
            number="000105",
            amount=Decimal(1_000_000),
            issue_date=TODAY,
            due_date=TODAY + timedelta(days=30),
            checkbook_id=book.id,
        ),
        user,
    )
    assert svc.next_check_number(db, book.id) == "000106"


def test_next_number_is_empty_when_the_book_is_finished(db, user):
    bank = _bank(db)
    book = _book(db, user, bank, first_number="000101", last_number="000101")
    svc.create_check(
        db,
        CheckIn(
            type="payable",
            number="000101",
            amount=Decimal(500_000),
            issue_date=TODAY,
            due_date=TODAY + timedelta(days=10),
            checkbook_id=book.id,
        ),
        user,
    )
    assert svc.next_check_number(db, book.id) == ""


def test_used_checkbook_cannot_be_deleted(db, user):
    """دسته‌ای که برگ خورده سابقه‌ی چک‌هاست؛ حذفش آن‌ها را بی‌ریشه می‌کند."""
    bank = _bank(db)
    book = _book(db, user, bank)
    svc.create_check(
        db,
        CheckIn(
            type="payable",
            number="000101",
            amount=Decimal(1),
            issue_date=TODAY,
            due_date=TODAY,
            checkbook_id=book.id,
        ),
        user,
    )
    with pytest.raises(HTTPException) as e:
        svc.delete_checkbook(db, book.id)
    assert e.value.status_code == 409
    # ولی بستنش همیشه ممکن است
    assert svc.set_checkbook_active(db, book.id, False).is_active is False


def test_checkbook_list_reports_remaining_leaves(db, user):
    bank = _bank(db)
    book = _book(db, user, bank)
    svc.create_check(
        db,
        CheckIn(
            type="payable",
            number="000101",
            amount=Decimal(1),
            issue_date=TODAY,
            due_date=TODAY,
            checkbook_id=book.id,
        ),
        user,
    )
    row = next(r for r in svc.list_checkbooks(db) if r["id"] == book.id)
    assert (row["used_count"], row["remaining_count"]) == (1, 9)
    assert row["bank_account_name"] == bank.name


# ── استردادِ چک ──────────────────────────────────────────────────────────────


def _receivable(db, user, contact) -> Check:
    return svc.create_check(
        db,
        CheckIn(
            type="receivable",
            number="R-1",
            amount=Decimal(3_000_000),
            issue_date=TODAY,
            due_date=TODAY + timedelta(days=20),
            contact_id=contact.id,
        ),
        user,
    )


def test_returning_a_check_moves_the_debt_back_to_receivables(db, user):
    """استرداد دقیقاً معکوسِ لحظه‌ی دریافتِ چک است."""
    contact = _contact(db)
    check = _receivable(db, user, contact)

    svc.update_check_status(db, check.id, "returned", None, user)
    db.refresh(check)
    assert check.status == "returned"

    entry = (
        db.query(Check)
        .filter(Check.id == check.id)
        .one()
    )
    assert entry.status == "returned"

    # سندِ استرداد: بدهکارِ حساب‌های دریافتنی، بستانکارِ اسنادِ دریافتنی
    from app.models.accounting import JournalEntry, JournalLine

    last = db.query(JournalEntry).order_by(JournalEntry.number.desc()).first()
    assert "استرداد" in last.description
    lines = db.query(JournalLine).filter(JournalLine.entry_id == last.id).all()
    debited = {l.account_id for l in lines if Decimal(l.debit) > 0}
    credited = {l.account_id for l in lines if Decimal(l.credit) > 0}
    assert get_account(db, cc.ACCOUNTS_RECEIVABLE).id in debited
    assert get_account(db, cc.CHECKS_RECEIVABLE).id in credited


def test_a_deposited_check_cannot_be_returned(db, user):
    """چکی که به بانک واگذار شده دستِ ما نیست؛ اول باید برگردد."""
    contact = _contact(db)
    check = _receivable(db, user, contact)
    bank = _bank(db)
    svc.update_check_status(db, check.id, "deposited", bank.id, user)

    with pytest.raises(HTTPException) as e:
        svc.update_check_status(db, check.id, "returned", None, user)
    assert e.value.status_code == 400


def test_payable_check_cannot_be_returned(db, user):
    """استرداد فقط برای چکِ دریافتی معنی دارد."""
    check = svc.create_check(
        db,
        CheckIn(
            type="payable",
            number="P-1",
            amount=Decimal(1_000_000),
            issue_date=TODAY,
            due_date=TODAY + timedelta(days=5),
        ),
        user,
    )
    with pytest.raises(HTTPException):
        svc.update_check_status(db, check.id, "returned", None, user)


# ── تسویه‌ی کارتخوان ─────────────────────────────────────────────────────────


def _card_receipt(db, user, contact, bank, *, amount=1_000_000, day=TODAY, terminal="T-1") -> TreasuryTransaction:
    from app.schemas.treasury import TreasuryTransactionIn
    from app.services import treasury as treasury_svc

    return treasury_svc.create_receipt(
        db,
        TreasuryTransactionIn(
            transaction_date=day,
            contact_id=contact.id,
            amount=Decimal(amount),
            method="bank",
            bank_account_id=bank.id,
            description="فروشِ کارتی",
        ),
        user,
        paid_via="pos_terminal",
        reference_no=f"RRN-{amount}-{day}-{terminal}",
        terminal_no=terminal,
    )


def test_pending_groups_card_receipts_by_terminal_and_day(db, user):
    contact = _contact(db)
    bank = _bank(db)
    _card_receipt(db, user, contact, bank, amount=1_000_000)
    _card_receipt(db, user, contact, bank, amount=2_000_000)
    _card_receipt(db, user, contact, bank, amount=500_000, terminal="T-2")

    rows = svc.pos_pending_settlements(db, terminal_no=None, date_from=None, date_to=None)
    by_terminal = {r["terminal_no"]: r for r in rows}
    assert by_terminal["T-1"]["count"] == 2
    assert by_terminal["T-1"]["gross_amount"] == Decimal(3_000_000)
    assert by_terminal["T-2"]["gross_amount"] == Decimal(500_000)


def test_settlement_marks_receipts_and_books_only_the_fee(db, user):
    """مبلغِ ناخالص دوباره ثبت نمی‌شود — فقط کارمزد به هزینه می‌رود.

    رسیدِ کارتی در لحظه‌ی ثبت، بانک را بدهکار کرده. اگر تسویه دوباره ناخالص را
    ثبت می‌کرد، درآمد دو بار می‌آمد.
    """
    from app.models.accounting import JournalEntry

    contact = _contact(db)
    bank = _bank(db)
    _card_receipt(db, user, contact, bank, amount=1_000_000)
    _card_receipt(db, user, contact, bank, amount=2_000_000)
    before = db.query(JournalEntry).count()

    result = svc.settle_pos(
        db,
        PosSettlementIn(
            settlement_date=TODAY,
            date_from=TODAY,
            date_to=TODAY,
            terminal_no="T-1",
            bank_account_id=bank.id,
            fee_amount=Decimal(30_000),
        ),
        user,
    )
    assert result["settled_count"] == 2
    assert result["gross_amount"] == Decimal(3_000_000)
    assert result["net_amount"] == Decimal(2_970_000)

    # یک سند بیشتر، نه دو تا: فقط کارمزد.
    assert db.query(JournalEntry).count() == before + 1
    assert db.query(TreasuryTransaction).filter(TreasuryTransaction.settled_at.is_(None)).count() == 0


def test_zero_fee_settlement_writes_no_entry(db, user):
    """سندِ صفر دفتر را شلوغ می‌کند بی‌آنکه چیزی بگوید."""
    from app.models.accounting import JournalEntry

    contact = _contact(db)
    bank = _bank(db)
    _card_receipt(db, user, contact, bank, amount=800_000)
    before = db.query(JournalEntry).count()

    svc.settle_pos(
        db,
        PosSettlementIn(settlement_date=TODAY, date_from=TODAY, date_to=TODAY, fee_amount=Decimal(0)),
        user,
    )
    assert db.query(JournalEntry).count() == before


def test_already_settled_receipts_are_not_offered_twice(db, user):
    contact = _contact(db)
    bank = _bank(db)
    _card_receipt(db, user, contact, bank, amount=400_000)
    svc.settle_pos(
        db,
        PosSettlementIn(settlement_date=TODAY, date_from=TODAY, date_to=TODAY, fee_amount=Decimal(0)),
        user,
    )
    assert svc.pos_pending_settlements(db, terminal_no=None, date_from=None, date_to=None) == []
    with pytest.raises(HTTPException) as e:
        svc.settle_pos(
            db,
            PosSettlementIn(settlement_date=TODAY, date_from=TODAY, date_to=TODAY, fee_amount=Decimal(0)),
            user,
        )
    assert e.value.status_code == 400


def test_fee_larger_than_gross_is_refused(db, user):
    contact = _contact(db)
    bank = _bank(db)
    _card_receipt(db, user, contact, bank, amount=100_000)
    with pytest.raises(HTTPException) as e:
        svc.settle_pos(
            db,
            PosSettlementIn(
                settlement_date=TODAY,
                date_from=TODAY,
                date_to=TODAY,
                bank_account_id=bank.id,
                fee_amount=Decimal(200_000),
            ),
            user,
        )
    assert e.value.status_code == 400


def test_bank_fee_role_lands_on_the_shared_template_code(db, user):
    """کارمزد روی همان کد ۵۱۱۱ِ قالب‌های صنفی می‌نشیند، نه یک حسابِ دومِ هم‌معنی."""
    contact = _contact(db)
    bank = _bank(db)
    _card_receipt(db, user, contact, bank, amount=1_000_000)
    svc.settle_pos(
        db,
        PosSettlementIn(
            settlement_date=TODAY,
            date_from=TODAY,
            date_to=TODAY,
            bank_account_id=bank.id,
            fee_amount=Decimal(10_000),
        ),
        user,
    )
    fee_account = get_account(db, cc.BANK_FEE)
    assert fee_account.code == "5111"
    assert db.query(Account).filter(Account.code.like("5111%")).count() == 1
