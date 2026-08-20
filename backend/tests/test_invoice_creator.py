"""نمایشِ ثبت‌کننده‌ی فاکتور — نام و نقشِ کاربری که فاکتور را زده.

`created_by_id` از قبل روی مدل بود؛ این تست قراردادِ خروجیِ API را می‌سنجد که نام و
نقش را هم بدهد (برای «چه کسی این فاکتور را زد» در رابط کاربری).
"""
from tests.factories import main_warehouse, make_item


def _make_purchase(client, wh, item):
    return client.post(
        "/api/purchase-invoices",
        json={
            "invoice_date": "2026-03-15",
            "warehouse_id": str(wh.id),
            "lines": [{"item_id": str(item.id), "qty": 3, "unit_cost": 1000}],
        },
    )


def test_create_response_carries_creator(client, db):
    wh = main_warehouse(db)
    item = make_item(db)
    r = _make_purchase(client, wh, item)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["created_by_id"] is not None
    assert body["created_by_name"] == "مالک تست"
    assert body["created_by_role"] == "مدیر/مالک"


def test_list_response_carries_creator(client, db):
    wh = main_warehouse(db)
    item = make_item(db)
    _make_purchase(client, wh, item)
    rows = client.get("/api/purchase-invoices").json()["items"]
    assert rows, "فاکتور باید در فهرست باشد"
    assert rows[0]["created_by_name"] == "مالک تست"
    assert rows[0]["created_by_role"] == "مدیر/مالک"


def test_sales_invoice_creator(client, db, user):
    """سمتِ فروش هم همان — بعد از تأمینِ موجودی، فاکتورِ فروش با نامِ ثبت‌کننده برمی‌گردد."""
    from decimal import Decimal
    from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn
    from app.services.inventory import post_purchase_invoice

    wh = main_warehouse(db)
    item = make_item(db)
    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date="2026-03-15",
            warehouse_id=wh.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(10), unit_cost=Decimal(1000))],
        ),
        user,
    )
    r = client.post(
        "/api/sales-invoices",
        json={
            "invoice_date": "2026-03-16",
            "warehouse_id": str(wh.id),
            "lines": [{"item_id": str(item.id), "qty": 2, "unit_price": 5000}],
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["created_by_name"] == "مالک تست"
    assert r.json()["created_by_role"] == "مدیر/مالک"
