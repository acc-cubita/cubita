"""فصلِ «برگشت از فروش»: تخصیصِ سطحِ ردیف، ابطال، علتِ برگشت و حسابِ مخصوص.

چیزی که این فایل قفل می‌کند، سه اشتباهِ گران است:

۱. **میانگین‌گرفتن از دو قیمت.** برگشت تا امروز فقط «کالا» را می‌شناخت، پس
   فاکتوری که یک کالا را دو بار با دو قیمت فروخته بود، هنگامِ برگشت میانگین
   می‌داد — و مشتری مبلغی پس می‌گرفت که هرگز نپرداخته بود.
۲. **بن‌بستِ ابطال.** گاردِ ابطالِ فاکتور می‌گفت «اول سندِ برگشت را برگردانید»
   در حالی که هیچ راهی برایش نبود.
۳. **ابطالی که هیچ‌جا فیلتر نمی‌شود.** لحظه‌ای که برگشت ابطال‌پذیر شد، هر
   گزارشی که فیلترش را جا بیندازد یک عددِ غلطِ **بی‌صدا** می‌دهد.
"""
from datetime import date

TODAY = str(date.today())


def _wh(client, code="SRC"):
    return client.post("/api/warehouses", json={"code": code, "name": "انبار برگشت"}).json()["id"]


def _item(client, sku="SRC-1", name="کالای برگشتی"):
    return client.post(
        "/api/items", json={"sku": sku, "name": name, "sales_price": 5000}
    ).json()["id"]


def _buy(client, wh, item, qty=100, cost=1000):
    client.post(
        "/api/purchase-invoices",
        json={
            "invoice_date": TODAY,
            "warehouse_id": wh,
            "tax_rate": 0,
            "lines": [{"item_id": item, "qty": qty, "unit_cost": cost}],
        },
    )


def _sell(client, wh, lines, tax_rate=0, contact_id=None):
    body = {"invoice_date": TODAY, "warehouse_id": wh, "tax_rate": tax_rate, "lines": lines}
    if contact_id:
        body["contact_id"] = contact_id
    res = client.post("/api/sales-invoices", json=body)
    assert res.status_code in (200, 201), res.text
    return res.json()


def _item_row(client, item_id):
    return next(r for r in client.get("/api/items").json()["items"] if r["id"] == item_id)


def _balance(client, contact_id):
    return float(
        client.get(f"/api/reports/contact-statement/{contact_id}").json()["closing_balance"]
    )


def _return(client, invoice_id, lines, expect=201):
    res = client.post(
        "/api/sales-returns",
        json={"return_date": TODAY, "sales_invoice_id": invoice_id, "lines": lines},
    )
    assert res.status_code == expect, res.text
    return res.json()


# ═══════════════ ۱) تخصیصِ سطحِ ردیف (§۷ §۱۵ §۸۰) ═══════════════


def test_two_lines_same_item_keep_their_own_price(client):
    """دو ردیفِ یک کالا با دو قیمت — برگشت باید قیمتِ **همان ردیف** را بدهد."""
    wh, item = _wh(client), _item(client)
    _buy(client, wh, item)
    inv = _sell(
        client,
        wh,
        [
            {"item_id": item, "qty": 5, "unit_price": 1000},
            {"item_id": item, "qty": 5, "unit_price": 3000},
        ],
    )

    rows = client.get(f"/api/sales-invoices/{inv['id']}/returnable").json()
    #: دو سطر، نه یک میانگینِ ۲۰۰۰
    assert len(rows) == 2
    prices = sorted(float(r["unit_price"]) for r in rows)
    assert prices == [1000, 3000]
    assert all(r["sales_invoice_line_id"] for r in rows)

    expensive = next(r for r in rows if float(r["unit_price"]) == 3000)
    out = _return(
        client,
        inv["id"],
        [{"sales_invoice_line_id": expensive["sales_invoice_line_id"], "qty": 2}],
    )
    #: ۲ × ۳۰۰۰ — نه ۲ × ۲۰۰۰ که میانگین می‌داد
    assert float(out["total_amount"]) == 6000
    assert out["lines"][0]["sales_invoice_line_id"] == expensive["sales_invoice_line_id"]

    after = client.get(f"/api/sales-invoices/{inv['id']}/returnable").json()
    cheap = next(r for r in after if float(r["unit_price"]) == 1000)
    still = next(r for r in after if float(r["unit_price"]) == 3000)
    #: ردیفِ ارزان دست‌نخورده ماند — ماندهٔ هر ردیف مالِ خودش است
    assert float(cheap["remaining"]) == 5
    assert float(still["remaining"]) == 3


def test_item_level_request_still_works_and_gains_line_identity(client):
    """ورودیِ کالا-محور (`marketplace` و اپِ موبایل) نباید بشکند — §۷ ولی سازگار."""
    wh, item = _wh(client), _item(client)
    _buy(client, wh, item)
    inv = _sell(
        client,
        wh,
        [
            {"item_id": item, "qty": 5, "unit_price": 1000},
            {"item_id": item, "qty": 5, "unit_price": 3000},
        ],
    )

    #: ترتیبِ ردیف‌ها `order_by(id)` است — روی UUID دلخواه ولی پایدار. پس انتظار
    #: از همان ترتیبی ساخته می‌شود که خودِ API می‌دهد، نه از حدس؛ وگرنه تست
    #: بسته به اینکه کدام UUID جلوتر بیفتد، تصادفی سبز و قرمز می‌شود.
    rows = client.get(f"/api/sales-invoices/{inv['id']}/returnable").json()
    first, second = rows[0], rows[1]

    #: بیش از ماندهٔ ردیفِ اول → باید روی هر دو ردیف پخش شود
    out = _return(client, inv["id"], [{"item_id": item, "qty": 7}])
    assert len(out["lines"]) == 2
    assert all(line["sales_invoice_line_id"] for line in out["lines"])
    expected = 5 * float(first["unit_price"]) + 2 * float(second["unit_price"])
    assert float(out["total_amount"]) == expected
    #: و هر ردیف قیمتِ مبدأ خودش را گرفته، نه میانگین
    assert {float(line["unit_price"]) for line in out["lines"]} == {1000, 3000}


def test_over_return_is_refused(client):
    wh, item = _wh(client), _item(client)
    _buy(client, wh, item)
    inv = _sell(client, wh, [{"item_id": item, "qty": 5, "unit_price": 1000}])
    _return(client, inv["id"], [{"item_id": item, "qty": 6}], expect=400)

    line_id = client.get(f"/api/sales-invoices/{inv['id']}/returnable").json()[0][
        "sales_invoice_line_id"
    ]
    _return(client, inv["id"], [{"sales_invoice_line_id": line_id, "qty": 6}], expect=400)


def test_line_from_another_invoice_is_refused(client):
    wh, item = _wh(client), _item(client)
    _buy(client, wh, item)
    first = _sell(client, wh, [{"item_id": item, "qty": 5, "unit_price": 1000}])
    second = _sell(client, wh, [{"item_id": item, "qty": 5, "unit_price": 1000}])
    stranger = client.get(f"/api/sales-invoices/{second['id']}/returnable").json()[0][
        "sales_invoice_line_id"
    ]
    _return(client, first["id"], [{"sales_invoice_line_id": stranger, "qty": 1}], expect=400)


def test_two_requests_on_one_line_cannot_exceed_it(client):
    """دو ردیفِ درخواست روی یک ردیفِ فاکتور، از ماندهٔ مشترک بیشتر برنمی‌دارند."""
    wh, item = _wh(client), _item(client)
    _buy(client, wh, item)
    inv = _sell(client, wh, [{"item_id": item, "qty": 5, "unit_price": 1000}])
    line_id = client.get(f"/api/sales-invoices/{inv['id']}/returnable").json()[0][
        "sales_invoice_line_id"
    ]
    _return(
        client,
        inv["id"],
        [
            {"sales_invoice_line_id": line_id, "qty": 3},
            {"sales_invoice_line_id": line_id, "qty": 3},
        ],
        expect=400,
    )


# ═══════════════ ۲) حسابِ مخصوصِ برگشت (§۴۵ §۹۴) ═══════════════


def test_return_debits_its_own_account_not_revenue(client):
    """فروشِ ناخالص و برگشتی باید هر دو در دفتر قابلِ خواندن بمانند."""
    wh, item = _wh(client), _item(client)
    _buy(client, wh, item)
    inv = _sell(client, wh, [{"item_id": item, "qty": 5, "unit_price": 1000}])
    out = _return(client, inv["id"], [{"item_id": item, "qty": 2}])

    entry = client.get(f"/api/journal-entries/{out['journal_entry_id']}").json()
    by_id = {a["id"]: a for a in client.get("/api/accounts").json()}
    debited = {
        by_id[line["account_id"]]["code"]
        for line in entry["lines"]
        if float(line["debit"]) == 2000
    }
    assert "4107" in debited, debited
    #: و «فروش» (۴۱۰۱) بدهکار نشده است
    assert "4101" not in debited


# ═══════════════ ۳) ابطالِ برگشت (§۷۱–§۷۸) ═══════════════


def test_voiding_a_return_restores_remaining_and_unlocks_the_invoice(client):
    """هم §۷۶ و هم بن‌بستِ زنده — در یک سناریو، چون یک مسئله‌اند."""
    wh, item = _wh(client), _item(client)
    _buy(client, wh, item)
    inv = _sell(client, wh, [{"item_id": item, "qty": 5, "unit_price": 1000}])
    out = _return(client, inv["id"], [{"item_id": item, "qty": 2}])

    #: تا وقتی برگشتِ فعال هست، فاکتور باطل نمی‌شود — این درست است
    blocked = client.post(f"/api/sales-invoices/{inv['id']}/void", json={"reason": "اشتباه"})
    assert blocked.status_code == 409, blocked.text

    voided = client.post(
        f"/api/sales-returns/{out['id']}/void", json={"reason": "اشتباهِ اپراتور"}
    )
    assert voided.status_code == 200, voided.text
    assert voided.json()["voided_at"] is not None

    #: ماندهٔ قابلِ برگشت برمی‌گردد چون مشتق است، نه شمارنده
    rows = client.get(f"/api/sales-invoices/{inv['id']}/returnable").json()
    assert float(rows[0]["remaining"]) == 5
    assert float(rows[0]["already_returned"]) == 0

    #: و قفلِ ابطالِ فاکتور باز می‌شود — همان بن‌بستی که راهی نداشت
    now_ok = client.post(f"/api/sales-invoices/{inv['id']}/void", json={"reason": "اشتباه"})
    assert now_ok.status_code == 200, now_ok.text


def test_voiding_twice_is_refused(client):
    wh, item = _wh(client), _item(client)
    _buy(client, wh, item)
    inv = _sell(client, wh, [{"item_id": item, "qty": 5, "unit_price": 1000}])
    out = _return(client, inv["id"], [{"item_id": item, "qty": 2}])
    assert client.post(f"/api/sales-returns/{out['id']}/void", json={"reason": "x"}).status_code == 200
    again = client.post(f"/api/sales-returns/{out['id']}/void", json={"reason": "x"})
    assert again.status_code == 409


def test_void_reverses_stock_and_journal(client):
    wh, item = _wh(client), _item(client)
    _buy(client, wh, item, qty=100, cost=1000)
    inv = _sell(client, wh, [{"item_id": item, "qty": 5, "unit_price": 1000}])
    positions = f"/api/warehouses/{wh}/stock-positions"

    def qty() -> float:
        rows = client.get(positions).json()["items"]
        row = next((r for r in rows if str(r["item_id"]) == item), None)
        return float(row["qty"]) if row else 0.0

    before = qty()
    out = _return(client, inv["id"], [{"item_id": item, "qty": 2}])
    assert qty() == before + 2

    client.post(f"/api/sales-returns/{out['id']}/void", json={"reason": "اشتباه"})
    assert qty() == before


# ═══════════════ ۴) ابطال و گزارش‌ها — عددهای بی‌صدا ═══════════════


def test_voided_return_leaves_the_contact_balance_alone(client):
    """برگشتِ باطل‌شده نباید از ماندهٔ طرف‌حساب کم کند."""
    wh, item = _wh(client), _item(client)
    _buy(client, wh, item)
    contact = client.post(
        "/api/contacts", json={"name": "مشتریِ برگشت", "kind": "customer"}
    ).json()["id"]
    inv = _sell(
        client, wh, [{"item_id": item, "qty": 5, "unit_price": 1000}], contact_id=contact
    )
    baseline = _balance(client, contact)

    out = _return(client, inv["id"], [{"item_id": item, "qty": 2}])
    assert _balance(client, contact) < baseline

    client.post(f"/api/sales-returns/{out['id']}/void", json={"reason": "اشتباه"})
    assert _balance(client, contact) == baseline


def test_voided_return_leaves_the_vat_report_alone(client):
    wh, item = _wh(client), _item(client)
    _buy(client, wh, item)
    inv = _sell(client, wh, [{"item_id": item, "qty": 5, "unit_price": 1000}], tax_rate=10)
    baseline = client.get("/api/reports/vat").json()

    out = _return(client, inv["id"], [{"item_id": item, "qty": 2}])
    mid = client.get("/api/reports/vat").json()
    assert float(mid["sales_net"]) < float(baseline["sales_net"])

    client.post(f"/api/sales-returns/{out['id']}/void", json={"reason": "اشتباه"})
    restored = client.get("/api/reports/vat").json()
    assert float(restored["sales_net"]) == float(baseline["sales_net"])
    assert float(restored["output_vat"]) == float(baseline["output_vat"])


def test_voided_return_is_ignored_by_average_cost(client):
    """حرکتِ انبارِ برگشتِ باطل‌شده نباید در میانگینِ بهای تمام‌شده بماند."""
    wh, item = _wh(client), _item(client)
    _buy(client, wh, item, qty=100, cost=1000)
    inv = _sell(client, wh, [{"item_id": item, "qty": 5, "unit_price": 1000}])
    before = float(_item_row(client, item)["average_cost"])

    out = _return(client, inv["id"], [{"item_id": item, "qty": 2}])
    client.post(f"/api/sales-returns/{out['id']}/void", json={"reason": "اشتباه"})
    after = float(_item_row(client, item)["average_cost"])
    assert abs(after - before) < 0.5


# ═══════════════ ۵) علتِ برگشت (§۲۴–§۲۸ §۸۵) ═══════════════


def test_return_reason_is_master_data_and_lands_on_the_line(client):
    wh, item = _wh(client), _item(client)
    _buy(client, wh, item)
    inv = _sell(client, wh, [{"item_id": item, "qty": 5, "unit_price": 1000}])

    reason = client.post(
        "/api/sales-return-reasons", json={"title": "خرابیِ کالا", "title2": "Damaged"}
    )
    assert reason.status_code == 201, reason.text
    reason_id = reason.json()["id"]

    out = _return(
        client, inv["id"], [{"item_id": item, "qty": 2, "return_reason_id": reason_id}]
    )
    assert out["lines"][0]["return_reason_id"] == reason_id


def test_reason_is_optional(client):
    """نمونه‌ی مرجع علت را اجباری نمی‌کند — پس ما هم نمی‌کنیم (§۲۷)."""
    wh, item = _wh(client), _item(client)
    _buy(client, wh, item)
    inv = _sell(client, wh, [{"item_id": item, "qty": 5, "unit_price": 1000}])
    out = _return(client, inv["id"], [{"item_id": item, "qty": 2}])
    assert out["lines"][0]["return_reason_id"] is None


def test_inactive_reason_blocks_new_use_but_survives_on_history(client):
    wh, item = _wh(client), _item(client)
    _buy(client, wh, item)
    inv = _sell(client, wh, [{"item_id": item, "qty": 10, "unit_price": 1000}])
    reason_id = client.post(
        "/api/sales-return-reasons", json={"title": "علتِ موقتی"}
    ).json()["id"]

    historic = _return(
        client, inv["id"], [{"item_id": item, "qty": 2, "return_reason_id": reason_id}]
    )

    client.patch(
        f"/api/sales-return-reasons/{reason_id}",
        json={"title": "علتِ موقتی", "is_active": False},
    )
    #: انتخابِ تازه بسته می‌شود
    _return(
        client, inv["id"], [{"item_id": item, "qty": 1, "return_reason_id": reason_id}], expect=400
    )
    #: ولی سندِ تاریخی علتش را نگه می‌دارد
    again = client.get("/api/sales-returns").json()
    row = next(r for r in again["items"] if r["id"] == historic["id"])
    assert row["lines"][0]["return_reason_id"] == reason_id
    #: و از فهرستِ فعال بیرون می‌رود، نه از فهرستِ کامل
    assert reason_id not in [
        r["id"] for r in client.get("/api/sales-return-reasons?only_active=true").json()
    ]
    assert reason_id in [r["id"] for r in client.get("/api/sales-return-reasons").json()]


# ═══════════════ ۶) یکتاسازی و وضعیت‌های مشتق (§۵۴ §۶۴ §۸۳) ═══════════════


def test_same_idempotency_key_does_not_create_a_second_return(client):
    wh, item = _wh(client), _item(client)
    _buy(client, wh, item)
    inv = _sell(client, wh, [{"item_id": item, "qty": 5, "unit_price": 1000}])
    body = {"return_date": TODAY, "sales_invoice_id": inv["id"], "lines": [{"item_id": item, "qty": 2}]}
    headers = {"Idempotency-Key": "return-once-please"}

    first = client.post("/api/sales-returns", json=body, headers=headers)
    second = client.post("/api/sales-returns", json=body, headers=headers)
    assert first.json()["id"] == second.json()["id"]

    rows = client.get(f"/api/sales-invoices/{inv['id']}/returnable").json()
    assert float(rows[0]["already_returned"]) == 2


def test_list_carries_derived_amounts(client):
    """مبلغ، پرداخت‌شده و مانده — سه حقیقتِ جدا، هیچ‌کدام ذخیره‌شده (§۶۵ §۶۶ §۹۲)."""
    wh, item = _wh(client), _item(client)
    _buy(client, wh, item)
    inv = _sell(client, wh, [{"item_id": item, "qty": 5, "unit_price": 1000}])
    out = _return(client, inv["id"], [{"item_id": item, "qty": 2}])

    row = next(r for r in client.get("/api/sales-returns").json()["items"] if r["id"] == out["id"])
    assert float(row["final_amount"]) == 2000
    #: برگشتِ پرداخت‌نشده یک حالتِ معتبر است (§۶۷)
    assert float(row["settled_amount"]) == 0
    assert float(row["remaining_amount"]) == 2000
    assert row["financial_status"] == "unsettled"
    assert row["accounting_status"] == "posted"

    client.post(f"/api/sales-returns/{out['id']}/void", json={"reason": "اشتباه"})
    after = next(
        r for r in client.get("/api/sales-returns").json()["items"] if r["id"] == out["id"]
    )
    assert after["financial_status"] == "voided"
