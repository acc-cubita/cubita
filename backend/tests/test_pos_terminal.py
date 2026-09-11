"""کارتخوان — رسیدِ بانکیِ پرداختِ کارتی، طرف‌حسابِ گذری، idempotencyِ RRN، و CRUDِ ترمینال."""
from datetime import date
from decimal import Decimal

from app.models.accounting import Account, JournalLine
from app.models.banking import BankAccount
from app.models.treasury import TreasuryTransaction
from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn, SalesInvoiceIn, SalesInvoiceLineIn
from app.schemas.treasury import CardPaymentIn, TreasuryTransactionIn
from app.services import chart_codes as cc
from app.services.common import get_account
from app.services.credit import customer_outstanding
from app.services.inventory import post_purchase_invoice, post_sales_invoice
from app.services.treasury import (
    WALKIN_CARD_CONTACT_NAME,
    create_receipt,
    get_or_create_walkin_card_contact,
    record_card_payment,
)
from tests.factories import main_warehouse, make_contact, make_item


def _make_bank(db) -> BankAccount:
    """حساب بانکیِ تسویه‌ی کارتخوان، متصل به معینِ «بانک»."""
    gl = get_account(db, cc.BANK)
    b = BankAccount(name="کارتخوانِ تست", bank_name="ملت", account_number="1", iban="IR0", gl_account_id=gl.id)
    db.add(b)
    db.flush()
    return b


def _gl_balance(db, account_id) -> Decimal:
    rows = db.query(JournalLine.debit, JournalLine.credit).filter(JournalLine.account_id == account_id).all()
    return sum((Decimal(d) - Decimal(c) for d, c in rows), Decimal(0))


def _clearing_balance(db) -> Decimal:
    """مانده‌ی «وجوهِ در راهِ کارت‌خوان».

    **تا مهاجرتِ ۰۱۰۹ این تست‌ها معینِ بانک را می‌سنجیدند.** درست هم بود — همان‌جا
    بدهکار می‌شد. ولی پول آن لحظه به بانک نرسیده بود؛ رسیدنش کارِ تسویه است. حالا
    مرحله‌ی اول اینجا می‌نشیند و بانک تا تسویه تکان نمی‌خورد.
    """
    from app.services import pos_settlements

    return _gl_balance(db, pos_settlements.clearing_account(db).id)


def _card(bank, **over) -> CardPaymentIn:
    base = dict(
        transaction_date=date(2026, 5, 1),
        amount=Decimal(2_000_000),
        bank_account_id=bank.id,
        reference_no="RRN-100",
        trace_no="T-55",
        card_mask="6037****1234",
        terminal_no="TERM-9",
        psp="simulator",
    )
    base.update(over)
    return CardPaymentIn(**base)


# ── پرداختِ کارتیِ گذری (بدونِ طرف‌حساب) ────────────────────────────────────────

def test_walkin_card_payment_creates_system_contact_and_bank_receipt(db, user):
    bank = _make_bank(db)
    txn = record_card_payment(db, _card(bank), user)

    assert txn.type == "receipt"
    assert txn.method == "bank"
    assert txn.bank_account_id == bank.id
    # طرف‌حسابِ گذریِ سیستمی ساخته شد و رسید به آن خورد
    contact = db.get(TreasuryTransaction, txn.id).contact
    assert contact.is_system is True
    assert contact.name == WALKIN_CARD_CONTACT_NAME
    # وجوهِ در راه بدهکار شد — نه بانک، چون شرکتِ پرداخت هنوز واریز نکرده.
    assert _clearing_balance(db) == Decimal(2_000_000)
    assert _gl_balance(db, bank.gl_account_id) == Decimal(0)


def test_walkin_card_metadata_is_stored(db, user):
    bank = _make_bank(db)
    txn = record_card_payment(db, _card(bank), user)
    assert txn.paid_via == "pos_terminal"
    assert txn.reference_no == "RRN-100"
    assert txn.trace_no == "T-55"
    assert txn.card_mask == "6037****1234"
    assert txn.terminal_no == "TERM-9"
    assert txn.psp == "simulator"


def test_walkin_full_flow_nets_receivable_to_zero(db, user):
    """فاکتورِ گذری + رسیدِ کارت → ماندهٔ دریافتنیِ گذری صفر، وجوهِ در راه بدهکار."""
    bank = _make_bank(db)
    wh = main_warehouse(db)
    item = make_item(db)
    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=date(2026, 1, 1),
            warehouse_id=wh.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(10), unit_cost=Decimal(500_000))],
        ),
        user,
    )
    walkin = get_or_create_walkin_card_contact(db)
    post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=date(2026, 5, 1),
            warehouse_id=wh.id,
            contact_id=walkin.id,
            tax_rate=Decimal(0),
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(2), unit_price=Decimal(1_000_000))],
        ),
        user,
    )
    assert customer_outstanding(db, walkin.id) == Decimal(2_000_000)

    record_card_payment(db, _card(bank, amount=Decimal(2_000_000)), user)

    assert customer_outstanding(db, walkin.id) == Decimal(0)
    assert _clearing_balance(db) == Decimal(2_000_000)


def test_walkin_contact_reused_not_duplicated(db, user):
    bank = _make_bank(db)
    t1 = record_card_payment(db, _card(bank, reference_no="A1"), user)
    t2 = record_card_payment(db, _card(bank, reference_no="A2"), user)
    assert t1.contact_id == t2.contact_id  # همان طرف‌حسابِ گذری
    count = db.query(TreasuryTransaction).filter(TreasuryTransaction.contact_id == t1.contact_id).count()
    assert count == 2


# ── پرداختِ کارتی علیهِ طرف‌حسابِ واقعی ────────────────────────────────────────

def test_card_payment_settles_real_contact_receivable(db, user):
    bank = _make_bank(db)
    wh = main_warehouse(db)
    item = make_item(db)
    contact = make_contact(db)
    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=date(2026, 1, 1),
            warehouse_id=wh.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(10), unit_cost=Decimal(500_000))],
        ),
        user,
    )
    post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=date(2026, 5, 1),
            warehouse_id=wh.id,
            contact_id=contact.id,
            tax_rate=Decimal(0),
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(3), unit_price=Decimal(1_000_000))],
        ),
        user,
    )
    assert customer_outstanding(db, contact.id) == Decimal(3_000_000)

    record_card_payment(db, _card(bank, contact_id=contact.id, amount=Decimal(3_000_000), reference_no="RRN-C"), user)

    assert customer_outstanding(db, contact.id) == Decimal(0)
    assert _clearing_balance(db) == Decimal(3_000_000)


# ── idempotency روی RRN ────────────────────────────────────────────────────────

def test_duplicate_rrn_returns_same_txn_no_second_receipt(db, user):
    bank = _make_bank(db)
    first = record_card_payment(db, _card(bank, reference_no="DUP-1"), user)
    again = record_card_payment(db, _card(bank, reference_no="DUP-1"), user)
    assert again.id == first.id
    count = db.query(TreasuryTransaction).filter(TreasuryTransaction.reference_no == "DUP-1").count()
    assert count == 1


# ── طرف‌حسابِ گذری از فهرستِ مشتریان پنهان است ────────────────────────────────

def test_system_contact_hidden_from_contacts_list(db, user, client):
    bank = _make_bank(db)
    record_card_payment(db, _card(bank), user)
    r = client.get("/api/contacts")
    assert r.status_code == 200, r.text
    names = [c["name"] for c in r.json()["items"]]
    assert WALKIN_CARD_CONTACT_NAME not in names


# ── endpointِ HTTP کارت‌پرداخت ────────────────────────────────────────────────

def test_card_payment_endpoint_returns_metadata(db, user, client):
    bank = _make_bank(db)
    r = client.post(
        "/api/treasury/card-payment",
        json={
            "transaction_date": "2026-05-01",
            "amount": 2500000,
            "bank_account_id": str(bank.id),
            "reference_no": "HTTP-1",
            "trace_no": "TR-1",
            "card_mask": "6037****9999",
            "terminal_no": "T-1",
            "psp": "simulator",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["method"] == "bank"
    assert body["paid_via"] == "pos_terminal"
    assert body["reference_no"] == "HTTP-1"
    assert body["card_mask"] == "6037****9999"


def test_card_payment_endpoint_requires_reference(db, user, client):
    bank = _make_bank(db)
    r = client.post(
        "/api/treasury/card-payment",
        json={
            "transaction_date": "2026-05-01",
            "amount": 100000,
            "bank_account_id": str(bank.id),
            "reference_no": "  ",
        },
    )
    assert r.status_code == 422, r.text


# ── CRUDِ ترمینال ─────────────────────────────────────────────────────────────

def test_terminal_crud_and_default_uniqueness(db, user, client):
    bank = _make_bank(db)
    a = client.post(
        "/api/pos-terminals",
        json={"label": "کارتخوانِ ۱", "transport": "simulator", "bank_account_id": str(bank.id), "is_default": True},
    )
    assert a.status_code == 201, a.text
    a_id = a.json()["id"]
    assert a.json()["is_default"] is True

    # ترمینالِ دومِ پیش‌فرض → اولی باید از پیش‌فرض خارج شود
    b = client.post(
        "/api/pos-terminals",
        json={"label": "کارتخوانِ ۲", "transport": "network", "host": "192.168.1.50", "port": 8888, "is_default": True},
    )
    assert b.status_code == 201, b.text

    listing = client.get("/api/pos-terminals").json()
    defaults = [t["id"] for t in listing if t["is_default"]]
    assert defaults == [b.json()["id"]]

    # ویرایش
    p = client.patch(f"/api/pos-terminals/{a_id}", json={"label": "کارتخوانِ نو", "transport": "simulator"})
    assert p.status_code == 200, p.text
    assert p.json()["label"] == "کارتخوانِ نو"

    # حذف
    d = client.delete(f"/api/pos-terminals/{a_id}")
    assert d.status_code == 204, d.text
    assert a_id not in [t["id"] for t in client.get("/api/pos-terminals").json()]


def test_terminal_rejects_invalid_transport(db, user, client):
    r = client.post("/api/pos-terminals", json={"label": "بد", "transport": "carrier-pigeon"})
    assert r.status_code == 422, r.text


def test_terminal_network_requires_host(db, user, client):
    r = client.post("/api/pos-terminals", json={"label": "بی‌host", "transport": "network"})
    assert r.status_code == 422, r.text
