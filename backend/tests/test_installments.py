"""فروش اقساطی: زمان‌بندیِ اقساط + پرداخت از خزانه + هشدار معوق."""
from datetime import date, timedelta
from decimal import Decimal

TODAY = date.today()


def _customer(client):
    return client.post("/api/contacts", json={"name": "مشتری اقساطی", "type": "customer"}).json()["id"]


_seq = [0]


def _backing_sale(client, contact_id, amount):
    """به مشتری «بدهیِ پشتیبان» می‌دهد — فروشِ نسیه که حساب‌های دریافتنی را بدهکار می‌کند.

    از این پس قراردادِ اقساط بدونِ چنین بدهی رد می‌شود، پس تست‌ها باید اول آن را بسازند.
    """
    _seq[0] += 1
    k = _seq[0]
    wh = client.post("/api/warehouses", json={"code": f"IW{k}", "name": "انبار اقساط"}).json()["id"]
    item = client.post("/api/items", json={"sku": f"INST-{k}", "name": "کالای اقساطی", "sales_price": amount}).json()["id"]
    client.post(
        "/api/purchase-invoices",
        json={"invoice_date": str(TODAY), "warehouse_id": wh, "tax_rate": 0, "lines": [{"item_id": item, "qty": 1, "unit_cost": 1}]},
    )
    r = client.post(
        "/api/sales-invoices",
        json={"invoice_date": str(TODAY), "warehouse_id": wh, "contact_id": contact_id, "tax_rate": 0, "lines": [{"item_id": item, "qty": 1, "unit_price": amount}]},
    )
    assert r.status_code in (200, 201), r.text


def _plan(client, backing=True, **overrides):
    contact_id = overrides.pop("contact_id", None) or _customer(client)
    total = overrides.get("total_amount", 1000000)
    if backing:
        _backing_sale(client, contact_id, total)  # بدهیِ پشتیبان تا محافظ رد نشود
    body = {
        "contact_id": contact_id,
        "title": "خرید یخچال",
        "total_amount": 1000000,
        "down_payment": 0,
        "num_installments": 3,
        "interval_months": 1,
        "start_date": str(TODAY),
    }
    body.update(overrides)
    body["contact_id"] = contact_id
    r = client.post("/api/installment-plans", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_plan_without_backing_receivable_rejected(client):
    """قراردادِ اقساط بدونِ بدهیِ پشتیبان (فاکتورِ نسیه) باید رد شود."""
    cust = _customer(client)
    r = client.post(
        "/api/installment-plans",
        json={"contact_id": cust, "total_amount": 500000, "down_payment": 0, "num_installments": 2, "interval_months": 1, "start_date": str(TODAY)},
    )
    assert r.status_code == 400


def test_installment_receipt_cannot_drive_ar_negative(client):
    """اگر طلبِ مشتری جدا وصول شده باشد، دریافتِ قسط (که AR را منفی می‌کند) رد می‌شود."""
    cust = _customer(client)
    plan = _plan(client, contact_id=cust, total_amount=300000, num_installments=3)  # AR پشتیبان ۳۰۰٬۰۰۰
    paid = client.post(
        "/api/treasury/receipts",
        json={"transaction_date": str(TODAY), "contact_id": cust, "amount": 300000, "method": "cash"},
    )
    assert paid.status_code in (200, 201), paid.text  # کلِ طلب جدا وصول شد → AR صفر
    inst = plan["installments"][0]
    r = client.post(
        f"/api/installment-plans/{plan['id']}/installments/{inst['id']}/pay",
        json={"amount": float(inst["amount"]), "transaction_date": str(TODAY), "method": "cash"},
    )
    assert r.status_code == 400  # گاردِ اضافه‌دریافت


def test_create_plan_generates_schedule_with_remainder_on_last(client):
    plan = _plan(client)  # financed 1,000,000 / 3
    assert len(plan["installments"]) == 3
    amts = [float(i["amount"]) for i in plan["installments"]]
    assert amts == [333333, 333333, 333334]  # باقیمانده روی قسطِ آخر
    assert float(plan["financed"]) == 1000000
    assert plan["number"] is not None
    # سررسیدها صعودی‌اند و اولی = تاریخ شروع
    dues = [i["due_date"] for i in plan["installments"]]
    assert dues == sorted(dues)
    assert dues[0] == str(TODAY)


def test_down_payment_reduces_financed(client):
    plan = _plan(client, total_amount=1200000, down_payment=200000, num_installments=2)
    assert float(plan["financed"]) == 1000000
    assert [float(i["amount"]) for i in plan["installments"]] == [500000, 500000]


def test_pay_installment_records_receipt_and_completes_plan(client):
    cust = _customer(client)
    plan = _plan(client, contact_id=cust, total_amount=300000, num_installments=3)
    ins = plan["installments"]

    # پرداختِ هر سه قسط
    for i in ins:
        r = client.post(
            f"/api/installment-plans/{plan['id']}/installments/{i['id']}/pay",
            json={"amount": float(i["amount"]), "transaction_date": str(TODAY), "method": "cash"},
        )
        assert r.status_code == 200, r.text
        plan = r.json()

    assert plan["status"] == "completed"
    assert float(plan["total_paid"]) == 300000
    assert float(plan["total_remaining"]) == 0
    assert all(x["status"] == "paid" for x in plan["installments"])

    # پرداخت‌ها به‌صورتِ دریافتِ خزانه در کارت‌حسابِ مشتری دیده می‌شوند (بستانکار)
    st = client.get(f"/api/reports/contact-statement/{cust}").json()
    receipts = [l for l in st["lines"] if l["kind"] == "receipt"]
    assert len(receipts) == 3
    assert sum(float(l["credit"]) for l in receipts) == 300000


def test_overpay_installment_rejected(client):
    plan = _plan(client, total_amount=300000, num_installments=3)
    first = plan["installments"][0]
    r = client.post(
        f"/api/installment-plans/{plan['id']}/installments/{first['id']}/pay",
        json={"amount": float(first["amount"]) + 1, "transaction_date": str(TODAY), "method": "cash"},
    )
    assert r.status_code == 400


def test_partial_payment_marks_partial(client):
    plan = _plan(client, total_amount=300000, num_installments=3)
    first = plan["installments"][0]
    r = client.post(
        f"/api/installment-plans/{plan['id']}/installments/{first['id']}/pay",
        json={"amount": 50000, "transaction_date": str(TODAY), "method": "cash"},
    )
    assert r.status_code == 200
    plan = r.json()
    inst0 = plan["installments"][0]
    assert inst0["status"] == "partial"
    assert float(inst0["remaining"]) == float(inst0["amount"]) - 50000


def test_cancel_plan(client):
    plan = _plan(client)
    r = client.post(f"/api/installment-plans/{plan['id']}/cancel")
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"


def test_overdue_installment_appears_in_alerts(client):
    start = TODAY - timedelta(days=60)  # اقساطِ گذشته
    _plan(client, start_date=str(start))
    alerts = client.get("/api/alerts").json()
    assert any(a["category"] == "installment" for a in alerts["items"])


# ── قیمت نقدی و سود ──────────────────────────────────────────────────────────


def test_cash_price_and_profit_must_add_up(client):
    cust = _customer(client)
    _backing_sale(client, cust, 1_200_000)
    r = client.post(
        "/api/installment-plans",
        json={
            "contact_id": cust,
            "total_amount": 1_200_000,
            "cash_price": 1_000_000,
            "profit_amount": 150_000,  # ۱٬۱۵۰٬۰۰۰ ≠ ۱٬۲۰۰٬۰۰۰
            "num_installments": 3,
            "interval_months": 1,
            "start_date": str(TODAY),
        },
    )
    assert r.status_code == 422


def test_profit_defaults_to_zero_for_old_shaped_requests(client):
    """درخواستِ بدونِ قیمت نقدی باید مثلِ قبل کار کند: کل = نقدی، سود صفر."""
    plan = _plan(client)
    assert plan["cash_price"] == "1000000"
    assert plan["profit_amount"] == "0"
    assert plan["profit_pct"] == "0.0"


def test_profit_is_reported_with_percentage(client):
    cust = _customer(client)
    _backing_sale(client, cust, 1_200_000)
    plan = _plan(
        client,
        backing=False,
        contact_id=cust,
        total_amount=1_200_000,
        cash_price=1_000_000,
        profit_amount=200_000,
    )
    assert plan["cash_price"] == "1000000"
    assert plan["profit_amount"] == "200000"
    assert plan["profit_pct"] == "20.0"


# ── جریمه‌ی دیرکرد ───────────────────────────────────────────────────────────


def test_penalty_accrues_only_on_late_installments(client):
    cust = _customer(client)
    _backing_sale(client, cust, 900_000)
    plan = _plan(
        client,
        backing=False,
        contact_id=cust,
        total_amount=900_000,
        num_installments=3,
        penalty_rate=2,
        start_date=str(TODAY - timedelta(days=60)),
    )
    late = [i for i in plan["installments"] if i["days_late"] > 0]
    assert late, "قسط‌های گذشته باید تأخیر داشته باشند"
    assert all(Decimal(i["penalty"]) > 0 for i in late)
    # قسطِ سررسیدنشده نه تأخیر دارد نه جریمه
    future = [i for i in plan["installments"] if i["days_late"] == 0]
    assert all(i["penalty"] == "0" for i in future)
    assert Decimal(plan["penalty_total"]) > 0


def test_no_penalty_when_rate_is_zero(client):
    plan = _plan(client, start_date=str(TODAY - timedelta(days=90)))
    assert Decimal(plan["penalty_rate"]) == 0
    assert Decimal(plan["penalty_total"]) == 0


# ── تسهیمِ یک فیش بین چند قسط ────────────────────────────────────────────────


def test_settle_allocates_oldest_first(client):
    plan = _plan(client, total_amount=900_000, num_installments=3)  # ۳ قسطِ ۳۰۰٬۰۰۰
    r = client.post(
        f"/api/installment-plans/{plan['id']}/settle",
        json={"amount": 700_000, "transaction_date": str(TODAY), "method": "cash"},
    )
    assert r.status_code == 200, r.text
    out = r.json()
    paid = [Decimal(i["paid_amount"]) for i in out["installments"]]
    # ۳۰۰ + ۳۰۰ + ۱۰۰ — از قدیمی‌ترین به بعد
    assert paid == [Decimal(300_000), Decimal(300_000), Decimal(100_000)]
    assert out["total_paid"] == "700000"
    # هر تخصیص ردِ خودش را دارد
    assert len(out["payments"]) == 3
    assert {p["installment_seq"] for p in out["payments"]} == {1, 2, 3}


def test_settle_rejects_more_than_outstanding(client):
    plan = _plan(client, total_amount=900_000, num_installments=3)
    r = client.post(
        f"/api/installment-plans/{plan['id']}/settle",
        json={"amount": 950_000, "transaction_date": str(TODAY), "method": "cash"},
    )
    assert r.status_code == 400


def test_settling_everything_completes_the_plan(client):
    plan = _plan(client, total_amount=900_000, num_installments=3)
    r = client.post(
        f"/api/installment-plans/{plan['id']}/settle",
        json={"amount": 900_000, "transaction_date": str(TODAY), "method": "cash"},
    )
    assert r.json()["status"] == "completed"


# ── تاریخچه‌ی پرداخت ─────────────────────────────────────────────────────────


def test_payment_history_records_treasury_link(client):
    plan = _plan(client, total_amount=900_000, num_installments=3)
    inst = plan["installments"][0]
    r = client.post(
        f"/api/installment-plans/{plan['id']}/installments/{inst['id']}/pay",
        json={"amount": 300_000, "transaction_date": str(TODAY), "method": "cash", "notes": "فیش ۱۲۳"},
    )
    assert r.status_code == 200, r.text
    payments = r.json()["payments"]
    assert len(payments) == 1
    assert payments[0]["amount"] == "300000"
    assert payments[0]["notes"] == "فیش ۱۲۳"
    # پرداخت به سندِ خزانه‌ی واقعی گره خورده، نه یک عددِ معلق
    assert payments[0]["treasury_transaction_id"]


# ── تنظیمِ مجددِ زمان‌بندی ────────────────────────────────────────────────────


def test_reschedule_must_preserve_total(client):
    plan = _plan(client, total_amount=900_000, num_installments=3)
    first = plan["installments"][0]
    r = client.post(
        f"/api/installment-plans/{plan['id']}/reschedule",
        json={"lines": [{"installment_id": first["id"], "due_date": first["due_date"], "amount": 100_000}]},
    )
    assert r.status_code == 400  # ۱۰۰ + ۳۰۰ + ۳۰۰ ≠ ۹۰۰


def test_reschedule_moves_amount_between_installments(client):
    plan = _plan(client, total_amount=900_000, num_installments=3)
    a, b = plan["installments"][0], plan["installments"][1]
    r = client.post(
        f"/api/installment-plans/{plan['id']}/reschedule",
        json={
            "lines": [
                {"installment_id": a["id"], "due_date": a["due_date"], "amount": 100_000},
                {"installment_id": b["id"], "due_date": b["due_date"], "amount": 500_000},
            ]
        },
    )
    assert r.status_code == 200, r.text
    amounts = [Decimal(i["amount"]) for i in r.json()["installments"]]
    assert amounts == [Decimal(100_000), Decimal(500_000), Decimal(300_000)]


def test_reschedule_cannot_go_below_paid(client):
    plan = _plan(client, total_amount=900_000, num_installments=3)
    inst = plan["installments"][0]
    client.post(
        f"/api/installment-plans/{plan['id']}/installments/{inst['id']}/pay",
        json={"amount": 200_000, "transaction_date": str(TODAY), "method": "cash"},
    )
    r = client.post(
        f"/api/installment-plans/{plan['id']}/reschedule",
        json={
            "lines": [
                {"installment_id": inst["id"], "due_date": inst["due_date"], "amount": 100_000},
                {"installment_id": plan["installments"][1]["id"], "due_date": plan["installments"][1]["due_date"], "amount": 500_000},
            ]
        },
    )
    assert r.status_code == 400


def test_reschedule_renumbers_by_due_date(client):
    """جابه‌جاییِ سررسید باید شماره‌ها را هم مرتب کند — «قسط بعدی» به seq تکیه می‌کند."""
    plan = _plan(client, total_amount=900_000, num_installments=3)
    a, c = plan["installments"][0], plan["installments"][2]
    r = client.post(
        f"/api/installment-plans/{plan['id']}/reschedule",
        json={
            "lines": [
                {"installment_id": a["id"], "due_date": c["due_date"], "amount": 300_000},
                {"installment_id": c["id"], "due_date": a["due_date"], "amount": 300_000},
            ]
        },
    )
    assert r.status_code == 200, r.text
    out = r.json()["installments"]
    assert [i["seq"] for i in out] == [1, 2, 3]
    assert out[0]["due_date"] <= out[1]["due_date"] <= out[2]["due_date"]


# ── تسویه‌ی زودهنگام ─────────────────────────────────────────────────────────


def test_early_settlement_quote_caps_discount_at_unearned_profit(client):
    cust = _customer(client)
    _backing_sale(client, cust, 1_200_000)
    plan = _plan(
        client,
        backing=False,
        contact_id=cust,
        total_amount=1_200_000,
        cash_price=1_000_000,
        profit_amount=200_000,
        num_installments=4,
    )
    q = client.get(f"/api/installment-plans/{plan['id']}/early-settlement").json()
    assert q["remaining"] == "1200000"
    assert q["unearned_profit"] == "200000"  # هنوز چیزی وصول نشده
    too_much = client.get(f"/api/installment-plans/{plan['id']}/early-settlement?discount=250000")
    assert too_much.status_code == 400
    ok = client.get(f"/api/installment-plans/{plan['id']}/early-settlement?discount=200000").json()
    assert ok["payable"] == "1000000"  # یعنی همان قیمتِ نقدی


# ── نمای مدیریتی ─────────────────────────────────────────────────────────────


def test_summary_buckets_overdue_by_age(client):
    cust = _customer(client)
    _backing_sale(client, cust, 900_000)
    _plan(
        client,
        backing=False,
        contact_id=cust,
        total_amount=900_000,
        num_installments=3,
        start_date=str(TODAY - timedelta(days=45)),
    )
    s = client.get("/api/installment-plans/summary").json()
    assert s["active_plans"] >= 1
    assert Decimal(s["overdue_amount"]) > 0
    by_key = {b["key"]: b for b in s["buckets"]}
    assert by_key["d31_60"]["count"] >= 1  # قسطِ اول ۴۵ روز معوق است
    assert by_key["d1_30"]["count"] >= 1  # قسطِ دوم ۱۵ روز
    assert s["top_debtors"] and s["top_debtors"][0]["contact_name"] == "مشتری اقساطی"


def test_summary_collected_pct_tracks_payments(client):
    plan = _plan(client, total_amount=900_000, num_installments=3)
    client.post(
        f"/api/installment-plans/{plan['id']}/settle",
        json={"amount": 450_000, "transaction_date": str(TODAY), "method": "cash"},
    )
    s = client.get("/api/installment-plans/summary").json()
    assert Decimal(s["total_collected"]) >= Decimal(450_000)
    assert Decimal(s["collected_pct"]) > 0
