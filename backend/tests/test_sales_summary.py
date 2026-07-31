"""خلاصه‌ی فروش — جمع‌بندیِ سمت سرور: سود ناخالص، مالیات، ۳۰ روزِ اخیر، حذفِ باطل‌ها.

این جمع در پایگاه‌داده انجام می‌شود تا کلاینت مجبور نباشد کلِ فاکتورها را دانلود کند.
"""
from datetime import date, timedelta
from decimal import Decimal

from app.schemas.invoices import (
    PurchaseInvoiceIn,
    PurchaseInvoiceLineIn,
    SalesInvoiceIn,
    SalesInvoiceLineIn,
)
from app.services.inventory import post_purchase_invoice, post_sales_invoice
from app.services.reports import get_sales_summary
from app.services.voiding import void_sales_invoice
from tests.factories import main_warehouse, make_item

TODAY = date.today()


def _stock_in(db, user, item, wh, qty, unit_cost):
    return post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(qty), unit_cost=Decimal(unit_cost))],
        ),
        user,
    )


def _sell(db, user, item, wh, qty, price, tax=0, when=TODAY):
    return post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=when,
            warehouse_id=wh.id,
            tax_rate=Decimal(tax),
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(qty), unit_price=Decimal(price))],
        ),
        user,
    )


def test_summary_empty(db):
    s = get_sales_summary(db)
    assert s["invoice_count"] == 0
    assert s["total_net"] == Decimal(0)
    assert s["gross_profit"] == Decimal(0)
    assert s["margin_pct"] == Decimal(0)


def test_summary_profit_and_tax(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    _stock_in(db, user, item, wh, 100, 600_000)  # میانگین بهای ۶۰۰هزار
    _sell(db, user, item, wh, 2, 1_000_000, tax=10)  # خالص ۲م، بها ۱٫۲م، سود ۸۰۰هزار، مالیات ۲۰۰هزار

    s = get_sales_summary(db)
    assert s["invoice_count"] == 1
    assert s["total_net"] == Decimal(2_000_000)
    assert s["total_tax"] == Decimal(200_000)
    assert s["total_with_tax"] == Decimal(2_200_000)
    assert s["total_cost"] == Decimal(1_200_000)
    assert s["gross_profit"] == Decimal(800_000)
    assert s["margin_pct"] == Decimal("40.00")
    assert s["avg_invoice"] == Decimal(2_200_000)


def test_voided_invoice_excluded(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    _stock_in(db, user, item, wh, 100, 500_000)
    inv = _sell(db, user, item, wh, 1, 1_000_000)
    void_sales_invoice(db, inv.id, reason="اشتباهِ ثبت", user=user)

    s = get_sales_summary(db)
    assert s["invoice_count"] == 0
    assert s["total_net"] == Decimal(0)
    assert s["gross_profit"] == Decimal(0)


def test_last_30_days_window(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    _stock_in(db, user, item, wh, 100, 100_000)
    _sell(db, user, item, wh, 1, 500_000, when=TODAY)
    _sell(db, user, item, wh, 1, 500_000, when=TODAY - timedelta(days=40))

    s = get_sales_summary(db)
    assert s["invoice_count"] == 2
    assert s["total_net"] == Decimal(1_000_000)
    # فقط فاکتورِ اخیر در پنجره‌ی ۳۰ روز می‌آید
    assert s["last_30_with_tax"] == Decimal(500_000)


def test_summary_endpoint(client):
    r = client.get("/api/sales-invoices/summary")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["invoice_count"] == 0
    assert Decimal(body["gross_profit"]) == Decimal(0)
