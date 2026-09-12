"""کالای در راه — بستنِ واگراییِ «فاکتور ثبت شد ولی کالا نرسیده».

فاکتورِ خرید همان لحظه «موجودی کالا» را بدهکار می‌کرد، حتی وقتی کالا قرار بود
بعداً با رسیدِ انبار بیاید. نتیجه: ترازنامه کالایی را دارایی نشان می‌داد که در
هیچ انباری نبود، و گزارشِ انبار صفر می‌گفت.

ادعای اصلی این فایل ساده است: **دفتر و گزارشِ انبار باید همیشه یک عدد بگویند.**
"""
from datetime import date
from decimal import Decimal

from app.models.accounting import JournalLine
from app.schemas.invoices import (
    PurchaseInvoiceIn,
    PurchaseInvoiceLineIn,
    WarehouseReceiptIn,
    WarehouseReceiptLineIn,
)
from app.services import chart_codes as cc
from app.services.common import get_account
from app.services.inventory import post_purchase_invoice
from app.services.reports import get_inventory_report
from app.services.warehouse_receipts import create_warehouse_receipt, void_warehouse_receipt
from tests.factories import main_warehouse, make_contact, make_item

TODAY = date(2026, 3, 15)


class Ledger:
    def __init__(self, db):
        self.db = db
        self.before = {}

    def snap(self, *roles):
        for role in roles:
            self.before[role] = self._balance(role)
        return self

    def delta(self, role):
        return self._balance(role) - self.before[role]

    def _balance(self, role):
        account_id = get_account(self.db, role).id
        rows = (
            self.db.query(JournalLine.debit, JournalLine.credit)
            .filter(JournalLine.account_id == account_id)
            .all()
        )
        return sum((Decimal(d) - Decimal(c) for d, c in rows), Decimal(0))


def buy_pending(db, user, item, *, qty=10, unit_cost=5_000_000, supplier=None):
    """فاکتورِ خرید بدونِ انبار — کالا بعداً با رسید می‌آید."""
    return post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=None,
            contact_id=(supplier or make_contact(db, name="تأمین‌کننده", type_="supplier")).id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(qty), unit_cost=Decimal(unit_cost))],
        ),
        user,
    )


def receive(db, user, invoice, qty):
    return create_warehouse_receipt(
        db,
        invoice.id,
        WarehouseReceiptIn(
            receipt_date=TODAY,
            warehouse_id=main_warehouse(db).id,
            lines=[
                WarehouseReceiptLineIn(
                    purchase_invoice_line_id=invoice.lines[0].id, qty=Decimal(qty)
                )
            ],
        ),
        user,
    )


def report_value(db):
    return Decimal(get_inventory_report(db, None, as_of=TODAY)["total_value"])


# ─────────────────── واگرایی بسته می‌شود ───────────────────


def test_an_unreceived_purchase_is_not_warehouse_stock(db, user):
    """کالایی که نرسیده، موجودیِ انبار نیست.

    پیش از این دفتر ۵۰ میلیون موجودی نشان می‌داد و گزارشِ انبار صفر.
    """
    item = make_item(db, name="لیوان")
    ledger = Ledger(db).snap(cc.INVENTORY, cc.GOODS_IN_TRANSIT)
    before = report_value(db)

    buy_pending(db, user, item, qty=10, unit_cost=5_000_000)

    assert ledger.delta(cc.INVENTORY) == Decimal(0), "کالای نرسیده نباید موجودیِ انبار شود"
    assert ledger.delta(cc.GOODS_IN_TRANSIT) == Decimal(50_000_000)
    assert report_value(db) - before == Decimal(0)


def test_the_receipt_moves_it_into_the_warehouse(db, user):
    """§۳۴ — رسید دارایی را جابه‌جا می‌کند، نه اینکه بسازدش."""
    item = make_item(db, name="لیوان")
    ledger = Ledger(db).snap(cc.INVENTORY, cc.GOODS_IN_TRANSIT)
    before = report_value(db)

    invoice = buy_pending(db, user, item, qty=10, unit_cost=5_000_000)
    receive(db, user, invoice, 10)

    assert ledger.delta(cc.GOODS_IN_TRANSIT) == Decimal(0), "کالای در راه باید صفر شود"
    assert ledger.delta(cc.INVENTORY) == Decimal(50_000_000)
    assert report_value(db) - before == Decimal(50_000_000)


def test_ledger_and_stock_report_agree_at_every_step(db, user):
    """ادعای اصلی: در هیچ لحظه‌ای دفتر و گزارشِ انبار دو عدد نمی‌گویند."""
    item = make_item(db, name="لیوان")
    ledger = Ledger(db).snap(cc.INVENTORY)
    before = report_value(db)

    invoice = buy_pending(db, user, item, qty=10, unit_cost=5_000_000)
    assert ledger.delta(cc.INVENTORY) == report_value(db) - before

    receive(db, user, invoice, 4)
    assert ledger.delta(cc.INVENTORY) == report_value(db) - before

    receive(db, user, invoice, 6)
    assert ledger.delta(cc.INVENTORY) == report_value(db) - before


def test_a_partial_receipt_moves_only_its_share(db, user):
    item = make_item(db, name="لیوان")
    ledger = Ledger(db).snap(cc.INVENTORY, cc.GOODS_IN_TRANSIT)

    invoice = buy_pending(db, user, item, qty=10, unit_cost=5_000_000)
    receive(db, user, invoice, 4)

    assert ledger.delta(cc.INVENTORY) == Decimal(20_000_000)
    assert ledger.delta(cc.GOODS_IN_TRANSIT) == Decimal(30_000_000)


def test_the_last_receipt_clears_the_rounding_remainder(db, user):
    """بهای واحد عددِ صحیحِ گردشده است.

    بدونِ بردنِ ته‌مانده با آخرین تحویل، چند ریال برای همیشه در «کالای در راه»
    جا می‌ماند — حسابی که باید صفر شود و هرگز نمی‌شد.
    """
    item = make_item(db, name="لیوان")
    ledger = Ledger(db).snap(cc.GOODS_IN_TRANSIT)

    # ۱۰۰۰ ریال بر ۳ عدد بخش‌پذیر نیست
    invoice = buy_pending(db, user, item, qty=3, unit_cost=1_000)
    receive(db, user, invoice, 1)
    receive(db, user, invoice, 1)
    receive(db, user, invoice, 1)

    assert ledger.delta(cc.GOODS_IN_TRANSIT) == Decimal(0)


def test_a_service_is_never_in_transit(db, user):
    """خدمت حرکتِ انباری نمی‌سازد و رسیدی هم نمی‌آوردش — همان لحظه هزینه می‌شود."""
    service = make_item(db, name="مشاوره", is_service=True)
    ledger = Ledger(db).snap(cc.GOODS_IN_TRANSIT, cc.SERVICE_EXPENSE)

    buy_pending(db, user, service, qty=2, unit_cost=1_000_000)

    assert ledger.delta(cc.GOODS_IN_TRANSIT) == Decimal(0)
    assert ledger.delta(cc.SERVICE_EXPENSE) == Decimal(2_000_000)


def test_an_invoice_with_a_warehouse_still_goes_straight_to_stock(db, user):
    """گردشِ «خرید و ورودِ هم‌زمان» دست‌نخورده می‌ماند."""
    item = make_item(db, name="لیوان")
    ledger = Ledger(db).snap(cc.INVENTORY, cc.GOODS_IN_TRANSIT)

    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=main_warehouse(db).id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(2), unit_cost=Decimal(1_000_000))],
        ),
        user,
    )
    assert ledger.delta(cc.INVENTORY) == Decimal(2_000_000)
    assert ledger.delta(cc.GOODS_IN_TRANSIT) == Decimal(0)


# ─────────────────── ابطال باید سند را هم برگرداند ───────────────────


def test_voiding_a_receipt_reverses_its_journal(db, user):
    """ابطالِ بی‌برگشتِ سند یعنی کالا برگردد ولی مبلغش در دفتر بماند."""
    item = make_item(db, name="لیوان")
    invoice = buy_pending(db, user, item, qty=10, unit_cost=5_000_000)
    receipt = receive(db, user, invoice, 10)

    ledger = Ledger(db).snap(cc.INVENTORY, cc.GOODS_IN_TRANSIT)
    void_warehouse_receipt(db, receipt.id, reason="اشتباه بود", user=user)

    assert ledger.delta(cc.INVENTORY) == Decimal(-50_000_000)
    assert ledger.delta(cc.GOODS_IN_TRANSIT) == Decimal(50_000_000), "کالا باید به «در راه» برگردد"


def test_voiding_a_direct_receipt_reverses_the_payable_too(db, user):
    """رسیدِ مستقیم بدهی شناخته؛ ابطالش باید همان را پس بگیرد."""
    item = make_item(db, name="لیوان")
    supplier = make_contact(db, name="تأمین‌کننده", type_="supplier")
    receipt = create_warehouse_receipt(
        db,
        None,
        WarehouseReceiptIn(
            receipt_date=TODAY,
            warehouse_id=main_warehouse(db).id,
            contact_id=supplier.id,
            lines=[WarehouseReceiptLineIn(item_id=item.id, qty=Decimal(3), unit_cost=Decimal(1_000_000))],
        ),
        user,
    )
    ledger = Ledger(db).snap(cc.INVENTORY, cc.ACCOUNTS_PAYABLE)

    void_warehouse_receipt(db, receipt.id, reason="اشتباه بود", user=user)

    assert ledger.delta(cc.INVENTORY) == Decimal(-3_000_000)
    assert ledger.delta(cc.ACCOUNTS_PAYABLE) == Decimal(3_000_000)


def test_re_receiving_after_a_void_is_clean(db, user):
    """ابطال باید مانده‌ی قابلِ تحویل را هم آزاد کند، نه فقط سند را."""
    item = make_item(db, name="لیوان")
    invoice = buy_pending(db, user, item, qty=10, unit_cost=5_000_000)
    receipt = receive(db, user, invoice, 10)
    void_warehouse_receipt(db, receipt.id, reason="اشتباه بود", user=user)

    ledger = Ledger(db).snap(cc.INVENTORY, cc.GOODS_IN_TRANSIT)
    receive(db, user, invoice, 10)

    assert ledger.delta(cc.INVENTORY) == Decimal(50_000_000)
    assert ledger.delta(cc.GOODS_IN_TRANSIT) == Decimal(-50_000_000)
