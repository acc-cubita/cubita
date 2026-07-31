"""باقی‌ماندهٔ قابلِ برگشت و چاپِ سندِ برگشت از خرید."""
from datetime import date

TODAY = str(date.today())


def _wh(client):
    return client.post("/api/warehouses", json={"code": "PW", "name": "انبار خرید"}).json()["id"]


def _item(client, sku="PR-1"):
    return client.post("/api/items", json={"sku": sku, "name": "کالای خریدنی", "sales_price": 5000}).json()["id"]


def _buy(client, wh, item, qty=10, cost=1000):
    return client.post(
        "/api/purchase-invoices",
        json={
            "invoice_date": TODAY,
            "warehouse_id": wh,
            "tax_rate": 0,
            "lines": [{"item_id": item, "qty": qty, "unit_cost": cost}],
        },
    ).json()


def test_purchase_returnable_reports_remaining(client):
    wh, item = _wh(client), _item(client)
    inv = _buy(client, wh, item, qty=10)

    rows = client.get(f"/api/purchase-invoices/{inv['id']}/returnable").json()
    assert len(rows) == 1
    assert float(rows[0]["sold"]) == 10
    assert float(rows[0]["remaining"]) == 10

    client.post(
        "/api/purchase-returns",
        json={"return_date": TODAY, "purchase_invoice_id": inv["id"], "lines": [{"item_id": item, "qty": 3}]},
    )
    rows2 = client.get(f"/api/purchase-invoices/{inv['id']}/returnable").json()
    assert float(rows2[0]["already_returned"]) == 3
    assert float(rows2[0]["remaining"]) == 7


def test_purchase_returnable_404(client):
    r = client.get("/api/purchase-invoices/00000000-0000-0000-0000-000000000999/returnable")
    assert r.status_code == 404


def test_purchase_return_print(client):
    wh, item = _wh(client), _item(client)
    inv = _buy(client, wh, item, qty=10)
    ret = client.post(
        "/api/purchase-returns",
        json={"return_date": TODAY, "purchase_invoice_id": inv["id"], "lines": [{"item_id": item, "qty": 2}]},
    ).json()

    r = client.get(f"/api/purchase-returns/{ret['id']}/print")
    assert r.status_code == 200
    html = r.text
    assert "برگشت از خرید" in html
    assert "کالای خریدنی" in html
