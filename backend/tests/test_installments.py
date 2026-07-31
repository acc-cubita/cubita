"""فروش اقساطی: زمان‌بندیِ اقساط + پرداخت از خزانه + هشدار معوق."""
from datetime import date, timedelta

TODAY = date.today()


def _customer(client):
    return client.post("/api/contacts", json={"name": "مشتری اقساطی", "type": "customer"}).json()["id"]


def _plan(client, **overrides):
    body = {
        "contact_id": overrides.pop("contact_id", None) or _customer(client),
        "title": "خرید یخچال",
        "total_amount": 1000000,
        "down_payment": 0,
        "num_installments": 3,
        "interval_months": 1,
        "start_date": str(TODAY),
    }
    body.update(overrides)
    r = client.post("/api/installment-plans", json=body)
    assert r.status_code == 201, r.text
    return r.json()


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
