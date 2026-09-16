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


# ─────────────────── تحویلِ مواد / رسیدِ محصول / محاسبه‌ی بها ───────────────────


def _started_plan(client, key, wh, bom_id, qty=10):
    plan = client.post(
        "/api/production-plans",
        json={"bom_id": bom_id, "warehouse_id": wh, "planned_date": TODAY, "qty_planned": qty},
        headers={"Idempotency-Key": key},
    ).json()
    r = client.patch(f"/api/production-plans/{plan['id']}/status", json={"status": "started"})
    assert r.status_code == 200, r.text
    return r.json()


def test_issuing_materials_makes_a_real_warehouse_issue_and_debits_wip(client):
    wh = _wh(client)
    a = _item(client, "MI-A", "جزء الف")
    fin = _item(client, "MI-FIN", "محصول")
    _buy(client, wh, a, 100, 1000)
    bom = client.post("/api/boms", json={"finished_item_id": fin, "yield_qty": 1, "lines": [{"component_item_id": a, "qty": 2}]}).json()
    plan = _started_plan(client, "mi-plan-1", wh, bom["id"], qty=10)

    r = client.post(
        f"/api/production-plans/{plan['id']}/issue-materials",
        json={"issue_date": TODAY},
        headers={"Idempotency-Key": "mi-issue-1"},
    )
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["issue_type"] == "production"
    assert d["production_plan_id"] == plan["id"]
    assert float(d["total_qty"]) == 20  # ۲×۱۰ (کلِ باقی‌مانده، چون qty داده نشده)
    assert float(d["total_cost"]) == 20000  # ۲۰×۱۰۰۰

    #: حواله در فهرستِ عمومیِ خروج‌ها هم دیده می‌شود — یک موتور، نه دو.
    issues = client.get("/api/warehouse-issues", params={"issue_type": "production", "limit": 200}).json()
    rows = issues["items"] if isinstance(issues, dict) else issues
    assert any(row["id"] == d["id"] for row in rows)

    #: موجودیِ جزء کم شده؛ محصول هنوز وارد نشده (رسید جدا است).
    assert _stock(client).get(a) == 80  # ۱۰۰ − ۲۰
    assert _stock(client).get(fin) is None

    updated_plan = [p for p in client.get("/api/production-plans", params={"limit": 200}).json()["items"] if p["id"] == plan["id"]][0]
    assert float(updated_plan["material_cost_issued"]) == 20000


def test_issuing_materials_rejects_qty_beyond_remaining(client):
    wh = _wh(client)
    a = _item(client, "MIQ-A", "جزء")
    fin = _item(client, "MIQ-FIN", "محصول")
    _buy(client, wh, a, 100, 1000)
    bom = client.post("/api/boms", json={"finished_item_id": fin, "yield_qty": 1, "lines": [{"component_item_id": a, "qty": 1}]}).json()
    plan = _started_plan(client, "miq-plan-1", wh, bom["id"], qty=5)

    r = client.post(
        f"/api/production-plans/{plan['id']}/issue-materials",
        json={"issue_date": TODAY, "qty": 6},
        headers={"Idempotency-Key": "miq-issue-1"},
    )
    assert r.status_code == 400


def test_issuing_materials_rejects_a_draft_plan(client):
    wh = _wh(client)
    a = _item(client, "MID-A", "جزء")
    fin = _item(client, "MID-FIN", "محصول")
    _buy(client, wh, a, 100, 1000)
    bom = client.post("/api/boms", json={"finished_item_id": fin, "yield_qty": 1, "lines": [{"component_item_id": a, "qty": 1}]}).json()
    plan = client.post(
        "/api/production-plans",
        json={"bom_id": bom["id"], "warehouse_id": wh, "planned_date": TODAY, "qty_planned": 5},
        headers={"Idempotency-Key": "mid-plan-1"},
    ).json()

    r = client.post(
        f"/api/production-plans/{plan['id']}/issue-materials",
        json={"issue_date": TODAY},
        headers={"Idempotency-Key": "mid-issue-1"},
    )
    assert r.status_code == 409


def test_receiving_output_makes_a_real_warehouse_receipt_priced_from_issued_material(client):
    wh = _wh(client)
    a = _item(client, "MR-A", "جزء")
    fin = _item(client, "MR-FIN", "محصول")
    _buy(client, wh, a, 100, 1000)
    bom = client.post("/api/boms", json={"finished_item_id": fin, "yield_qty": 1, "lines": [{"component_item_id": a, "qty": 2}]}).json()
    plan = _started_plan(client, "mr-plan-1", wh, bom["id"], qty=10)

    client.post(
        f"/api/production-plans/{plan['id']}/issue-materials",
        json={"issue_date": TODAY},
        headers={"Idempotency-Key": "mr-issue-1"},
    )

    #: رسیدِ جزئی: نیمی از برنامه.
    r = client.post(
        f"/api/production-plans/{plan['id']}/receive-output",
        json={"receipt_date": TODAY, "qty": 4},
        headers={"Idempotency-Key": "mr-receipt-1"},
    )
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["receipt_type"] == "production"
    assert d["production_plan_id"] == plan["id"]
    #: نرخِ واحد = کلِ موادِ تحویل‌شده (۲۰۰۰۰) ÷ تعدادِ برنامه (۱۰) = ۲۰۰۰
    assert float(d["lines"][0]["unit_cost"]) == 2000

    assert _avg_cost(client, fin) == 2000
    assert _stock(client).get(fin) == 4

    updated_plan = [p for p in client.get("/api/production-plans", params={"limit": 200}).json()["items"] if p["id"] == plan["id"]][0]
    assert float(updated_plan["qty_produced"]) == 4

    #: رسیدِ دوم برای باقی‌ماندهٔ برنامه، همان نرخ.
    r2 = client.post(
        f"/api/production-plans/{plan['id']}/receive-output",
        json={"receipt_date": TODAY, "qty": 6},
        headers={"Idempotency-Key": "mr-receipt-2"},
    )
    assert r2.status_code == 201, r2.text
    assert float(r2.json()["lines"][0]["unit_cost"]) == 2000
    assert _stock(client).get(fin) == 10


def test_receiving_output_rejects_qty_beyond_remaining(client):
    wh = _wh(client)
    a = _item(client, "MRQ-A", "جزء")
    fin = _item(client, "MRQ-FIN", "محصول")
    _buy(client, wh, a, 100, 1000)
    bom = client.post("/api/boms", json={"finished_item_id": fin, "yield_qty": 1, "lines": [{"component_item_id": a, "qty": 1}]}).json()
    plan = _started_plan(client, "mrq-plan-1", wh, bom["id"], qty=5)
    client.post(f"/api/production-plans/{plan['id']}/issue-materials", json={"issue_date": TODAY}, headers={"Idempotency-Key": "mrq-issue-1"})

    r = client.post(
        f"/api/production-plans/{plan['id']}/receive-output",
        json={"receipt_date": TODAY, "qty": 6},
        headers={"Idempotency-Key": "mrq-receipt-1"},
    )
    assert r.status_code == 400


def test_calculating_cost_distributes_labor_and_overhead_onto_average_cost(client):
    wh = _wh(client)
    a = _item(client, "MC-A", "جزء")
    fin = _item(client, "MC-FIN", "محصول")
    _buy(client, wh, a, 100, 1000)
    bom = client.post("/api/boms", json={"finished_item_id": fin, "yield_qty": 1, "lines": [{"component_item_id": a, "qty": 1}]}).json()
    plan = _started_plan(client, "mc-plan-1", wh, bom["id"], qty=10)
    client.post(f"/api/production-plans/{plan['id']}/issue-materials", json={"issue_date": TODAY}, headers={"Idempotency-Key": "mc-issue-1"})
    client.post(
        f"/api/production-plans/{plan['id']}/receive-output",
        json={"receipt_date": TODAY, "qty": 10},
        headers={"Idempotency-Key": "mc-receipt-1"},
    )
    assert _avg_cost(client, fin) == 1000  # فقط بهای مواد تا این‌جا

    r = client.post(
        f"/api/production-plans/{plan['id']}/calculate-cost",
        json={"calc_date": TODAY, "labor_cost": 3000, "overhead_cost": 2000},
        headers={"Idempotency-Key": "mc-calc-1"},
    )
    assert r.status_code == 201, r.text
    #: (۳۰۰۰+۲۰۰۰)/۱۰ = ۵۰۰ روی هر واحد اضافه می‌شود
    assert _avg_cost(client, fin) == 1500


def test_calculating_cost_rejects_when_nothing_received_yet(client):
    wh = _wh(client)
    a = _item(client, "MCN-A", "جزء")
    fin = _item(client, "MCN-FIN", "محصول")
    bom = client.post("/api/boms", json={"finished_item_id": fin, "yield_qty": 1, "lines": [{"component_item_id": a, "qty": 1}]}).json()
    plan = _started_plan(client, "mcn-plan-1", wh, bom["id"], qty=5)

    r = client.post(
        f"/api/production-plans/{plan['id']}/calculate-cost",
        json={"calc_date": TODAY, "labor_cost": 1000},
        headers={"Idempotency-Key": "mcn-calc-1"},
    )
    assert r.status_code == 400


def test_calculating_cost_double_submit_is_idempotent(client):
    wh = _wh(client)
    a = _item(client, "MCI-A", "جزء")
    fin = _item(client, "MCI-FIN", "محصول")
    _buy(client, wh, a, 100, 1000)
    bom = client.post("/api/boms", json={"finished_item_id": fin, "yield_qty": 1, "lines": [{"component_item_id": a, "qty": 1}]}).json()
    plan = _started_plan(client, "mci-plan-1", wh, bom["id"], qty=10)
    client.post(f"/api/production-plans/{plan['id']}/issue-materials", json={"issue_date": TODAY}, headers={"Idempotency-Key": "mci-issue-1"})
    client.post(
        f"/api/production-plans/{plan['id']}/receive-output",
        json={"receipt_date": TODAY, "qty": 10},
        headers={"Idempotency-Key": "mci-receipt-1"},
    )

    body = {"calc_date": TODAY, "labor_cost": 1000}
    headers = {"Idempotency-Key": "mci-calc-1"}
    client.post(f"/api/production-plans/{plan['id']}/calculate-cost", json=body, headers=headers)
    client.post(f"/api/production-plans/{plan['id']}/calculate-cost", json=body, headers=headers)
    #: دوبار کلیک نباید دستمزد را دوبار روی بها بنشاند.
    assert _avg_cost(client, fin) == 1100  # ۱۰۰۰ + ۱۰۰۰/۱۰


# ───────────────────────────── گزارش‌های تولید ─────────────────────────────


def _full_run(client, prefix, *, planned=10, issued=None, received=10, labor=0, overhead=0, bom_qty=2):
    """یک گردشِ کاملِ تولید تا هر جایی که تست می‌خواهد — برمی‌گرداند (plan, item ids)."""
    wh = _wh(client)
    a = _item(client, f"{prefix}-A", "جزء")
    fin = _item(client, f"{prefix}-FIN", "محصول")
    _buy(client, wh, a, 1000, 1000)
    bom = client.post(
        "/api/boms",
        json={"finished_item_id": fin, "yield_qty": 1, "lines": [{"component_item_id": a, "qty": bom_qty}]},
    ).json()
    plan = _started_plan(client, f"{prefix}-plan", wh, bom["id"], qty=planned)

    issue_body = {"issue_date": TODAY}
    if issued is not None:
        issue_body["qty"] = issued
    client.post(f"/api/production-plans/{plan['id']}/issue-materials", json=issue_body, headers={"Idempotency-Key": f"{prefix}-issue"})
    if received:
        client.post(
            f"/api/production-plans/{plan['id']}/receive-output",
            json={"receipt_date": TODAY, "qty": received},
            headers={"Idempotency-Key": f"{prefix}-receipt"},
        )
    if labor or overhead:
        client.post(
            f"/api/production-plans/{plan['id']}/calculate-cost",
            json={"calc_date": TODAY, "labor_cost": labor, "overhead_cost": overhead},
            headers={"Idempotency-Key": f"{prefix}-calc"},
        )
    return plan, a, fin


def test_material_variance_is_zero_when_consumption_matches_the_formula(client):
    plan, comp, _ = _full_run(client, "VAR1", planned=10, received=10, bom_qty=2)

    rows = client.get("/api/production-reports/material-variance", params={"plan_id": plan["id"]}).json()
    assert len(rows) == 1
    row = rows[0]
    assert row["component_item_id"] == comp
    assert float(row["standard_qty"]) == 20  # ۲ × ۱۰ تولیدشده
    assert float(row["actual_qty"]) == 20
    assert float(row["variance_qty"]) == 0


def test_material_variance_shows_the_gap_when_production_lags_the_issue(client):
    """موادِ تحویل‌شده برای ۱۰ واحد ولی فقط ۴ واحد تولید شد — ۱۲ واحد هنوز روی خط است."""
    plan, _, _ = _full_run(client, "VAR2", planned=10, received=4, bom_qty=2)

    row = client.get("/api/production-reports/material-variance", params={"plan_id": plan["id"]}).json()[0]
    assert float(row["qty_produced"]) == 4
    assert float(row["standard_qty"]) == 8    # ۲ × ۴
    assert float(row["actual_qty"]) == 20     # کلِ باقی‌مانده تحویل شده بود
    assert float(row["variance_qty"]) == 12


def test_the_kardex_shows_material_in_and_product_out(client):
    plan, comp, fin = _full_run(client, "KDX1", planned=5, received=5, bom_qty=3)

    rows = client.get("/api/production-reports/kardex", params={"plan_id": plan["id"]}).json()
    assert len(rows) == 2

    material = next(r for r in rows if r["item_id"] == comp)
    assert material["kind"] == "issue"
    assert float(material["qty_in"]) == 15   # ۳ × ۵ واردِ خط
    assert float(material["qty_out"]) == 0

    product = next(r for r in rows if r["item_id"] == fin)
    assert product["kind"] == "receipt"
    assert float(product["qty_in"]) == 0
    assert float(product["qty_out"]) == 5    # خروجِ خط به انبار


def test_the_kardex_filters_by_item(client):
    plan, comp, fin = _full_run(client, "KDX2", planned=5, received=5)

    only_material = client.get("/api/production-reports/kardex", params={"plan_id": plan["id"], "item_id": comp}).json()
    assert len(only_material) == 1
    assert only_material[0]["item_id"] == comp

    only_product = client.get("/api/production-reports/kardex", params={"plan_id": plan["id"], "item_id": fin}).json()
    assert len(only_product) == 1
    assert only_product[0]["item_id"] == fin


def test_the_cost_report_splits_material_labor_and_overhead(client):
    #: ۱۰ واحد، هرکدام ۲ جزءِ ۱۰۰۰ ریالی = موادِ ۲۰٬۰۰۰ · دستمزد ۵٬۰۰۰ · سربار ۵٬۰۰۰
    plan, _, _ = _full_run(client, "CST1", planned=10, received=10, labor=5000, overhead=5000, bom_qty=2)

    row = client.get("/api/production-reports/cost", params={"plan_id": plan["id"]}).json()[0]
    assert float(row["material_cost"]) == 20000
    assert float(row["labor_cost"]) == 5000
    assert float(row["overhead_cost"]) == 5000
    assert float(row["total_cost"]) == 30000
    assert float(row["unit_cost"]) == 3000  # ۳۰٬۰۰۰ ÷ ۱۰


def test_a_voided_material_issue_leaves_the_reports(client):
    """ابطال یعنی آن حرکت هرگز نبوده — انحرافی که از حواله‌ی باطل ساخته شود دروغ است."""
    plan, _, _ = _full_run(client, "VOID1", planned=6, received=6, bom_qty=2)

    issues = client.get("/api/warehouse-issues", params={"issue_type": "production", "limit": 200}).json()["items"]
    mine = [r for r in issues if r["kind"] == "issue"][0]
    voided = client.post(f"/api/warehouse-issues/{mine['id']}/void", json={"reason": "آزمون"})
    assert voided.status_code == 200, voided.text

    row = client.get("/api/production-reports/material-variance", params={"plan_id": plan["id"]}).json()[0]
    assert float(row["actual_qty"]) == 0        # حواله‌ی باطل شمرده نمی‌شود
    assert float(row["standard_qty"]) == 12     # استاندارد سرِ جایش است

    kardex = client.get("/api/production-reports/kardex", params={"plan_id": plan["id"]}).json()
    assert all(r["kind"] != "issue" for r in kardex)
