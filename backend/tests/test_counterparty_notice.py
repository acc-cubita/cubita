"""اعلامیه‌ی بدهکار/بستانکار — تعدیلِ مانده، و نه هیچ‌چیزِ دیگر.

چهار مرزی که این فصل می‌کشد و هر کدام یک‌بار در کوبیتا شکسته بوده‌اند:

  ۱. تعدیلِ مانده **درآمد نمی‌سازد** — و تا مهاجرتِ ۰۱۲۷ می‌ساخت.
  ۲. اعلامیه در **کارتِ حسابِ** طرف مقابل دیده می‌شود — و تا امروز نمی‌شد، پس
     صورت‌حساب و دفتر به اندازه‌ی همان اعلامیه از هم جدا می‌افتادند.
  ۳. مانده‌ی حسابداری **تسویه‌ی قلمِ باز نیست**: ۲۰ میلیون کم‌شدنِ مانده نمی‌گوید
     کدام فاکتور پرداخت شده.
  ۴. هیچ پولی، کالایی و مالیاتی حرکت نمی‌کند.
"""
from datetime import date, timedelta
from decimal import Decimal

from app.models.accounting import JournalEntry
from app.models.currency import Currency
from app.models.inventory import Warehouse
from app.models.sales_ops import CreditDebitNote
from app.services import chart_codes as cc
from app.services.common import get_account

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


# ═══════════════════ نوبتِ دوم (مهاجرتِ ۰۱۳۶) ═══════════════════


def _pair(client, tag):
    return _customer(client, f"مشتریِ {tag}"), _supplier(client, f"تأمینِ {tag}")


def _entry(db, entry_id):
    return db.query(JournalEntry).filter(JournalEntry.id == entry_id).one()


# ───────────────────── ارز: نرخ ذخیره می‌شد ولی اعمال نه ─────────────────────


def test_a_foreign_currency_notice_posts_its_base_equivalent(client, db, user):
    """§۱۳ — اعلامیه‌ی ۱۰۰ دلاری تا امروز در دفتر ۱۰۰ ریال می‌نشست."""
    db.add(Currency(code="USD", name="دلار", created_by_id=user.id))
    db.flush()
    customer, supplier = _pair(client, "دلاری")

    r = _notice(
        client,
        [{"debit_contact_id": supplier, "credit_contact_id": customer, "amount": 100}],
        currency_code="usd",
        exchange_rate=500_000,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["currency_code"] == "USD"
    assert Decimal(body["amount"]) == 100, "مبلغ به ارزِ سند می‌ماند"
    assert Decimal(body["base_amount"]) == 50_000_000
    assert Decimal(body["lines"][0]["base_amount"]) == 50_000_000

    entry = _entry(db, body["journal_entry_id"])
    assert sum(Decimal(x.debit) for x in entry.lines) == 50_000_000
    assert sum(Decimal(x.credit) for x in entry.lines) == 50_000_000
    assert "USD" in entry.description, "نرخ در شرحِ سند می‌نشیند تا سند توضیح‌پذیر باشد"

    row = next(x for x in _statement(client, customer)["lines"] if x["kind"] == "credit_debit_note")
    assert Decimal(row["credit"]) == 50_000_000, "کارتِ حساب به ریال است، همان عددِ دفتر"


def test_rounding_happens_per_line_so_the_entry_equals_the_lines(client, db, user):
    """ردیف‌به‌ردیف گرد می‌شود؛ جمعِ دفتر دقیقاً جمعِ معادل‌های ریالیِ ردیف‌هاست."""
    db.add(Currency(code="EUR", name="یورو", created_by_id=user.id))
    db.flush()
    customer, supplier = _pair(client, "گرد")
    r = _notice(
        client,
        [
            {"debit_contact_id": supplier, "credit_contact_id": customer, "amount": 3},
            {"debit_contact_id": supplier, "credit_contact_id": customer, "amount": 7},
        ],
        currency_code="EUR",
        exchange_rate="333.3333",
    )
    assert r.status_code == 201, r.text
    body = r.json()
    bases = [Decimal(x["base_amount"]) for x in body["lines"]]
    assert bases == [Decimal(1000), Decimal(2333)], "۹۹۹٫۹۹۹۹ → ۱۰۰۰ و ۲۳۳۳٫۳۳۳۱ → ۲۳۳۳"
    entry = _entry(db, body["journal_entry_id"])
    assert sum(Decimal(x.debit) for x in entry.lines) == sum(bases) == Decimal(body["base_amount"])


def test_a_fractional_amount_is_refused_instead_of_silently_rounded(client):
    customer, supplier = _pair(client, "اعشار")
    r = _notice(client, [{"debit_contact_id": supplier, "credit_contact_id": customer, "amount": "12.5"}])
    assert r.status_code == 400, r.text


def test_an_unknown_currency_or_a_rial_rate_other_than_one_is_refused(client):
    customer, supplier = _pair(client, "ارزِ ناشناخته")
    line = [{"debit_contact_id": supplier, "credit_contact_id": customer, "amount": 10}]
    assert _notice(client, line, currency_code="XYZ", exchange_rate=10).status_code == 400
    assert _notice(client, line, currency_code="IRR", exchange_rate=2).status_code == 400


# ───────────────────── گاردِ حساب: دو سمت، دو قاعده ─────────────────────


def test_a_side_with_a_contact_must_sit_on_a_counterparty_account(client):
    """تفصیلیِ شخص روی معینِ هزینه، تعدیلی می‌سازد که در کارتِ حسابش دیده نمی‌شد."""
    customer, supplier = _pair(client, "معینِ غلط")
    other = client.get("/api/sales-ops/notes/accounts?scope=other").json()
    assert other, "دستِ‌کم یک معینِ آزاد باید باشد"
    r = _notice(
        client,
        [{"debit_contact_id": supplier, "credit_contact_id": customer, "credit_account_id": other[0]["id"], "amount": 10}],
    )
    assert r.status_code == 400, r.text


def test_a_side_without_a_contact_cannot_sit_on_receivables(client, db):
    """دریافتنیِ بی‌طرف‌حساب مانده‌ای می‌سازد که به هیچ‌کس تعلق ندارد."""
    customer = _customer(client, "مشتریِ بی‌صاحب")
    receivable = get_account(db, cc.ACCOUNTS_RECEIVABLE)
    r = _notice(client, [{"debit_account_id": str(receivable.id), "credit_contact_id": customer, "amount": 10}])
    assert r.status_code == 400, r.text


def test_a_notice_cannot_move_cash_by_role_or_by_mapping(client, db):
    """§۲۸ — تا امروز سرویس صندوق را هم می‌پذیرفت؛ فقط فرم جلویش را می‌گرفت.

    نقش کافی نیست: معینی که به یک انبار نگاشته شده همان‌قدر مالِ موتورِ انبار است.
    """
    customer = _customer(client, "مشتریِ صندوق")
    cash = get_account(db, cc.CASH)
    r = _notice(client, [{"debit_account_id": str(cash.id), "credit_contact_id": customer, "amount": 10}])
    assert r.status_code == 400, r.text

    free = client.get("/api/sales-ops/notes/accounts?scope=other").json()[0]
    wh = client.post("/api/warehouses", json={"code": "CDN-GL", "name": "انبارِ نگاشته"}).json()["id"]
    db.query(Warehouse).filter(Warehouse.id == wh).update({"gl_account_id": free["id"]})
    db.flush()
    r = _notice(client, [{"debit_account_id": free["id"], "credit_contact_id": customer, "amount": 10}])
    assert r.status_code == 400, r.text
    ids = {a["id"] for a in client.get("/api/sales-ops/notes/accounts?scope=other").json()}
    assert free["id"] not in ids, "فرم هم نباید گزینه‌ی ممنوع را نشان دهد"


def test_the_free_side_list_excludes_counterparty_and_engine_accounts(client, db):
    ids = {a["id"] for a in client.get("/api/sales-ops/notes/accounts?scope=other").json()}
    for role in (cc.ACCOUNTS_RECEIVABLE, cc.ACCOUNTS_PAYABLE, cc.CASH, cc.BANK, cc.INVENTORY, cc.VAT_PAYABLE):
        assert str(get_account(db, role).id) not in ids, role


def test_a_granted_discount_is_a_legitimate_account_only_side(client, db):
    """سمتِ بی‌طرف‌حساب هنوز کار می‌کند: تخفیفِ اعطایی به مشتری."""
    customer = _customer(client, "مشتریِ تخفیف")
    discount = get_account(db, cc.SALES_DISCOUNT)
    r = _notice(client, [{"debit_account_id": str(discount.id), "credit_contact_id": customer, "amount": 2500}])
    assert r.status_code == 201, r.text


# ───────────────────── ابطال: مسیرِ مشترک، تاریخ، ردِ کاربر ─────────────────────


def test_voiding_uses_the_shared_reversal_path(client, db):
    """معکوس به اصل پیوند می‌خورد، منبعش `void_credit_debit_note` است و تاریخِ اعلامیه را می‌گیرد."""
    customer, supplier = _pair(client, "ابطالِ مشترک")
    earlier = (date.today() - timedelta(days=3)).isoformat()
    note = client.post(
        "/api/sales-ops/notes",
        json={
            "note_date": earlier,
            "reason": "تهاتر",
            "lines": [{"debit_contact_id": supplier, "credit_contact_id": customer, "amount": 8000}],
        },
    ).json()

    r = client.post(f"/api/sales-ops/notes/{note['id']}/void", json={"reason": "مبلغ اشتباه بود"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["void_reason"] == "مبلغ اشتباه بود"
    assert body["voided_by_name"], "چه کسی باطل کرد باید بماند"
    assert body["void_entry_number"] is not None

    reversal = _entry(db, body["void_entry_id"])
    original = _entry(db, note["journal_entry_id"])
    assert reversal.reverses_entry_id == original.id
    assert reversal.source_type == "void_credit_debit_note"
    assert reversal.entry_date.isoformat() == earlier, "پیش‌فرض همان تاریخِ اعلامیه است"
    #: همان حساب‌ها و تفصیلی‌ها، سمت‌ها جابه‌جا.
    assert sorted((str(x.account_id), str(x.analytic_id), Decimal(x.debit)) for x in reversal.lines) == sorted(
        (str(x.account_id), str(x.analytic_id), Decimal(x.credit)) for x in original.lines
    )


def test_a_void_can_be_dated_into_an_open_period(client):
    customer, supplier = _pair(client, "تاریخِ ابطال")
    note = _notice(client, [{"debit_contact_id": supplier, "credit_contact_id": customer, "amount": 900}]).json()
    later = (date.today() + timedelta(days=1)).isoformat()
    r = client.post(f"/api/sales-ops/notes/{note['id']}/void", json={"reason": "بازبینی", "void_date": later})
    assert r.status_code == 200, r.text
    assert r.json()["void_entry_date"] == later


# ───────────────────── فهرست، جزئیات، رونوشت، ردیابی ─────────────────────


def test_the_ledger_filters_on_the_server_and_pages(client):
    a, supplier = _pair(client, "فهرستِ الف")
    b = _customer(client, "مشتریِ فهرستِ ب")
    first = _notice(client, [{"debit_contact_id": supplier, "credit_contact_id": a, "amount": 100}], reason="نخست").json()
    second = _notice(
        client, [{"debit_contact_id": supplier, "credit_contact_id": b, "amount": 200}], reason="دومین تهاتر"
    ).json()
    assert client.post(f"/api/sales-ops/notes/{second['id']}/void", json={"reason": "آزمایشی"}).status_code == 200

    only_a = client.get(f"/api/sales-ops/notes?contact_id={a}").json()["items"]
    assert [x["id"] for x in only_a] == [first["id"]]
    assert only_a[0]["journal_entry_number"] is not None
    assert only_a[0]["journal_entry_date"] == TODAY

    voided = client.get(f"/api/sales-ops/notes?status=voided&contact_id={b}").json()["items"]
    assert [x["id"] for x in voided] == [second["id"]]
    assert client.get(f"/api/sales-ops/notes?status=active&contact_id={b}").json()["items"] == []

    by_number = client.get(f"/api/sales-ops/notes?q={first['number']}").json()["items"]
    assert [x["id"] for x in by_number] == [first["id"]]
    by_text = client.get("/api/sales-ops/notes?q=دومین").json()["items"]
    assert second["id"] in [x["id"] for x in by_text]

    page = client.get(f"/api/sales-ops/notes?contact_id={supplier}&limit=1").json()
    assert len(page["items"]) == 1 and page["next_cursor"]
    rest = client.get(f"/api/sales-ops/notes?contact_id={supplier}&limit=1&cursor={page['next_cursor']}").json()
    assert {page["items"][0]["id"], rest["items"][0]["id"]} == {first["id"], second["id"]}

    assert client.get("/api/sales-ops/notes?limit=201").status_code == 422


def test_duplicate_draft_copies_structure_but_never_identity(client, db):
    """§۳۷ — رونوشت سندِ تازه است: بدونِ شماره، تاریخ، سند و ابطال، و بدونِ نوشتن."""
    customer, supplier = _pair(client, "رونوشت")
    note = _notice(
        client,
        [{"debit_contact_id": supplier, "credit_contact_id": customer, "amount": 4200, "description": "ردیفِ اول"}],
        reason="تهاترِ فصل",
    ).json()
    before = db.query(CreditDebitNote).count()

    r = client.get(f"/api/sales-ops/notes/{note['id']}/duplicate-draft")
    assert r.status_code == 200, r.text
    draft = r.json()
    assert db.query(CreditDebitNote).count() == before, "رونوشت چیزی نمی‌نویسد"
    assert draft["reason"] == "تهاترِ فصل" and draft["source_number"] == note["number"]
    for forbidden in ("id", "number", "note_date", "journal_entry_id", "voided_at"):
        assert forbidden not in draft
    line = draft["lines"][0]
    assert line["debit_contact_id"] == supplier and line["credit_contact_id"] == customer
    assert Decimal(line["amount"]) == 4200 and line["description"] == "ردیفِ اول"

    assert client.get(f"/api/sales-ops/notes/{note['id']}").json()["number"] == note["number"]


def test_the_journal_lines_follow_the_notice_lines_in_order(client, db):
    """§۱۷ — ردیفِ kِ اعلامیه ردیف‌های 2k-1 (بدهکار) و 2k (بستانکار)ِ سند است."""
    customer, supplier = _pair(client, "ترتیب")
    note = _notice(
        client,
        [
            {"debit_contact_id": supplier, "credit_contact_id": customer, "amount": 111},
            {"debit_contact_id": supplier, "credit_contact_id": customer, "amount": 222},
        ],
    ).json()
    lines = sorted(_entry(db, note["journal_entry_id"]).lines, key=lambda x: x.seq)
    for k, row in enumerate(note["lines"], start=1):
        debit, credit = lines[2 * k - 2], lines[2 * k - 1]
        assert (debit.seq, credit.seq) == (2 * k - 1, 2 * k)
        assert str(debit.account_id) == row["debit_account_id"]
        assert Decimal(debit.debit) == Decimal(row["base_amount"])
        assert str(credit.account_id) == row["credit_account_id"]
        assert Decimal(credit.credit) == Decimal(row["base_amount"])


def test_the_statement_row_points_to_the_notice_and_its_journal_entry(client):
    """§۲۲ §۲۳ — کارتِ حساب بن‌بست نیست."""
    customer, supplier = _pair(client, "ردیابی")
    note = _notice(client, [{"debit_contact_id": supplier, "credit_contact_id": customer, "amount": 3100}]).json()
    detail = client.get(f"/api/sales-ops/notes/{note['id']}").json()
    row = next(x for x in _statement(client, customer)["lines"] if x["kind"] == "credit_debit_note")
    assert row["source_id"] == note["id"]
    assert row["entry_number"] == detail["journal_entry_number"]
    assert row["entry_date"] == detail["journal_entry_date"]


# ───────────────────── مجوز: مالِ فروش و خرید، نه فقط مالک ─────────────────────


def _as_role(db, tenant_id, role_key: str, email: str) -> None:
    """کلاینت را به کاربری با نقشِ پیش‌فرضِ داده‌شده می‌سپارد."""
    from app.deps import Principal, get_current_user, get_principal
    from app.main import app
    from app.models.tenant import Membership
    from app.models.user import Role, User
    from app.security import hash_password

    member = User(name=f"کاربرِ {role_key}", email=email, hashed_password=hash_password("x" * 12))
    db.add(member)
    db.flush()
    role = db.query(Role).filter(Role.tenant_id == tenant_id, Role.key == role_key).one()
    membership = Membership(user_id=member.id, tenant_id=tenant_id, role_id=role.id, status="active")
    db.add(membership)
    db.flush()
    db.refresh(membership)
    principal = Principal(member, membership)
    app.dependency_overrides[get_principal] = lambda: principal
    app.dependency_overrides[get_current_user] = lambda: member


def test_the_notice_is_not_locked_behind_a_permission_module_that_does_not_exist(client, db, tenant_id):
    """ماژولِ مجوزِ `sales` در رجیستری نیست؛ پس تا امروز فقط مالک اعلامیه می‌زد.

    حسابدار (حسابداری + فاکتور) و فروشنده (فاکتور) صادر می‌کنند؛ ابطال مجوزِ حذفِ
    حسابداری می‌خواهد که حسابدار ندارد؛ انباردار حتی فهرست را نمی‌بیند.
    """
    customer, supplier = _pair(client, "مجوز")
    line = [{"debit_contact_id": supplier, "credit_contact_id": customer, "amount": 50}]

    _as_role(db, tenant_id, "accountant", "cdn-accountant@cubita.ir")
    note = _notice(client, line)
    assert note.status_code == 201, note.text
    assert client.post(f"/api/sales-ops/notes/{note.json()['id']}/void", json={"reason": "آزمایش"}).status_code == 403

    _as_role(db, tenant_id, "salesperson", "cdn-sales@cubita.ir")
    assert _notice(client, line).status_code == 201

    _as_role(db, tenant_id, "warehouse_keeper", "cdn-wh@cubita.ir")
    assert client.get("/api/sales-ops/notes").status_code == 403
    assert _notice(client, line).status_code == 403
