"""باشگاه مشتریان / CRM — سرنخ، پیگیری و امتیازِ وفاداری."""
from datetime import date


def test_lead_lifecycle_and_convert(client):
    r = client.post(
        "/api/crm/leads",
        json={"name": "علی رضایی", "phone": "09120000000", "source": "اینستاگرام", "estimated_value": 5_000_000},
    )
    assert r.status_code == 201, r.text
    lead = r.json()
    assert lead["status"] == "new"
    lid = lead["id"]

    # فهرست
    assert any(x["id"] == lid for x in client.get("/api/crm/leads").json())

    # تغییر وضعیت
    r = client.patch(f"/api/crm/leads/{lid}", json={"status": "qualified"})
    assert r.status_code == 200 and r.json()["status"] == "qualified"

    # فیلترِ وضعیت
    assert any(x["id"] == lid for x in client.get("/api/crm/leads", params={"status": "qualified"}).json())

    # تبدیل به مشتری
    r = client.post(f"/api/crm/leads/{lid}/convert")
    assert r.status_code == 200, r.text
    contact_id = r.json()["contact_id"]

    conv = next(x for x in client.get("/api/crm/leads").json() if x["id"] == lid)
    assert conv["status"] == "won"
    assert conv["converted_contact_id"] == contact_id

    # تبدیلِ دوباره رد می‌شود
    assert client.post(f"/api/crm/leads/{lid}/convert").status_code == 400


def test_lead_status_validation(client):
    r = client.post("/api/crm/leads", json={"name": "x", "status": "bogus"})
    assert r.status_code == 422


def test_activity_needs_a_link(client):
    r = client.post(
        "/api/crm/activities",
        json={"kind": "call", "subject": "تماس", "activity_date": str(date.today())},
    )
    assert r.status_code == 400


def test_activity_on_lead_and_done(client):
    lid = client.post("/api/crm/leads", json={"name": "سرنخ ۲"}).json()["id"]
    r = client.post(
        "/api/crm/activities",
        json={"kind": "meeting", "subject": "جلسه", "activity_date": str(date.today()), "lead_id": lid},
    )
    assert r.status_code == 201, r.text
    aid = r.json()["id"]
    assert r.json()["done"] is False

    r = client.patch(f"/api/crm/activities/{aid}", json={"done": True})
    assert r.json()["done"] is True

    acts = client.get("/api/crm/activities", params={"lead_id": lid}).json()
    assert len(acts) == 1 and acts[0]["id"] == aid


def test_loyalty_balance(client):
    cid = client.post("/api/contacts", json={"name": "مشتری وفادار", "type": "customer"}).json()["id"]
    client.post("/api/crm/loyalty/transactions", json={"contact_id": cid, "points": 100, "reason": "خرید", "txn_date": str(date.today())})
    client.post("/api/crm/loyalty/transactions", json={"contact_id": cid, "points": -30, "reason": "استفاده", "txn_date": str(date.today())})

    row = next(x for x in client.get("/api/crm/loyalty").json() if x["contact_id"] == cid)
    assert row["balance"] == 70
    assert row["contact_name"] == "مشتری وفادار"

    # امتیازِ صفر رد می‌شود
    r = client.post("/api/crm/loyalty/transactions", json={"contact_id": cid, "points": 0, "txn_date": str(date.today())})
    assert r.status_code == 422
