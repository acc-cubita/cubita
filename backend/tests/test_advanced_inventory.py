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

    # ذخیره‌ی دوباره فقط ردیفِ فرستاده‌شده را عوض می‌کند؛ ردیفِ نیامده می‌ماند.
    #
    # این تست تا امروز عکسِ این را تثبیت می‌کرد («b removed») — و همان یک خط
    # رفتاری را قانونی می‌کرد که کلِ ماتریسِ قیمت را با یک «ذخیره» پاک می‌کرد.
    r = client.put(f"/api/price-lists/{pl}/items", json={"items": [{"item_id": a, "price": 7500}]})
    got = {x["item_id"]: float(x["price"]) for x in client.get(f"/api/price-lists/{pl}/items").json()}
    assert got == {a: 7500, b: 12000}

    # حذفِ یک قاعده مسیرِ صریحِ خودش را دارد
    row_b = next(x["id"] for x in client.get(f"/api/price-lists/{pl}/items").json() if x["item_id"] == b)
    assert client.delete(f"/api/price-lists/{pl}/items/{row_b}").status_code == 204
    assert [x["item_id"] for x in client.get(f"/api/price-lists/{pl}/items").json()] == [a]

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


# ── جداسازیِ بارِ ورودی (بچ‌سازیِ خودکار هنگامِ خرید) ──────────────────
def _main_wh(client):
    return next(w["id"] for w in client.get("/api/warehouses").json() if w["code"] == "MAIN")


def test_purchase_creates_a_batch_per_line(client):
    wh = _main_wh(client)
    a = _item(client, "BP-A", "الف")
    b = _item(client, "BP-B", "ب")
    r = client.post("/api/purchase-invoices", json={
        "invoice_date": TODAY, "warehouse_id": wh,
        "lines": [
            {"item_id": a, "qty": 100, "unit_cost": 5000},
            {"item_id": b, "qty": 40, "unit_cost": 8000},
        ],
    })
    assert r.status_code == 201, r.text
    num = r.json()["number"]

    batches = client.get("/api/stock-batches").json()
    mine = [x for x in batches if x["source_type"] == "purchase_invoice"]
    assert len(mine) == 2
    by_item = {x["item_id"]: x for x in mine}
    assert float(by_item[a]["received_qty"]) == 100 and float(by_item[a]["qty"]) == 100
    assert float(by_item[a]["unit_cost"]) == 5000
    assert by_item[a]["batch_number"] == f"P{num}-1"
    assert by_item[b]["batch_number"] == f"P{num}-2"
    assert by_item[a]["defect_qty"] == "0" or float(by_item[a]["defect_qty"]) == 0


def test_service_line_creates_no_batch(client):
    wh = _main_wh(client)
    svc = client.post("/api/items", json={"sku": "SVC-1", "name": "خدمت", "is_service": True}).json()["id"]
    client.post("/api/purchase-invoices", json={
        "invoice_date": TODAY, "warehouse_id": wh,
        "lines": [{"item_id": svc, "qty": 1, "unit_cost": 1000}],
    })
    assert client.get("/api/stock-batches", params={"item_id": svc}).json() == []


# ── سریالِ کارتن ─────────────────────────────────────────
def test_batch_serials_manual_and_sequence(client):
    wh = _wh(client)
    it = _item(client, "SER-1", "کالای سریالی")
    batch = client.post("/api/stock-batches", json={
        "item_id": it, "warehouse_id": wh, "batch_number": "SB-1", "qty": 50, "received_date": TODAY,
    }).json()["id"]

    # افزودنِ دستی
    r = client.post(f"/api/stock-batches/{batch}/serials", json={"serials": ["CTN-A", "CTN-B", "CTN-A"]})
    assert r.status_code == 201, r.text
    assert sorted(s["serial"] for s in r.json()) == ["CTN-A", "CTN-B"]  # تکراری حذف شد

    # توالیِ خودکار CTN-001..CTN-003 با صفرِ چپ
    r = client.post(f"/api/stock-batches/{batch}/serials", json={"prefix": "CTN-", "start": 1, "count": 3, "pad": 3})
    serials = sorted(s["serial"] for s in r.json())
    assert "CTN-001" in serials and "CTN-002" in serials and "CTN-003" in serials

    # نشانه‌گذاریِ یکی به‌عنوان معیوب
    one = next(s for s in client.get(f"/api/stock-batches/{batch}/serials").json() if s["serial"] == "CTN-001")
    r = client.patch(f"/api/stock-batch-serials/{one['id']}", json={"status": "defect"})
    assert r.status_code == 200 and r.json()["status"] == "defect"

    # حذفِ یک سریال
    assert client.delete(f"/api/stock-batch-serials/{one['id']}").status_code == 204

    # serial_count روی بار به‌روز است
    b = next(x for x in client.get("/api/stock-batches").json() if x["id"] == batch)
    assert b["serial_count"] == 4  # A, B, 002, 003


# ── کسری/معیوب/ضایعات ───────────────────────────────────
def test_batch_defect_reduces_stock_and_batch(client):
    wh = _main_wh(client)
    it = _item(client, "DF-1", "کالای معیوب‌دار")
    client.post("/api/purchase-invoices", json={
        "invoice_date": TODAY, "warehouse_id": wh,
        "lines": [{"item_id": it, "qty": 100, "unit_cost": 5000}],
    })
    batch = next(x for x in client.get("/api/stock-batches", params={"item_id": it}).json() if x["source_type"] == "purchase_invoice")

    # ۱۰ عدد معیوب
    r = client.post(f"/api/stock-batches/{batch['id']}/adjust", json={
        "qty": 10, "reason": "defect", "notes": "کارتنِ خیس", "adjustment_date": TODAY,
    })
    assert r.status_code == 200, r.text
    assert float(r.json()["qty"]) == 90 and float(r.json()["defect_qty"]) == 10

    # موجودیِ انبار هم ۱۰ کم شده (۱۰۰ → ۹۰)
    levels = client.get("/api/stock").json()
    total = sum(float(s["qty"]) for s in levels if s["item_id"] == it)
    assert total == 90


def test_batch_defect_cannot_exceed_remaining(client):
    wh = _main_wh(client)
    it = _item(client, "DF-2", "کالا")
    client.post("/api/purchase-invoices", json={
        "invoice_date": TODAY, "warehouse_id": wh,
        "lines": [{"item_id": it, "qty": 5, "unit_cost": 1000}],
    })
    batch = next(x for x in client.get("/api/stock-batches", params={"item_id": it}).json() if x["source_type"] == "purchase_invoice")
    r = client.post(f"/api/stock-batches/{batch['id']}/adjust", json={"qty": 6, "reason": "shortage", "adjustment_date": TODAY})
    assert r.status_code == 400
