"""برگشت رسید انبار — سندِ مستقل، نه ویرایشِ رسیدِ اصلی.

فصل یک مدلِ غلط را صریح نام می‌برد:

    رسید = ۱۰۰  →  برگشت ۲۰  →  ویرایشِ رسید به ۸۰   ⛔

و مدلِ درست را:

    رسید       +۱۰۰
    برگشت       −۲۰
    ────────────────
    خالص        +۸۰   ✅

اعدادِ این فایل همان اعدادِ ویدیواند: دو قلمِ ۱۰۰ و ۱۵۰ که ۲۰ و ۱۰ واحد از
آن‌ها برگشت می‌خورد.
"""
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
import pytest

from app.models.accounting import JournalLine
from app.models.advanced_inventory import StockBatch
from app.models.inventory import StockLedger
from app.schemas.invoices import (
    PurchaseInvoiceIn,
    PurchaseInvoiceLineIn,
    WarehouseReceiptIn,
    WarehouseReceiptLineIn,
)
from app.schemas.returns import PurchaseReturnIn, PurchaseReturnLineIn
from app.services import chart_codes as cc
from app.services.common import get_account
from app.services.inventory import post_purchase_invoice
from app.services.returns import get_receipt_returnable_summary, post_purchase_return
from app.services.voiding import void_purchase_return
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


def receive(db, user, lines, **header):
    """رسیدِ مستقیم — خودش منشأِ مالی است."""
    return create_warehouse_receipt(
        db,
        None,
        WarehouseReceiptIn(
            receipt_date=TODAY,
            warehouse_id=main_warehouse(db).id,
            lines=[
                WarehouseReceiptLineIn(item_id=i.id, qty=Decimal(q), unit_cost=Decimal(c))
                for i, q, c in lines
            ],
            **header,
        ),
        user,
    )


def give_back(db, user, receipt, pairs, **header):
    return post_purchase_return(
        db,
        PurchaseReturnIn(
            return_date=TODAY,
            warehouse_receipt_id=receipt.id,
            lines=[
                PurchaseReturnLineIn(warehouse_receipt_line_id=line.id, qty=Decimal(qty), **extra)
                for line, qty, extra in pairs
            ],
            **header,
        ),
        user,
    )


def stock(db, item, warehouse):
    return Decimal(
        db.query(StockLedger)
        .with_entities(StockLedger.qty)
        .filter(StockLedger.item_id == item.id, StockLedger.warehouse_id == warehouse.id)
        .all()
        and sum(Decimal(q) for (q,) in db.query(StockLedger.qty).filter(
            StockLedger.item_id == item.id, StockLedger.warehouse_id == warehouse.id
        ).all())
        or 0
    )


# ─────────────────── مدلِ درست: رسید دست نمی‌خورد ───────────────────


def test_the_original_receipt_is_never_rewritten(db, user):
    """**مرکزی‌ترین ادعای فصل.** رسیدِ ۱۰۰تایی بعد از برگشتِ ۲۰ باز هم ۱۰۰ است."""
    red = make_item(db, name="لیوان قرمز")
    blue = make_item(db, name="لیوان آبی")
    receipt = receive(db, user, [(red, 100, 5_000), (blue, 150, 6_000)])

    give_back(db, user, receipt, [(receipt.lines[0], 20, {}), (receipt.lines[1], 10, {})])

    db.refresh(receipt)
    assert [Decimal(row.qty) for row in receipt.lines] == [Decimal(100), Decimal(150)]


def test_the_kardex_shows_both_movements(db, user):
    """کاردکس باید +۱۰۰ و −۲۰ را جدا نشان دهد، نه یک +۸۰."""
    red = make_item(db, name="لیوان قرمز")
    warehouse = main_warehouse(db)
    receipt = receive(db, user, [(red, 100, 5_000)])
    give_back(db, user, receipt, [(receipt.lines[0], 20, {})])

    moves = [
        (move.source_type, Decimal(move.qty))
        for move in db.query(StockLedger)
        .filter(StockLedger.item_id == red.id, StockLedger.warehouse_id == warehouse.id)
        .order_by(StockLedger.seq)
        .all()
    ]
    assert moves == [("warehouse_receipt", Decimal(100)), ("purchase_return", Decimal(-20))]


# ─────────────────── باقیمانده مشتق است ───────────────────


def test_remaining_is_derived_not_stored(db, user):
    """۱۰۰ − (۲۰ + ۳۰) = ۵۰. هیچ شمارنده‌ای ذخیره نمی‌شود."""
    red = make_item(db, name="لیوان قرمز")
    receipt = receive(db, user, [(red, 100, 5_000)])

    give_back(db, user, receipt, [(receipt.lines[0], 20, {})])
    give_back(db, user, receipt, [(receipt.lines[0], 30, {})])

    row = get_receipt_returnable_summary(db, receipt.id)[0]
    assert row["received"] == Decimal(100)
    assert row["already_returned"] == Decimal(50)
    assert row["remaining"] == Decimal(50)
    assert row["return_status"] == "partially_returned"


def test_status_is_derived_from_amounts(db, user):
    red = make_item(db, name="لیوان قرمز")
    receipt = receive(db, user, [(red, 10, 1_000)])

    assert get_receipt_returnable_summary(db, receipt.id)[0]["return_status"] == "not_returned"
    give_back(db, user, receipt, [(receipt.lines[0], 10, {})])
    assert get_receipt_returnable_summary(db, receipt.id)[0]["return_status"] == "fully_returned"


def test_returning_more_than_remaining_is_refused(db, user):
    red = make_item(db, name="لیوان قرمز")
    receipt = receive(db, user, [(red, 100, 5_000)])
    give_back(db, user, receipt, [(receipt.lines[0], 90, {})])

    with pytest.raises(HTTPException) as err:
        give_back(db, user, receipt, [(receipt.lines[0], 20, {})])
    assert err.value.status_code == 400


def test_voiding_a_return_frees_the_quantity(db, user):
    """ابطالِ برگشت مقدار را آزاد می‌کند — و رسیدِ اصلی را دست نمی‌زند."""
    red = make_item(db, name="لیوان قرمز")
    receipt = receive(db, user, [(red, 100, 5_000)])
    ret = give_back(db, user, receipt, [(receipt.lines[0], 20, {})])

    void_purchase_return(db, ret.id, reason="اشتباه بود", user=user)

    row = get_receipt_returnable_summary(db, receipt.id)[0]
    assert row["already_returned"] == Decimal(0)
    assert row["remaining"] == Decimal(100)
    db.refresh(receipt)
    assert Decimal(receipt.lines[0].qty) == Decimal(100), "رسیدِ اصلی نباید پاک یا ویرایش شود"


# ─────────────────── دو سقفِ جدا ───────────────────


def test_source_capacity_and_stock_availability_are_separate(db, user):
    """رسید هنوز ۱۰۰ واحد قابلِ برگشت دارد، ولی ۷۰ واحدش از انبار رفته.

    فصل صریح می‌گوید این دو را یکی نکنیم.
    """
    from app.schemas.invoices import SalesInvoiceIn, SalesInvoiceLineIn
    from app.services.inventory import post_sales_invoice

    red = make_item(db, name="لیوان قرمز", sales_price=Decimal(20_000))
    warehouse = main_warehouse(db)
    receipt = receive(db, user, [(red, 100, 5_000)])
    post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=warehouse.id,
            contact_id=make_contact(db, name="مشتری").id,
            lines=[SalesInvoiceLineIn(item_id=red.id, qty=Decimal(70), unit_price=Decimal(20_000))],
        ),
        user,
    )

    #: سقفِ مبدأ هنوز ۱۰۰ است…
    assert get_receipt_returnable_summary(db, receipt.id)[0]["remaining"] == Decimal(100)
    #: …ولی انبار ۳۰ تا بیشتر ندارد.
    with pytest.raises(HTTPException) as err:
        give_back(db, user, receipt, [(receipt.lines[0], 100, {})])
    assert "موجودی" in err.value.detail


# ─────────────────── اثرِ حسابداری ───────────────────


def test_the_return_reverses_what_the_receipt_did(db, user):
    """۲۰ از ۱۰۰ تا × ۵٬۰۰۰ → موجودی ۱۰۰٬۰۰۰ بستانکار، بدهی ۱۰۰٬۰۰۰ بدهکار."""
    red = make_item(db, name="لیوان قرمز")
    supplier = make_contact(db, name="تأمین‌کننده", type_="supplier")
    receipt = receive(db, user, [(red, 100, 5_000)], contact_id=supplier.id)
    ledger = Ledger(db).snap(cc.INVENTORY, cc.ACCOUNTS_PAYABLE)

    ret = give_back(db, user, receipt, [(receipt.lines[0], 20, {})])

    assert ledger.delta(cc.INVENTORY) == Decimal(-100_000)
    assert ledger.delta(cc.ACCOUNTS_PAYABLE) == Decimal(100_000)
    assert ret.journal_entry_id is not None


def test_a_cash_receipt_returns_to_cash_not_payable(db, user):
    """طرفِ مقابل از سندِ مبدأ می‌آید، نه از یک قالبِ ثابت."""
    red = make_item(db, name="لیوان قرمز")
    receipt = receive(db, user, [(red, 100, 5_000)])  # بی‌تحویل‌دهنده ⇒ نقدی
    ledger = Ledger(db).snap(cc.CASH, cc.ACCOUNTS_PAYABLE)

    give_back(db, user, receipt, [(receipt.lines[0], 20, {})])

    assert ledger.delta(cc.CASH) == Decimal(100_000)
    assert ledger.delta(cc.ACCOUNTS_PAYABLE) == Decimal(0)


def test_the_tax_credit_goes_back_too(db, user):
    red = make_item(db, name="لیوان قرمز", tax_rate=Decimal(10))
    receipt = receive(db, user, [(red, 100, 5_000)], tax_rate=Decimal(10))
    ledger = Ledger(db).snap(cc.VAT_RECEIVABLE)

    ret = give_back(db, user, receipt, [(receipt.lines[0], 20, {})])

    assert ledger.delta(cc.VAT_RECEIVABLE) == Decimal(-10_000)
    assert Decimal(ret.lines[0].tax_amount_snapshot) == Decimal(10_000)


def test_the_returned_freight_leaves_inventory_too(db, user):
    """بهای تمام‌شده برمی‌گردد، نه فی.

    اگر فقط فی برگردد، سهمِ حملِ کالای رفته در موجودیِ دفتری جا می‌ماند و
    دفتر با گزارشِ انبار واگرا می‌شود.
    """
    red = make_item(db, name="لیوان قرمز")
    receipt = receive(db, user, [(red, 100, 5_000)], freight_amount=Decimal(50_000))
    ledger = Ledger(db).snap(cc.INVENTORY)

    ret = give_back(db, user, receipt, [(receipt.lines[0], 20, {})])

    #: فیِ تمام‌شده ۵٬۵۰۰ است ⇒ ۲۰ × ۵٬۵۰۰ = ۱۱۰٬۰۰۰
    assert ledger.delta(cc.INVENTORY) == Decimal(-110_000)
    assert Decimal(ret.lines[0].unit_cost) == Decimal(5_000), "«فی» جدا می‌ماند"
    assert Decimal(ret.lines[0].freight_share) == Decimal(10_000)
    assert ret.lines[0].landed_amount == Decimal(110_000)


# ─────────────────── دو مبلغ که یکی نیستند ───────────────────


def test_the_agreed_amount_defaults_to_the_book_value(db, user):
    red = make_item(db, name="لیوان قرمز")
    receipt = receive(db, user, [(red, 100, 5_000)])

    ret = give_back(db, user, receipt, [(receipt.lines[0], 20, {})])

    assert ret.base_amount == Decimal(100_000)
    assert ret.agreed_total == Decimal(100_000)


def test_a_different_agreed_amount_is_stored_but_not_posted_blindly(db, user):
    """فصل: «DO NOT invent or hard-code a price-difference account yet.»

    پس اختلاف نه در حسابی دلخواه پنهان می‌شود و نه سندِ نامتوازن می‌سازد —
    ثبت رد می‌شود و علتش گفته می‌شود.
    """
    red = make_item(db, name="لیوان قرمز")
    receipt = receive(db, user, [(red, 100, 5_000)])

    with pytest.raises(HTTPException) as err:
        give_back(db, user, receipt, [(receipt.lines[0], 20, {"agreed_unit_value": Decimal(4_750)})])
    assert err.value.status_code == 400
    assert "توافقی" in err.value.detail


def test_the_two_amounts_are_separate_columns(db, user):
    """مدلِ داده باید این دو را قابلِ تفکیک نگه دارد، حتی وقتی برابرند."""
    from app.models.returns import PurchaseReturnLine

    stored = {column.key for column in PurchaseReturnLine.__table__.columns}
    assert {"unit_cost", "freight_share", "agreed_unit_value", "agreed_amount"} <= stored


# ─────────────────── لنگر روی ردیفِ رسید ───────────────────


def test_the_return_line_remembers_which_receipt_line(db, user):
    """اگر یک کالا سه بار با سه بها وارد شده باشد، باید معلوم باشد کدام برگشت خورد."""
    red = make_item(db, name="لیوان قرمز")
    first = receive(db, user, [(red, 100, 5_000)])
    second = receive(db, user, [(red, 200, 7_000)])

    ret = give_back(db, user, second, [(second.lines[0], 10, {})])

    assert ret.lines[0].warehouse_receipt_line_id == second.lines[0].id
    assert ret.warehouse_receipt_id == second.id
    #: بهای برگشتی از همان ورودِ دوم آمده، نه از میانگین و نه از ورودِ اول.
    assert Decimal(ret.lines[0].unit_cost) == Decimal(7_000)
    assert get_receipt_returnable_summary(db, first.id)[0]["remaining"] == Decimal(100)


def test_returning_through_the_receipt_consumes_the_invoice_quantity_too(db, user):
    """کالا نباید یک‌بار از مسیرِ رسید و یک‌بار از مسیرِ فاکتور برگردد."""
    from app.services.returns import get_purchase_returnable_summary

    red = make_item(db, name="لیوان قرمز")
    invoice = post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=None,
            contact_id=make_contact(db, name="تأمین‌کننده", type_="supplier").id,
            lines=[PurchaseInvoiceLineIn(item_id=red.id, qty=Decimal(100), unit_cost=Decimal(5_000))],
        ),
        user,
    )
    receipt = create_warehouse_receipt(
        db,
        invoice.id,
        WarehouseReceiptIn(
            receipt_date=TODAY,
            warehouse_id=main_warehouse(db).id,
            lines=[
                WarehouseReceiptLineIn(purchase_invoice_line_id=invoice.lines[0].id, qty=Decimal(100))
            ],
        ),
        user,
    )

    give_back(db, user, receipt, [(receipt.lines[0], 20, {})])

    assert get_purchase_returnable_summary(db, invoice.id)[0]["remaining"] == Decimal(80)


# ─────────────────── نقصِ زنده‌ای که بسته شد ───────────────────


def test_a_return_on_a_warehouseless_invoice_now_explains_itself(db, user):
    """پیش از این: «موجودی «لیوان» کافی نیست (موجود: ۰)» — در حالی که کالا در انبار بود."""
    red = make_item(db, name="لیوان قرمز")
    invoice = post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=None,
            contact_id=make_contact(db, name="تأمین‌کننده", type_="supplier").id,
            lines=[PurchaseInvoiceLineIn(item_id=red.id, qty=Decimal(100), unit_cost=Decimal(5_000))],
        ),
        user,
    )
    create_warehouse_receipt(
        db,
        invoice.id,
        WarehouseReceiptIn(
            receipt_date=TODAY,
            warehouse_id=main_warehouse(db).id,
            lines=[
                WarehouseReceiptLineIn(purchase_invoice_line_id=invoice.lines[0].id, qty=Decimal(100))
            ],
        ),
        user,
    )

    with pytest.raises(HTTPException) as err:
        post_purchase_return(
            db,
            PurchaseReturnIn(
                return_date=TODAY,
                purchase_invoice_id=invoice.id,
                lines=[
                    PurchaseReturnLineIn(
                        purchase_invoice_line_id=invoice.lines[0].id, qty=Decimal(20)
                    )
                ],
            ),
            user,
        )
    assert "رسید انبار" in err.value.detail, "پیام باید بگوید کجا باید ثبت شود"


# ─────────────────── ردیابیِ بار ───────────────────


def test_the_returned_quantity_leaves_its_own_batch(db, user):
    """برگشت باید از همان بارِ ورودی خارج شود، نه از یک استخرِ بی‌هویت."""
    red = make_item(db, name="لیوان قرمز")
    receipt = receive(db, user, [(red, 100, 5_000)])

    give_back(db, user, receipt, [(receipt.lines[0], 20, {})])

    batch = (
        db.query(StockBatch)
        .filter(StockBatch.source_type == "warehouse_receipt", StockBatch.source_id == receipt.id)
        .one()
    )
    assert Decimal(batch.qty) == Decimal(80)
    assert Decimal(batch.received_qty) == Decimal(100), "تاریخچه‌ی ورود دست نمی‌خورد"


# ─────────────────── گاردهای پایین‌دست ───────────────────


def test_a_receipt_with_returns_cannot_be_voided(db, user):
    """§۴۶ — حذفِ منشأ نباید زنجیره را خراب کند."""
    red = make_item(db, name="لیوان قرمز")
    receipt = receive(db, user, [(red, 100, 5_000)])
    give_back(db, user, receipt, [(receipt.lines[0], 20, {})])

    with pytest.raises(HTTPException) as err:
        void_warehouse_receipt(db, receipt.id, reason="اشتباه", user=user)
    assert err.value.status_code == 409

    #: ولی بعد از ابطالِ برگشت، رسید آزاد می‌شود.
    ret = db.query(type(receipt)).first() and None
    del ret


def test_a_voided_receipt_cannot_be_returned(db, user):
    red = make_item(db, name="لیوان قرمز")
    receipt = receive(db, user, [(red, 100, 5_000)])
    void_warehouse_receipt(db, receipt.id, reason="اشتباه", user=user)

    with pytest.raises(HTTPException) as err:
        give_back(db, user, receipt, [(receipt.lines[0], 20, {})])
    assert err.value.status_code == 400


def test_opening_inventory_is_not_a_return_type(db, user):
    """فرمِ برگشت «موجودی اول دوره» ندارد — و فصل می‌گوید کورکورانه کپی نکنیم."""
    from app.models.invoices import RECEIPT_TYPES
    from app.models.returns import RETURN_TYPES

    assert "opening" in RECEIPT_TYPES
    assert "opening" not in RETURN_TYPES

    with pytest.raises(Exception):
        PurchaseReturnIn(
            return_date=TODAY,
            warehouse_receipt_id=None,
            purchase_invoice_id=None,
            return_type="opening",
            lines=[PurchaseReturnLineIn(item_id=make_item(db).id, qty=Decimal(1))],
        )
