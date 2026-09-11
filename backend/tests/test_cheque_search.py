"""جستجو و ردیابیِ چک — پیدا کردن، و بعد دنبال‌کردنِ مسیر.

دو قیدِ اصلیِ این فایل:

**۱. رویداد باید بگوید کجا ثبت شده.** تا پیش از مهاجرتِ ۰۱۱۵ تایم‌لاین می‌گفت
«دریافت، فلان تاریخ» ولی نه «در کدام رسید». سؤالِ «این چک با کدام رسید آمد؟»
اولین سؤالِ هر حسابرسی است و هیچ جوابی نداشت.

**۲. «الان کجاست» مشتق است، نه ذخیره‌شده.** ستونِ جدا یعنی عددی که می‌تواند با
وضعیت نخواند — و آن‌وقت صفحه‌ی جستجو چیزی می‌گوید که دفتر تأییدش نمی‌کند.
"""
from datetime import date, timedelta
from decimal import Decimal

from app.models.banking import BankAccount, Check
from app.models.cashbox import Cashbox
from app.models.check_event import CheckEvent
from app.models.inventory import Contact
from app.schemas.banking import CheckIn
from app.schemas.payments import PaymentIn
from app.schemas.receipts import ReceiptCashIn, ReceiptChequeIn, ReceiptIn
from app.services import cashboxes
from app.services import chart_codes as cc
from app.services import check_ops as svc
from app.services import check_search as search
from app.services.common import get_account
from app.services.payments import create_payment
from app.services.receipts import create_receipt

TODAY = date(2026, 6, 1)
DUE = TODAY + timedelta(days=10)


# ───────────────────────────────── ساخت‌وسازها ─────────────────────────────────


def _bank(db, name="بانک تست") -> BankAccount:
    bank = BankAccount(
        name=name, bank_name="ملت", account_number="1", iban="IR1",
        gl_account_id=get_account(db, cc.BANK).id,
    )
    db.add(bank)
    db.flush()
    return bank


def _contact(db, name="مشتری تست", type_="customer") -> Contact:
    contact = Contact(name=name, type=type_)
    db.add(contact)
    db.flush()
    return contact


def _check(db, user, **kw) -> Check:
    data = dict(
        type="receivable", number="CHK-100", amount=Decimal(5_000_000),
        issue_date=TODAY, due_date=DUE,
    )
    data.update(kw)
    return svc.create_check(db, CheckIn(**data), user)


def _numbers(rows) -> set[str]:
    return {c.number for c in rows}


# ───────────────────────────── فیلترها (§۴ §۵ §۹ §۱۰) ─────────────────────────


def test_the_sayad_id_is_searchable(db, user):
    """§۵ — گاهی تنها چیزی که کاربر دارد کدِ صیادیِ روی برگ است.

    فیلترِ قبلی سمتِ کلاینت بود و اصلاً این ستون را نمی‌دید.
    """
    _check(db, user, number="CHK-A", sayad_id="1234567890123456")
    _check(db, user, number="CHK-B", sayad_id="9999999999999999")

    assert _numbers(search.search(db, q="1234567890123456").all()) == {"CHK-A"}


def test_back_number_and_owner_are_searchable(db, user):
    _check(db, user, number="CHK-C", back_number="پ-۵۵", description="")
    _check(db, user, number="CHK-D", owner_name="رضا کریمی")

    assert _numbers(search.search(db, q="پ-۵۵").all()) == {"CHK-C"}
    assert _numbers(search.search(db, q="کریمی").all()) == {"CHK-D"}


def test_the_counterparty_name_is_searchable(db, user):
    """§۷ — کاربر نامِ شرکت را می‌داند، نه شناسه‌اش."""
    contact = _contact(db, name="شرکت الف")
    _check(db, user, number="CHK-E", contact_id=contact.id)
    _check(db, user, number="CHK-F")

    assert _numbers(search.search(db, q="شرکت الف").all()) == {"CHK-E"}


def test_due_date_range(db, user):
    """§۹ — «چک‌های این هفته» و «سررسیدگذشته» از همین فیلتر می‌آیند."""
    _check(db, user, number="CHK-G", due_date=TODAY + timedelta(days=3))
    _check(db, user, number="CHK-H", due_date=TODAY + timedelta(days=40))

    rows = search.search(db, due_from=TODAY, due_to=TODAY + timedelta(days=7)).all()
    assert _numbers(rows) == {"CHK-G"}


def test_amount_range(db, user):
    """§۱۰ — «چک‌های بیشتر از ۵۰۰ میلیون»."""
    _check(db, user, number="CHK-I", amount=Decimal(1_000_000))
    _check(db, user, number="CHK-J", amount=Decimal(900_000_000))

    assert _numbers(search.search(db, amount_min=Decimal(500_000_000)).all()) == {"CHK-J"}


def test_type_and_status_filters(db, user):
    """§۳ — یک موتور، و نوعِ چک یکی از فیلترهاست؛ نه دو موتورِ جدا."""
    _check(db, user, number="CHK-K")
    _check(db, user, number="CHK-L", type="payable")

    assert _numbers(search.search(db, type_="payable").all()) == {"CHK-L"}
    assert _numbers(search.search(db, status="in_hand").all()) == {"CHK-K"}


# ───────────────────────────── «الان کجاست» (§۲۰ §۲۱) ─────────────────────────


def test_a_cheque_in_hand_is_held_by_the_company(db, user):
    check = _check(db, user)
    holder = search.current_holder(db, check)
    assert holder.kind == "company"
    assert holder.label == "نزدِ ما"


def test_a_deposited_cheque_names_the_bank(db, user):
    check = _check(db, user)
    bank = _bank(db, name="بانک ملت — جاری")
    svc.update_check_status(db, check.id, "deposited", bank.id, user)
    db.refresh(check)

    holder = search.current_holder(db, check)
    assert holder.kind == "bank_account"
    assert holder.id == bank.id
    assert "بانک ملت" in holder.label


def test_an_endorsed_cheque_names_the_recipient_not_the_giver(db, user):
    """**تفکیکی که ساده به‌نظر می‌رسد و نیست (§۲۱).**

    `check.contact_id` کسی است که چک را به ما داده و بعد از خرج‌کردن هم همان
    می‌ماند. گیرنده روی **رویدادِ خرج** نشسته. اگر «الان کجاست» از `contact_id`
    خوانده می‌شد، چکِ خرج‌شده می‌گفت دستِ همان کسی است که ازش گرفته‌ایم.
    """
    giver = _contact(db, name="مشتری دهنده")
    taker = _contact(db, name="تأمین‌کننده گیرنده", type_="supplier")
    check = _check(db, user, contact_id=giver.id)
    svc.update_check_status(db, check.id, "endorsed", None, user, contact_id=taker.id)
    db.refresh(check)

    holder = search.current_holder(db, check)
    assert holder.kind == "contact"
    assert holder.id == taker.id
    assert "گیرنده" in holder.label
    #: و صاحبِ اصلی سرِ جایش مانده — چیزی بازنویسی نشده.
    assert check.contact_id == giver.id


def test_a_cashed_cheque_names_the_cashbox(db, user):
    check = _check(db, user)
    box = cashboxes.get_or_create_default(db)
    svc.update_check_status(db, check.id, "cashed", None, user, cashbox_id=box.id)
    db.refresh(check)

    holder = search.current_holder(db, check)
    assert holder.kind == "cashbox"
    assert holder.id == box.id


def test_a_cleared_cheque_has_no_location(db, user):
    """وصول‌شده «جایی» ندارد — وضعیت خودش جواب است."""
    check = _check(db, user)
    svc.update_check_status(db, check.id, "deposited", _bank(db).id, user)
    svc.update_check_status(db, check.id, "cleared", None, user)
    db.refresh(check)

    assert search.current_holder(db, check).kind == "none"


# ───────────────────────────── سندِ منبع (§۱۴ §۱۶) ─────────────────────────────


def test_a_cheque_received_in_a_receipt_points_back_at_it(db, user):
    """**قیدِ اصلی.** «این چک با کدام رسید آمد؟»

    پیش از مهاجرتِ ۰۱۱۵ رویداد فقط می‌گفت «دریافت» و هیچ اشاره‌ای به رسید نداشت،
    پس drill-downِ §۱۴ اصلاً ممکن نبود.
    """
    contact = _contact(db, name="مشتری رسیددار")
    receipt = create_receipt(
        db,
        ReceiptIn(
            receipt_type="customer",
            contact_id=contact.id,
            receipt_date=TODAY,
            cheques=[
                ReceiptChequeIn(
                    amount=Decimal(3_000_000), number="CHK-RCP", bank_name="ملت", due_date=DUE
                )
            ],
        ),
        user,
    )

    check = db.query(Check).filter(Check.number == "CHK-RCP").one()
    timeline = svc.timeline(db, check.id)
    assert len(timeline) == 1
    step = timeline[0]
    assert step["operation"] == "receive"
    assert step["source_type"] == "receipt"
    assert step["source_id"] == receipt.id
    #: شماره هر بار از خودِ سند خوانده می‌شود، نه از کپیِ روی رویداد.
    assert step["source_number"] == int(receipt.number)
    assert step["source_label"] == "رسید دریافت"


def test_a_cheque_spent_in_a_payment_points_back_at_it(db, user):
    """§۱۶ — «خرج شد» بدونِ «در کدام اعلامیه» نیمی از جواب است."""
    giver = _contact(db, name="مشتری الف")
    supplier = _contact(db, name="تأمین‌کننده ب", type_="supplier")
    check = _check(db, user, number="CHK-PAY", contact_id=giver.id)

    payment = create_payment(
        db,
        PaymentIn(
            payment_type="supplier",
            contact_id=supplier.id,
            payment_date=TODAY,
            description="پرداخت با چکِ خرج‌شده",
            description2="آزمون",
            endorsed_cheques=[{"check_id": check.id}],
        ),
        user,
    )

    endorse = [e for e in svc.timeline(db, check.id) if e["operation"] == "endorse"]
    assert len(endorse) == 1
    assert endorse[0]["source_type"] == "payment"
    assert endorse[0]["source_id"] == payment.id
    assert endorse[0]["source_number"] == int(payment.number)


def test_a_directly_recorded_cheque_has_no_source(db, user):
    """`NULL` حقیقت است، نه شکاف: این چک سندِ منبعِ بیرونی ندارد."""
    check = _check(db, user, number="CHK-DIRECT")
    step = svc.timeline(db, check.id)[0]
    assert step["source_type"] is None
    assert step["source_id"] is None


def test_every_event_has_exactly_one_identity(db, user):
    """§۱۶ — یا سندِ منبع، یا شماره‌ی عملیاتِ خودش؛ هیچ رویدادی بی‌هویت نمی‌ماند.

    گذرِ تکی تا امروز هیچ‌کدام را نداشت: نه منبعی، نه شماره‌ای. یعنی رویدادی که
    حسابرسی دنبالش می‌گشت، به سؤالِ «در کدام عملیات؟» جوابی نمی‌داد.
    """
    check = _check(db, user)
    svc.update_check_status(db, check.id, "deposited", _bank(db).id, user)

    deposit = [e for e in svc.timeline(db, check.id) if e["operation"] == "deposit"][0]
    assert deposit["source_type"] is None
    assert deposit["operation_no"] is not None


# ───────────────────────────── تاریخچه‌ی تغییرناپذیر (§۲۹) ────────────────────


def test_a_reversal_adds_an_event_and_removes_none(db, user):
    """§۲۹ — «برگشت از خرج» نباید وانمود کند خرج‌کردنی نبوده."""
    taker = _contact(db, name="گیرنده", type_="supplier")
    check = _check(db, user)
    svc.update_check_status(db, check.id, "endorsed", None, user, contact_id=taker.id)
    svc.update_check_status(db, check.id, "in_hand", None, user)

    operations = [e["operation"] for e in svc.timeline(db, check.id)]
    assert operations == ["receive", "endorse", "return_endorsed"]
    assert db.query(CheckEvent).filter(CheckEvent.check_id == check.id).count() == 3


# ───────────────────────────── KPI و اندپوینت (§۳۴) ───────────────────────────


def test_summary_counts_and_amounts_per_status(db, user):
    _check(db, user, number="CHK-S1", amount=Decimal(1_000_000))
    _check(db, user, number="CHK-S2", amount=Decimal(2_000_000))
    deposited = _check(db, user, number="CHK-S3", amount=Decimal(4_000_000))
    svc.update_check_status(db, deposited.id, "deposited", _bank(db).id, user)

    rows = {r["status"]: r for r in search.summary(db, type_="receivable")}
    assert rows["in_hand"]["count"] == 2
    assert rows["in_hand"]["amount"] == Decimal(3_000_000)
    assert rows["deposited"]["count"] == 1
    assert rows["deposited"]["amount"] == Decimal(4_000_000)


def test_the_search_endpoint_filters_on_the_server(db, user, client):
    """§۲۲ — فیلتر باید روی سرور بیفتد، نه در مرورگر.

    اگر فیلتر سمتِ کلاینت بماند، صفحه‌بندیِ سرور (سقفِ ۲۰۰) یعنی نتیجه‌ی جستجو
    بی‌صدا ناقص می‌شود — دقیقاً همان شکستِ خاموشی که مخزن منعش می‌کند.
    """
    _check(db, user, number="CHK-X1", sayad_id="1111222233334444")
    _check(db, user, number="CHK-X2")
    db.commit()

    body = client.get("/api/checks", params={"q": "1111222233334444"}).json()
    assert [c["number"] for c in body["items"]] == ["CHK-X1"]
    #: و «الان کجاست» در همان ردیف می‌آید (§۲۰).
    assert body["items"][0]["holder_label"] == "نزدِ ما"

    summary_body = client.get("/api/checks/summary", params={"type": "receivable"}).json()
    assert any(r["status"] == "in_hand" and r["count"] == 2 for r in summary_body)
