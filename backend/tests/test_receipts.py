"""رسید دریافت — یک رویداد، چند ابزار، یک سند.

**قیدِ اصلی (§۶ §۲۴ §۳۰):** یک رسید می‌تواند هم‌زمان نقد و حواله و کارت‌خوان و چک
داشته باشد، و همه‌ی آن‌ها **یک** سندِ حسابداری می‌سازند که هر ردیفش به حسابِ
ماهیتِ خودش می‌خورد. تا پیش از مهاجرتِ ۰۱۰۹ رسید سربرگ نداشت، پس
`TreasuryTransaction.method` عملاً می‌گفت «یک رسید، یک ابزار».

**مرزی که این فایل قفلش می‌کند:** چک جزءِ خزانه **نمی‌شود**. یک `Check` واقعی با
چرخه‌ی عمرِ مستقل می‌ماند (§۱۰ §۱۳)، چون `contact_balance` چک را جداگانه می‌شمارد
و جزءِ خزانه‌کردنش یعنی هر چکِ دریافتی دو بار از مانده کم شود.

**چرا تاریخِ ثابتِ ۱۴۰۵:** تست‌های `client` در همان مستأجر کامیت می‌کنند، پس
شمارشِ مطلق روی داده‌ی مشترک به ترتیبِ اجرا وابسته می‌شود. هر تست ابزارهای
اختصاصیِ خودش را می‌سازد و فقط دلتا را می‌سنجد.
"""
import itertools
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.accounting import JournalEntry, JournalLine
from app.models.banking import BankAccount, Check
from app.models.cashbox import Cashbox
from app.models.inventory import Contact
from app.models.pos_terminal import PosTerminal
from app.models.receipt import Receipt
from app.models.treasury import TreasuryTransaction
from app.schemas.receipts import (
    ReceiptCardIn,
    ReceiptCashIn,
    ReceiptChequeIn,
    ReceiptIn,
    ReceiptTransferIn,
)
from app.services import chart_codes as cc
from app.services import receipts as svc
from app.services.check_ops import update_check_status
from app.services.common import get_account
from app.services.reports import contact_balance

TODAY = date(1405, 6, 20)
_SEQ = itertools.count(1)


# ── ابزارها ──────────────────────────────────────────────────────────────────


def _contact(db) -> Contact:
    row = Contact(name=f"مشتریِ آزمون {next(_SEQ)}", type="customer")
    db.add(row)
    db.flush()
    return row


def _bank(db) -> BankAccount:
    acct = BankAccount(
        name=f"بانکِ آزمون {next(_SEQ)}",
        gl_account_id=get_account(db, cc.BANK).id,
    )
    db.add(acct)
    db.flush()
    return acct


def _cashbox(db) -> Cashbox:
    box = Cashbox(name=f"صندوقِ آزمون {next(_SEQ)}")
    db.add(box)
    db.flush()
    return box


def _terminal(db, bank=None) -> PosTerminal:
    term = PosTerminal(
        label=f"کارتخوانِ آزمون {next(_SEQ)}",
        bank_account_id=(bank or _bank(db)).id,
        terminal_no=f"T{next(_SEQ):06d}",
    )
    db.add(term)
    db.flush()
    return term


def _discount_account(db):
    """حسابِ تخفیف را کاربر می‌دهد — کوبیتا نقشِ سیستمیِ «تخفیف» ندارد و ساختنِ
    یکی یعنی حدس‌زدنِ چیزی که چارتِ هر کسب‌وکار جورِ خودش می‌چیند."""
    from app.models.accounting import Account

    row = Account(
        code=f"59{next(_SEQ):04d}",
        name=f"تخفیفِ تسویه {next(_SEQ)}",
        type="expense",
        parent_id=None,
    )
    db.add(row)
    db.flush()
    return row


def _sayad() -> str:
    return f"{next(_SEQ):016d}"


def _receipt(db, user, **kw) -> Receipt:
    contact = kw.pop("contact", None) or _contact(db)
    payload = ReceiptIn(
        receipt_type=kw.pop("receipt_type", "customer"),
        contact_id=contact.id,
        receipt_date=kw.pop("receipt_date", TODAY),
        **kw,
    )
    return svc.create_receipt(db, payload, user)


def _lines(db, receipt: Receipt) -> list[JournalLine]:
    return db.query(JournalLine).filter(JournalLine.entry_id == receipt.journal_entry_id).all()


def _debit_on(db, receipt: Receipt, role: str) -> Decimal:
    account_id = get_account(db, role).id
    return sum((Decimal(x.debit) for x in _lines(db, receipt) if x.account_id == account_id), Decimal(0))


def _credit_on(db, receipt: Receipt, role: str) -> Decimal:
    account_id = get_account(db, role).id
    return sum((Decimal(x.credit) for x in _lines(db, receipt) if x.account_id == account_id), Decimal(0))


# ── قیدِ اصلی: چهار ابزار، یک سند ─────────────────────────────────────────────


def test_a_receipt_can_carry_four_instruments_in_one_entry(db, user):
    """§۶ §۲۴ §۳۳ — هر جزء به حسابِ ماهیتِ خودش، و جمع از اجزا توضیح‌پذیر است."""
    box, bank, term = _cashbox(db), _bank(db), _terminal(db)
    receipt = _receipt(
        db,
        user,
        cash=[ReceiptCashIn(amount=Decimal(1_400))],
        transfers=[ReceiptTransferIn(amount=Decimal(15), bank_account_id=bank.id, reference_no="HV-1")],
        cards=[ReceiptCardIn(amount=Decimal(1_800), pos_terminal_id=term.id, reference_no="RRN-1")],
        cheques=[ReceiptChequeIn(amount=Decimal(145), number="C-1", due_date=TODAY + timedelta(days=60))],
    )

    assert receipt.receipt_amount == Decimal(3_360)
    assert receipt.settlement_total == Decimal(3_360)

    # یک سند، پنج ردیف: چهار بدهکار + یک بستانکار
    assert len(_lines(db, receipt)) == 5
    assert _credit_on(db, receipt, cc.ACCOUNTS_RECEIVABLE) == Decimal(3_360)
    assert _debit_on(db, receipt, cc.CHECKS_RECEIVABLE) == Decimal(145)

    # صندوق و بانک با تفصیلیِ خودشان، نه با حسابِ عمومی
    rows = svc.components(db, receipt)
    assert {row["kind"] for row in rows} == {"cash", "transfer", "card", "cheque"}
    # هر جزء به موجودیتِ واقعیِ خودش برمی‌گردد (§۳۸)
    assert all(row["source_id"] is not None for row in rows)
    assert {row["label"] for row in rows} >= {box.name, bank.name}


def test_the_items_summary_is_derived_not_typed(db, user):
    """§۳۵ — «اقلام» از اجزا مشتق می‌شود، نه متنی که کاربر بنویسد."""
    receipt = _receipt(
        db,
        user,
        cash=[ReceiptCashIn(amount=Decimal(100))],
        cheques=[ReceiptChequeIn(amount=Decimal(50), number="C-2", due_date=TODAY + timedelta(days=10))],
    )
    assert svc.to_out(db, receipt)["items_summary"] == "وجه نقد، چک"


def test_a_receipt_needs_at_least_one_component(db, user):
    with pytest.raises(ValueError):
        ReceiptIn(contact_id=_contact(db).id, receipt_date=TODAY)


# ── چک: موجودیتِ مستقل، نه JSON داخلِ رسید ───────────────────────────────────


def test_a_receipt_cheque_becomes_a_real_check_in_hand(db, user):
    """§۱۰ §۱۳ §۳۸ — چک چرخه‌ی عمرِ خودش را دارد و از رسید قابلِ ردیابی است."""
    receipt = _receipt(
        db,
        user,
        cheques=[
            ReceiptChequeIn(
                amount=Decimal(500),
                number="C-3",
                due_date=TODAY + timedelta(days=45),
                sayad_id=_sayad(),
                back_number="PN-9",
                branch_name="مرکزی",
                owner_name="شخصِ ثالث",
            )
        ],
    )
    check = db.query(Check).filter(Check.receipt_id == receipt.id).one()
    assert check.type == "receivable"
    assert check.status == "in_hand"
    assert check.owner_name == "شخصِ ثالث"
    assert check.due_date != receipt.receipt_date  # §۱۲ سررسید با تاریخِ رسید فرق دارد


def test_a_receipt_cheque_does_not_create_a_second_entry(db, user):
    """§۳۰ — یک رسید، یک سند. چکِ داخلِ رسید سندِ جدا نمی‌زند."""
    before = db.query(JournalEntry).count()
    receipt = _receipt(
        db,
        user,
        cheques=[ReceiptChequeIn(amount=Decimal(700), number="C-4", due_date=TODAY + timedelta(days=20))],
    )
    assert db.query(JournalEntry).count() == before + 1
    assert _debit_on(db, receipt, cc.CHECKS_RECEIVABLE) == Decimal(700)


def test_a_duplicate_sayad_code_is_refused(db, user):
    """§۱۱ — کد صیادی در سطحِ کشور یکتاست، پس تکراری یعنی خطای ورودِ داده."""
    sayad = _sayad()
    _receipt(
        db,
        user,
        cheques=[
            ReceiptChequeIn(amount=Decimal(10), number="C-5", due_date=TODAY, sayad_id=sayad)
        ],
    )
    with pytest.raises(HTTPException) as err:
        _receipt(
            db,
            user,
            cheques=[
                ReceiptChequeIn(amount=Decimal(10), number="C-6", due_date=TODAY, sayad_id=sayad)
            ],
        )
    assert err.value.status_code == 409
    assert sayad in err.value.detail


def test_the_sayad_code_is_separate_from_the_cheque_number(db, user):
    """§۱۱ — این دو یک فیلد نیستند و ادغامشان استعلامِ صیاد را ناممکن می‌کند."""
    sayad = _sayad()
    receipt = _receipt(
        db,
        user,
        cheques=[
            ReceiptChequeIn(amount=Decimal(10), number="0012345", due_date=TODAY, sayad_id=sayad)
        ],
    )
    check = db.query(Check).filter(Check.receipt_id == receipt.id).one()
    assert check.number == "0012345"
    assert check.sayad_id == sayad


@pytest.mark.parametrize("bad", ["12345", "abcdefghijklmnop"])
def test_a_malformed_sayad_code_is_refused(bad):
    with pytest.raises(ValueError):
        ReceiptChequeIn(amount=Decimal(1), number="X", due_date=TODAY, sayad_id=bad)


# ── نوعِ دریافت تفسیرِ حسابداری را عوض می‌کند ────────────────────────────────


def test_the_default_receipt_type_credits_receivables_exactly_as_before(db, user):
    """پیش‌فرض رفتارِ امروز است — هیچ داده‌ی مستقری معنایش عوض نمی‌شود."""
    receipt = _receipt(db, user, cash=[ReceiptCashIn(amount=Decimal(90))])
    assert receipt.receipt_type == "customer"
    assert _credit_on(db, receipt, cc.ACCOUNTS_RECEIVABLE) == Decimal(90)


def test_a_supplier_receipt_credits_payables_not_receivables(db, user):
    """§۲ — برگشتِ پول از تأمین‌کننده به «دریافتنی» نمی‌خورد. این اشکال بود."""
    receipt = _receipt(
        db, user, receipt_type="supplier", cash=[ReceiptCashIn(amount=Decimal(80))]
    )
    assert _credit_on(db, receipt, cc.ACCOUNTS_PAYABLE) == Decimal(80)
    assert _credit_on(db, receipt, cc.ACCOUNTS_RECEIVABLE) == Decimal(0)


def test_an_unknown_receipt_type_is_refused(db):
    with pytest.raises(ValueError):
        ReceiptIn(
            receipt_type="wizard",
            contact_id=_contact(db).id,
            receipt_date=TODAY,
            cash=[ReceiptCashIn(amount=Decimal(1))],
        )


# ── تخفیف: بدهی را می‌بندد، ولی پول نیست ────────────────────────────────────


def test_a_settlement_discount_is_not_cash(db, user):
    """§۲۳ — تخفیف مطالبه را کم می‌کند بی‌آنکه چیزی وارد صندوق شود."""
    discount_account = _discount_account(db)
    receipt = _receipt(
        db,
        user,
        cash=[ReceiptCashIn(amount=Decimal(95))],
        discount_amount=Decimal(5),
        discount_account_id=discount_account.id,
    )
    assert receipt.receipt_amount == Decimal(95)  # پولِ واقعی
    assert receipt.settlement_total == Decimal(100)  # بدهیِ بسته‌شده
    assert _credit_on(db, receipt, cc.ACCOUNTS_RECEIVABLE) == Decimal(100)
    debits = {
        line.account_id: Decimal(line.debit) for line in _lines(db, receipt) if Decimal(line.debit) > 0
    }
    assert debits[discount_account.id] == Decimal(5)


def test_a_discount_without_an_account_is_refused(db):
    with pytest.raises(ValueError):
        ReceiptIn(
            contact_id=_contact(db).id,
            receipt_date=TODAY,
            discount_amount=Decimal(5),
            cash=[ReceiptCashIn(amount=Decimal(95))],
        )


# ── ارز از موتورِ خودِ کوبیتا می‌آید ─────────────────────────────────────────


def test_the_base_currency_amount_is_what_the_entry_posts(db, user):
    """§۹ — مبالغِ اجزا به ارزِ سندند؛ دفتر همیشه پایه می‌خورد."""
    receipt = _receipt(
        db,
        user,
        currency_code="IRR",
        exchange_rate=Decimal(1),
        cash=[ReceiptCashIn(amount=Decimal(250))],
    )
    assert receipt.base_currency_amount == receipt.receipt_amount == Decimal(250)


def test_a_non_positive_rate_is_refused(db):
    with pytest.raises(ValueError):
        ReceiptIn(
            contact_id=_contact(db).id,
            receipt_date=TODAY,
            exchange_rate=Decimal(0),
            cash=[ReceiptCashIn(amount=Decimal(1))],
        )


def test_the_base_currency_rate_must_be_one(db, user):
    """ریال نرخ ندارد؛ نرخِ غیرِ یک روی ارزِ پایه یعنی عددی که دفتر با آن نمی‌خواند."""
    with pytest.raises(HTTPException) as err:
        _receipt(
            db,
            user,
            currency_code="IRR",
            exchange_rate=Decimal(2),
            cash=[ReceiptCashIn(amount=Decimal(1))],
        )
    assert err.value.status_code == 400


def test_an_undefined_currency_is_refused(db, user):
    with pytest.raises(HTTPException) as err:
        _receipt(
            db,
            user,
            currency_code="XYZ",
            exchange_rate=Decimal(2),
            cash=[ReceiptCashIn(amount=Decimal(10))],
        )
    assert err.value.status_code == 400


# ── شماره‌ی مرجع ─────────────────────────────────────────────────────────────


def test_a_duplicate_reference_number_is_refused(db, user):
    """§۱۷ — کد پیگیری برای پیدا کردنِ تراکنش است، پس تکراری یعنی دوباره‌ثبت."""
    term = _terminal(db)
    ref = f"RRN{next(_SEQ):09d}"
    _receipt(db, user, cards=[ReceiptCardIn(amount=Decimal(10), pos_terminal_id=term.id, reference_no=ref)])
    with pytest.raises(HTTPException) as err:
        _receipt(
            db, user, cards=[ReceiptCardIn(amount=Decimal(10), pos_terminal_id=term.id, reference_no=ref)]
        )
    assert err.value.status_code == 409


def test_a_card_component_needs_a_tracking_code(db):
    term = _terminal(db)
    with pytest.raises(ValueError):
        ReceiptCardIn(amount=Decimal(1), pos_terminal_id=term.id, reference_no="  ")


# ── ابطال ────────────────────────────────────────────────────────────────────


def test_voiding_a_receipt_reverses_the_entry_and_restores_the_balance(db, user):
    """§۳۹ — اصلاح با سندِ معکوس، نه حذف. و مانده باید واقعاً برگردد."""
    contact = _contact(db)
    opening = contact_balance(db, contact.id)
    receipt = _receipt(db, user, contact=contact, cash=[ReceiptCashIn(amount=Decimal(400))])
    assert contact_balance(db, contact.id) == opening - Decimal(400)

    svc.void_receipt(db, receipt.id, reason="اشتباه ثبت شد", user=user)

    assert receipt.voided_at is not None
    assert contact_balance(db, contact.id) == opening
    reversal = (
        db.query(JournalEntry).filter(JournalEntry.reverses_entry_id == receipt.journal_entry_id).one()
    )
    assert reversal.source_type == "void_receipt"


def test_voiding_stamps_every_component(db, user):
    receipt = _receipt(
        db,
        user,
        cash=[ReceiptCashIn(amount=Decimal(30))],
        cheques=[ReceiptChequeIn(amount=Decimal(70), number="C-7", due_date=TODAY)],
    )
    svc.void_receipt(db, receipt.id, reason="", user=user)
    txns = db.query(TreasuryTransaction).filter(TreasuryTransaction.receipt_id == receipt.id).all()
    checks = db.query(Check).filter(Check.receipt_id == receipt.id).all()
    assert txns and checks
    assert all(t.voided_at is not None for t in txns)
    assert all(c.voided_at is not None for c in checks)


def test_a_receipt_cannot_be_voided_twice(db, user):
    receipt = _receipt(db, user, cash=[ReceiptCashIn(amount=Decimal(10))])
    svc.void_receipt(db, receipt.id, reason="", user=user)
    with pytest.raises(HTTPException) as err:
        svc.void_receipt(db, receipt.id, reason="", user=user)
    assert err.value.status_code == 409


def test_voiding_is_refused_once_a_cheque_has_moved_on(db, user):
    """چکی که واگذار شده سندِ خودش را زده؛ ابطالِ رسید آن را نمی‌داند."""
    bank = _bank(db)
    receipt = _receipt(
        db,
        user,
        cheques=[ReceiptChequeIn(amount=Decimal(600), number="C-8", due_date=TODAY + timedelta(days=5))],
    )
    check = db.query(Check).filter(Check.receipt_id == receipt.id).one()
    update_check_status(db, check.id, "deposited", bank.id, user)

    with pytest.raises(HTTPException) as err:
        svc.void_receipt(db, receipt.id, reason="", user=user)
    assert err.value.status_code == 409
    assert "C-8" in err.value.detail


def test_voided_receipts_leave_the_aging_report(db, user):
    """گاردی که بی‌آن ابطال بی‌صدا بی‌اثر می‌شد."""
    from app.services.credit import customer_outstanding

    contact = _contact(db)
    before = customer_outstanding(db, contact.id)
    receipt = _receipt(db, user, contact=contact, cash=[ReceiptCashIn(amount=Decimal(120))])
    assert customer_outstanding(db, contact.id) == before - Decimal(120)
    svc.void_receipt(db, receipt.id, reason="", user=user)
    assert customer_outstanding(db, contact.id) == before


# ── تکثیر ────────────────────────────────────────────────────────────────────


def test_duplicating_clears_every_unique_identifier(db, user):
    """§۳۷ — کپیِ کورکورانه‌ی شناسه‌ها یعنی دو رکوردِ مالی با یک هویت."""
    term = _terminal(db)
    receipt = _receipt(
        db,
        user,
        cash=[ReceiptCashIn(amount=Decimal(10))],
        cards=[ReceiptCardIn(amount=Decimal(20), pos_terminal_id=term.id, reference_no=f"R{next(_SEQ)}")],
        cheques=[
            ReceiptChequeIn(amount=Decimal(30), number="C-9", due_date=TODAY, sayad_id=_sayad())
        ],
    )
    draft = svc.duplicate_draft(db, receipt.id)

    assert draft["cards"][0]["reference_no"] == ""
    assert draft["cheques"][0]["number"] == ""
    assert draft["cheques"][0]["sayad_id"] == ""
    assert draft["related_documents"] == []
    # ولی چیزهایی که هویت نیستند می‌مانند
    assert draft["cash"][0]["amount"] == Decimal(10)
    assert draft["contact_id"] == receipt.contact_id


def test_duplicating_writes_nothing(db, user):
    receipt = _receipt(db, user, cash=[ReceiptCashIn(amount=Decimal(10))])
    before = db.query(Receipt).count()
    svc.duplicate_draft(db, receipt.id)
    assert db.query(Receipt).count() == before


# ── راس‌گیری ─────────────────────────────────────────────────────────────────


def test_the_weighted_maturity_matches_a_hand_computed_case():
    """§۲۷ §۲۸ — (۱۰۰×۳۰ + ۳۰۰×۶۰) ÷ ۴۰۰ = ۵۲٫۵ روز."""
    base = date(1405, 1, 1)
    result = svc.weighted_maturity(
        [(Decimal(100), base + timedelta(days=30)), (Decimal(300), base + timedelta(days=60))], base
    )
    assert result["average_days"] == Decimal("52.50")
    assert result["ras_date"] == base + timedelta(days=53)  # گردِ نیم‌به‌بالا
    assert result["counted_rows"] == 2


def test_same_day_rows_can_be_excluded():
    """چک‌های روز عملاً نقدند و میانگین را بی‌دلیل به صفر می‌کشند."""
    base = date(1405, 1, 1)
    rows = [(Decimal(100), base), (Decimal(300), base + timedelta(days=60))]
    assert svc.weighted_maturity(rows, base, include_same_day=False)["average_days"] == Decimal("60.00")
    assert svc.weighted_maturity(rows, base, include_same_day=True)["average_days"] == Decimal("45.00")


def test_excluding_every_row_leaves_the_base_date_not_an_error():
    base = date(1405, 1, 1)
    result = svc.weighted_maturity([(Decimal(10), base)], base, include_same_day=False)
    assert result["ras_date"] == base
    assert result["counted_rows"] == 0


# ── رگرسیون: قراردادِ قدیمی نمی‌شکند ────────────────────────────────────────


def test_the_legacy_single_instrument_path_still_works_and_now_gets_a_number(db, user):
    """اپِ موبایل همین شکل را می‌فرستد؛ بدنه و پاسخ عوض نشده‌اند."""
    from app.schemas.treasury import TreasuryTransactionIn

    contact = _contact(db)
    txn = svc.create_single_instrument(
        db,
        TreasuryTransactionIn(
            transaction_date=TODAY,
            contact_id=contact.id,
            amount=Decimal(500),
            method="cash",
            description="دریافت نقدی",
        ),
        user,
    )
    assert txn.type == "receipt"
    assert txn.method == "cash"
    assert txn.amount == Decimal(500)
    # ولی حالا سربرگ هم دارد
    assert txn.receipt_id is not None
    receipt = db.get(Receipt, txn.receipt_id)
    assert int(receipt.number) > 0
    assert receipt.receipt_type == "customer"


def test_a_bank_method_legacy_receipt_becomes_a_transfer_component(db, user):
    from app.schemas.treasury import TreasuryTransactionIn

    bank = _bank(db)
    txn = svc.create_single_instrument(
        db,
        TreasuryTransactionIn(
            transaction_date=TODAY,
            contact_id=_contact(db).id,
            amount=Decimal(300),
            method="bank",
            bank_account_id=bank.id,
        ),
        user,
    )
    assert txn.method == "bank"
    assert txn.bank_account_id == bank.id
    rows = svc.components(db, db.get(Receipt, txn.receipt_id))
    assert [r["kind"] for r in rows] == ["transfer"]


def test_machine_made_receipts_stay_header_less(db, user):
    """قسط و بازارگاه سندِ خودشان را دارند؛ رسیدِ جدا یعنی دو سند برای یک رویداد."""
    from app.schemas.treasury import TreasuryTransactionIn
    from app.services import treasury as treasury_service

    txn = treasury_service.create_receipt(
        db,
        TreasuryTransactionIn(
            transaction_date=TODAY,
            contact_id=_contact(db).id,
            amount=Decimal(75),
            method="cash",
        ),
        user,
    )
    assert txn.receipt_id is None


# ── چاپ ──────────────────────────────────────────────────────────────────────


def test_the_printed_sheet_is_built_from_the_receipt_itself(db, user):
    """§۲۵ §۲۶ — نسخه‌ی دومی از داده‌ی مالی ساخته نمی‌شود، و حروف مشتق است."""
    from app.services.printing import render_receipt

    term = _terminal(db)
    receipt = _receipt(
        db,
        user,
        cash=[ReceiptCashIn(amount=Decimal(1_400))],
        cards=[ReceiptCardIn(amount=Decimal(100), pos_terminal_id=term.id, reference_no=f"P{next(_SEQ)}")],
        cheques=[ReceiptChequeIn(amount=Decimal(50), number="C-P", due_date=TODAY + timedelta(days=30))],
    )
    html = render_receipt(
        business_name="کسب‌وکارِ آزمون",
        number=int(receipt.number),
        receipt_date=receipt.receipt_date,
        type_label=svc.type_label(receipt.receipt_type),
        party_name="مشتری",
        party_detail="",
        description=receipt.description,
        components=svc.components(db, receipt),
        receipt_amount=receipt.base_currency_amount,
        settlement_total=receipt.base_currency_amount,
    )
    # هر سه ابزار در برگه دیده می‌شوند (§۲۵)
    for label in ("وجه نقد", "کارت‌خوان", "چک"):
        assert label in html
    assert "مبلغ به حروف" in html
    assert "امضای پرداخت‌کننده" in html
    # و برگه‌ی رسیدِ باطل، باطل‌بودنش را می‌گوید
    svc.void_receipt(db, receipt.id, reason="اشتباه", user=user)
    voided_html = render_receipt(
        business_name="کسب‌وکارِ آزمون",
        number=int(receipt.number),
        receipt_date=receipt.receipt_date,
        type_label=svc.type_label(receipt.receipt_type),
        party_name="مشتری",
        party_detail="",
        description=receipt.description,
        components=svc.components(db, receipt),
        receipt_amount=receipt.base_currency_amount,
        settlement_total=receipt.base_currency_amount,
        voided_at=receipt.voided_at,
        void_reason=receipt.void_reason,
    )
    assert "این رسید باطل شده است" in voided_html
