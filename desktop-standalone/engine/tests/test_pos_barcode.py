"""بارکدِ کالا برای صندوقِ فروشگاهی (POS)."""


def test_item_barcode_create_and_lookup(client):
    r = client.post(
        "/api/items",
        json={"sku": "BC-1", "name": "کالای بارکددار", "barcode": "6260000000017", "sales_price": 50000},
    )
    assert r.status_code == 201, r.text
    assert r.json()["barcode"] == "6260000000017"

    r = client.get("/api/items/by-barcode", params={"code": "6260000000017"})
    assert r.status_code == 200
    assert r.json()["sku"] == "BC-1"

    assert client.get("/api/items/by-barcode", params={"code": "0000"}).status_code == 404


def test_blank_barcode_stored_as_null(client):
    r = client.post("/api/items", json={"sku": "BC-2", "name": "بدون بارکد", "barcode": "   "})
    assert r.status_code == 201
    assert r.json()["barcode"] is None


def test_barcode_can_be_set_and_cleared_via_update(client):
    item_id = client.post("/api/items", json={"sku": "BC-3", "name": "کالا"}).json()["id"]
    r = client.patch(f"/api/items/{item_id}", json={"barcode": "12345678"})
    assert r.status_code == 200 and r.json()["barcode"] == "12345678"
    r = client.patch(f"/api/items/{item_id}", json={"barcode": ""})
    assert r.status_code == 200 and r.json()["barcode"] is None
