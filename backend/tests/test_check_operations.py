"""عملیاتِ چک — واگذاری، نقد کردن، تاریخچه، و عملیاتِ گروهی.

`test_check_lifecycle.py` گذرهای پایه را می‌بندد. این فایل چیزهایی را می‌بندد که
پیش از مهاجرتِ ۰۱۱۰ اصلاً وجود نداشتند:

* واگذاری در دفتر دیده شود (§۹ §۱۳)،
* چک بتواند نقد شود و پولش به صندوق برود (§۱۸-۲۰)،
* هر گذر ردی از خودش بگذارد (§۳۵ §۳۶ §۴۶)،
* یک عملیات چند چک را ببرد و نتیجه‌ی هر کدام جدا باشد (§۴۴ §۴۵).
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.accounting import JournalEntry, JournalLine
from app.models.banking import BankAccount, BankTransaction
from app.models.cashbox import Cashbox
from app.models.check_event import CheckEvent
from app.models.inventory import Contact
from app.schemas.banking import CheckIn
from app.services import cashboxes
from app.services import chart_codes as cc
from app.services import check_ops as svc
from app.services.common import get_account

TODAY = date(2026, 6, 1)
DUE = TODAY + timedelta(days=10)


# ───────────────────────────────── ساخت‌وسازها ─────────────────────────────────


def _bank(db, name="بانک تست") -> BankAccount:
    gl = get_account(db, cc.BANK)
    bank = BankAccount(
        name=name, bank_name="ملت", account_number="1", iban="IR1", gl_account_id=gl.id
    )
    db.add(bank)
    db.flush()
    return bank


def _contact(db, name="مشتری تست") -> Contact:
    contact = Contact(name=name, type="customer")
    db.add(contact)
    db.flush()
    return contact


def _receivable(db, user, *, number="R-1", amount=1_000_000, **kw) -> object:
    return svc.create_check(
        db,
        CheckIn(
            type="receivable",
            number=number,
            amount=Decimal(amount),
            issue_date=TODAY,
            due_date=DUE,
            **kw,
        ),
        user,
    )


def _balance(db, role: str) -> Decimal:
    account_id = get_account(db, role).id
    rows = db.query(JournalLine).filter(JournalLine.account_id == account_id).all()
    return sum((Decimal(r.debit) - Decimal(r.credit) for r in rows), Decimal(0))


def _account_balance(db, account_id, analytic_id=None) -> Decimal:
    rows = (
        db.query(JournalLine)
        .filter(
            JournalLine.account_id == account_id,
            JournalLine.analytic_id.is_not_distinct_from(analytic_id),
        )
        .all()
    )
    return sum((Decimal(r.debit) - Decimal(r.credit) for r in rows), Decimal(0))


# ───────────────────── واگذاری: طبقه‌بندیِ دوباره، نه وصول ─────────────────────


def test_deposit_reclassifies_instead_of_doing_nothing(db, user):
    """**قلبِ این تغییر (§۹ §۱۳).**

    تا پیش از مهاجرتِ ۰۱۱۰ این گذر هیچ سندی نمی‌زد، پس مبلغِ چک تا لحظه‌ی وصول
    روی «چک‌های دریافتنی» می‌ماند و دفتر نمی‌توانست بگوید چقدرش دستِ بانک است.
    """
    check = _receivable(db, user, amount=1_000_000)
    assert _balance(db, cc.CHECKS_RECEIVABLE) == Decimal(1_000_000)

    svc.update_check_status(db, check.id, "deposited", _bank(db).id, user)

    assert _balance(db, cc.CHECKS_RECEIVABLE) == Decimal(0)
    assert _balance(db, cc.CHECKS_IN_COLLECTION) == Decimal(1_000_000)


def test_deposit_creates_no_bank_value(db, user):
    """واگذاری وصول نیست — بانک هنوز چیزی نگرفته (§۹)."""
    bank = _bank(db)
    check = _receivable(db, user)
    svc.update_check_status(db, check.id, "deposited", bank.id, user)

    assert _account_balance(db, bank.gl_account_id, bank.analytic_id) == Decimal(0)
    assert db.query(BankTransaction).count() == 0


def test_collection_closes_the_in_collection_account(db, user):
    """وصول از حسابِ واسط بستانکار می‌شود، نه از «چک‌های دریافتنی» (§۱۵)."""
    bank = _bank(db)
    check = _receivable(db, user, amount=2_000_000)
    svc.update_check_status(db, check.id, "deposited", bank.id, user)

    svc.update_check_status(db, check.id, "cleared", None, user)

    assert _balance(db, cc.CHECKS_IN_COLLECTION) == Decimal(0)
    assert _balance(db, cc.CHECKS_RECEIVABLE) == Decimal(0)
    assert _account_balance(db, bank.gl_account_id, bank.analytic_id) == Decimal(2_000_000)


def test_dishonor_returns_the_debt_and_closes_the_clearing(db, user):
    """§۱۶ — بانک بالا نمی‌رود؛ طلب به حسابِ مشتری برمی‌گردد."""
    bank = _bank(db)
    check = _receivable(db, user, amount=500_000)
    svc.update_check_status(db, check.id, "deposited", bank.id, user)
    before_receivable = _balance(db, cc.ACCOUNTS_RECEIVABLE)

    svc.update_check_status(db, check.id, "bounced", None, user)

    assert _account_balance(db, bank.gl_account_id, bank.analytic_id) == Decimal(0)
    assert _balance(db, cc.CHECKS_IN_COLLECTION) == Decimal(0)
    assert _balance(db, cc.ACCOUNTS_RECEIVABLE) == before_receivable + Decimal(500_000)


# ──────────────────────────── نقد کردن (§۱۸-۲۰) ────────────────────────────


def test_cashing_puts_the_money_in_the_cashbox_not_the_bank(db, user):
    """§۱۹ — نقد کردن و وصولِ بانکی دو مسیرِ جداست."""
    bank = _bank(db)
    check = _receivable(db, user, amount=700_000)

    svc.update_check_status(db, check.id, "cashed", None, user)

    box = cashboxes.get_or_create_default(db)
    db.refresh(check)
    assert check.status == "cashed"
    assert check.cashbox_id == box.id
    assert _account_balance(db, cashboxes.gl_account_id(db, box), box.analytic_id) == Decimal(700_000)
    assert _account_balance(db, bank.gl_account_id, bank.analytic_id) == Decimal(0)
    assert _balance(db, cc.CHECKS_RECEIVABLE) == Decimal(0)


def test_cashing_a_named_cashbox(db, user):
    """پول به همان صندوقی می‌رود که انتخاب شده، نه پیش‌فرض."""
    box = cashboxes.create_cashbox(db, {"name": "صندوقِ شعبه", "analytic_id": None})
    check = _receivable(db, user, amount=300_000)

    svc.update_check_status(db, check.id, "cashed", None, user, cashbox_id=box.id)

    db.refresh(check)
    assert check.cashbox_id == box.id


def test_a_deposited_cheque_cannot_be_cashed(db, user):
    """§۲۱ — چکی که دستِ بانک است نقد نمی‌شود؛ اول باید برگردد."""
    check = _receivable(db, user)
    svc.update_check_status(db, check.id, "deposited", _bank(db).id, user)

    with pytest.raises(HTTPException) as err:
        svc.update_check_status(db, check.id, "cashed", None, user)
    assert err.value.status_code == 400


def test_a_cashed_cheque_is_a_dead_end(db, user):
    check = _receivable(db, user)
    svc.update_check_status(db, check.id, "cashed", None, user)

    with pytest.raises(HTTPException) as err:
        svc.update_check_status(db, check.id, "deposited", _bank(db).id, user)
    assert err.value.status_code == 400


# ──────────────────────────── استردادِ پرداختنی (§۳۱) ────────────────────────────


def test_payable_refund_uses_payable_accounts(db, user):
    """**تله‌ای که بسته شد.**

    شاخه‌ی `returned` ردیف‌های سمتِ دریافتنی را بی‌قیدوشرط می‌نشاند. تا وقتی
    `issued → returned` بسته بود کسی نمی‌دیدش؛ بازکردنِ گذر بدونِ اصلاحِ ردیف‌ها
    سندی می‌زد که بدهیِ ما را به طلب تبدیل می‌کرد.
    """
    check = svc.create_check(
        db,
        CheckIn(
            type="payable",
            number="P-9",
            amount=Decimal(400_000),
            issue_date=TODAY,
            due_date=DUE,
        ),
        user,
    )
    #: صدور، بدهی را از «حساب‌های پرداختنی» به «اسنادِ پرداختنی» برده بود.
    assert _balance(db, cc.ACCOUNTS_PAYABLE) == Decimal(400_000)
    assert _balance(db, cc.CHECKS_PAYABLE) == Decimal(-400_000)
    before_receivable = _balance(db, cc.ACCOUNTS_RECEIVABLE)

    svc.update_check_status(db, check.id, "returned", None, user)

    #: استرداد دقیقاً معکوسِ صدور است: هر دو حساب به پیش از وجودِ چک برمی‌گردند،
    #: و سمتِ دریافتنی اصلاً دست نمی‌خورد.
    assert _balance(db, cc.ACCOUNTS_PAYABLE) == Decimal(0)
    assert _balance(db, cc.CHECKS_PAYABLE) == Decimal(0)
    assert _balance(db, cc.ACCOUNTS_RECEIVABLE) == before_receivable


# ──────────────────────────── تاریخچه (§۳۵ §۳۶ §۴۶) ────────────────────────────


def test_creation_writes_the_first_event(db, user):
    """بدونِ این، تاریخچه از وسط شروع می‌شد."""
    contact = _contact(db)
    check = _receivable(db, user, contact_id=contact.id)

    (event,) = svc.timeline(db, check.id)
    assert event["operation"] == "receive"
    assert event["from_status"] is None
    assert event["to_status"] == "in_hand"
    assert event["contact_id"] == contact.id
    assert event["journal_entry_id"] is not None


def test_timeline_explains_the_current_state(db, user):
    """§۳۵ — «واخواست‌شده» باید بگوید از چه راهی به اینجا رسیده."""
    bank = _bank(db)
    check = _receivable(db, user)
    svc.update_check_status(db, check.id, "deposited", bank.id, user)
    svc.update_check_status(db, check.id, "bounced", None, user)

    steps = svc.timeline(db, check.id)
    assert [s["operation"] for s in steps] == ["receive", "deposit", "dishonor"]
    assert steps[1]["bank_account_name"] == bank.name
    assert steps[-1]["to_status_label"] == "برگشتی (واخواست)"


def test_two_paths_to_in_hand_are_different_operations(db, user):
    """**§۳۴ در سطحِ تاریخچه.**

    «بازگشت از بانک» و «برگشت از خرج» هر دو به «نزدِ ما» می‌رسند. اگر نامِ عملیات
    را از وضعیتِ مقصد استنتاج می‌کردیم، در تاریخچه یک چیز می‌شدند.
    """
    from_bank = _receivable(db, user, number="R-A")
    svc.update_check_status(db, from_bank.id, "deposited", _bank(db).id, user)
    svc.update_check_status(db, from_bank.id, "in_hand", None, user)

    from_endorse = _receivable(db, user, number="R-B")
    svc.update_check_status(db, from_endorse.id, "endorsed", None, user)
    svc.update_check_status(db, from_endorse.id, "in_hand", None, user)

    assert svc.timeline(db, from_bank.id)[-1]["operation"] == "undeposit"
    assert svc.timeline(db, from_endorse.id)[-1]["operation"] == "return_endorsed"


def test_history_cannot_be_rewritten(db, user):
    """§۴۷ — تاریخچه‌ی واخواست پاک نمی‌شود تا وضعیت تمیزتر به‌نظر برسد."""
    from sqlalchemy.exc import DatabaseError

    check = _receivable(db, user)
    svc.update_check_status(db, check.id, "deposited", _bank(db).id, user)
    event = db.query(CheckEvent).filter(CheckEvent.operation == "deposit").one()

    with pytest.raises(DatabaseError):
        db.query(CheckEvent).filter(CheckEvent.id == event.id).delete(synchronize_session=False)
        db.flush()
    db.rollback()


def test_event_links_to_its_journal(db, user):
    """§۳۷ — از عملیات به سند، و از سند به عملیات."""
    from app.services import entry_source

    check = _receivable(db, user)
    svc.update_check_status(db, check.id, "deposited", _bank(db).id, user)

    step = svc.timeline(db, check.id)[-1]
    entry = db.get(JournalEntry, step["journal_entry_id"])
    assert entry.source_type == "check"
    assert entry_source.SOURCE_MODELS[entry.source_type].__name__ == "CheckEvent"


# ──────────────────────── عملیاتِ گروهی (§۴۴ §۴۵) ────────────────────────


def test_one_operation_can_carry_several_cheques(db, user):
    bank = _bank(db)
    a = _receivable(db, user, number="R-1", amount=50_000)
    b = _receivable(db, user, number="R-2", amount=20_000)
    c = _receivable(db, user, number="R-3", amount=30_000)

    result = svc.run_operation(
        db, user, check_ids=[a.id, b.id, c.id], new_status="deposited", bank_account_id=bank.id
    )

    assert len(result["done"]) == 3
    assert result["failed"] == []
    assert result["total_amount"] == Decimal(100_000)
    assert result["operation"] == "deposit"
    #: همه‌ی ردیف‌ها یک شماره و یک دسته گرفته‌اند.
    events = db.query(CheckEvent).filter(CheckEvent.batch_id == result["batch_id"]).all()
    assert len(events) == 3
    assert {e.operation_no for e in events} == {result["operation_no"]}


def test_one_ineligible_cheque_does_not_sink_the_rest(db, user):
    """§۴۵ — کاربر باید بداند **کدام** چک و **چرا**، نه «عملیات ناموفق»."""
    bank = _bank(db)
    ok = _receivable(db, user, number="R-1", amount=50_000)
    already = _receivable(db, user, number="R-2", amount=20_000)
    svc.update_check_status(db, already.id, "cashed", None, user)

    result = svc.run_operation(
        db, user, check_ids=[ok.id, already.id], new_status="deposited", bank_account_id=bank.id
    )

    assert [r["number"] for r in result["done"]] == ["R-1"]
    assert len(result["failed"]) == 1
    assert result["failed"][0]["check_id"] == already.id
    #: پیام باید شماره‌ی چک و وضعیتِ فارسی‌اش را بگوید (§۴۳).
    assert "R-2" in result["failed"][0]["reason"]
    assert "نقد شده" in result["failed"][0]["reason"]

    db.refresh(ok)
    assert ok.status == "deposited"


def test_an_operation_where_nothing_is_eligible_is_refused(db, user):
    check = _receivable(db, user)
    svc.update_check_status(db, check.id, "cashed", None, user)

    with pytest.raises(HTTPException) as err:
        svc.run_operation(db, user, check_ids=[check.id], new_status="deposited", bank_account_id=_bank(db).id)
    assert err.value.status_code == 400


def test_operation_list_is_the_second_view(db, user):
    """§۴۰ §۴۱ — «چه اتفاقی افتاده»، در برابرِ «الان چه داریم»."""
    bank = _bank(db)
    check = _receivable(db, user, amount=250_000)
    svc.update_check_status(db, check.id, "deposited", bank.id, user)
    svc.update_check_status(db, check.id, "cleared", None, user)

    rows = svc.list_operations(db)
    assert [r["operation"] for r in rows] == ["collect", "deposit", "receive"]
    assert rows[0]["check_number"] == check.number
    assert rows[0]["check_amount"] == Decimal(250_000)

    only_deposits = svc.list_operations(db, operation="deposit")
    assert len(only_deposits) == 1


# ─────────────────────────── پیامِ خطا (§۴۳) ───────────────────────────


def test_invalid_transition_says_why_in_persian(db, user):
    """پیامِ قبلی وضعیت‌ها را با نامِ داخلیِ انگلیسی می‌گفت."""
    check = _receivable(db, user)
    svc.update_check_status(db, check.id, "cashed", None, user)

    with pytest.raises(HTTPException) as err:
        svc.update_check_status(db, check.id, "cleared", None, user)
    message = err.value.detail
    assert "نقد شده" in message
    assert "in_hand" not in message
    assert "cashed" not in message


def test_error_lists_what_is_possible_instead(db, user):
    check = _receivable(db, user)
    with pytest.raises(HTTPException) as err:
        svc.update_check_status(db, check.id, "cleared", None, user)
    #: از «نزدِ ما» می‌شود واگذار کرد، خرج کرد، نقد کرد یا مسترد کرد.
    assert "واگذارشده به بانک" in err.value.detail
    assert "نقد شده" in err.value.detail


# ─────────────────────────── شناسه‌های برگ (§۸ §۲۸) ───────────────────────────


def test_sayad_and_back_number_are_stored(db, user):
    check = _receivable(db, user, sayad_id="۰۰۰۱۲۳۴۵۶۷۸۹۰۱۲۳", back_number="۴۵/۱۲")
    db.refresh(check)
    assert check.sayad_id == "۰۰۰۱۲۳۴۵۶۷۸۹۰۱۲۳"
    assert check.back_number == "۴۵/۱۲"


# ─────────────────────────── قراردادِ اندپوینت (§۴۸) ───────────────────────────


def test_repeated_status_patch_with_one_key_transitions_once(db, user, client):
    """Retry نباید دو گذر و دو سند بسازد."""
    bank = _bank(db)
    check = _receivable(db, user)

    payload = {"status": "deposited", "bank_account_id": str(bank.id)}
    headers = {"Idempotency-Key": "deposit-once"}
    first = client.patch(f"/api/checks/{check.id}/status", json=payload, headers=headers)
    again = client.patch(f"/api/checks/{check.id}/status", json=payload, headers=headers)

    assert first.status_code == 200, first.text
    assert again.status_code == 200, again.text
    assert db.query(CheckEvent).filter(CheckEvent.operation == "deposit").count() == 1


def test_timeline_endpoint_returns_the_steps(db, user, client):
    check = _receivable(db, user)
    svc.update_check_status(db, check.id, "deposited", _bank(db).id, user)

    res = client.get(f"/api/checks/{check.id}/timeline")
    assert res.status_code == 200, res.text
    assert [s["operation"] for s in res.json()] == ["receive", "deposit"]


def test_bulk_endpoint_reports_each_cheque(db, user, client):
    bank = _bank(db)
    ok = _receivable(db, user, number="R-1")
    blocked = _receivable(db, user, number="R-2")
    svc.update_check_status(db, blocked.id, "cashed", None, user)

    res = client.post(
        "/api/check-operations",
        json={
            "check_ids": [str(ok.id), str(blocked.id)],
            "status": "deposited",
            "bank_account_id": str(bank.id),
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert len(body["done"]) == 1
    assert len(body["failed"]) == 1
    assert body["operation_label"] == "واگذاری به بانک"
