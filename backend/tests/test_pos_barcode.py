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


def test_duplicate_barcode_rejected_on_create(client):
    """دو کالا با یک بارکد مجاز نیست — بازتابِ یکتاییِ uq_items_tenant_barcode."""
    r = client.post("/api/items", json={"sku": "DUP-1", "name": "اولی", "barcode": "6261111111118"})
    assert r.status_code == 201
    r = client.post("/api/items", json={"sku": "DUP-2", "name": "دومی", "barcode": "6261111111118"})
    assert r.status_code == 409, r.text
    assert "قبلاً" in r.json()["detail"] and "اولی" in r.json()["detail"]


def test_duplicate_barcode_rejected_on_update(client):
    a = client.post("/api/items", json={"sku": "DUP-3", "name": "الف", "barcode": "6262222222225"}).json()
    b = client.post("/api/items", json={"sku": "DUP-4", "name": "ب"}).json()
    # تلاش برای دادنِ بارکدِ الف به ب → رد
    r = client.patch(f"/api/items/{b['id']}", json={"barcode": "6262222222225"})
    assert r.status_code == 409, r.text
    # به‌روزرسانیِ خودِ الف با همان بارکدِ خودش نباید رد شود (exclude_id)
    r = client.patch(f"/api/items/{a['id']}", json={"barcode": "6262222222225", "name": "الف نو"})
    assert r.status_code == 200, r.text


def test_multiple_items_without_barcode_allowed(client):
    """چند کالای بی‌بارکد (NULL) باید مجاز بمانند — ایندکسِ یکتا جزئی است."""
    assert client.post("/api/items", json={"sku": "NB-1", "name": "یک"}).status_code == 201
    assert client.post("/api/items", json={"sku": "NB-2", "name": "دو"}).status_code == 201
