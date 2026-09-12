"""«ثبت فاکتور» چه‌قدر کار انجام دهد — انتخابِ خودِ کسب‌وکار.

سه ادعا:

  ۱. پیش‌فرض **خودکار** است: فاکتور همان لحظه سندِ حسابداری و خروجِ انبار می‌زند.
  ۲. «دومرحله‌ای» هیچ‌کدام را نمی‌زند، ولی هر دو از فهرست صادر می‌شوند.
  ۳. عوض‌کردنِ سیاست **گذشته را دست نمی‌زند** — نه سندی پس می‌گیرد، نه سندی
     به فاکتورِ دیروز می‌دهد.
"""
from datetime import date

import pytest

from app.models.invoices import SalesInvoice, SalesInvoiceLine

TODAY = date.today().isoformat()


def _wh(client):
    return client.post("/api/warehouses", json={"code": "SP", "name": "انبار"}).json()["id"]


def _item(client, sku="SP-1"):
    return client.post("/api/items", json={"sku": sku, "name": "لیوان", "sales_price": 1000}).json()["id"]


def _stock(client, wh, item, qty=50):
    return client.post(
        "/api/purchase-invoices",
        json={
            "invoice_date": TODAY,
            "warehouse_id": wh,
            "lines": [{"item_id": item, "qty": qty, "unit_cost": 400}],
        },
    )


def _sell(client, wh, item, qty=2):
    r = client.post(
        "/api/sales-invoices",
        json={
            "invoice_date": TODAY,
            "warehouse_id": wh,
            "tax_rate": 0,
            "lines": [{"item_id": item, "qty": qty, "unit_price": 1000}],
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def _mode(client, mode):
    r = client.patch("/api/sales-invoice-posting", json={"mode": mode})
    assert r.status_code == 200, r.text
    return r.json()


def _line_ids(db, invoice_id):
    """شناسه‌ی ردیف‌های فاکتور — خروجیِ HTTP ردیف‌ها را برنمی‌گرداند."""
    return [
        row.id
        for row in db.query(SalesInvoiceLine)
        .filter(SalesInvoiceLine.invoice_id == invoice_id)
        .order_by(SalesInvoiceLine.id)
    ]


def _journal_of(db, invoice_id):
    db.expire_all()
    return db.get(SalesInvoice, invoice_id).journal_entry_id


def _stock_qty(client, wh, item):
    rows = client.get(f"/api/warehouses/{wh}/stock-positions").json()["items"]
    row = next((x for x in rows if x["item_id"] == item), None)
    return float(row["qty"]) if row else 0.0


# ───────────────────── سیاست و پیش‌فرضش ─────────────────────


def test_the_default_is_immediate_and_not_yet_chosen(client):
    r = client.get("/api/sales-invoice-posting")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "immediate"
    #: هنوز کسی انتخاب نکرده — رابط باید بتواند «پیش‌فرض» را از «انتخاب‌شده» جدا کند.
    assert body["is_explicit"] is False
    assert {o["key"] for o in body["options"]} == {"immediate", "staged"}
    assert next(o for o in body["options"] if o["is_default"])["key"] == "immediate"
    #: هر گزینه باید بگوید چه می‌شود، وگرنه کاربر کورکورانه انتخاب می‌کند.
    assert all(o["hint"] and o["effects"] for o in body["options"])


def test_an_unknown_mode_is_refused(client):
    assert client.patch("/api/sales-invoice-posting", json={"mode": "sometimes"}).status_code == 400


def test_choosing_a_mode_makes_it_explicit(client):
    assert _mode(client, "staged")["is_explicit"] is True
    assert client.get("/api/sales-invoice-posting").json()["mode"] == "staged"
    assert _mode(client, "immediate")["mode"] == "immediate"


# ───────────────────── اثرِ واقعیِ هر حالت ─────────────────────


def test_immediate_posts_the_journal_and_moves_stock(client):
    wh, item = _wh(client), _item(client)
    _stock(client, wh, item)
    before = _stock_qty(client, wh, item)

    invoice = _sell(client, wh, item, qty=2)

    assert invoice["journal_entry_id"] is not None, "سندِ حسابداری همان لحظه باید صادر شود"
    assert _stock_qty(client, wh, item) == before - 2


def test_staged_posts_neither_until_you_ask(client, db):
    wh, item = _wh(client), _item(client, "SP-2")
    _stock(client, wh, item)
    _mode(client, "staged")
    before = _stock_qty(client, wh, item)

    invoice = _sell(client, wh, item, qty=2)
    assert invoice["journal_entry_id"] is None
    assert _stock_qty(client, wh, item) == before, "موجودی نباید دست بخورد"

    #: و هر دو گام از فهرست در دسترس‌اند
    r = client.post(f"/api/sales-invoices/{invoice['id']}/journal")
    assert r.status_code == 200, r.text
    assert r.json()["journal_entry_id"] is not None

    line_id = _line_ids(db, invoice["id"])[0]
    issued = client.post(
        f"/api/sales-invoices/{invoice['id']}/warehouse-issues",
        json={
            "issue_date": TODAY,
            "warehouse_id": wh,
            "lines": [{"sales_invoice_line_id": str(line_id), "qty": 2}],
        },
    )
    assert issued.status_code in (200, 201), issued.text
    assert _stock_qty(client, wh, item) == before - 2


def test_switching_the_policy_leaves_yesterdays_invoices_alone(client, db):
    """تاریخ بازنویسی نمی‌شود — نه سندی پس گرفته می‌شود، نه سندی بخشیده."""
    wh, item = _wh(client), _item(client, "SP-3")
    _stock(client, wh, item)

    posted = _sell(client, wh, item, qty=1)          # خودکار
    _mode(client, "staged")
    unposted = _sell(client, wh, item, qty=1)        # دومرحله‌ای

    _mode(client, "immediate")                        # برگشت به خودکار

    #: فاکتورِ دومرحله‌ای همچنان بی‌سند است؛ سیاستِ تازه به عقب نمی‌رود.
    assert _journal_of(db, unposted["id"]) is None
    #: و فاکتورِ خودکار سندش را نگه می‌دارد.
    assert _journal_of(db, posted["id"]) is not None


@pytest.mark.parametrize("mode", ["immediate", "staged"])
def test_neither_mode_lets_you_sell_stock_you_do_not_have(client, db, mode):
    """مرزِ سیاست و یکپارچگی: این پرچم *زمانِ* کار را عوض می‌کند، نه مجازبودنش."""
    wh, item = _wh(client), _item(client, f"SP-X-{mode}")
    _stock(client, wh, item, qty=1)
    _mode(client, mode)

    r = client.post(
        "/api/sales-invoices",
        json={
            "invoice_date": TODAY,
            "warehouse_id": wh,
            "tax_rate": 0,
            "lines": [{"item_id": item, "qty": 99, "unit_price": 1000}],
        },
    )
    if mode == "immediate":
        assert r.status_code == 400, "کسرِ همان لحظه باید جلوی فروشِ نداشته را بگیرد"
    else:
        #: در حالتِ دومرحله‌ای فاکتور ثبت می‌شود (تعهدِ تجاری است)، ولی خروجِ انبار
        #: باید رد شود — همان‌جا که کالا واقعاً حرکت می‌کند.
        assert r.status_code == 201, r.text
        line_id = _line_ids(db, r.json()["id"])[0]
        issued = client.post(
            f"/api/sales-invoices/{r.json()['id']}/warehouse-issues",
            json={
                "issue_date": TODAY,
                "warehouse_id": wh,
                "lines": [{"sales_invoice_line_id": str(line_id), "qty": 99}],
            },
        )
        assert issued.status_code == 400
