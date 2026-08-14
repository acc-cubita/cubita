"""خلاصه‌ی خرید — جمع‌بندیِ سمت‌سرور (قرینه‌ی خلاصه‌ی فروش، بدون سود)."""
from datetime import date
from decimal import Decimal

from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn
from app.services.inventory import post_purchase_invoice
from app.services.reports import get_purchase_summary
from app.services.voiding import void_purchase_invoice
from tests.factories import main_warehouse, make_item

TODAY = date.today()


def _buy(db, user, item, wh, qty, cost, tax=0):
    return post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            tax_rate=Decimal(tax),
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(qty), unit_cost=Decimal(cost))],
        ),
        user,
    )


def test_purchase_summary_empty(db):
    s = get_purchase_summary(db)
    assert s["invoice_count"] == 0
    assert s["total_with_tax"] == Decimal(0)
    assert s["avg_invoice"] == Decimal(0)


def test_purchase_summary_totals(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    _buy(db, user, item, wh, 2, 1_000_000, tax=10)
    s = get_purchase_summary(db)
    assert s["invoice_count"] == 1
    assert s["total_net"] == Decimal(2_000_000)
    assert s["total_tax"] == Decimal(200_000)
    assert s["total_with_tax"] == Decimal(2_200_000)
    assert s["avg_invoice"] == Decimal(2_200_000)


def test_purchase_summary_excludes_voided(db, user):
    wh = main_warehouse(db)
    item = make_item(db)
    inv = _buy(db, user, item, wh, 1, 1_000_000)
    void_purchase_invoice(db, inv.id, reason="اشتباهِ ثبت", user=user)
    s = get_purchase_summary(db)
    assert s["invoice_count"] == 0
    assert s["total_net"] == Decimal(0)


def test_purchase_summary_endpoint(client):
    r = client.get("/api/purchase-invoices/summary")
    assert r.status_code == 200, r.text
    assert r.json()["invoice_count"] == 0
