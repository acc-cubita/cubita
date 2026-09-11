"""تسویه‌ی کارت‌خوان — دو مرحله‌ی جدا، و آنچه از جدانبودنشان می‌شکست.

پیش از مهاجرتِ ۰۱۰۹ رسیدِ کارتی مستقیم معینِ بانک را بدهکار می‌کرد. این فایل همان
چیزی را می‌بندد که آن‌وقت نمی‌شد بست:

* پول پیش از رسیدن به بانک روی بانک ننشیند،
* تسویه سند و شماره و ردِ برگشت داشته باشد،
* و «این رسید با کدام تسویه رفت» همیشه جواب داشته باشد — نه فقط وقتی کارمزد
  بزرگ‌تر از صفر است.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import func

from app.models.accounting import Account, JournalEntry, JournalLine
from app.models.banking import BankAccount, BankTransaction
from app.models.inventory import Contact
from app.models.pos_terminal import PosTerminal
from app.models.treasury import TreasuryTransaction
from app.services import card_terminals
from app.services import chart_codes as cc
from app.services import pos_settlements as svc
from app.services.common import get_account

TODAY = date(2026, 6, 1)


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


def _terminal(db, bank, *, no="T-1", label="کارتخوانِ صندوق") -> PosTerminal:
    term = PosTerminal(label=label, terminal_no=no, bank_account_id=bank.id)
    db.add(term)
    db.flush()
    return term


def _card_receipt(db, user, contact, term, *, amount=1_000_000, day=TODAY) -> TreasuryTransaction:
    from app.schemas.treasury import TreasuryTransactionIn
    from app.services import treasury as treasury_svc

    return treasury_svc.create_receipt(
        db,
        TreasuryTransactionIn(
            transaction_date=day,
            contact_id=contact.id,
            amount=Decimal(amount),
            method="bank",
            bank_account_id=term.bank_account_id,
            description="فروشِ کارتی",
        ),
        user,
        paid_via="pos_terminal",
        reference_no=f"RRN-{amount}-{day}-{term.terminal_no}",
        terminal_no=term.terminal_no,
        pos_terminal_id=term.id,
    )


def _account_balance(db, account_id, analytic_id=None) -> Decimal:
    """بدهکار منهای بستانکارِ یک جفتِ (معین، تفصیلی) — همان فرمولِ مانده‌ی بانک."""
    debit, credit = (
        db.query(
            func.coalesce(func.sum(JournalLine.debit), 0),
            func.coalesce(func.sum(JournalLine.credit), 0),
        )
        .filter(
            JournalLine.account_id == account_id,
            JournalLine.analytic_id.is_not_distinct_from(analytic_id),
        )
        .one()
    )
    return Decimal(debit) - Decimal(credit)


def _settle(db, user, term, **kw):
    params = {
        "pos_terminal_id": term.id,
        "settlement_date": TODAY,
        "settle_through": TODAY,
        "fee_amount": Decimal(0),
    }
    params.update(kw)
    return svc.create(db, user, **params)


# ───────────────────────── مرحله‌ی اول: پول هنوز در راه است ─────────────────────


def test_card_receipt_debits_clearing_not_bank(db, user):
    """**قلبِ این تغییر.**

    تا پیش از مهاجرتِ ۰۱۰۹ این تست شکست می‌خورد: مانده‌ی بانک بلافاصله
    ۱٬۰۰۰٬۰۰۰ می‌شد، در حالی که شرکتِ پرداخت هنوز چیزی واریز نکرده بود.
    """
    contact = _contact(db)
    bank = _bank(db)
    term = _terminal(db, bank)
    _card_receipt(db, user, contact, term, amount=1_000_000)

    clearing = svc.clearing_account(db)
    assert _account_balance(db, clearing.id) == Decimal(1_000_000)
    assert _account_balance(db, bank.gl_account_id, bank.analytic_id) == Decimal(0)


def test_cash_and_plain_bank_receipts_are_untouched(db, user):
    """فقط رسیدِ کارتی مسیرش عوض شده؛ واریزِ بانکیِ معمولی همان‌جا می‌ماند."""
    from app.schemas.treasury import TreasuryTransactionIn
    from app.services import treasury as treasury_svc

    contact = _contact(db)
    bank = _bank(db)
    treasury_svc.create_receipt(
        db,
        TreasuryTransactionIn(
            transaction_date=TODAY,
            contact_id=contact.id,
            amount=Decimal(700_000),
            method="bank",
            bank_account_id=bank.id,
        ),
        user,
    )
    assert _account_balance(db, bank.gl_account_id, bank.analytic_id) == Decimal(700_000)
    assert _account_balance(db, svc.clearing_account(db).id) == Decimal(0)


def test_terminal_balance_equals_its_ledger_balance(db, user):
    """عددِ عملیاتیِ دستگاه و مانده‌ی دفتری‌اش باید یکی باشند.

    تا پیش از این نمی‌توانستند — پول در دفتر روی بانک بود. حالا که هر دو از یک
    رویداد می‌آیند، اختلافشان یعنی یکی از دو طرف خراب شده.
    """
    contact = _contact(db)
    bank = _bank(db)
    term = _terminal(db, bank)
    _card_receipt(db, user, contact, term, amount=1_500_000)
    _card_receipt(db, user, contact, term, amount=2_500_000)

    assert card_terminals.unsettled_balance(db, term) == Decimal(4_000_000)
    assert _account_balance(db, svc.clearing_account(db).id, term.analytic_id) == Decimal(4_000_000)


def test_pending_groups_by_terminal_and_day(db, user):
    contact = _contact(db)
    bank = _bank(db)
    t1 = _terminal(db, bank, no="T-1")
    t2 = _terminal(db, bank, no="T-2", label="کارتخوانِ انبار")
    _card_receipt(db, user, contact, t1, amount=1_000_000)
    _card_receipt(db, user, contact, t1, amount=2_000_000)
    _card_receipt(db, user, contact, t2, amount=500_000)

    by_terminal = {r["terminal_no"]: r for r in svc.pending_groups(db)}
    assert by_terminal["T-1"]["count"] == 2
    assert by_terminal["T-1"]["gross_amount"] == Decimal(3_000_000)
    assert by_terminal["T-2"]["gross_amount"] == Decimal(500_000)


# ───────────────────────── مرحله‌ی دوم: تسویه به بانک ─────────────────────────


def test_settlement_moves_money_from_clearing_to_bank(db, user):
    """§۲۳ §۲۶ — بانک بدهکارِ خالص، کارمزد بدهکار، وجوهِ در راه بستانکارِ ناخالص."""
    contact = _contact(db)
    bank = _bank(db)
    term = _terminal(db, bank)
    _card_receipt(db, user, contact, term, amount=1_000_000)
    _card_receipt(db, user, contact, term, amount=2_000_000)

    settlement = _settle(db, user, term, fee_amount=Decimal(30_000))

    assert settlement.gross_amount == Decimal(3_000_000)
    assert settlement.fee_amount == Decimal(30_000)
    assert settlement.net_amount == Decimal(2_970_000)

    #: وجوهِ در راه صفر شده، بانک خالص را گرفته، کارمزد هزینه شده.
    assert _account_balance(db, svc.clearing_account(db).id, term.analytic_id) == Decimal(0)
    assert _account_balance(db, bank.gl_account_id, bank.analytic_id) == Decimal(2_970_000)
    assert _account_balance(db, get_account(db, cc.BANK_FEE).id) == Decimal(30_000)


def test_settlement_does_not_touch_receivable_again(db, user):
    """§۲۴ — طلبِ مشتری در مرحله‌ی اول تسویه شده؛ دوباره کم نمی‌شود."""
    contact = _contact(db)
    bank = _bank(db)
    term = _terminal(db, bank)
    _card_receipt(db, user, contact, term, amount=1_000_000)

    receivable = get_account(db, cc.ACCOUNTS_RECEIVABLE)
    before = _account_balance(db, receivable.id)
    _settle(db, user, term)
    assert _account_balance(db, receivable.id) == before


def test_settlement_creates_no_revenue(db, user):
    """§۲۷ — تسویه جابه‌جاییِ دارایی است، نه فروشِ تازه."""
    contact = _contact(db)
    bank = _bank(db)
    term = _terminal(db, bank)
    _card_receipt(db, user, contact, term, amount=1_000_000)

    revenue = get_account(db, cc.SALES_REVENUE)
    before = _account_balance(db, revenue.id)
    _settle(db, user, term, fee_amount=Decimal(5_000))
    assert _account_balance(db, revenue.id) == before


def test_zero_fee_settlement_still_books_the_transfer(db, user):
    """**تغییرِ رفتارِ عمدی.**

    پیش از این، تسویه‌ی بی‌کارمزد هیچ سندی نمی‌زد — و درست هم بود، چون پول از قبل
    روی بانک نشسته بود. حالا انتقالِ «در راه ← بانک» خودش رویداد است و بدونِ سند،
    پول تا ابد در وجوهِ در راه می‌ماند.
    """
    contact = _contact(db)
    bank = _bank(db)
    term = _terminal(db, bank)
    _card_receipt(db, user, contact, term, amount=800_000)
    before = db.query(JournalEntry).count()

    _settle(db, user, term)

    assert db.query(JournalEntry).count() == before + 1
    assert _account_balance(db, bank.gl_account_id, bank.analytic_id) == Decimal(800_000)
    assert _account_balance(db, svc.clearing_account(db).id, term.analytic_id) == Decimal(0)


def test_zero_fee_settlement_is_still_traceable(db, user):
    """باگی که این ستون برایش ساخته شد.

    `settlement_txn_id` فقط با کارمزدِ مثبت پر می‌شد، پس تسویه‌ی بی‌کارمزد — یعنی
    حالتِ رایج — هیچ ردی نمی‌گذاشت و «این رسید با کدام تسویه رفت؟» بی‌جواب بود.
    """
    contact = _contact(db)
    bank = _bank(db)
    term = _terminal(db, bank)
    receipt = _card_receipt(db, user, contact, term, amount=400_000)

    settlement = _settle(db, user, term)

    db.refresh(receipt)
    assert receipt.settlement_id == settlement.id
    assert [r["id"] for r in svc.related_receipts(db, settlement)] == [receipt.id]


def test_settlement_creates_a_bank_row_for_reconciliation(db, user):
    """§۳۶ — واریزِ واقعیِ PSP باید ردیفِ سیستمی داشته باشد تا تطبیق‌پذیر باشد.

    پیش از این تنها ردیفِ ساخته‌شده «منهای کارمزد» بود؛ صورت‌حسابِ بانک یک واریزِ
    مثبتِ خالص دارد و آن دو هرگز به هم نمی‌خوردند.
    """
    contact = _contact(db)
    bank = _bank(db)
    term = _terminal(db, bank)
    _card_receipt(db, user, contact, term, amount=1_000_000)

    settlement = _settle(db, user, term, fee_amount=Decimal(20_000))

    txn = db.get(BankTransaction, settlement.bank_transaction_id)
    assert txn is not None
    assert Decimal(txn.amount) == Decimal(980_000)
    assert txn.bank_account_id == bank.id


def test_settlement_number_is_its_own_sequence(db, user):
    """§۵ — شماره‌ی تسویه با شماره‌ی سند و شماره‌ی پایانه یکی نیست."""
    contact = _contact(db)
    bank = _bank(db)
    term = _terminal(db, bank)
    _card_receipt(db, user, contact, term, amount=100_000)
    first = _settle(db, user, term)
    _card_receipt(db, user, contact, term, amount=200_000, day=TODAY + timedelta(days=1))
    second = _settle(
        db, user, term, settlement_date=TODAY + timedelta(days=1),
        settle_through=TODAY + timedelta(days=1),
    )
    assert second.number == first.number + 1


def test_settle_through_excludes_later_receipts(db, user):
    """§۹ — برش تاریخ‌دار است؛ رسیدِ بعد از آن در این تسویه نمی‌آید."""
    contact = _contact(db)
    bank = _bank(db)
    term = _terminal(db, bank)
    inside = _card_receipt(db, user, contact, term, amount=100_000, day=TODAY)
    outside = _card_receipt(db, user, contact, term, amount=900_000, day=TODAY + timedelta(days=3))

    settlement = _settle(db, user, term, settle_through=TODAY)

    assert settlement.gross_amount == Decimal(100_000)
    db.refresh(inside)
    db.refresh(outside)
    assert inside.settlement_id == settlement.id
    assert outside.settled_at is None


def test_settlement_date_and_settle_through_stay_separate(db, user):
    """§۸ — مشتری دهم کارت کشیده، بانک یازدهم واریز کرده؛ هر دو باید بمانند."""
    contact = _contact(db)
    bank = _bank(db)
    term = _terminal(db, bank)
    _card_receipt(db, user, contact, term, amount=500_000, day=TODAY)

    settlement = _settle(db, user, term, settlement_date=TODAY + timedelta(days=1))

    assert settlement.settle_through == TODAY
    assert settlement.settlement_date == TODAY + timedelta(days=1)
    entry = db.get(JournalEntry, settlement.journal_entry_id)
    #: سند با تاریخِ *واریز* می‌خورد، نه تاریخِ کارت‌کشی.
    assert entry.entry_date == TODAY + timedelta(days=1)


def test_a_receipt_is_never_settled_twice(db, user):
    """§۱۵ — همان رسید در تسویه‌ی دوم نمی‌آید و تسویه‌ی خالی رد می‌شود."""
    contact = _contact(db)
    bank = _bank(db)
    term = _terminal(db, bank)
    _card_receipt(db, user, contact, term, amount=400_000)
    _settle(db, user, term)

    assert svc.pending_groups(db) == []
    with pytest.raises(HTTPException) as err:
        _settle(db, user, term)
    assert err.value.status_code == 400


def test_fee_larger_than_gross_is_refused(db, user):
    contact = _contact(db)
    bank = _bank(db)
    term = _terminal(db, bank)
    _card_receipt(db, user, contact, term, amount=100_000)
    with pytest.raises(HTTPException) as err:
        _settle(db, user, term, fee_amount=Decimal(200_000))
    assert err.value.status_code == 400


def test_bank_fee_role_lands_on_the_shared_template_code(db, user):
    """کارمزد روی همان کد ۵۱۱۱ِ قالب‌های صنفی می‌نشیند، نه یک حسابِ دومِ هم‌معنی."""
    contact = _contact(db)
    bank = _bank(db)
    term = _terminal(db, bank)
    _card_receipt(db, user, contact, term, amount=1_000_000)
    _settle(db, user, term, fee_amount=Decimal(10_000))

    assert get_account(db, cc.BANK_FEE).code == "5111"
    assert db.query(Account).filter(Account.code.like("5111%")).count() == 1


def test_terminal_without_bank_account_is_refused(db, user):
    """§۶ — حسابِ مقصد از خودِ دستگاه می‌آید؛ نبودش یعنی تسویه نمی‌داند کجا برود."""
    contact = _contact(db)
    bank = _bank(db)
    term = _terminal(db, bank)
    _card_receipt(db, user, contact, term, amount=100_000)
    term.bank_account_id = None
    db.flush()

    with pytest.raises(HTTPException) as err:
        _settle(db, user, term)
    assert err.value.status_code == 400


# ─────────────────────────────────── ابطال ───────────────────────────────────


def test_void_reverses_the_entry_and_frees_the_receipts(db, user):
    """§۳۳ — سابقه پاک نمی‌شود؛ سندِ معکوس می‌خورد و رسیدها دوباره در صف می‌آیند."""
    contact = _contact(db)
    bank = _bank(db)
    term = _terminal(db, bank)
    receipt = _card_receipt(db, user, contact, term, amount=600_000)
    settlement = _settle(db, user, term, fee_amount=Decimal(6_000))

    svc.void(db, settlement.id, user, "بانک واریز را برگرداند")

    db.refresh(settlement)
    db.refresh(receipt)
    assert settlement.voided_at is not None
    assert receipt.settled_at is None
    assert receipt.settlement_id is None

    #: دفتر به حالتِ پیش از تسویه برگشته — پول دوباره در راه است.
    assert _account_balance(db, bank.gl_account_id, bank.analytic_id) == Decimal(0)
    assert _account_balance(db, svc.clearing_account(db).id, term.analytic_id) == Decimal(600_000)
    assert _account_balance(db, get_account(db, cc.BANK_FEE).id) == Decimal(0)

    #: سندِ اصلی سرِ جایش مانده و یک سندِ معکوس کنارش نشسته.
    assert db.get(JournalEntry, settlement.journal_entry_id) is not None
    assert card_terminals.unsettled_balance(db, term) == Decimal(600_000)


def test_voided_receipts_can_be_settled_again(db, user):
    contact = _contact(db)
    bank = _bank(db)
    term = _terminal(db, bank)
    _card_receipt(db, user, contact, term, amount=600_000)
    first = _settle(db, user, term)
    svc.void(db, first.id, user, "اشتباهِ تاریخ")

    second = _settle(db, user, term)
    assert second.gross_amount == Decimal(600_000)
    assert second.id != first.id


def test_void_is_refused_after_bank_reconciliation(db, user):
    """اگر بانک تطبیق داده، ابطال مغایرت‌گیری را با ارجاعِ آویزان رها می‌کند."""
    contact = _contact(db)
    bank = _bank(db)
    term = _terminal(db, bank)
    _card_receipt(db, user, contact, term, amount=600_000)
    settlement = _settle(db, user, term)

    txn = db.get(BankTransaction, settlement.bank_transaction_id)
    txn.is_reconciled = True
    db.flush()

    with pytest.raises(HTTPException) as err:
        svc.void(db, settlement.id, user, "هرچه")
    assert err.value.status_code == 409


def test_void_twice_is_refused(db, user):
    contact = _contact(db)
    bank = _bank(db)
    term = _terminal(db, bank)
    _card_receipt(db, user, contact, term, amount=600_000)
    settlement = _settle(db, user, term)
    svc.void(db, settlement.id, user, "بارِ اول")

    with pytest.raises(HTTPException) as err:
        svc.void(db, settlement.id, user, "بارِ دوم")
    assert err.value.status_code == 409


def test_void_without_reason_is_refused(db, user):
    """ابطالِ بی‌دلیل برای کسی که ماه بعد دفتر را می‌خواند از خودِ اشتباه بدتر است."""
    contact = _contact(db)
    bank = _bank(db)
    term = _terminal(db, bank)
    _card_receipt(db, user, contact, term, amount=600_000)
    settlement = _settle(db, user, term)

    with pytest.raises(HTTPException) as err:
        svc.void(db, settlement.id, user, "   ")
    assert err.value.status_code == 400


# ──────────────────────────────── پیش‌نمایش و فهرست ────────────────────────────


def test_preview_explains_the_amount(db, user):
    """§۱۲ — کاربر باید پیش از ثبت ببیند مبلغ از کدام رسیدها ساخته می‌شود."""
    contact = _contact(db, "آقای کریمی")
    bank = _bank(db)
    term = _terminal(db, bank)
    _card_receipt(db, user, contact, term, amount=300_000)
    _card_receipt(db, user, contact, term, amount=700_000)

    out = svc.preview(db, pos_terminal_id=term.id, settle_through=TODAY)

    assert out["receipt_count"] == 2
    assert out["gross_amount"] == Decimal(1_000_000)
    assert sum(r["amount"] for r in out["receipts"]) == out["gross_amount"]
    assert out["receipts"][0]["contact_name"] == "آقای کریمی"
    assert out["bank_account_name"] == bank.name


def test_list_row_carries_the_drilldown_targets(db, user):
    """§۲۸ §۲۹ — فهرست باید راهِ رفتن به دستگاه، بانک، سند و رسیدها را بدهد."""
    contact = _contact(db)
    bank = _bank(db)
    term = _terminal(db, bank)
    _card_receipt(db, user, contact, term, amount=250_000)
    settlement = _settle(db, user, term)

    (row,) = svc.list_settlements(db)
    assert row["id"] == settlement.id
    assert row["number"] == settlement.number
    assert row["terminal_no"] == "T-1"
    assert row["bank_account_name"] == bank.name
    assert row["settle_through"] == TODAY
    assert row["receipt_count"] == 1
    assert row["journal_entry_id"] == settlement.journal_entry_id
    assert row["bank_transaction_id"] is not None


def test_journal_entry_points_back_to_the_settlement(db, user):
    """نیمه‌ی دومِ ردیابی: از سندِ دفتر به عملیاتی که ساختش."""
    from app.services import entry_source

    contact = _contact(db)
    bank = _bank(db)
    term = _terminal(db, bank)
    _card_receipt(db, user, contact, term, amount=250_000)
    settlement = _settle(db, user, term)

    entry = db.get(JournalEntry, settlement.journal_entry_id)
    assert entry_source.SOURCE_MODELS[entry.source_type].__name__ == "PosSettlement"


# ──────────────────────────── قراردادِ اندپوینت‌ها ────────────────────────────


def test_preview_route_is_not_swallowed_by_the_id_route(db, user, client):
    """`/preview` باید **پیش از** `/{settlement_id}` اعلام شده باشد.

    وگرنه FastAPI رشته‌ی «preview» را شناسه‌ی UUID می‌گیرد و ۴۲۲ می‌دهد — خطایی که
    نه tsc می‌گیردش نه تستِ سرویس، چون سرویس سالم است و فقط مسیریابی خراب.
    """
    contact = _contact(db)
    bank = _bank(db)
    term = _terminal(db, bank)
    _card_receipt(db, user, contact, term, amount=120_000)

    res = client.get(
        "/api/pos-settlements/preview",
        params={"pos_terminal_id": str(term.id), "settle_through": TODAY.isoformat()},
    )
    assert res.status_code == 200, res.text
    assert res.json()["receipt_count"] == 1


def test_settlement_endpoint_round_trip(db, user, client):
    contact = _contact(db)
    bank = _bank(db)
    term = _terminal(db, bank)
    _card_receipt(db, user, contact, term, amount=500_000)

    created = client.post(
        "/api/pos-settlements",
        json={
            "pos_terminal_id": str(term.id),
            "settlement_date": TODAY.isoformat(),
            "settle_through": TODAY.isoformat(),
            "fee_amount": "5000",
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["net_amount"] == "495000"

    listed = client.get("/api/pos-settlements")
    assert listed.status_code == 200
    assert [r["id"] for r in listed.json()] == [body["id"]]

    detail = client.get(f"/api/pos-settlements/{body['id']}")
    assert detail.status_code == 200
    assert len(detail.json()["receipts"]) == 1


def test_repeated_post_with_one_key_creates_one_settlement(db, user, client):
    """ارسالِ دوباره‌ی همان درخواست نباید دو تسویه و دو سند بسازد."""
    from app.models.pos_settlement import PosSettlement

    contact = _contact(db)
    bank = _bank(db)
    term = _terminal(db, bank)
    _card_receipt(db, user, contact, term, amount=500_000)

    payload = {
        "pos_terminal_id": str(term.id),
        "settlement_date": TODAY.isoformat(),
        "settle_through": TODAY.isoformat(),
        "fee_amount": "0",
    }
    headers = {"Idempotency-Key": "settle-once"}
    first = client.post("/api/pos-settlements", json=payload, headers=headers)
    again = client.post("/api/pos-settlements", json=payload, headers=headers)

    assert first.status_code == 201, first.text
    assert again.status_code == 201, again.text
    assert again.json()["id"] == first.json()["id"]
    assert db.query(PosSettlement).count() == 1
