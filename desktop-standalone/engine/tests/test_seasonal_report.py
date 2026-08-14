"""گزارش معاملات فصلی (ماده ۱۶۹ ق.م.م): تجمیعِ خرید/فروشِ فصلی به تفکیکِ طرف حساب."""
from app.jalali import jalali_to_gregorian

YEAR = 1404
# یک تاریخ در «تابستان» (فصل ۲: تیر/مرداد/شهریور) و یکی در «بهار» (فصل ۱).
SUMMER = jalali_to_gregorian(YEAR, 5, 15).isoformat()   # مرداد
SPRING = jalali_to_gregorian(YEAR, 2, 10).isoformat()   # اردیبهشت


def _wh(client):
    return client.post("/api/warehouses", json={"code": "SZ", "name": "انبار"}).json()["id"]


def _item(client, sku):
    return client.post("/api/items", json={"sku": sku, "name": "کالا"}).json()["id"]


def _customer(client, **extra):
    body = {"name": "شرکت الف", "type": "customer", **extra}
    return client.post("/api/contacts", json=body).json()["id"]


def _supplier(client, **extra):
    body = {"name": "تأمین‌کننده ب", "type": "supplier", **extra}
    return client.post("/api/contacts", json=body).json()["id"]


def _buy(client, wh, item_id, qty, cost, date, contact_id=None, tax_rate=0):
    return client.post("/api/purchase-invoices", json={
        "invoice_date": date, "warehouse_id": wh, "contact_id": contact_id, "tax_rate": tax_rate,
        "lines": [{"item_id": item_id, "qty": qty, "unit_cost": cost}],
    })


def _sell(client, wh, item_id, qty, price, date, contact_id=None, tax_rate=0):
    return client.post("/api/sales-invoices", json={
        "invoice_date": date, "warehouse_id": wh, "contact_id": contact_id, "tax_rate": tax_rate,
        "lines": [{"item_id": item_id, "qty": qty, "unit_price": price}],
    })


def _seasonal(client, year=YEAR, quarter=2):
    r = client.get(f"/api/reports/seasonal?year={year}&quarter={quarter}")
    assert r.status_code == 200, r.text
    return r.json()


def test_seasonal_aggregates_sales_and_purchases_by_party(client):
    wh = _wh(client)
    it = _item(client, "SZ-1")
    cust = _customer(client, entity_type="legal", national_id="10101010101", economic_code="411111111111")
    supp = _supplier(client, entity_type="real", national_id="0012345678")

    # خرید در تابستان: ۱۰۰ × ۱٬۰۰۰ = ۱۰۰٬۰۰۰
    assert _buy(client, wh, it, 100, 1000, SUMMER, supp).status_code == 201
    # فروش در تابستان: ۵ × ۲۰٬۰۰۰ = ۱۰۰٬۰۰۰ + ۱۰٪ مالیات
    assert _sell(client, wh, it, 5, 20000, SUMMER, cust, tax_rate=10).status_code == 201

    rep = _seasonal(client)
    assert rep["quarter_label"] == "تابستان"

    # فروش
    srow = next(r for r in rep["sales"]["rows"] if r["contact_id"] == cust)
    assert srow["entity_type"] == "legal"
    assert srow["national_id"] == "10101010101"
    assert srow["economic_code"] == "411111111111"
    assert float(srow["net"]) == 100000
    assert float(srow["vat"]) == 10000
    assert float(srow["total"]) == 110000
    assert srow["invoice_count"] == 1

    # خرید
    prow = next(r for r in rep["purchases"]["rows"] if r["contact_id"] == supp)
    assert float(prow["net"]) == 100000
    assert prow["entity_type"] == "real"


def test_seasonal_walkin_sale_goes_to_aggregate_bucket(client):
    wh = _wh(client)
    it = _item(client, "SZ-2")
    _buy(client, wh, it, 100, 1000, SUMMER)
    # فروشِ نقدیِ بدونِ طرف حساب
    assert _sell(client, wh, it, 2, 15000, SUMMER, None).status_code == 201

    rep = _seasonal(client)
    agg = next(r for r in rep["sales"]["rows"] if r["contact_id"] is None)
    assert agg["entity_type"] == "aggregate"
    assert float(agg["net"]) == 30000


def test_seasonal_quarter_boundary_excludes_other_seasons(client):
    wh = _wh(client)
    it = _item(client, "SZ-3")
    cust = _customer(client)
    _buy(client, wh, it, 100, 1000, SPRING)
    # فروش در بهار — نباید در گزارشِ تابستان بیاید
    assert _sell(client, wh, it, 3, 10000, SPRING, cust).status_code == 201

    summer = _seasonal(client, quarter=2)
    assert all(r["contact_id"] != cust for r in summer["sales"]["rows"])

    spring = _seasonal(client, quarter=1)
    srow = next(r for r in spring["sales"]["rows"] if r["contact_id"] == cust)
    assert float(srow["net"]) == 30000


def test_seasonal_return_reduces_party_net(client):
    wh = _wh(client)
    it = _item(client, "SZ-4")
    cust = _customer(client)
    _buy(client, wh, it, 100, 1000, SUMMER)
    inv = _sell(client, wh, it, 10, 5000, SUMMER, cust).json()  # net 50,000

    # برگشت ۲ واحد در همان فصل → کاهشِ ۱۰٬۰۰۰
    r = client.post("/api/sales-returns", json={
        "return_date": SUMMER, "sales_invoice_id": inv["id"],
        "lines": [{"item_id": it, "qty": 2}],
    })
    assert r.status_code == 201, r.text

    rep = _seasonal(client)
    srow = next(r for r in rep["sales"]["rows"] if r["contact_id"] == cust)
    assert float(srow["net"]) == 40000


def test_seasonal_whole_year_covers_all_quarters(client):
    wh = _wh(client)
    it = _item(client, "SZ-5")
    cust = _customer(client)
    _buy(client, wh, it, 100, 1000, SPRING)
    _sell(client, wh, it, 1, 10000, SPRING, cust)
    _sell(client, wh, it, 1, 10000, SUMMER, cust)

    rep = _seasonal(client, quarter=0)
    assert rep["quarter_label"] == "کل سال"
    srow = next(r for r in rep["sales"]["rows"] if r["contact_id"] == cust)
    assert float(srow["net"]) == 20000
