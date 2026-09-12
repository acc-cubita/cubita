"""اعلامیه‌ی بدهکار/بستانکار — تعدیلِ مانده، و نه هیچ‌چیزِ دیگر.

چهار مرزی که این فصل می‌کشد و هر کدام یک‌بار در کوبیتا شکسته بوده‌اند:

  ۱. تعدیلِ مانده **درآمد نمی‌سازد** — و تا مهاجرتِ ۰۱۲۷ می‌ساخت.
  ۲. اعلامیه در **کارتِ حسابِ** طرف مقابل دیده می‌شود — و تا امروز نمی‌شد، پس
     صورت‌حساب و دفتر به اندازه‌ی همان اعلامیه از هم جدا می‌افتادند.
  ۳. مانده‌ی حسابداری **تسویه‌ی قلمِ باز نیست**: ۲۰ میلیون کم‌شدنِ مانده نمی‌گوید
     کدام فاکتور پرداخت شده.
  ۴. هیچ پولی، کالایی و مالیاتی حرکت نمی‌کند.
"""
from datetime import date

TODAY = date.today().isoformat()


def _customer(client, name="مشتریِ اعلامیه"):
    return client.post("/api/contacts", json={"name": name, "type": "customer"}).json()["id"]


def _supplier(client, name="تأمین‌کننده‌ی اعلامیه"):
    return client.post("/api/contacts", json={"name": name, "type": "supplier"}).json()["id"]


def _notice(client, lines, *, reason="بابت تهاتر حساب", **kw):
    return client.post(
        "/api/sales-ops/notes",
        json={"note_date": TODAY, "reason": reason, "lines": lines, **kw},
    )


def _open_items(client, contact_id, account_id):
    """اقلامِ بازِ یک طرف حساب روی یک معین. معین از خودِ سند می‌آید، نه از کدِ ثابت."""
    r = client.get(f"/api/settlements/open-items?contact_id={contact_id}&account_id={account_id}")
    assert r.status_code == 200, r.text
    return r.json()["items"]


def _statement(client, contact_id):
    r = client.get(f"/api/reports/contact-statement/{contact_id}")
    assert r.status_code == 200, r.text
    return r.json()


# ───────────────────── یک موتور، دو نقش ─────────────────────


def test_the_same_document_serves_customer_and_supplier(client):
    """شاهدِ مرکزیِ فصل: تهاترِ تأمین‌کننده با مشتری، بدونِ هیچ حرکتِ پول."""
    customer, supplier = _customer(client), _supplier(client)

    r = _notice(
        client,
        [{"debit_contact_id": supplier, "credit_contact_id": customer, "amount": 20_000_000}],
    )
    assert r.status_code == 201, r.text
    body = r.json()

    assert body["journal_entry_id"] is not None, "اعلامیه باید در دفتر بنشیند"
    assert body["amount"] == "20000000" or float(body["amount"]) == 20_000_000
    line = body["lines"][0]
    assert line["debit_contact_id"] == supplier
    assert line["credit_contact_id"] == customer
    #: و عنوانِ حساب‌ها هم می‌آید، نه فقط کدشان — کدِ تنها انتخابِ اشتباه را آسان می‌کند.
    assert line["debit_account_name"] and line["credit_account_name"]
    assert line["debit_account_id"] != line["credit_account_id"]


def test_the_eligible_accounts_come_from_roles_not_from_codes(client):
    r = client.get("/api/sales-ops/notes/accounts")
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) == 2, "دریافتنی و پرداختنیِ تجاری"
    assert all(row["code"] and row["name"] for row in rows)


# ───────────────────── دیده‌شدن در کارتِ حساب ─────────────────────


def test_the_notice_shows_up_in_both_counterparties_statements(client):
    """تا امروز سند مانده را تکان می‌داد و کارتِ حساب خبر نداشت."""
    customer, supplier = _customer(client, "مشتریِ کارت"), _supplier(client, "تأمینِ کارت")
    assert _notice(
        client, [{"debit_contact_id": supplier, "credit_contact_id": customer, "amount": 5_000_000}]
    ).status_code == 201

    cust = _statement(client, customer)
    kinds = [row["kind"] for row in cust["lines"]]
    assert "credit_debit_note" in kinds, "اعلامیه باید در کارتِ حسابِ مشتری دیده شود"
    row = next(x for x in cust["lines"] if x["kind"] == "credit_debit_note")
    assert float(row["credit"]) == 5_000_000, "مشتری سمتِ بستانکار بود"
    assert float(row["debit"]) == 0

    supp = _statement(client, supplier)
    row = next(x for x in supp["lines"] if x["kind"] == "credit_debit_note")
    assert float(row["debit"]) == 5_000_000, "تأمین‌کننده سمتِ بدهکار بود"


def test_voiding_a_notice_removes_it_from_the_statement(client):
    """کارتِ حساب نمای اثرهای معتبر است — با ابطال، بدونِ اصلاحِ دستی درست می‌شود."""
    customer, supplier = _customer(client, "مشتریِ ابطال"), _supplier(client, "تأمینِ ابطال")
    note = _notice(
        client, [{"debit_contact_id": supplier, "credit_contact_id": customer, "amount": 3_000_000}]
    ).json()

    before = _statement(client, customer)["closing_balance"]
    assert client.post(
        f"/api/sales-ops/notes/{note['id']}/void", json={"reason": "اشتباه بود"}
    ).status_code == 200

    after = _statement(client, customer)
    assert not any(x["kind"] == "credit_debit_note" for x in after["lines"])
    assert float(after["closing_balance"]) == float(before) + 3_000_000


# ───────────────────── مرزها ─────────────────────


def test_a_notice_moves_no_cash_no_stock_no_tax(client):
    """§۳۵ §۳۶ §۳۷ — این سند فقط مانده را جابه‌جا می‌کند."""
    customer, supplier = _customer(client, "مشتریِ مرز"), _supplier(client, "تأمینِ مرز")
    before_tx = len(client.get("/api/treasury/transactions").json())

    assert _notice(
        client, [{"debit_contact_id": supplier, "credit_contact_id": customer, "amount": 1_000_000}]
    ).status_code == 201

    assert len(client.get("/api/treasury/transactions").json()) == before_tx, "هیچ حرکتِ خزانه‌ای"


def test_the_balance_moved_but_no_invoice_became_settled(client):
    """§۳۳ §۳۴ — مانده‌ی حسابداری و وضعیتِ تسویه دو حقیقتِ مستقل‌اند.

    اعلامیه‌ای که مانده‌ی مشتری را ۲۰ میلیون کم می‌کند نمی‌گوید کدام فاکتور
    تسویه شده — و نباید هیچ فاکتوری را تسویه‌شده علامت بزند.
    """
    customer = _customer(client, "مشتریِ قلمِ باز")
    supplier = _supplier(client, "تأمینِ قلمِ باز")

    wh = client.post("/api/warehouses", json={"code": "CN", "name": "انبار"}).json()["id"]
    item = client.post("/api/items", json={"sku": "CN-1", "name": "کالا", "sales_price": 1000}).json()["id"]
    client.post(
        "/api/purchase-invoices",
        json={"invoice_date": TODAY, "warehouse_id": wh, "lines": [{"item_id": item, "qty": 50, "unit_cost": 400}]},
    )
    inv = client.post(
        "/api/sales-invoices",
        json={
            "invoice_date": TODAY,
            "warehouse_id": wh,
            "contact_id": customer,
            "tax_rate": 0,
            "lines": [{"item_id": item, "qty": 10, "unit_price": 1000}],
        },
    )
    assert inv.status_code == 201, inv.text

    note = _notice(
        client, [{"debit_contact_id": supplier, "credit_contact_id": customer, "amount": 4000}]
    )
    assert note.status_code == 201, note.text
    receivable = note.json()["lines"][0]["credit_account_id"]

    rows = _open_items(client, customer, receivable)
    invoices = [x for x in rows if x["source_type"] == "sales_invoice"]
    assert invoices, "فاکتور باید هنوز قلمِ باز باشد"
    assert all(x["status"] == "unsettled" for x in invoices), "هیچ فاکتوری تسویه‌شده نشد"


def test_the_notice_itself_is_an_open_item_for_both_sides(client):
    """سند خودش قلمِ باز است — برای هر دو طرف، هرکدام روی معینِ خودش."""
    customer = _customer(client, "مشتریِ دوسویه")
    supplier = _supplier(client, "تأمینِ دوسویه")
    r = _notice(client, [{"debit_contact_id": supplier, "credit_contact_id": customer, "amount": 6000}])
    assert r.status_code == 201, r.text
    line = r.json()["lines"][0]

    for who, account, side in (
        (customer, line["credit_account_id"], "credit"),
        (supplier, line["debit_account_id"], "debit"),
    ):
        notes = [x for x in _open_items(client, who, account) if x["source_type"] == "credit_debit_note"]
        assert notes, f"اعلامیه باید قلمِ بازِ {who} باشد"
        assert notes[0]["side"] == side
        assert float(notes[0]["document_amount"]) == 6000


# ───────────────────── ثبتِ دوباره ─────────────────────


def test_the_same_request_twice_adjusts_the_balance_once(client):
    """§۴۶ — ثبتِ دوباره یعنی تعدیلِ مانده دو بار، بی‌صداترین خطای این سند."""
    customer, supplier = _customer(client, "مشتریِ تکرار"), _supplier(client, "تأمینِ تکرار")
    payload = {
        "note_date": TODAY,
        "reason": "تهاتر",
        "lines": [{"debit_contact_id": supplier, "credit_contact_id": customer, "amount": 9000}],
    }
    headers = {"Idempotency-Key": "notice-retry-1"}

    first = client.post("/api/sales-ops/notes", json=payload, headers=headers)
    second = client.post("/api/sales-ops/notes", json=payload, headers=headers)
    assert first.status_code == 201, first.text
    assert second.status_code in (200, 201), second.text
    assert first.json()["id"] == second.json()["id"], "همان سند، نه سندِ دوم"

    rows = [x for x in _statement(client, customer)["lines"] if x["kind"] == "credit_debit_note"]
    assert len(rows) == 1
    assert float(rows[0]["credit"]) == 9000
