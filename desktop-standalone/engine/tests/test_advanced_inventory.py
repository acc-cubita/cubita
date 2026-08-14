"""انبار پیشرفته — لیستِ قیمت و بچ/تاریخِ انقضا."""
from datetime import date, timedelta

TODAY = str(date.today())


def _wh(client):
    return client.post("/api/warehouses", json={"code": "ADV", "name": "انبار"}).json()["id"]


def _item(client, sku, name):
    return client.post("/api/items", json={"sku": sku, "name": name}).json()["id"]


def test_price_list_crud_and_prices(client):
    a = _item(client, "PL-A", "کالا الف")
    b = _item(client, "PL-B", "کالا ب")

    r = client.post("/api/price-lists", json={"name": "قیمت عمده"})
    assert r.status_code == 201, r.text
    pl = r.json()["id"]

    assert any(x["id"] == pl for x in client.get("/api/price-lists").json())

    # set prices
    r = client.put(f"/api/price-lists/{pl}/items", json={"items": [{"item_id": a, "price": 8000}, {"item_id": b, "price": 12000}]})
    assert r.status_code == 200, r.text
    prices = {x["item_id"]: float(x["price"]) for x in r.json()}
    assert prices[a] == 8000 and prices[b] == 12000

    # replace prices (b removed, a changed)
    r = client.put(f"/api/price-lists/{pl}/items", json={"items": [{"item_id": a, "price": 7500}]})
    got = client.get(f"/api/price-lists/{pl}/items").json()
    assert len(got) == 1 and float(got[0]["price"]) == 7500

    # deactivate
    r = client.patch(f"/api/price-lists/{pl}", json={"is_active": False})
    assert r.json()["is_active"] is False

    # negative price rejected
    assert client.put(f"/api/price-lists/{pl}/items", json={"items": [{"item_id": a, "price": -5}]}).status_code == 422


def test_stock_batches_and_expiring(client):
    wh = _wh(client)
    milk = _item(client, "MILK", "شیر")

    soon = str(date.today() + timedelta(days=10))
    far = str(date.today() + timedelta(days=200))

    r = client.post("/api/stock-batches", json={"item_id": milk, "warehouse_id": wh, "batch_number": "B-100", "expiry_date": soon, "qty": 50, "received_date": TODAY})
    assert r.status_code == 201, r.text
    client.post("/api/stock-batches", json={"item_id": milk, "warehouse_id": wh, "batch_number": "B-200", "expiry_date": far, "qty": 30, "received_date": TODAY})

    # list all
    assert len(client.get("/api/stock-batches").json()) == 2

    # expiring within 30 days → only B-100
    exp = client.get("/api/stock-batches/expiring", params={"days": 30}).json()
    assert len(exp) == 1 and exp[0]["batch_number"] == "B-100"

    # expiring within 365 → both
    assert len(client.get("/api/stock-batches/expiring", params={"days": 365}).json()) == 2


def test_batch_requires_number(client):
    wh = _wh(client)
    it = _item(client, "NB", "کالا")
    r = client.post("/api/stock-batches", json={"item_id": it, "warehouse_id": wh, "batch_number": "  ", "received_date": TODAY})
    assert r.status_code == 422
