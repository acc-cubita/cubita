"""تولید و بهای تمام‌شده — BOM و سفارشِ تولید."""
from datetime import date

import pytest

TODAY = str(date.today())


@pytest.fixture(autouse=True)
def _grant_manufacturing(db, tenant_id):
    """«تولید» ماژولِ محدود است (require_module)؛ برای این تست‌ها به مستأجرِ آزمون گرنت می‌شود."""
    from app.models.tenant import Tenant

    db.get(Tenant, tenant_id).granted_modules = ["manufacturing"]
    db.flush()


def _wh(client):
    r = client.post("/api/warehouses", json={"code": "MFG", "name": "انبار تولید"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _item(client, sku, name):
    r = client.post("/api/items", json={"sku": sku, "name": name})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _buy(client, wh, item_id, qty, unit_cost):
    r = client.post(
        "/api/purchase-invoices",
        json={"invoice_date": TODAY, "warehouse_id": wh, "tax_rate": 0, "lines": [{"item_id": item_id, "qty": qty, "unit_cost": unit_cost}]},
    )
    assert r.status_code == 201, r.text


def _avg_cost(client, item_id):
    for it in client.get("/api/items").json()["items"]:
        if it["id"] == item_id:
            return float(it["average_cost"])
    return None


def _stock(client):
    return {s["item_id"]: float(s["qty"]) for s in client.get("/api/stock").json()}


def test_production_costing(client):
    wh = _wh(client)
    a = _item(client, "COMP-A", "جزء الف")
    b = _item(client, "COMP-B", "جزء ب")
    fin = _item(client, "FIN-1", "محصول نهایی")
    _buy(client, wh, a, 100, 1000)  # میانگین ۱۰۰۰
    _buy(client, wh, b, 50, 2000)   # میانگین ۲۰۰۰

    bom = client.post(
        "/api/boms",
        json={"finished_item_id": fin, "name": "فرمولِ محصول", "yield_qty": 1,
              "lines": [{"component_item_id": a, "qty": 1}, {"component_item_id": b, "qty": 2}]},
    )
    assert bom.status_code == 201, bom.text

    po = client.post(
        "/api/production-orders",
        json={"bom_id": bom.json()["id"], "warehouse_id": wh, "production_date": TODAY, "qty_produced": 10},
    )
    assert po.status_code == 201, po.text
    d = po.json()
    assert float(d["component_cost"]) == 50000  # ۱۰×۱۰۰۰ + ۲۰×۲۰۰۰
    assert float(d["unit_cost"]) == 5000
    assert float(d["overhead_cost"]) == 0
    assert d["number"] is not None

    assert _avg_cost(client, fin) == 5000
    s = _stock(client)
    assert s.get(a) == 90   # ۱۰۰ − ۱۰
    assert s.get(b) == 30   # ۵۰ − ۲۰
    assert s.get(fin) == 10


def test_production_with_overhead(client):
    wh = _wh(client)
    a = _item(client, "OC-A", "جزء")
    fin = _item(client, "OC-FIN", "محصول")
    _buy(client, wh, a, 100, 1000)
    bom = client.post("/api/boms", json={"finished_item_id": fin, "yield_qty": 1, "lines": [{"component_item_id": a, "qty": 2}]})
    po = client.post(
        "/api/production-orders",
        json={"bom_id": bom.json()["id"], "warehouse_id": wh, "production_date": TODAY, "qty_produced": 5, "overhead_cost": 5000},
    )
    assert po.status_code == 201, po.text
    d = po.json()
    assert float(d["component_cost"]) == 10000  # ۵×۲×۱۰۰۰
    assert float(d["overhead_cost"]) == 5000
    assert float(d["unit_cost"]) == 3000        # (۱۰۰۰۰+۵۰۰۰)/۵


def test_insufficient_component_stock_rejected(client):
    wh = _wh(client)
    a = _item(client, "IS-A", "جزء کم")
    fin = _item(client, "IS-FIN", "محصول")
    _buy(client, wh, a, 5, 1000)
    bom = client.post("/api/boms", json={"finished_item_id": fin, "yield_qty": 1, "lines": [{"component_item_id": a, "qty": 1}]})
    po = client.post("/api/production-orders", json={"bom_id": bom.json()["id"], "warehouse_id": wh, "production_date": TODAY, "qty_produced": 10})
    assert po.status_code == 400  # لازم ۱۰، موجود ۵


def test_finished_cannot_be_its_own_component(client):
    fin = _item(client, "SELF-1", "محصول")
    r = client.post("/api/boms", json={"finished_item_id": fin, "yield_qty": 1, "lines": [{"component_item_id": fin, "qty": 1}]})
    assert r.status_code == 400


def test_bom_requires_lines(client):
    fin = _item(client, "NOLINES", "محصول")
    r = client.post("/api/boms", json={"finished_item_id": fin, "yield_qty": 1, "lines": []})
    assert r.status_code == 422


# ────────────────────────── سفارشِ تولید (برنامه) ──────────────────────────


def test_production_plan_gets_a_number_and_draft_status(client):
    wh = _wh(client)
    a = _item(client, "PL-A", "جزء")
    fin = _item(client, "PL-FIN", "محصول")
    bom = client.post("/api/boms", json={"finished_item_id": fin, "yield_qty": 1, "lines": [{"component_item_id": a, "qty": 1}]}).json()

    plan = client.post(
        "/api/production-plans",
        json={"bom_id": bom["id"], "warehouse_id": wh, "planned_date": TODAY, "qty_planned": 20},
        headers={"Idempotency-Key": "plan-1"},
    )
    assert plan.status_code == 201, plan.text
    d = plan.json()
    assert d["status"] == "draft"
    assert d["number"] == 1
    assert float(d["qty_planned"]) == 20
    assert float(d["qty_produced"]) == 0


def test_production_plan_does_not_touch_stock(client):
    wh = _wh(client)
    a = _item(client, "PLS-A", "جزء")
    fin = _item(client, "PLS-FIN", "محصول")
    _buy(client, wh, a, 100, 1000)
    bom = client.post("/api/boms", json={"finished_item_id": fin, "yield_qty": 1, "lines": [{"component_item_id": a, "qty": 1}]}).json()

    client.post(
        "/api/production-plans",
        json={"bom_id": bom["id"], "warehouse_id": wh, "planned_date": TODAY, "qty_planned": 20},
        headers={"Idempotency-Key": "plan-2"},
    )
    # سفارش (برنامه) هیچ اثری روی موجودی ندارد
    assert _stock(client).get(a) == 100


def test_production_plan_status_transition_rejects_illegal_jump(client):
    wh = _wh(client)
    a = _item(client, "PLT-A", "جزء")
    fin = _item(client, "PLT-FIN", "محصول")
    bom = client.post("/api/boms", json={"finished_item_id": fin, "yield_qty": 1, "lines": [{"component_item_id": a, "qty": 1}]}).json()
    plan = client.post(
        "/api/production-plans",
        json={"bom_id": bom["id"], "warehouse_id": wh, "planned_date": TODAY, "qty_planned": 5},
        headers={"Idempotency-Key": "plan-3"},
    ).json()

    bad = client.patch(f"/api/production-plans/{plan['id']}/status", json={"status": "finished"})
    assert bad.status_code == 409

    ok = client.patch(f"/api/production-plans/{plan['id']}/status", json={"status": "started"})
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == "started"


def test_production_document_linked_to_a_plan_updates_its_produced_qty(client):
    wh = _wh(client)
    a = _item(client, "LNK-A", "جزء")
    fin = _item(client, "LNK-FIN", "محصول")
    _buy(client, wh, a, 100, 1000)
    bom = client.post("/api/boms", json={"finished_item_id": fin, "yield_qty": 1, "lines": [{"component_item_id": a, "qty": 1}]}).json()
    plan = client.post(
        "/api/production-plans",
        json={"bom_id": bom["id"], "warehouse_id": wh, "planned_date": TODAY, "qty_planned": 20},
        headers={"Idempotency-Key": "plan-4"},
    ).json()

    doc = client.post(
        "/api/production-orders",
        json={
            "bom_id": bom["id"], "warehouse_id": wh, "production_date": TODAY,
            "qty_produced": 7, "production_plan_id": plan["id"],
        },
        headers={"Idempotency-Key": "doc-1"},
    )
    assert doc.status_code == 201, doc.text
    assert doc.json()["production_plan_id"] == plan["id"]

    updated_plan = client.get("/api/production-plans", params={"limit": 200}).json()["items"]
    mine = [p for p in updated_plan if p["id"] == plan["id"]][0]
    assert float(mine["qty_produced"]) == 7


def test_production_document_without_a_plan_still_works(client):
    """تولیدِ بی‌برنامه هم باید کار کند — سفارش اختیاری است."""
    wh = _wh(client)
    a = _item(client, "NOPL-A", "جزء")
    fin = _item(client, "NOPL-FIN", "محصول")
    _buy(client, wh, a, 100, 1000)
    bom = client.post("/api/boms", json={"finished_item_id": fin, "yield_qty": 1, "lines": [{"component_item_id": a, "qty": 1}]}).json()

    doc = client.post(
        "/api/production-orders",
        json={"bom_id": bom["id"], "warehouse_id": wh, "production_date": TODAY, "qty_produced": 3},
        headers={"Idempotency-Key": "doc-2"},
    )
    assert doc.status_code == 201, doc.text
    assert doc.json()["production_plan_id"] is None


def test_the_api_creates_and_lists_plans_filtered_by_status(client):
    wh = _wh(client)
    a = _item(client, "FLT-A", "جزء")
    fin = _item(client, "FLT-FIN", "محصول")
    bom = client.post("/api/boms", json={"finished_item_id": fin, "yield_qty": 1, "lines": [{"component_item_id": a, "qty": 1}]}).json()

    body = {"bom_id": bom["id"], "warehouse_id": wh, "planned_date": TODAY, "qty_planned": 5}
    headers = {"Idempotency-Key": "plan-5"}
    first = client.post("/api/production-plans", json=body, headers=headers)
    second = client.post("/api/production-plans", json=body, headers=headers)
    assert first.status_code == 201, first.text
    assert second.json()["id"] == first.json()["id"]

    drafts = client.get("/api/production-plans", params={"status": "draft", "limit": 200}).json()["items"]
    assert first.json()["id"] in {row["id"] for row in drafts}

    started = client.get("/api/production-plans", params={"status": "started", "limit": 200}).json()["items"]
    assert first.json()["id"] not in {row["id"] for row in started}
