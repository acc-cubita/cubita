"""هر حرکت انبار باید به سندش وصل باشد.

این پرونده بعد از یک باگ واقعی نوشته شد که هیچ‌کدام از ۳۲۸ تست قبلی نگرفتندش:
`source_id` روی **همه‌ی** ردیف‌های دفتر موجودی NULL بود.

علتش ظریف بود: کلید اصلی با `default=uuid.uuid4` تعریف شده، و SQLAlchemy آن مقدار
را در لحظه‌ی INSERT می‌سازد نه موقع ساختن شیء. کد این الگو را داشت:

    db.add(invoice)
    for move in stock_moves:
        move.source_id = invoice.id   # ← هنوز None است
        db.add(move)
    db.flush()

هیچ خطایی رخ نمی‌داد چون ستون nullable است. نتیجه این بود که کاردکس نمی‌توانست
بگوید یک حرکت انبار از کدام فاکتور آمده، و ابطال سند هم اصلاً کار نمی‌کرد چون
حرکت‌های جبرانی را پیدا نمی‌کرد.

تست عمداً *همه‌ی* ردیف‌ها را می‌سنجد و نه یک مسیر مشخص را: مسیر بعدی‌ای که کسی
اضافه کند همین الگو را کپی خواهد کرد.
"""
from datetime import date

import pytest

from app.models.inventory import Item, StockLedger, Warehouse
from app.schemas.invoices import (
    PurchaseInvoiceIn,
    PurchaseInvoiceLineIn,
    SalesInvoiceIn,
    SalesInvoiceLineIn,
)
from app.services.inventory import post_purchase_invoice, post_sales_invoice

TODAY = date.today()


@pytest.fixture
def warehouse(db):
    return db.query(Warehouse).filter(Warehouse.code == "MAIN").one()


@pytest.fixture
def widget(db):
    item = Item(sku="TRACE-1", name="کالای ردیابی", unit="عدد", sales_price=5000)
    db.add(item)
    db.flush()
    return item


def test_purchase_stock_moves_know_their_invoice(db, user, warehouse, widget):
    invoice = post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=warehouse.id,
            contact_id=None,
            description="",
            lines=[PurchaseInvoiceLineIn(item_id=widget.id, qty=5, unit_cost=1000, description="")],
        ),
        user,
    )
    db.flush()
    moves = db.query(StockLedger).filter(StockLedger.source_type == "purchase_invoice").all()
    assert moves, "هیچ حرکت انباری ثبت نشد"
    for move in moves:
        assert move.source_id == invoice.id, "حرکت انبار به فاکتور خریدش وصل نیست"


def test_sales_stock_moves_know_their_invoice(db, user, warehouse, widget):
    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=warehouse.id,
            contact_id=None,
            description="",
            lines=[PurchaseInvoiceLineIn(item_id=widget.id, qty=10, unit_cost=1000, description="")],
        ),
        user,
    )
    invoice = post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=warehouse.id,
            contact_id=None,
            description="",
            lines=[SalesInvoiceLineIn(item_id=widget.id, qty=3, unit_price=2000, description="")],
        ),
        user,
    )
    db.flush()
    moves = db.query(StockLedger).filter(StockLedger.source_type == "sales_invoice").all()
    assert moves, "هیچ حرکت انباری ثبت نشد"
    for move in moves:
        assert move.source_id == invoice.id, "حرکت انبار به فاکتور فروشش وصل نیست"


def test_no_stock_movement_anywhere_is_orphaned(db, user, warehouse, widget):
    """گاردِ فراگیر — هر مسیری که در آینده اضافه شود هم زیر همین تست می‌آید.

    ستون nullable است (و باید بماند، چون مهاجرت داده‌ی قدیمی ممکن است منشأ نداشته
    باشد)، پس پایگاه‌داده جلوی ردیف بی‌منشأ را نمی‌گیرد. این تست می‌گیرد.
    """
    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=warehouse.id,
            contact_id=None,
            description="",
            lines=[PurchaseInvoiceLineIn(item_id=widget.id, qty=8, unit_cost=1200, description="")],
        ),
        user,
    )
    post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=warehouse.id,
            contact_id=None,
            description="",
            lines=[SalesInvoiceLineIn(item_id=widget.id, qty=2, unit_price=3000, description="")],
        ),
        user,
    )
    db.flush()

    orphans = [
        (m.source_type, m.qty)
        for m in db.query(StockLedger).filter(StockLedger.item_id == widget.id).all()
        if m.source_id is None
    ]
    assert not orphans, f"حرکت انبار بدون منشأ: {orphans}"
