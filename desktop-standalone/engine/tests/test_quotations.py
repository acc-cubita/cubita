"""پیش‌فاکتور: مشتری از فهرستِ اشخاص یا نامِ دستی."""
from datetime import date

TODAY = str(date.today())


def _wh(client):
    return client.post("/api/warehouses", json={"code": "QW", "name": "انبار"}).json()["id"]


def _item(client):
    return client.post("/api/items", json={"sku": "Q-1", "name": "کالا", "sales_price": 5000}).json()["id"]


def _buy(client, wh, item, qty=100, cost=1000):
    client.post("/api/purchase-invoices", json={
        "invoice_date": TODAY, "warehouse_id": wh, "tax_rate": 0,
        "lines": [{"item_id": item, "qty": qty, "unit_cost": cost}],
    })


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


def test_quotation_print_shows_manual_customer_name(client):
    wh, item = _wh(client), _item(client)
    q = _quote(client, wh, item, customer_name="آقای رضایی").json()
    r = client.get(f"/api/sales-quotations/{q['id']}/print")
    assert r.status_code == 200
    html = r.text
    assert "پیش‌فاکتور" in html
    assert "آقای رضایی" in html  # نامِ مشتریِ دستی در چاپ می‌آید


def test_quotation_print_empty_description_shows_proforma(client):
    wh, item = _wh(client), _item(client)
    q = _quote(client, wh, item).json()  # بدونِ توضیحات
    html = client.get(f"/api/sales-quotations/{q['id']}/print").text
    # توضیحاتِ خالی → «پیش‌فاکتور»، بدونِ جمله‌ی پیش‌فرض
    assert "پیش‌فاکتور" in html


def test_convert_carries_user_description_without_default_sentence(client):
    wh, item = _wh(client), _item(client)
    _buy(client, wh, item)
    q = _quote(client, wh, item, description="سفارشِ ویژه").json()
    inv = client.post(f"/api/sales-quotations/{q['id']}/convert").json()
    assert inv["description"] == "سفارشِ ویژه"
    assert "از پیش‌فاکتور شماره" not in inv["description"]


def test_convert_empty_description_stays_empty(client):
    wh, item = _wh(client), _item(client)
    _buy(client, wh, item)
    q = _quote(client, wh, item).json()
    inv = client.post(f"/api/sales-quotations/{q['id']}/convert").json()
    assert inv["description"] == ""


def test_update_quotation_edits_lines_total_and_customer(client):
    wh, item = _wh(client), _item(client)
    q = _quote(client, wh, item).json()  # qty 3 × 5000 = 15000
    assert float(q["total_amount"]) == 15000

    r = client.put(
        f"/api/sales-quotations/{q['id']}",
        json={
            "quotation_date": TODAY,
            "warehouse_id": wh,
            "customer_name": "مشتریِ ویرایش‌شده",
            "description": "به‌روزشده",
            "lines": [{"item_id": item, "qty": 5, "unit_price": 5000, "description": ""}],
        },
    )
    assert r.status_code == 200, r.text
    updated = r.json()
    assert float(updated["total_amount"]) == 25000  # ۵ × ۵۰۰۰
    assert updated["customer_name"] == "مشتریِ ویرایش‌شده"
    assert updated["description"] == "به‌روزشده"
    assert updated["number"] == q["number"]  # شماره ثابت می‌ماند
    assert len(updated["lines"]) == 1 and float(updated["lines"][0]["qty"]) == 5


def test_update_quotation_blocked_after_convert(client):
    wh, item = _wh(client), _item(client)
    _buy(client, wh, item)
    q = _quote(client, wh, item).json()
    client.post(f"/api/sales-quotations/{q['id']}/convert")
    r = client.put(
        f"/api/sales-quotations/{q['id']}",
        json={
            "quotation_date": TODAY,
            "warehouse_id": wh,
            "lines": [{"item_id": item, "qty": 1, "unit_price": 5000, "description": ""}],
        },
    )
    assert r.status_code == 400
    assert "تبدیل" in r.json()["detail"]


def test_quotation_pdf_endpoint(client):
    wh, item = _wh(client), _item(client)
    q = _quote(client, wh, item, customer_name="آقای رضایی").json()
    r = client.get(f"/api/sales-quotations/{q['id']}/pdf")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content[:4] == b"%PDF"  # امضای فایلِ PDF
