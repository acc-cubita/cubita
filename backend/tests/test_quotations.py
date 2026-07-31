"""پیش‌فاکتور: مشتری از فهرستِ اشخاص یا نامِ دستی."""
from datetime import date

TODAY = str(date.today())


def _wh(client):
    return client.post("/api/warehouses", json={"code": "QW", "name": "انبار"}).json()["id"]


def _item(client):
    return client.post("/api/items", json={"sku": "Q-1", "name": "کالا", "sales_price": 5000}).json()["id"]


def _quote(client, wh, item, **extra):
    body = {
        "quotation_date": TODAY,
        "warehouse_id": wh,
        "lines": [{"item_id": item, "qty": 3, "unit_price": 5000, "description": ""}],
        **extra,
    }
    return client.post("/api/sales-quotations", json=body)


def test_quotation_with_contact(client):
    wh, item = _wh(client), _item(client)
    cust = client.post("/api/contacts", json={"name": "شرکت الف", "type": "customer"}).json()["id"]
    r = _quote(client, wh, item, contact_id=cust)
    assert r.status_code == 201, r.text
    q = r.json()
    assert q["contact_id"] == cust
    assert q["customer_name"] is None
    assert float(q["total_amount"]) == 15000


def test_quotation_with_manual_customer_name(client):
    wh, item = _wh(client), _item(client)
    r = _quote(client, wh, item, customer_name="آقای رضایی")
    assert r.status_code == 201, r.text
    q = r.json()
    assert q["contact_id"] is None
    assert q["customer_name"] == "آقای رضایی"


def test_contact_takes_precedence_over_manual_name(client):
    wh, item = _wh(client), _item(client)
    cust = client.post("/api/contacts", json={"name": "شرکت ب", "type": "customer"}).json()["id"]
    r = _quote(client, wh, item, contact_id=cust, customer_name="نامِ نادیده")
    assert r.status_code == 201, r.text
    q = r.json()
    assert q["contact_id"] == cust
    assert q["customer_name"] is None  # وقتی طرف‌حساب انتخاب شده، نامِ دستی نادیده گرفته می‌شود


def test_quotation_without_customer_still_valid(client):
    wh, item = _wh(client), _item(client)
    r = _quote(client, wh, item)
    assert r.status_code == 201, r.text
    assert r.json()["contact_id"] is None
    assert r.json()["customer_name"] is None
