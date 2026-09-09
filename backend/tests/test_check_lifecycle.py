"""گرافِ وضعیتِ چک — لبه‌های بازگشت.

چک یک ماشینِ وضعیت است، نه یک پرچمِ `is_paid`. کوبیتا این را از قبل درست مدل کرده
بود و «استرداد» و «برگشتی» و «خرج‌شده» را از هم جدا نگه می‌داشت — ولی گراف **دو
لبه کم داشت** و همان دو، دو حالت را بن‌بست می‌کردند:

* `endorsed` اصلاً کلیدی در جدولِ انتقال نداشت، پس چکی که خرج شده بود تا ابد قفل
  می‌ماند و «برگشت از خرج کردن» ناممکن بود.
* `deposited` راهِ بازگشت نداشت، با آن‌که کامنتِ خودِ جدول و متنِ صفحه‌ی «استرداد
  چک» هر دو وعده‌اش را می‌دادند: «چکی که به بانک واگذار شده اول باید برگردد».

قیدِ اصلیِ این فایل: **رفت‌وبرگشت اثرِ خالص ندارد.** هر لبه‌ی بازگشتی باید دقیقاً
معکوسِ لبه‌ی رفت باشد، وگرنه چرخه از هیچ، بدهی یا طلب می‌سازد.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.accounting import JournalEntry, JournalLine
from app.models.banking import BankAccount, Check
from app.models.inventory import Contact
from app.schemas.banking import CheckIn
from app.services import banking as svc
from app.services import chart_codes as cc
from app.services.common import get_account

TODAY = date(2026, 6, 1)
AMOUNT = Decimal(3_000_000)


def _bank(db) -> BankAccount:
    bank = BankAccount(
        name="بانک تست", bank_name="ملت", account_number="1", iban="IR1",
        gl_account_id=get_account(db, cc.BANK).id,
    )
    db.add(bank)
    db.flush()
    return bank


def _contact(db) -> Contact:
    contact = Contact(name="مشتری تست", type="customer")
    db.add(contact)
    db.flush()
    return contact


def _receivable(db, user, number="R-1") -> Check:
    return svc.create_check(
        db,
        CheckIn(
            type="receivable",
            number=number,
            amount=AMOUNT,
            issue_date=TODAY,
            due_date=TODAY + timedelta(days=20),
            contact_id=_contact(db).id,
        ),
        user,
    )


def _balance(db, role: str) -> Decimal:
    """مانده‌ی خامِ یک حسابِ نقش‌دار — بدهکار منهای بستانکار."""
    account_id = get_account(db, role).id
    rows = db.query(JournalLine).filter(JournalLine.account_id == account_id).all()
    return sum((Decimal(r.debit) - Decimal(r.credit) for r in rows), Decimal(0))


def _last_entry(db) -> JournalEntry:
    return db.query(JournalEntry).order_by(JournalEntry.number.desc()).first()


def _entry_count(db) -> int:
    return db.query(JournalEntry).count()


# ── برگشت از خرج کردن (§۱۷) ─────────────────────────────────────────────────


def test_an_endorsed_check_can_come_back(db, user):
    """**قیدِ اصلی.** پیش از این `endorsed` بن‌بست بود و هر انتقالی رد می‌شد."""
    check = _receivable(db, user)
    svc.update_check_status(db, check.id, "endorsed", None, user)

    svc.update_check_status(db, check.id, "in_hand", None, user)
    db.refresh(check)

    assert check.status == "in_hand"


def test_the_return_entry_reverses_the_endorsement(db, user):
    """سندِ برگشت باید دقیقاً معکوسِ سندِ خرج باشد."""
    check = _receivable(db, user)
    svc.update_check_status(db, check.id, "endorsed", None, user)
    svc.update_check_status(db, check.id, "in_hand", None, user)

    entry = _last_entry(db)
    lines = db.query(JournalLine).filter(JournalLine.entry_id == entry.id).all()
    debited = {line.account_id for line in lines if Decimal(line.debit) > 0}
    credited = {line.account_id for line in lines if Decimal(line.credit) > 0}

    assert "برگشت از خرج" in entry.description
    #: خرج کردن `پرداختنی` را بدهکار و `اسناد دریافتنی` را بستانکار کرد؛ این‌جا برعکس.
    assert get_account(db, cc.CHECKS_RECEIVABLE).id in debited
    assert get_account(db, cc.ACCOUNTS_PAYABLE).id in credited


def test_the_round_trip_nets_to_zero(db, user):
    """**مهم‌ترین تست.** خرج‌کردن و برگشتش نباید از هیچ، بدهی یا طلب بسازد."""
    check = _receivable(db, user)
    before_receivable = _balance(db, cc.CHECKS_RECEIVABLE)
    before_payable = _balance(db, cc.ACCOUNTS_PAYABLE)

    svc.update_check_status(db, check.id, "endorsed", None, user)
    svc.update_check_status(db, check.id, "in_hand", None, user)

    assert _balance(db, cc.CHECKS_RECEIVABLE) == before_receivable
    assert _balance(db, cc.ACCOUNTS_PAYABLE) == before_payable


def test_a_returned_check_can_move_again(db, user):
    """گراف نباید بن‌بستِ تازه بسازد — چک پس از برگشت دوباره در جریان است."""
    check = _receivable(db, user)
    svc.update_check_status(db, check.id, "endorsed", None, user)
    svc.update_check_status(db, check.id, "in_hand", None, user)

    svc.update_check_status(db, check.id, "deposited", _bank(db).id, user)
    db.refresh(check)
    assert check.status == "deposited"


# ── بازگشت از بانک ──────────────────────────────────────────────────────────


def test_a_deposited_check_can_come_back(db, user):
    """کامنتِ جدول و متنِ صفحه‌ی استرداد هر دو این را وعده می‌دادند و نبود."""
    check = _receivable(db, user)
    bank = _bank(db)
    svc.update_check_status(db, check.id, "deposited", bank.id, user)

    svc.update_check_status(db, check.id, "in_hand", None, user)
    db.refresh(check)

    assert check.status == "in_hand"
    assert check.bank_account_id is None, "چک دیگر نزدِ بانک نیست"


def test_coming_back_from_the_bank_makes_no_entry(db, user):
    """واگذاری سندی نزده بود، پس بازگشتش هم نباید بزند.

    سندِ بی‌اثر دفتر را شلوغ می‌کند بی‌آنکه چیزی بگوید.
    """
    check = _receivable(db, user)
    svc.update_check_status(db, check.id, "deposited", _bank(db).id, user)
    before = _entry_count(db)

    svc.update_check_status(db, check.id, "in_hand", None, user)

    assert _entry_count(db) == before


def test_a_check_back_from_the_bank_can_be_returned_to_its_owner(db, user):
    """زنجیره‌ی کاملی که صفحه‌ی «استرداد چک» وعده می‌داد: واگذاری → بازگشت → استرداد."""
    check = _receivable(db, user)
    svc.update_check_status(db, check.id, "deposited", _bank(db).id, user)
    svc.update_check_status(db, check.id, "in_hand", None, user)

    svc.update_check_status(db, check.id, "returned", None, user)
    db.refresh(check)
    assert check.status == "returned"


# ── آنچه نباید عوض شود ──────────────────────────────────────────────────────


def test_the_three_kinds_of_return_stay_distinct(db, user):
    """**رگرسیونِ §۱۸.** استرداد ≠ واخواست ≠ برگشت از خرج."""
    returned = _receivable(db, user, "R-A")
    svc.update_check_status(db, returned.id, "returned", None, user)

    bounced = _receivable(db, user, "R-B")
    svc.update_check_status(db, bounced.id, "deposited", _bank(db).id, user)
    svc.update_check_status(db, bounced.id, "bounced", None, user)

    unendorsed = _receivable(db, user, "R-C")
    svc.update_check_status(db, unendorsed.id, "endorsed", None, user)
    svc.update_check_status(db, unendorsed.id, "in_hand", None, user)

    db.refresh(returned), db.refresh(bounced), db.refresh(unendorsed)
    assert returned.status == "returned"
    assert bounced.status == "bounced"
    assert unendorsed.status == "in_hand"


def test_a_cleared_check_is_still_a_dead_end(db, user):
    """وصول واقعاً پایانِ راه است؛ لبه‌های تازه نباید حالت‌های پایانی را باز کنند."""
    check = _receivable(db, user)
    svc.update_check_status(db, check.id, "deposited", _bank(db).id, user)
    svc.update_check_status(db, check.id, "cleared", None, user)

    with pytest.raises(HTTPException) as err:
        svc.update_check_status(db, check.id, "in_hand", None, user)
    assert err.value.status_code == 400


def test_a_bounced_check_cannot_be_revived(db, user):
    check = _receivable(db, user)
    svc.update_check_status(db, check.id, "deposited", _bank(db).id, user)
    svc.update_check_status(db, check.id, "bounced", None, user)

    with pytest.raises(HTTPException):
        svc.update_check_status(db, check.id, "in_hand", None, user)


def test_a_payable_check_has_no_in_hand(db, user):
    """«نزدِ ما» فقط برای چکِ دریافتی معنی دارد."""
    check = svc.create_check(
        db,
        CheckIn(
            type="payable", number="P-1", amount=AMOUNT,
            issue_date=TODAY, due_date=TODAY + timedelta(days=5),
        ),
        user,
    )
    with pytest.raises(HTTPException):
        svc.update_check_status(db, check.id, "in_hand", None, user)
