"""کالای برگشتی به کدام انبار برمی‌گردد؟

مهاجرتِ ۰۱۲۵ ستونِ انبارِ فاکتور فروش را `nullable` کرد و سیاستِ «دومرحله‌ای»
فاکتورِ بی‌انبار را دست‌یافتنی کرد. برگشت از فروش همان ستون را در
`stock_ledger.warehouse_id` می‌نوشت — که `NOT NULL` است. نتیجه: **خطای ۵۰۰
مدیریت‌نشده**، روی مسیرِ زنده.

و مسئله‌ی عمیق‌ترش: در حالتِ دومرحله‌ای ممکن است کالا هنوز از انبار خارج نشده
باشد؛ برگرداندنش موجودی‌ای اضافه می‌کند که هرگز کم نشده بود.
"""
from datetime import date

import pytest

from app.models.inventory import StockLedger
from app.models.invoices import SalesInvoiceLine

TODAY = date.today().isoformat()


def _mode(client, mode):
    r = client.patch("/api/sales-invoice-posting", json={"mode": mode})
    assert r.status_code == 200, r.text


def _stocked(client, code):
    wh = client.post("/api/warehouses", json={"code": code, "name": f"انبار {code}"}).json()["id"]
    item = client.post("/api/items", json={"sku": f"{code}-1", "name": "کالا", "sales_price": 1000}).json()["id"]
    r = client.post(
        "/api/purchase-invoices",
        json={"invoice_date": TODAY, "warehouse_id": wh, "lines": [{"item_id": item, "qty": 60, "unit_cost": 400}]},
    )
    assert r.status_code == 201, r.text
    return wh, item


def _sell(client, item, *, wh=None, qty=5, contact=None):
    body = {
        "invoice_date": TODAY,
        "tax_rate": 0,
        "lines": [{"item_id": item, "qty": qty, "unit_price": 1000}],
    }
    if wh:
        body["warehouse_id"] = wh
    if contact:
        body["contact_id"] = contact
    r = client.post("/api/sales-invoices", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _line_id(db, invoice_id):
    return db.query(SalesInvoiceLine.id).filter(SalesInvoiceLine.invoice_id == invoice_id).scalar()


def _return(client, invoice_id, line_id, qty):
    return client.post(
        "/api/sales-returns",
        json={
            "sales_invoice_id": invoice_id,
            "return_date": TODAY,
            "lines": [{"sales_invoice_line_id": str(line_id), "qty": qty}],
        },
    )


def _issue(client, invoice_id, wh, line_id, qty):
    return client.post(
        f"/api/sales-invoices/{invoice_id}/warehouse-issues",
        json={
            "issue_date": TODAY,
            "warehouse_id": wh,
            "lines": [{"sales_invoice_line_id": str(line_id), "qty": qty}],
        },
    )


def _stock_rows(db, invoice_return_source="sales_return"):
    return (
        db.query(StockLedger.warehouse_id, StockLedger.qty)
        .filter(StockLedger.source_type == invoice_return_source)
        .all()
    )


# ───────────────────── باگی که بسته شد ─────────────────────


def test_returning_an_invoice_without_a_warehouse_no_longer_crashes(client, db):
    """پیش از این: `NotNullViolation` و ۵۰۰. حالا: پیامِ روشن با ۴۰۰."""
    _mode(client, "staged")
    wh, item = _stocked(client, "RW-A")
    invoice = _sell(client, item, qty=5)          # بی‌انبار — در حالتِ دومرحله‌ای مجاز است
    assert invoice["warehouse_id"] is None

    r = _return(client, invoice["id"], _line_id(db, invoice["id"]), 2)

    assert r.status_code == 400, r.text
    assert "خارج نشده" in r.json()["detail"]


def test_after_the_goods_leave_the_return_finds_their_warehouse(client, db):
    """دومرحله‌ای: برگشتِ تجاری موجودی را تکان نمی‌دهد؛ برگشتِ خروج کالا را برمی‌گرداند.

    از مهاجرتِ ۰۱۳۴ مالکِ برگشتِ فیزیکی «برگشت خروج انبار» است. پیشنهادِ انبارِ
    برگشت از **خروجِ واقعی** می‌آید، نه از سربرگِ فاکتور.
    """
    _mode(client, "staged")
    wh, item = _stocked(client, "RW-B")
    invoice = _sell(client, item, qty=5)
    line = _line_id(db, invoice["id"])

    issued = _issue(client, invoice["id"], wh, line, 5)
    assert issued.status_code in (200, 201), issued.text

    r = _return(client, invoice["id"], line, 2)
    assert r.status_code == 201, r.text
    assert r.json()["stock_mode"] == "issue_return"
    assert r.json()["physical_status"] == "not_returned"
    db.expire_all()
    assert _stock_rows(db) == [], "برگشتِ تجاری در دومرحله‌ای حرکتِ انبار نمی‌سازد"

    basis = client.get(f"/api/warehouse-issue-returns/basis/sales_return/{r.json()['id']}").json()
    assert basis["warehouse_id"] == wh
    back = client.post(
        "/api/warehouse-issue-returns",
        json={
            "return_date": TODAY, "return_type": "sale", "warehouse_id": basis["warehouse_id"],
            "lines": [{"sales_return_line_id": basis["lines"][0]["basis_line_id"], "qty": 2}],
        },
    )
    assert back.status_code == 201, back.text

    db.expire_all()
    rows = [(str(w), float(q)) for w, q in _stock_rows(db, "warehouse_issue_return")]
    assert (wh, 2.0) in rows, "کالا به همان انباری برگشت که از آن خارج شده بود"


def test_you_cannot_return_more_than_actually_left_the_warehouse(client, db):
    """برگشتِ بیش از خروج، موجودیِ نداشته می‌سازد."""
    _mode(client, "staged")
    wh, item = _stocked(client, "RW-C")
    invoice = _sell(client, item, qty=10)
    line = _line_id(db, invoice["id"])
    assert _issue(client, invoice["id"], wh, line, 4).status_code in (200, 201)

    r = _return(client, invoice["id"], line, 7)
    assert r.status_code == 400, r.text
    assert "خارج شده" in r.json()["detail"]


def test_goods_issued_from_two_warehouses_return_to_both(client, db):
    """§۲۴ — یک ردیفِ فاکتور می‌تواند از چند انبار تحقق یابد."""
    _mode(client, "staged")
    wh_a, item = _stocked(client, "RW-D")
    wh_b = client.post("/api/warehouses", json={"code": "RW-E", "name": "انبار دوم"}).json()["id"]
    assert client.post(
        "/api/purchase-invoices",
        json={"invoice_date": TODAY, "warehouse_id": wh_b, "lines": [{"item_id": item, "qty": 30, "unit_cost": 400}]},
    ).status_code == 201

    invoice = _sell(client, item, qty=10)
    line = _line_id(db, invoice["id"])
    assert _issue(client, invoice["id"], wh_a, line, 6).status_code in (200, 201)
    assert _issue(client, invoice["id"], wh_b, line, 4).status_code in (200, 201)

    #: در سیاستِ خودکار برگشت کالا را همان لحظه برمی‌گرداند — یک برگشتِ خروج برای هر انبار.
    _mode(client, "immediate")
    r = _return(client, invoice["id"], line, 8)
    assert r.status_code == 201, r.text

    db.expire_all()
    rows: dict[str, float] = {}
    for w, q in _stock_rows(db, "warehouse_issue_return"):
        rows[str(w)] = rows.get(str(w), 0.0) + float(q)
    #: به ترتیبِ خروج کشیده می‌شود: ۶ از انبارِ اول، ۲ از دومی.
    assert rows.get(wh_a) == 6.0
    assert rows.get(wh_b) == 2.0
    assert _stock_rows(db) == []


# ───────────────────── مسیرِ امروز دست‌نخورده ─────────────────────


def test_the_ordinary_path_still_returns_the_goods_at_once(client, db):
    """حالتِ خودکار برای کاربر عوض نمی‌شود: کالا همان لحظه برمی‌گردد — فقط با سندِ خودش."""
    _mode(client, "immediate")
    wh, item = _stocked(client, "RW-F")
    invoice = _sell(client, item, wh=wh, qty=5)
    assert invoice["warehouse_id"] == wh

    r = _return(client, invoice["id"], _line_id(db, invoice["id"]), 3)
    assert r.status_code == 201, r.text
    assert r.json()["physical_status"] == "fully_returned"

    db.expire_all()
    rows = [(str(w), float(q)) for w, q in _stock_rows(db, "warehouse_issue_return")]
    assert (wh, 3.0) in rows
    assert _stock_rows(db) == [], "دقیقاً یک حرکتِ مثبت — نه دو تا"


@pytest.mark.parametrize("mode", ["immediate", "staged"])
def test_a_service_line_never_touches_stock_in_either_mode(client, db, mode):
    """خدمت موجودی ندارد، پس نه خروجی لازم دارد نه برگشتش موجودی می‌سازد."""
    _mode(client, mode)
    wh = client.post("/api/warehouses", json={"code": f"RW-S{mode[:3]}", "name": "انبار"}).json()["id"]
    svc = client.post(
        "/api/items",
        json={"sku": f"RW-SVC-{mode}", "name": "خدمت", "sales_price": 5000, "is_service": True},
    ).json()["id"]

    body = {
        "invoice_date": TODAY,
        "tax_rate": 0,
        "lines": [{"item_id": svc, "qty": 1, "unit_price": 5000}],
    }
    if mode == "immediate":
        body["warehouse_id"] = wh
    invoice = client.post("/api/sales-invoices", json=body)
    assert invoice.status_code == 201, invoice.text

    line = _line_id(db, invoice.json()["id"])
    before = db.query(StockLedger).count()
    r = _return(client, invoice.json()["id"], line, 1)
    assert r.status_code == 201, r.text

    db.expire_all()
    assert db.query(StockLedger).count() == before, "خدمت هیچ ردیفِ موجودی نمی‌سازد"
