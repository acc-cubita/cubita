"""مرور فروش — و خطری که این فصل را خطرناک می‌کند: شمردنِ دوباره.

یک فاکتورِ سه‌ردیفی می‌تواند در نمای «اسناد» ۱۰۰ باشد و در نمای «اقلام» سه ردیف
که جمعشان هم ۱۰۰ است. اگر دانه‌بندی‌ها قاطی شوند، همان ۱۰۰ می‌شود ۳۰۰. و ردیفی
که از دو انبار خارج شده، با یک پیوستِ خام مبلغش دو برابر می‌شود.

تست‌های این فایل عمداً روی همین ریاضی تمرکز دارند، نه روی «آیا صفحه باز می‌شود».
"""
from datetime import date
from decimal import Decimal

from app.models.invoices import SalesInvoiceLine
from app.services import sales_review
from app.services.sales_review import Scope

TODAY = date.today().isoformat()


def _mode(client, mode):
    assert client.patch("/api/sales-invoice-posting", json={"mode": mode}).status_code == 200


def _customer(client, name):
    return client.post("/api/contacts", json={"name": name, "type": "customer"}).json()["id"]


def _stocked(client, code, qty=200):
    wh = client.post("/api/warehouses", json={"code": code, "name": f"انبار {code}"}).json()["id"]
    item = client.post("/api/items", json={"sku": f"{code}-I", "name": f"کالای {code}", "sales_price": 1000}).json()["id"]
    assert client.post(
        "/api/purchase-invoices",
        json={"invoice_date": TODAY, "warehouse_id": wh, "lines": [{"item_id": item, "qty": qty, "unit_cost": 400}]},
    ).status_code == 201
    return wh, item


def _sell(client, *, lines, wh=None, contact=None, tax=0):
    body = {"invoice_date": TODAY, "tax_rate": tax, "lines": lines}
    if wh:
        body["warehouse_id"] = wh
    if contact:
        body["contact_id"] = contact
    r = client.post("/api/sales-invoices", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _line_ids(db, invoice_id):
    return [
        row.id
        for row in db.query(SalesInvoiceLine)
        .filter(SalesInvoiceLine.invoice_id == invoice_id)
        .order_by(SalesInvoiceLine.id)
    ]


def _issue(client, invoice_id, wh, line_id, qty):
    r = client.post(
        f"/api/sales-invoices/{invoice_id}/warehouse-issues",
        json={
            "issue_date": TODAY,
            "warehouse_id": wh,
            "lines": [{"sales_invoice_line_id": str(line_id), "qty": qty}],
        },
    )
    assert r.status_code in (200, 201), r.text
    return r


def _return(client, invoice_id, line_id, qty):
    r = client.post(
        "/api/sales-returns",
        json={
            "sales_invoice_id": invoice_id,
            "return_date": TODAY,
            "lines": [{"sales_invoice_line_id": str(line_id), "qty": qty}],
        },
    )
    assert r.status_code == 201, r.text
    return r


# ═══════════════ ۱) دانه‌بندی — شمردنِ دوباره ═══════════════


def test_a_three_line_invoice_counts_once_at_document_grain(client, db):
    """۱۰۰ باید ۱۰۰ بماند، نه ۳۰۰."""
    contact = _customer(client, "مشتریِ دانه‌بندی")
    wh, item = _stocked(client, "SR-A")
    invoice = _sell(
        client,
        wh=wh,
        contact=contact,
        lines=[
            {"item_id": item, "qty": 1, "unit_price": 10_000},
            {"item_id": item, "qty": 2, "unit_price": 10_000},
            {"item_id": item, "qty": 3, "unit_price": 10_000},
        ],
    )
    db.expire_all()
    scope = Scope(contact_id=contact)

    docs = sales_review.documents(db, scope)
    mine = [d for d in docs if str(d["source_id"]) == invoice["id"]]
    assert len(mine) == 1, "یک ردیف برای یک سند"
    assert mine[0]["line_count"] == 3
    assert mine[0]["gross_amount"] == 60_000

    #: نمای اقلام همان داده است، **باز** — پس جمعشان با هم دو برابر می‌شمرد.
    rows = [r for r in sales_review.lines(db, scope) if str(r["source_id"]) == invoice["id"]]
    assert len(rows) == 3
    assert sum(r["gross_amount"] for r in rows) == mine[0]["gross_amount"]


def test_two_warehouse_issues_do_not_double_the_sales_amount(client, db):
    """ردیفی که از دو انبار رفته، مبلغش یک بار شمرده می‌شود."""
    _mode(client, "staged")
    contact = _customer(client, "مشتریِ دوانباره")
    wh_a, item = _stocked(client, "SR-B")
    wh_b = client.post("/api/warehouses", json={"code": "SR-B2", "name": "انبار دوم"}).json()["id"]
    assert client.post(
        "/api/purchase-invoices",
        json={"invoice_date": TODAY, "warehouse_id": wh_b, "lines": [{"item_id": item, "qty": 50, "unit_cost": 400}]},
    ).status_code == 201

    invoice = _sell(client, contact=contact, lines=[{"item_id": item, "qty": 10, "unit_price": 1000}])
    line = _line_ids(db, invoice["id"])[0]
    _issue(client, invoice["id"], wh_a, line, 6)
    _issue(client, invoice["id"], wh_b, line, 4)

    db.expire_all()
    scope = Scope(contact_id=contact)
    docs = [d for d in sales_review.documents(db, scope) if str(d["source_id"]) == invoice["id"]]
    assert len(docs) == 1
    assert docs[0]["gross_amount"] == 10_000, "دو خروج مبلغ را دو برابر نمی‌کند"
    assert docs[0]["issued_qty"] == 10, "ولی مقدارِ خارج‌شده جمعِ هر دو است"


def test_two_returns_on_one_line_do_not_double_the_sales_amount(client, db):
    contact = _customer(client, "مشتریِ دوبرگشته")
    wh, item = _stocked(client, "SR-C")
    invoice = _sell(client, wh=wh, contact=contact, lines=[{"item_id": item, "qty": 10, "unit_price": 1000}])
    line = _line_ids(db, invoice["id"])[0]
    _return(client, invoice["id"], line, 2)
    _return(client, invoice["id"], line, 3)

    db.expire_all()
    docs = [
        d for d in sales_review.documents(db, Scope(contact_id=contact))
        if str(d["source_id"]) == invoice["id"]
    ]
    assert len(docs) == 1
    assert docs[0]["gross_amount"] == 10_000
    assert docs[0]["returned_qty"] == 5, "دو برگشت با هم جمع می‌شوند"
    assert docs[0]["return_amount"] == 5_000
    assert docs[0]["net_sales"] == 5_000


# ═══════════════ ۲) تجاری در برابر فیزیکی ═══════════════


def test_sold_and_issued_are_separate_numbers(client, db):
    """قلبِ این فصل: «۱۰ فروختم، ۷ فرستادم» دو عددِ مستقل‌اند."""
    _mode(client, "staged")
    contact = _customer(client, "مشتریِ تحقق")
    wh, item = _stocked(client, "SR-D")
    invoice = _sell(client, contact=contact, lines=[{"item_id": item, "qty": 10, "unit_price": 1000}])
    line = _line_ids(db, invoice["id"])[0]
    _issue(client, invoice["id"], wh, line, 7)

    db.expire_all()
    scope = Scope(contact_id=contact)
    items = [r for r in sales_review.by_item(db, scope) if str(r["item_id"]) == item]
    assert len(items) == 1
    row = items[0]
    assert row["sold_qty"] == 10
    assert row["issued_qty"] == 7
    assert row["unissued_qty"] == 3, "اختلاف — مفیدترین عددِ این گزارش"

    #: و در خلاصه‌ی سرصفحه هم دیده می‌شود.
    assert sales_review.summary(db, scope)["unissued_qty"] == 3


def test_a_voided_issue_stops_counting_as_fulfilled(client, db):
    _mode(client, "staged")
    contact = _customer(client, "مشتریِ ابطالِ خروج")
    wh, item = _stocked(client, "SR-E")
    invoice = _sell(client, contact=contact, lines=[{"item_id": item, "qty": 8, "unit_price": 1000}])
    line = _line_ids(db, invoice["id"])[0]
    issue = _issue(client, invoice["id"], wh, line, 8).json()

    db.expire_all()
    scope = Scope(contact_id=contact)
    assert sales_review.summary(db, scope)["issued_qty"] == 8

    r = client.post(f"/api/warehouse-issues/{issue['id']}/void", json={"reason": "اشتباه بود"})
    assert r.status_code in (200, 204), r.text

    db.expire_all()
    assert sales_review.summary(db, scope)["issued_qty"] == 0
    assert sales_review.summary(db, scope)["unissued_qty"] == 8


def test_stock_comes_from_the_inventory_ledger_not_from_sales(client, db):
    """موجودی از دفترِ موجودی می‌آید، نه از «فروش منهای برگشت»."""
    contact = _customer(client, "مشتریِ موجودی")
    wh, item = _stocked(client, "SR-F", qty=100)
    _sell(client, wh=wh, contact=contact, lines=[{"item_id": item, "qty": 30, "unit_price": 1000}])

    db.expire_all()
    row = next(r for r in sales_review.by_item(db, Scope(item_id=item)) if str(r["item_id"]) == item)
    assert row["stock_qty"] == 70, "۱۰۰ خرید منهای ۳۰ خروج"
    assert row["sold_qty"] == 30


# ═══════════════ ۳) اجزای پول ═══════════════


def test_the_money_components_stay_separate_and_explain_the_net(client, db):
    """خالص باید از اجزایش قابلِ توضیح باشد، نه یک عددِ مبهم."""
    contact = _customer(client, "مشتریِ اجزا")
    wh, item = _stocked(client, "SR-G")
    _sell(
        client,
        wh=wh,
        contact=contact,
        lines=[
            {
                "item_id": item,
                "qty": 10,
                "unit_price": 1000,
                "discount": 500,
                "addition": 300,
                "duty_amount": 200,
            }
        ],
    )
    db.expire_all()
    row = next(r for r in sales_review.by_item(db, Scope(contact_id=contact)) if str(r["item_id"]) == item)

    assert row["gross_amount"] == 10_000
    assert row["discount"] == 500
    assert row["addition"] == 300
    assert row["duty"] == 200
    #: و خالص دقیقاً از همین‌ها ساخته می‌شود.
    assert row["net_amount"] == 10_000 - 500 + row["tax"] + 200 + 300


def test_the_average_price_is_weighted_and_historical(client, db):
    """فیِ متوسط از معاملاتِ واقعی می‌آید، و **وزنی** است.

    میانگینِ سادهٔ فی‌ها، ردیفِ یک‌عددی را هم‌وزنِ ردیفِ صدعددی می‌کرد.
    """
    contact = _customer(client, "مشتریِ فیِ متوسط")
    wh, item = _stocked(client, "SR-H")
    _sell(
        client,
        wh=wh,
        contact=contact,
        lines=[
            {"item_id": item, "qty": 1, "unit_price": 10_000},
            {"item_id": item, "qty": 99, "unit_price": 1_000},
        ],
    )
    db.expire_all()
    row = next(r for r in sales_review.by_item(db, Scope(contact_id=contact)) if str(r["item_id"]) == item)

    #: وزنی: (۱۰٬۰۰۰ + ۹۹٬۰۰۰) ÷ ۱۰۰ = ۱٬۰۹۰. میانگینِ ساده ۵٬۵۰۰ می‌داد.
    assert row["average_unit_price"] == Decimal("1090")


# ═══════════════ ۴) مشتری و انبار ═══════════════


def test_customer_view_counts_invoices_not_lines(client, db):
    contact = _customer(client, "مشتریِ شمارش")
    wh, item = _stocked(client, "SR-I")
    _sell(
        client,
        wh=wh,
        contact=contact,
        lines=[
            {"item_id": item, "qty": 1, "unit_price": 1000},
            {"item_id": item, "qty": 1, "unit_price": 1000},
        ],
    )
    _sell(client, wh=wh, contact=contact, lines=[{"item_id": item, "qty": 1, "unit_price": 1000}])

    db.expire_all()
    row = next(r for r in sales_review.by_customer(db, Scope(contact_id=contact)))
    assert row["invoice_count"] == 2, "دو فاکتور، نه سه ردیف"
    assert row["gross_amount"] == 3_000


def test_warehouse_view_attributes_to_the_issuing_warehouse(client, db):
    """انبار از سندِ خروج می‌آید، نه از سربرگِ فاکتور."""
    _mode(client, "staged")
    contact = _customer(client, "مشتریِ انبار")
    wh_a, item = _stocked(client, "SR-J")
    wh_b = client.post("/api/warehouses", json={"code": "SR-J2", "name": "انبار دوم"}).json()["id"]
    assert client.post(
        "/api/purchase-invoices",
        json={"invoice_date": TODAY, "warehouse_id": wh_b, "lines": [{"item_id": item, "qty": 40, "unit_cost": 400}]},
    ).status_code == 201

    invoice = _sell(client, contact=contact, lines=[{"item_id": item, "qty": 10, "unit_price": 1000}])
    line = _line_ids(db, invoice["id"])[0]
    _issue(client, invoice["id"], wh_a, line, 6)
    _issue(client, invoice["id"], wh_b, line, 4)

    db.expire_all()
    rows = {str(r["warehouse_id"]): r for r in sales_review.by_warehouse(db, Scope(contact_id=contact))}
    assert rows[wh_a]["issued_qty"] == 6
    assert rows[wh_b]["issued_qty"] == 4


# ═══════════════ ۵) ابطال ═══════════════


def test_a_voided_invoice_leaves_current_sales_but_stays_reportable(client, db):
    """فروشِ جاری اثرش را ندارد، ولی تاریخ پاک نمی‌شود."""
    contact = _customer(client, "مشتریِ ابطال")
    wh, item = _stocked(client, "SR-K")
    invoice = _sell(client, wh=wh, contact=contact, lines=[{"item_id": item, "qty": 4, "unit_price": 1000}])

    db.expire_all()
    scope = Scope(contact_id=contact)
    assert sales_review.summary(db, scope)["net_sales"] == 4_000

    r = client.post(f"/api/sales-invoices/{invoice['id']}/void", json={"reason": "اشتباه بود"})
    assert r.status_code in (200, 204), r.text

    db.expire_all()
    assert sales_review.summary(db, scope)["net_sales"] == 0, "از فروشِ جاری بیرون می‌رود"
    voided = sales_review.voided_documents(db, scope)
    assert [str(v["source_id"]) for v in voided] == [invoice["id"]], "ولی در نمای ابطالی‌ها هست"
    assert voided[0]["gross_amount"] == 4_000


# ═══════════════ ۶) پیش‌فاکتور ═══════════════


def test_preinvoice_progress_has_three_independent_numbers(client, db):
    """پیشنهادشده، فاکتورشده، خارج‌شده — و هیچ‌کدام از دیگری حدس زده نمی‌شود."""
    _mode(client, "staged")
    contact = _customer(client, "مشتریِ پیش‌فاکتور")
    wh, item = _stocked(client, "SR-L")

    q = client.post(
        "/api/sales-quotations",
        json={
            "quotation_date": TODAY,
            "contact_id": contact,
            "lines": [{"item_id": item, "qty": 20, "unit_price": 1000}],
        },
    )
    assert q.status_code == 201, q.text

    db.expire_all()
    rows = sales_review.preinvoices(db, Scope(contact_id=contact))
    assert len(rows) == 1
    assert rows[0]["quoted_qty"] == 20
    assert rows[0]["invoiced_qty"] == 0
    assert rows[0]["issued_qty"] == 0
    assert rows[0]["remaining_invoiceable"] == 20


def test_the_report_is_side_effect_free(client, db):
    """خواندنِ گزارش نباید هیچ‌چیز را عوض کند."""
    contact = _customer(client, "مشتریِ بی‌اثر")
    wh, item = _stocked(client, "SR-M")
    _sell(client, wh=wh, contact=contact, lines=[{"item_id": item, "qty": 5, "unit_price": 1000}])

    db.expire_all()
    scope = Scope(contact_id=contact)
    first = sales_review.summary(db, scope)
    for _ in range(3):
        sales_review.by_item(db, scope)
        sales_review.by_customer(db, scope)
        sales_review.documents(db, scope)
        sales_review.lines(db, scope)
        sales_review.by_warehouse(db, scope)
        sales_review.preinvoices(db, scope)
    db.expire_all()

    assert sales_review.summary(db, scope) == first
