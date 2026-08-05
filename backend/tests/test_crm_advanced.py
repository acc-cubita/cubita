"""ابزارهای پیشرفته‌ی باشگاه مشتریان — RFM، سطوح، جوایز/بازخرید، تولد."""
from datetime import date, timedelta

TODAY = str(date.today())


def _wh(client):
    return client.post("/api/warehouses", json={"code": "AD", "name": "انبار"}).json()["id"]


def _item(client):
    return client.post("/api/items", json={"sku": "AD-1", "name": "کالا", "sales_price": 100000}).json()["id"]


def _buy(client, wh, item, qty=1000, cost=1000):
    client.post("/api/purchase-invoices", json={
        "invoice_date": TODAY, "warehouse_id": wh, "tax_rate": 0,
        "lines": [{"item_id": item, "qty": qty, "unit_cost": cost}],
    })


def _customer(client, name="مشتری باشگاه"):
    return client.post("/api/contacts", json={"name": name, "type": "customer"}).json()["id"]


def _sell(client, wh, item, contact_id, qty=1, price=100000, when=TODAY):
    return client.post("/api/sales-invoices", json={
        "invoice_date": when, "warehouse_id": wh, "tax_rate": 0, "contact_id": contact_id,
        "lines": [{"item_id": item, "qty": qty, "unit_price": price}],
    })


def _points(client, contact_id, pts):
    client.post("/api/crm/loyalty/transactions", json={
        "contact_id": contact_id, "points": pts, "reason": "تست", "txn_date": TODAY,
    })


# ── بخش‌بندیِ RFM ──────────────────────────────────────
def test_rfm_segments_new_customer(client):
    wh, item = _wh(client), _item(client)
    _buy(client, wh, item)
    cust = _customer(client, "خریدارِ تازه")
    r = _sell(client, wh, item, cust, qty=2, price=100000)
    assert r.status_code == 201, r.text

    seg = client.get("/api/crm/segments")
    assert seg.status_code == 200, seg.text
    data = seg.json()
    assert data["total_customers"] == 1
    row = data["customers"][0]
    assert row["contact_id"] == cust
    assert row["frequency"] == 1
    assert row["recency_days"] == 0
    assert float(row["monetary"]) == 200000
    # یک خریدِ امروز → «تازه‌وارد»
    assert row["segment"] == "new"
    # خلاصه شاملِ همان بخش است
    assert any(s["segment"] == "new" and s["count"] == 1 for s in data["summary"])


def test_rfm_excludes_voided_and_no_contact(client):
    wh, item = _wh(client), _item(client)
    _buy(client, wh, item)
    cust = _customer(client)
    inv = _sell(client, wh, item, cust).json()
    # فروشِ نقدی بدونِ مشتری نباید در RFM بیاید
    _sell(client, wh, item, None)
    # باطل‌کردنِ فاکتورِ مشتری → دیگر نباید بشمارد
    client.post(f"/api/sales-invoices/{inv['id']}/void", json={"reason": "تست"})
    data = client.get("/api/crm/segments").json()
    assert data["total_customers"] == 0


# ── سطوحِ باشگاه ────────────────────────────────────────
def test_tiers_by_points_and_membership(client):
    # مبنا = امتیاز
    client.put("/api/crm/loyalty/settings", json={
        "is_enabled": False, "amount_per_point": 0, "tier_basis": "points",
    })
    client.post("/api/crm/loyalty/tiers", json={"name": "برنز", "threshold": 0, "discount_percent": 0})
    client.post("/api/crm/loyalty/tiers", json={"name": "نقره", "threshold": 100, "discount_percent": 5})
    client.post("/api/crm/loyalty/tiers", json={"name": "طلا", "threshold": 500, "discount_percent": 10})

    cust = _customer(client, "عضوِ نقره‌ای")
    _points(client, cust, 150)

    t = client.get(f"/api/crm/loyalty/tier/{cust}").json()
    assert t["tier_name"] == "نقره"
    assert float(t["discount_percent"]) == 5
    assert float(t["value"]) == 150

    members = client.get("/api/crm/loyalty/tier-members").json()
    assert any(m["contact_id"] == cust and m["tier_name"] == "نقره" for m in members)


def test_tier_discount_range_validation(client):
    r = client.post("/api/crm/loyalty/tiers", json={"name": "بد", "threshold": 0, "discount_percent": 150})
    assert r.status_code == 422


# ── جوایز و بازخرید ────────────────────────────────────
def test_reward_redeem_deducts_points(client):
    reward = client.post("/api/crm/loyalty/rewards", json={
        "name": "تخفیفِ ۱۰٪", "points_cost": 100, "kind": "discount", "value": "10",
    }).json()
    cust = _customer(client, "بازخریدکننده")
    _points(client, cust, 150)

    r = client.post("/api/crm/loyalty/redeem", json={"contact_id": cust, "reward_id": reward["id"]})
    assert r.status_code == 201, r.text
    assert r.json()["points"] == -100
    assert r.json()["reward_id"] == reward["id"]

    # مانده حالا ۵۰ است → بازخریدِ دوباره (لازم ۱۰۰) رد می‌شود
    bal = next(b for b in client.get("/api/crm/loyalty").json() if b["contact_id"] == cust)
    assert bal["balance"] == 50
    r2 = client.post("/api/crm/loyalty/redeem", json={"contact_id": cust, "reward_id": reward["id"]})
    assert r2.status_code == 400
    assert "کافی" in r2.json()["detail"]


def test_reward_cost_must_be_positive(client):
    r = client.post("/api/crm/loyalty/rewards", json={"name": "x", "points_cost": 0})
    assert r.status_code == 422


# ── تولد ────────────────────────────────────────────────
def test_upcoming_birthdays(client):
    today = date.today()
    # تولدِ فردا (همین ماه/روز، سالِ گذشته) → باید در فهرست باشد
    soon = today + timedelta(days=1)
    bday = date(1990, soon.month, soon.day)
    cust = client.post("/api/contacts", json={
        "name": "متولدِ فردا", "type": "customer", "birthday": str(bday),
    }).json()["id"]
    # مشتریِ بدونِ تولد نباید بیاید
    _customer(client, "بدونِ تولد")

    rows = client.get("/api/crm/birthdays", params={"days": 7}).json()
    assert any(r["contact_id"] == cust and r["days_until"] == 1 for r in rows)
    assert all(r["contact_id"] != _customer(client, "دیگری") for r in rows)


def test_loyalty_settings_extended_roundtrip(client):
    client.put("/api/crm/loyalty/settings", json={
        "is_enabled": True, "amount_per_point": 10000,
        "tier_basis": "spend", "tier_discount_auto": True, "birthday_gift_points": 20,
    })
    s = client.get("/api/crm/loyalty/settings").json()
    assert s["tier_basis"] == "spend"
    assert s["tier_discount_auto"] is True
    assert s["birthday_gift_points"] == 20
