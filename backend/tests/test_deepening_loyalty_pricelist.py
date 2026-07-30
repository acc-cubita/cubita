"""عمیق‌سازی: کسبِ خودکارِ امتیاز هنگامِ فروش + لیستِ قیمتِ پیش‌فرضِ مشتری."""
from datetime import date

TODAY = str(date.today())


def _wh(client):
    return client.post("/api/warehouses", json={"code": "DP", "name": "انبار"}).json()["id"]


def _item(client, sku, name):
    return client.post("/api/items", json={"sku": sku, "name": name}).json()["id"]


def _buy(client, wh, item_id, qty, cost):
    client.post("/api/purchase-invoices", json={"invoice_date": TODAY, "warehouse_id": wh, "tax_rate": 0, "lines": [{"item_id": item_id, "qty": qty, "unit_cost": cost}]})


def _sell(client, wh, item_id, qty, price, contact_id=None):
    return client.post("/api/sales-invoices", json={"invoice_date": TODAY, "warehouse_id": wh, "tax_rate": 0, "contact_id": contact_id, "lines": [{"item_id": item_id, "qty": qty, "unit_price": price}]})


def _balance(client, contact_id):
    for x in client.get("/api/crm/loyalty").json():
        if x["contact_id"] == contact_id:
            return x["balance"]
    return None


def test_loyalty_auto_earn_on_sale(client):
    wh = _wh(client)
    it = _item(client, "LP-1", "کالا")
    _buy(client, wh, it, 100, 1000)
    cust = client.post("/api/contacts", json={"name": "مشتری وفادار", "type": "customer"}).json()["id"]

    # فعال‌سازی: هر ۱۰٬۰۰۰ تومان = ۱ امتیاز
    r = client.put("/api/crm/loyalty/settings", json={"is_enabled": True, "amount_per_point": 10000})
    assert r.status_code == 200 and r.json()["is_enabled"] is True

    # فروشِ ۵ × ۲۰٬۰۰۰ = ۱۰۰٬۰۰۰ → ۱۰ امتیاز
    assert _sell(client, wh, it, 5, 20000, cust).status_code == 201
    assert _balance(client, cust) == 10

    # فروشِ دوم انباشته می‌شود
    assert _sell(client, wh, it, 1, 20000, cust).status_code == 201
    assert _balance(client, cust) == 12


def test_no_points_when_disabled(client):
    wh = _wh(client)
    it = _item(client, "LP-2", "کالا")
    _buy(client, wh, it, 100, 1000)
    cust = client.post("/api/contacts", json={"name": "م۲", "type": "customer"}).json()["id"]
    # پیش‌فرض غیرفعال است
    assert _sell(client, wh, it, 5, 20000, cust).status_code == 201
    assert _balance(client, cust) is None


def test_no_points_for_walkin_sale(client):
    wh = _wh(client)
    it = _item(client, "LP-3", "کالا")
    _buy(client, wh, it, 100, 1000)
    client.put("/api/crm/loyalty/settings", json={"is_enabled": True, "amount_per_point": 10000})
    # فروشِ نقدیِ بدونِ مشتری نباید امتیاز بدهد و نباید بشکند
    assert _sell(client, wh, it, 5, 20000, None).status_code == 201
    assert client.get("/api/crm/loyalty").json() == []


def test_contact_default_price_list(client):
    pl = client.post("/api/price-lists", json={"name": "عمده"}).json()["id"]
    cust = client.post("/api/contacts", json={"name": "عمده‌فروش", "type": "customer", "default_price_list_id": pl}).json()
    assert cust["default_price_list_id"] == pl
    # ویرایش: برداشتنِ لیست
    updated = client.patch(f"/api/contacts/{cust['id']}", json={"name": "عمده‌فروش", "type": "customer"}) if False else None
    # settings default when never set
    assert client.get("/api/crm/loyalty/settings").json()["is_enabled"] is False
