"""رسیدِ انبار پنج نوع دارد و تا امروز سندش **یک** قاعده داشت — قاعده‌ی خرید.

«تحویل‌دهنده داری؟ بدهی به او؛ نداری؟ نقد» برای خریدِ داخلی و وارداتی درست است.
روی دو نوعِ دیگر اثباتاً غلط بود:

* **تولید** — کالایی که خودمان ساختیم پول پرداخت نشده، ولی سند صندوق را دقیقاً
  به اندازه‌ی ارزشِ تولید کم می‌کرد. و چون نرخِ مالیات از خودِ کالا می‌آید، تولیدِ
  یک کالای نرخ‌دار «اعتبارِ مالیاتی» هم می‌ساخت — مالیاتی که به کسی داده نشده.
* **موجودی اول دوره** — افتتاحیه مسیرِ درستِ خودش را دارد که مقابلِ سرمایه
  می‌بندد؛ این مسیر به‌جایش صندوق را کم می‌کرد.

این فایل هر دو را می‌بندد و مسیرِ خرید را دست‌نخورده نگه می‌دارد.
"""
from datetime import date
from decimal import Decimal

from app.models.accounting import Account, JournalEntry, JournalLine
from app.schemas.invoices import WarehouseReceiptIn, WarehouseReceiptLineIn
from app.services import chart_codes as cc
from app.services.common import get_account
from app.services.warehouse_receipts import create_warehouse_receipt
from tests.factories import main_warehouse, make_contact, make_item

TODAY = date(2026, 3, 15)
QTY = Decimal(15)
COST = Decimal(160_000)
VALUE = QTY * COST


def _receipt(db, user, receipt_type, *, item=None, contact_id=None, tax_rate=None):
    item = item or make_item(db)
    extra = {} if tax_rate is None else {"tax_rate": tax_rate}
    return create_warehouse_receipt(
        db,
        None,
        WarehouseReceiptIn(
            receipt_date=TODAY,
            warehouse_id=main_warehouse(db).id,
            receipt_type=receipt_type,
            contact_id=contact_id,
            lines=[WarehouseReceiptLineIn(item_id=item.id, qty=QTY, unit_cost=COST)],
            **extra,
        ),
        user,
    )


def _entry(db, receipt) -> JournalEntry | None:
    return (
        db.query(JournalEntry)
        .filter(
            JournalEntry.source_type == "warehouse_receipt",
            JournalEntry.description.like(f"%{receipt.number}%"),
        )
        .first()
    )


def _credit_roles(db, entry) -> dict[str | None, Decimal]:
    """نقشِ هر حسابِ بستانکار → مبلغ. با نقش سنجیده می‌شود نه با کد."""
    out: dict[str | None, Decimal] = {}
    for line in entry.lines:
        if Decimal(line.credit) <= 0:
            continue
        role = db.get(Account, line.account_id).system_role
        out[role] = out.get(role, Decimal(0)) + Decimal(line.credit)
    return out


# --- تولید ------------------------------------------------------------------


def test_production_receipt_credits_work_in_process_not_cash(db, user):
    """گاردِ همان باگ: تولید نباید صندوق را کم کند."""
    receipt = _receipt(db, user, "production")
    credits = _credit_roles(db, _entry(db, receipt))

    assert credits == {cc.WORK_IN_PROCESS: VALUE}
    assert cc.CASH not in credits
    assert cc.ACCOUNTS_PAYABLE not in credits


def test_production_receipt_debits_inventory(db, user):
    """طرفِ بدهکار عوض نشده — کالا هنوز وارد موجودی می‌شود."""
    entry = _entry(db, _receipt(db, user, "production"))
    inventory_id = get_account(db, cc.INVENTORY).id
    debit = sum(
        (Decimal(l.debit) for l in entry.lines if l.account_id == inventory_id), Decimal(0)
    )
    assert debit == VALUE
    assert sum(Decimal(l.debit) for l in entry.lines) == sum(Decimal(l.credit) for l in entry.lines)


def test_production_receipt_with_contact_still_avoids_payable(db, user):
    """«تحویل‌دهنده» روی رسیدِ تولید یک نام است، نه یک طلبکار.

    کارگاهِ طرفِ قرارداد می‌تواند اینجا ثبت شود؛ ولی بدهی به او از این سند
    درنمی‌آید، چون این سند خریدی را ثبت نمی‌کند.
    """
    contact = make_contact(db)
    credits = _credit_roles(db, _entry(db, _receipt(db, user, "production", contact_id=contact.id)))
    assert credits == {cc.WORK_IN_PROCESS: VALUE}


def test_production_receipt_creates_no_input_vat(db, user):
    """مالیاتِ خرید بابتِ کالایی که خودمان ساخته‌ایم وجود ندارد."""
    item = make_item(db)
    item.tax_rate = Decimal(10)
    db.flush()

    entry = _entry(db, _receipt(db, user, "production", item=item, tax_rate=Decimal(10)))
    vat = db.query(Account).filter(Account.system_role == cc.VAT_RECEIVABLE).first()
    if vat is not None:
        assert not [l for l in entry.lines if l.account_id == vat.id]
    assert _credit_roles(db, entry) == {cc.WORK_IN_PROCESS: VALUE}


# --- موجودی اول دوره --------------------------------------------------------


def test_opening_receipt_credits_the_opening_account(db, user):
    credits = _credit_roles(db, _entry(db, _receipt(db, user, "opening")))
    assert credits == {cc.OPENING_ACCOUNT: VALUE}


# --- خرید: رفتارِ دیروز باید دقیقاً بماند ------------------------------------


def test_purchase_receipt_without_contact_still_credits_cash(db, user):
    credits = _credit_roles(db, _entry(db, _receipt(db, user, "purchase_domestic")))
    assert credits == {cc.CASH: VALUE}


def test_purchase_receipt_with_contact_still_credits_payable(db, user):
    contact = make_contact(db)
    receipt = _receipt(db, user, "purchase_domestic", contact_id=contact.id)
    credits = _credit_roles(db, _entry(db, receipt))
    assert credits == {cc.ACCOUNTS_PAYABLE: VALUE}


def test_other_receipt_is_unchanged(db, user):
    """«سایر» عمداً دست نخورد — معنایش هنوز از هیچ فصلی درنیامده."""
    credits = _credit_roles(db, _entry(db, _receipt(db, user, "other")))
    assert credits == {cc.CASH: VALUE}
