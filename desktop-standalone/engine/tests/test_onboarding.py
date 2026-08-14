"""راه‌اندازی: ورودِ گروهیِ کالا/اشخاص + مانده‌های اول دوره (سند افتتاحیه)."""
from datetime import date

TODAY = str(date.today())


def _acc(client, code):
    for a in client.get("/api/accounts").json():
        if a["code"] == code:
            return a["id"]
    raise AssertionError(f"account {code} not found")


# ── ورودِ گروهی ────────────────────────────────────────
def test_import_items_creates_and_skips_duplicates(client):
    # یک کالا از قبل هست تا رد شدنِ تکراری را بسنجیم
    client.post("/api/items", json={"sku": "IMP-1", "name": "قبلی"})
    r = client.post("/api/import/items", json={"rows": [
        {"sku": "IMP-1", "name": "تکراری"},               # رد
        {"sku": "IMP-2", "name": "کالای دو", "sales_price": 5000},
        {"sku": "IMP-3", "name": "کالای سه", "barcode": "1234567890123"},
        {"sku": "IMP-2", "name": "تکراری داخلِ دسته"},     # رد (داخلِ همین فایل)
        {"sku": "", "name": "بی‌کد"},                      # خطا
    ]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] == 2
    assert body["skipped"] == 2
    assert len(body["errors"]) == 1 and body["errors"][0]["row"] == 5

    skus = {i["sku"] for i in client.get("/api/items").json()["items"]}
    assert {"IMP-1", "IMP-2", "IMP-3"} <= skus


def test_import_contacts_creates_and_skips_by_name(client):
    client.post("/api/contacts", json={"name": "شرکت الف", "type": "customer"})
    r = client.post("/api/import/contacts", json={"rows": [
        {"name": "شرکت الف", "type": "customer"},          # رد (نامِ تکراری)
        {"name": "شرکت ب", "type": "supplier", "entity_type": "legal", "national_id": "10101010101"},
        {"name": "آقای پ", "type": "customer", "entity_type": "real"},
        {"name": "", "type": "customer"},                  # خطا
    ]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] == 2
    assert body["skipped"] == 1
    assert len(body["errors"]) == 1

    contacts = {c["name"]: c for c in client.get("/api/contacts").json()["items"]}
    assert contacts["شرکت ب"]["entity_type"] == "legal"
    assert contacts["شرکت ب"]["national_id"] == "10101010101"


# ── مانده‌های اول دوره ─────────────────────────────────
def test_opening_balances_balanced_with_plug(client):
    cash = _acc(client, "1101")
    capital = _acc(client, "3101")
    # فقط یک سمت را می‌دهیم؛ اختلاف به سرمایه بسته می‌شود
    r = client.post("/api/opening-balances", json={
        "entry_date": TODAY,
        "lines": [{"account_id": cash, "debit": 1000000}],
        "balancing_account_id": capital,
    })
    assert r.status_code == 201, r.text
    entry = r.json()
    assert entry["source_type"] == "opening"
    total_d = sum(float(l["debit"]) for l in entry["lines"])
    total_c = sum(float(l["credit"]) for l in entry["lines"])
    assert total_d == total_c == 1000000

    status = client.get("/api/opening-balances/status").json()
    assert status["exists"] is True

    # سندِ افتتاحیه‌ی دوم مجاز نیست
    r2 = client.post("/api/opening-balances", json={
        "entry_date": TODAY,
        "lines": [{"account_id": cash, "debit": 500000}],
        "balancing_account_id": capital,
    })
    assert r2.status_code == 409


def test_opening_unbalanced_without_plug_rejected(client):
    cash = _acc(client, "1101")
    r = client.post("/api/opening-balances", json={
        "entry_date": TODAY,
        "lines": [{"account_id": cash, "debit": 1000000}],
    })
    assert r.status_code == 400


def test_opening_stock_sets_average_cost_and_inventory_line(client):
    capital = _acc(client, "3101")
    wh = client.post("/api/warehouses", json={"code": "OP", "name": "انبار"}).json()["id"]
    it = client.post("/api/items", json={"sku": "OP-1", "name": "کالا"}).json()["id"]

    r = client.post("/api/opening-balances", json={
        "entry_date": TODAY,
        "stock": [{"item_id": it, "warehouse_id": wh, "qty": 10, "unit_cost": 5000}],
        "balancing_account_id": capital,
    })
    assert r.status_code == 201, r.text
    entry = r.json()
    # ارزشِ موجودی ۵۰٬۰۰۰ → بدهکارِ موجودی، بستانکارِ سرمایه
    total_d = sum(float(l["debit"]) for l in entry["lines"])
    assert total_d == 50000

    item = next(i for i in client.get("/api/items").json()["items"] if i["id"] == it)
    assert float(item["average_cost"]) == 5000

    # کاردکس باید حرکتِ «موجودی اول دوره» را نشان دهد
    kardex = client.get(f"/api/reports/kardex/{it}").json()
    assert any(l["source_label"] == "موجودی اول دوره" for l in kardex["lines"])
    assert float(kardex["closing_qty"]) == 10
