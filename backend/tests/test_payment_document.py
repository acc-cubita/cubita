"""اعلامیه‌ی پرداخت: چند ابزار، چرخه‌ی چک، کارمزد و idempotency."""

import pytest
from datetime import date, timedelta
from decimal import Decimal

from fastapi import HTTPException

from app.models.accounting import JournalEntry, JournalLine
from app.models.banking import BankAccount, BankTransaction, Check
from app.models.inventory import Contact
from app.models.payment import Payment, PaymentChequeTransfer
from app.schemas.banking import CheckIn, CheckbookIn
from app.schemas.payments import (
    PaymentBankWithdrawalIn,
    PaymentCashIn,
    PaymentEndorsedChequeIn,
    PaymentIn,
    PaymentPayableChequeIn,
)
from app.services import check_ops, checkbooks, payments
from app.services import chart_codes as cc
from app.services.common import get_account

TODAY = date(2026, 6, 1)


def _contact(db, kind="supplier", name="تأمین‌کننده تست"):
    row = Contact(name=name, type=kind)
    db.add(row)
    db.flush()
    return row


def _bank(db):
    row = BankAccount(
        name="بانک ملت شرکت", bank_name="ملت", account_number="123",
        iban="IR001", gl_account_id=get_account(db, cc.BANK).id,
    )
    db.add(row)
    db.flush()
    return row


def test_multi_instrument_payment_has_one_balanced_journal(db, user):
    supplier = _contact(db)
    bank = _bank(db)
    book = checkbooks.create_checkbook(
        db,
        CheckbookIn(
            bank_account_id=bank.id, serial="PAY-1", first_number="001", last_number="010", issue_date=TODAY
        ),
        user,
    )
    payment = payments.create_payment(
        db,
        PaymentIn(
            payment_type="supplier", contact_id=supplier.id, payment_date=TODAY,
            description="پرداخت ترکیبی", description2="تست",
            cash=[PaymentCashIn(amount=Decimal(100_000))],
            bank_withdrawals=[PaymentBankWithdrawalIn(
                bank_account_id=bank.id, amount=Decimal(200_000), bank_fee=Decimal(5_000), number="W-10"
            )],
            payable_cheques=[PaymentPayableChequeIn(
                checkbook_id=book.id, number="001", amount=Decimal(300_000), due_date=TODAY + timedelta(days=20)
            )],
        ),
        user,
    )

    assert payment.payment_amount == Decimal(600_000)
    assert payment.bank_fee_amount == Decimal(5_000)
    assert payment.settlement_total == Decimal(600_000)
    assert db.query(JournalEntry).filter(JournalEntry.id == payment.journal_entry_id).count() == 1
    lines = db.query(JournalLine).filter(JournalLine.entry_id == payment.journal_entry_id).all()
    assert sum((Decimal(line.debit) for line in lines), Decimal(0)) == Decimal(605_000)
    assert sum((Decimal(line.credit) for line in lines), Decimal(0)) == Decimal(605_000)

    withdrawal = db.query(BankTransaction).filter(BankTransaction.payment_id == payment.id).one()
    assert withdrawal.amount == Decimal(-205_000)
    assert withdrawal.principal_amount == Decimal(200_000)
    assert withdrawal.bank_fee_amount == Decimal(5_000)
    cheque = db.query(Check).filter(Check.payment_id == payment.id).one()
    assert cheque.status == "issued"
    assert cheque.number == "001"


def test_endorsing_reuses_the_original_received_cheque(db, user):
    customer = _contact(db, "customer", "مشتری")
    supplier = _contact(db)
    original = check_ops.create_check(
        db,
        CheckIn(
            type="receivable", number="R-500", amount=Decimal(450_000),
            issue_date=TODAY, due_date=TODAY + timedelta(days=10), contact_id=customer.id,
        ),
        user,
    )
    before = db.query(Check).count()
    payment = payments.create_payment(
        db,
        PaymentIn(
            contact_id=supplier.id, payment_date=TODAY,
            description="خرج چک", description2="تست",
            endorsed_cheques=[PaymentEndorsedChequeIn(check_id=original.id)],
        ),
        user,
    )
    db.refresh(original)

    assert db.query(Check).count() == before
    assert original.status == "endorsed"
    transfer = db.query(PaymentChequeTransfer).filter(PaymentChequeTransfer.payment_id == payment.id).one()
    assert transfer.check_id == original.id


def test_used_or_cleared_received_cheque_cannot_be_endorsed(db, user):
    customer = _contact(db, "customer", "مشتری")
    supplier = _contact(db)
    cheque = check_ops.create_check(
        db,
        CheckIn(
            type="receivable", number="R-X", amount=Decimal(10), issue_date=TODAY,
            due_date=TODAY, contact_id=customer.id,
        ),
        user,
    )
    cheque.status = "endorsed"
    db.flush()
    from fastapi import HTTPException
    import pytest

    with pytest.raises(HTTPException) as exc:
        payments.create_payment(
            db,
            PaymentIn(
                contact_id=supplier.id, payment_date=TODAY,
                description="خرج نامعتبر", description2="تست",
                endorsed_cheques=[PaymentEndorsedChequeIn(check_id=cheque.id)],
            ),
            user,
        )
    assert exc.value.status_code == 409


def test_payment_endpoint_replays_same_idempotency_key(db, user, client):
    supplier = _contact(db)
    payload = {
        "payment_type": "supplier", "contact_id": str(supplier.id), "payment_date": TODAY.isoformat(),
        "description": "پرداخت نقدی", "description2": "تست",
        "cash": [{"amount": 120000}],
    }
    first = client.post("/api/payments", json=payload, headers={"Idempotency-Key": "payment-retry-1"})
    second = client.post("/api/payments", json=payload, headers={"Idempotency-Key": "payment-retry-1"})
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["id"] == second.json()["id"]
    assert db.query(Payment).count() == 1


def test_void_restores_endorsed_cheque_and_keeps_history(db, user):
    customer = _contact(db, "customer", "مشتری")
    supplier = _contact(db)
    cheque = check_ops.create_check(
        db,
        CheckIn(
            type="receivable", number="R-V", amount=Decimal(90_000),
            issue_date=TODAY, due_date=TODAY, contact_id=customer.id,
        ),
        user,
    )
    payment = payments.create_payment(
        db,
        PaymentIn(
            contact_id=supplier.id, payment_date=TODAY,
            description="پرداخت قابل ابطال", description2="تست",
            endorsed_cheques=[PaymentEndorsedChequeIn(check_id=cheque.id)],
        ),
        user,
    )
    payments.void_payment(db, payment.id, reason="ثبت اشتباه", user=user)
    db.refresh(cheque)
    db.refresh(payment)
    transfer = db.query(PaymentChequeTransfer).filter(PaymentChequeTransfer.payment_id == payment.id).one()
    assert payment.voided_at is not None
    assert cheque.status == "in_hand"
    assert transfer.reversed_at is not None
    assert db.query(Payment).filter(Payment.id == payment.id).count() == 1


def test_the_payment_sheet_prints_from_the_payment_itself(db, user):
    """قرینه‌ی تستِ چاپِ رسید — تا دو سندِ خواهر یک توان داشته باشند.

    تا پیش از این، اعلامیه تنها سندِ مالیِ کوبیتا بود که چاپ نمی‌شد.
    """
    from app.services.printing import render_payment

    html = render_payment(
        business_name="کسب‌وکارِ آزمون",
        number=7,
        payment_date=TODAY,
        type_label="پرداخت به تأمین‌کننده",
        party_name="تأمین‌کننده",
        party_detail="",
        description="بابت فاکتور خرید",
        components=[
            {"kind": "cash", "label": "صندوق", "amount": Decimal(500), "bank_fee": 0,
             "reference_no": "", "due_date": None, "description": ""},
            {"kind": "bank_withdrawal", "label": "بانک ملت", "amount": Decimal(300),
             "bank_fee": Decimal(5), "reference_no": "W-1", "due_date": TODAY, "description": ""},
        ],
        payment_amount=Decimal(800),
        bank_fee_amount=Decimal(5),
        settlement_total=Decimal(800),
    )
    for label in ("اعلامیه پرداخت", "وجه نقد", "برداشت بانکی", "مبلغ به حروف", "کارمزد بانکی"):
        assert label in html


def test_an_endorsed_cheque_cannot_come_back_behind_the_payment_s_back(db, user):
    """چکِ خرج‌شده با اعلامیه، از مسیرِ صفحه‌ی چک برنمی‌گردد.

    بدونِ این گارد پول گم می‌شد: وضعیت به `in_hand` برمی‌گشت ولی ردیفِ
    `PaymentChequeTransfer` دست‌نخورده می‌ماند، ابطالِ اعلامیه ۴۰۹ می‌گرفت (چون
    گاردش وضعیتِ `endorsed` می‌خواهد)، پس سندِ اعلامیه می‌ماند و بدهی تسویه‌شده
    حساب می‌شد — در حالی که همان چک دوباره قابلِ خرج‌کردن بود.
    """
    customer = _contact(db, "customer", "مشتریِ چک")
    supplier = _contact(db)
    cheque = check_ops.create_check(
        db,
        CheckIn(
            type="receivable", number="R-PLEDGE", amount=Decimal(70_000),
            issue_date=TODAY, due_date=TODAY, contact_id=customer.id,
        ),
        user,
    )
    payment = payments.create_payment(
        db,
        PaymentIn(
            payment_type="supplier", contact_id=supplier.id, payment_date=TODAY,
            description="پرداخت", description2="آزمون",
            endorsed_cheques=[{"check_id": cheque.id}],
        ),
        user,
    )
    db.flush()
    assert cheque.status == "endorsed"

    #: مسیرِ دیگر باید بسته باشد — و پیام باید بگوید به‌جایش چه کند
    with pytest.raises(HTTPException) as err:
        check_ops.update_check_status(db, cheque.id, "in_hand", None, user)
    assert err.value.status_code == 409
    assert "اعلامیه" in err.value.detail

    #: و مسیرِ درست همچنان باز است
    payments.void_payment(db, payment.id, reason="اشتباه", user=user)
    db.refresh(cheque)
    assert cheque.status == "in_hand"

    #: بعد از ابطال، برگشتِ دستی دیگر مسدود نیست — تعهدی نمانده
    events = check_ops.timeline(db, cheque.id)
    assert [e["to_status"] for e in events] == ["in_hand", "endorsed", "in_hand"]


def test_a_cheque_spent_through_a_payment_lands_in_the_timeline(db, user):
    """ثابتِ مهاجرتِ ۰۱۱۰: هر تغییرِ وضعیت یک رویداد دارد — از هر مسیری."""
    customer = _contact(db, "customer", "مشتریِ تایم‌لاین")
    supplier = _contact(db)
    cheque = check_ops.create_check(
        db,
        CheckIn(
            type="receivable", number="R-TL", amount=Decimal(40_000),
            issue_date=TODAY, due_date=TODAY, contact_id=customer.id,
        ),
        user,
    )
    payments.create_payment(
        db,
        PaymentIn(
            payment_type="supplier", contact_id=supplier.id, payment_date=TODAY,
            description="پرداخت", description2="آزمون",
            endorsed_cheques=[{"check_id": cheque.id}],
        ),
        user,
    )
    db.flush()
    events = check_ops.timeline(db, cheque.id)
    endorse = [e for e in events if e["to_status"] == "endorsed"]
    assert len(endorse) == 1, "خرج‌کردن با اعلامیه باید در تایم‌لاین بیفتد"
    #: و به سندِ خودِ اعلامیه اشاره کند، نه به سندِ دوم
    assert endorse[0]["journal_entry_id"] is not None
