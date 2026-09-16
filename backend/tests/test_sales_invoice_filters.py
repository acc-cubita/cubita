"""فیلترِ سمتِ سرورِ فهرستِ فاکتورهای فروش.

**چه کم بود.** `GET /api/sales-invoices` فقط `limit` و `cursor` می‌گرفت. پس هر
صفحه‌ای که می‌خواست فاکتورهای یک مشتری یا یک بازه را نشان دهد **کلِ دفتر را
دانلود می‌کرد** و در مرورگر فیلتر می‌کرد — دو صفحه این کار را می‌کردند
(`SalesInvoiceListPage` و `ContactStatementPage`).

قراردادِ صفحه‌های کوبیتا (§۷) صریح است: «فیلتر سمتِ سرور است نه مرورگر. کشیدنِ
کلِ دفتر برای فیلترکردنش در کلاینت، با اولین کسب‌وکارِ چندساله از کار می‌افتد.»

**قیدی که این فایل نگه می‌دارد:** پاسخِ **بی‌فیلتر** نباید عوض شود. پیش‌فرض
همیشه رفتارِ دیروز است، وگرنه این تغییر فراخوان‌های موجود را بی‌صدا می‌شکند.
"""
from datetime import date
from decimal import Decimal

from app.models.inventory import Contact
from tests.factories import main_warehouse, make_item


def _customer(db, name) -> Contact:
    row = Contact(name=name, type="customer")
    db.add(row)
    db.flush()
    return row


def _stock_up(db, user, item, warehouse, qty=100) -> None:
    from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn
    from app.services.inventory import post_purchase_invoice

    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=date(2026, 1, 1),
            warehouse_id=warehouse.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(qty), unit_cost=Decimal(1000))],
        ),
        user,
    )


def _sell(db, user, client, *, contact, on: str, price=5000):
    item = make_item(db, sales_price=Decimal(price))
    warehouse = main_warehouse(db)
    _stock_up(db, user, item, warehouse)
    db.commit()
    response = client.post(
        "/api/sales-invoices",
        json={
            "invoice_date": on,
            "warehouse_id": str(warehouse.id),
            "contact_id": str(contact.id),
            "lines": [{"item_id": str(item.id), "qty": 1, "unit_price": price}],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _ids(response) -> set:
    assert response.status_code == 200, response.text
    return {row["id"] for row in response.json()["items"]}


# ─────────────── فیلترِ مشتری ───────────────


def test_the_contact_filter_returns_only_that_customer(client, db, user):
    """**هسته‌ی این اصلاح** — «فلان مشتری چه فاکتورهایی داشته».

    تا امروز جوابِ این سؤال یعنی دانلودِ کلِ دفتر.
    """
    alice = _customer(db, "مشتریِ الف")
    bob = _customer(db, "مشتریِ ب")
    mine = _sell(db, user, client, contact=alice, on="2026-06-10")
    theirs = _sell(db, user, client, contact=bob, on="2026-06-11")

    got = _ids(client.get("/api/sales-invoices", params={"contact_id": alice.id}))
    assert mine["id"] in got
    assert theirs["id"] not in got, "*** فاکتورِ مشتریِ دیگر در فهرست ماند ***"


def test_an_unknown_contact_returns_nothing(client, db, user):
    """مشتریِ بی‌فاکتور باید فهرستِ خالی بدهد، نه کلِ دفتر."""
    alice = _customer(db, "مشتریِ تنها")
    _sell(db, user, client, contact=alice, on="2026-06-12")
    empty = _customer(db, "مشتریِ بی‌خرید")

    assert _ids(client.get("/api/sales-invoices", params={"contact_id": empty.id})) == set()


# ─────────────── بازه‌ی تاریخ ───────────────


def test_the_date_range_includes_both_ends(client, db, user):
    """مرزها **شامل** خودشان‌اند — فاکتورِ روزِ اول و روزِ آخر باید بیایند."""
    who = _customer(db, "مشتریِ بازه")
    first = _sell(db, user, client, contact=who, on="2026-07-01")
    middle = _sell(db, user, client, contact=who, on="2026-07-15")
    last = _sell(db, user, client, contact=who, on="2026-07-31")

    got = _ids(client.get("/api/sales-invoices", params={"date_from": "2026-07-01", "date_to": "2026-07-31"}))
    assert {first["id"], middle["id"], last["id"]} <= got


def test_invoices_outside_the_range_are_excluded(client, db, user):
    who = _customer(db, "مشتریِ خارج از بازه")
    inside = _sell(db, user, client, contact=who, on="2026-08-15")
    before = _sell(db, user, client, contact=who, on="2026-07-20")
    after = _sell(db, user, client, contact=who, on="2026-09-05")

    got = _ids(client.get("/api/sales-invoices", params={"date_from": "2026-08-01", "date_to": "2026-08-31"}))
    assert inside["id"] in got
    assert before["id"] not in got
    assert after["id"] not in got


def test_one_sided_range_works(client, db, user):
    """فقط `date_from` یا فقط `date_to` هم باید کار کند."""
    who = _customer(db, "مشتریِ یک‌طرفه")
    old = _sell(db, user, client, contact=who, on="2026-02-01")
    new = _sell(db, user, client, contact=who, on="2026-11-01")

    only_from = _ids(client.get("/api/sales-invoices", params={"date_from": "2026-10-01"}))
    assert new["id"] in only_from and old["id"] not in only_from

    only_to = _ids(client.get("/api/sales-invoices", params={"date_to": "2026-03-01"}))
    assert old["id"] in only_to and new["id"] not in only_to


def test_the_filters_combine(client, db, user):
    """مشتری و بازه با هم — نه یکی یا دیگری."""
    alice = _customer(db, "الف ترکیبی")
    bob = _customer(db, "ب ترکیبی")
    want = _sell(db, user, client, contact=alice, on="2026-05-10")
    wrong_date = _sell(db, user, client, contact=alice, on="2026-01-10")
    wrong_contact = _sell(db, user, client, contact=bob, on="2026-05-11")

    got = _ids(client.get(
        "/api/sales-invoices",
        params={"contact_id": alice.id, "date_from": "2026-05-01", "date_to": "2026-05-31"},
    ))
    assert got == {want["id"]} or want["id"] in got
    assert wrong_date["id"] not in got
    assert wrong_contact["id"] not in got


# ─────────────── پیش‌فرض = رفتارِ دیروز ───────────────


def test_without_filters_nothing_changes(client, db, user):
    """**عمدی و مهم.** پاسخِ بی‌فیلتر باید همان باشد که بود.

    ده‌ها فراخوانِ موجود هیچ پارامتری نمی‌فرستند؛ اگر پیش‌فرض عوض شود،
    بی‌صدا می‌شکنند.
    """
    who = _customer(db, "مشتریِ پیش‌فرض")
    made = [
        _sell(db, user, client, contact=who, on="2026-04-01")["id"],
        _sell(db, user, client, contact=who, on="2026-04-02")["id"],
    ]
    got = _ids(client.get("/api/sales-invoices"))
    assert set(made) <= got, "*** فهرستِ بی‌فیلتر ردیف جا انداخت ***"


def test_the_lines_still_come_with_the_list(client, db, user):
    """فهرست از قبل ردیف‌های فاکتور را می‌دهد — به همین دلیل اندپوینتِ تکی لازم نشد.

    اگر این بشکند، رابط برای نمایشِ اقلام چاره‌ای جز فراخوانِ دوم ندارد.
    """
    who = _customer(db, "مشتریِ اقلام")
    made = _sell(db, user, client, contact=who, on="2026-06-20")

    rows = client.get("/api/sales-invoices", params={"contact_id": who.id}).json()["items"]
    row = next(r for r in rows if r["id"] == made["id"])
    assert row["lines"], "*** فهرست دیگر ردیف‌ها را نمی‌دهد ***"
    assert Decimal(str(row["lines"][0]["qty"])) == Decimal(1)
