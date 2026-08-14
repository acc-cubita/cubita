"""باقی‌ماندهٔ قابلِ برگشت و چاپِ سندِ برگشت از فروش."""
from datetime import date

TODAY = str(date.today())


def _wh(client):
    return client.post("/api/warehouses", json={"code": "RW", "name": "انبار برگشت"}).json()["id"]


def _item(client, sku="R-1"):
    return client.post("/api/items", json={"sku": sku, "name": "کالای برگشتی", "sales_price": 5000}).json()["id"]


def _buy(client, wh, item, qty=10, cost=1000):
    client.post(
        "/api/purchase-invoices",
        json={
            "invoice_date": TODAY,
            "warehouse_id": wh,
            "tax_rate": 0,
            "lines": [{"item_id": item, "qty": qty, "unit_cost": cost}],
        },
    )


def _sell(client, wh, item, qty=5, price=5000):
    return client.post(
        "/api/sales-invoices",
        json={
            "invoice_date": TODAY,
            "warehouse_id": wh,
            "tax_rate": 0,
            "lines": [{"item_id": item, "qty": qty, "unit_price": price}],
        },
    ).json()


def test_returnable_reports_remaining(client):
    wh, item = _wh(client), _item(client)
    _buy(client, wh, item, qty=10)
    inv = _sell(client, wh, item, qty=5)

    rows = client.get(f"/api/sales-invoices/{inv['id']}/returnable").json()
    assert len(rows) == 1
    row = rows[0]
    assert row["item_id"] == item
    assert float(row["sold"]) == 5
    assert float(row["already_returned"]) == 0
    assert float(row["remaining"]) == 5

    # برگشتِ جزئی → باقی‌مانده کم می‌شود
    client.post(
        "/api/sales-returns",
        json={"return_date": TODAY, "sales_invoice_id": inv["id"], "lines": [{"item_id": item, "qty": 2}]},
    )
    rows2 = client.get(f"/api/sales-invoices/{inv['id']}/returnable").json()
    assert float(rows2[0]["already_returned"]) == 2
    assert float(rows2[0]["remaining"]) == 3


def test_returnable_404_for_missing_invoice(client):
    r = client.get("/api/sales-invoices/00000000-0000-0000-0000-000000000999/returnable")
    assert r.status_code == 404


def test_sales_return_print_shows_kind_and_item(client):
    wh, item = _wh(client), _item(client)
    _buy(client, wh, item, qty=10)
    inv = _sell(client, wh, item, qty=5)
    ret = client.post(
        "/api/sales-returns",
        json={"return_date": TODAY, "sales_invoice_id": inv["id"], "lines": [{"item_id": item, "qty": 2}]},
    ).json()

    r = client.get(f"/api/sales-returns/{ret['id']}/print")
    assert r.status_code == 200
    html = r.text
    assert "برگشت از فروش" in html
    assert "کالای برگشتی" in html
