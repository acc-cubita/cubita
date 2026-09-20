"""انسداد، فراخوان، بستن، و گزارشِ ردیابیِ بار (§۱۵ §۱۶).

بارِ مسدود همان‌جا در انبار می‌ماند — فقط دیگر فروختنی نیست. این تفکیک اصلِ
خواسته‌ی §۱۶ است: موجودیِ فیزیکی نباید دست بخورد.
"""
from datetime import date

from app.models.advanced_inventory import StockBatch
from app.services import batches as batches_svc

TODAY = str(date.today())


def _main_wh(client):
    return next(w["id"] for w in client.get("/api/warehouses").json() if w["code"] == "MAIN")


def _item(client, sku, name, **extra):
    return client.post("/api/items", json={"sku": sku, "name": name, **extra}).json()["id"]


def _buy(client, wh, item_id, qty, cost=1000):
    r = client.post("/api/purchase-invoices", json={
        "invoice_date": TODAY, "warehouse_id": wh,
        "lines": [{"item_id": item_id, "qty": qty, "unit_cost": cost}],
    })
    assert r.status_code == 201, r.text
    return r.json()


def _batch(db, item_id):
    return db.query(StockBatch).filter(StockBatch.item_id == item_id).one()


# ── انسداد و فراخوان ─────────────────────────────────────────────────
def test_blocking_keeps_physical_stock_but_kills_sellable(client, db):
    wh = _main_wh(client)
    it = _item(client, "RC-BLOCK", "مسدودی")
    _buy(client, wh, it, 50)
    batch = _batch(db, it)

    r = client.post(f"/api/stock-batches/{batch.id}/hold", json={
        "hold_status": "blocked", "reason": "شکِ کیفیت",
    })
    assert r.status_code == 200, r.text
    row = r.json()
    assert float(row["physical_qty"]) == 50, "بار همان‌جاست"
    assert float(row["sellable_qty"]) == 0
    assert row["status"] == "blocked"
    assert row["hold_reason"] == "شکِ کیفیت"

    #: و از فهرستِ قابلِ فروش بیرون است.
    assert client.get("/api/stock-batches/available",
                      params={"item_id": it, "warehouse_id": wh}).json() == []


def test_recall_is_not_the_same_as_block(client, db):
    """یکی‌کردنشان یعنی گزارشِ «کدام بارها فراخوان شده‌اند» غیرممکن شود."""
    wh = _main_wh(client)
    it = _item(client, "RC-RECALL", "فراخوانی")
    _buy(client, wh, it, 20)
    batch = _batch(db, it)

    r = client.post(f"/api/stock-batches/{batch.id}/hold", json={
        "hold_status": "recalled", "reason": "اعلامِ کارخانه",
    })
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "recalled"
    assert r.json()["hold_status"] == "recalled"


def test_hold_without_a_reason_is_refused(client, db):
    wh = _main_wh(client)
    it = _item(client, "RC-NOREASON", "بی‌دلیل")
    _buy(client, wh, it, 5)
    batch = _batch(db, it)
    r = client.post(f"/api/stock-batches/{batch.id}/hold", json={"hold_status": "blocked"})
    assert r.status_code == 400
    assert "دلیل" in r.json()["detail"]


def test_releasing_the_hold_brings_it_back(client, db):
    wh = _main_wh(client)
    it = _item(client, "RC-FREE", "آزادشده")
    _buy(client, wh, it, 9)
    batch = _batch(db, it)
    client.post(f"/api/stock-batches/{batch.id}/hold", json={"hold_status": "blocked", "reason": "موقت"})

    r = client.post(f"/api/stock-batches/{batch.id}/release")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "available"
    assert float(r.json()["sellable_qty"]) == 9
    assert r.json()["hold_reason"] == ""


def test_blocked_batch_cannot_be_issued_even_explicitly(client, db):
    """نقضِ FEFO حق است، ولی بارِ مسدود حقِ خروج ندارد."""
    wh = _main_wh(client)
    it = _item(client, "RC-ISSUE", "خروجی")
    _buy(client, wh, it, 30)
    assert client.patch(f"/api/items/{it}", json={"is_batch_tracked": True}).status_code == 200
    batch = _batch(db, it)
    client.post(f"/api/stock-batches/{batch.id}/hold", json={"hold_status": "blocked", "reason": "قرنطینه"})

    receiver = client.post("/api/contacts", json={"name": "گیرنده‌ی مسدود", "type": "customer"}).json()["id"]
    r = client.post("/api/warehouse-issues", json={
        "issue_date": TODAY, "issue_type": "sale", "warehouse_id": wh, "receiver_id": receiver,
        "lines": [{"item_id": it, "qty": 5, "batch_allocations": [{"batch_id": str(batch.id), "qty": 5}]}],
    })
    assert r.status_code == 400
    assert "مسدود" in r.json()["detail"]


# ── بستن ─────────────────────────────────────────────────────────────
def test_closing_a_batch_takes_it_out_of_circulation(client, db):
    wh = _main_wh(client)
    it = _item(client, "RC-CLOSE", "بسته")
    _buy(client, wh, it, 4)
    batch = _batch(db, it)

    r = client.post(f"/api/stock-batches/{batch.id}/close", json={"is_closed": True})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "closed"
    assert float(r.json()["sellable_qty"]) == 0
    #: و بازکردنش برمی‌گرداند — تصمیم است، نه مسیرِ یک‌طرفه.
    back = client.post(f"/api/stock-batches/{batch.id}/close", json={"is_closed": False})
    assert back.json()["status"] == "available"


# ── ردیابی ───────────────────────────────────────────────────────────
def test_trace_reports_where_the_batch_went_and_to_whom(client, db):
    """§۱۵ §۱۶ — بی هیچ جدولِ تازه‌ای، چون حرکت شناسه‌ی سندش را دارد."""
    wh = _main_wh(client)
    it = _item(client, "RC-TRACE", "ردیابی")
    _buy(client, wh, it, 100)
    assert client.patch(f"/api/items/{it}", json={"is_batch_tracked": True}).status_code == 200
    batch = _batch(db, it)

    receiver = client.post("/api/contacts", json={"name": "فروشگاهِ الف", "type": "customer"}).json()["id"]
    issue = client.post("/api/warehouse-issues", json={
        "issue_date": TODAY, "issue_type": "sale", "warehouse_id": wh, "receiver_id": receiver,
        "lines": [{"item_id": it, "qty": 30}],
    })
    assert issue.status_code == 201, issue.text
    client.post(f"/api/stock-batches/{batch.id}/adjust", json={
        "qty": 5, "reason": "defect", "adjustment_date": TODAY,
    })

    r = client.get(f"/api/stock-batches/{batch.id}/trace")
    assert r.status_code == 200, r.text
    t = r.json()
    assert float(t["received_qty"]) == 100
    assert float(t["sold_qty"]) == 30
    assert float(t["damaged_qty"]) == 5
    assert float(t["remaining_qty"]) == 65
    #: هر حرکت با نامِ خوانای سندش می‌آید، از همان واژگانِ کاردکس.
    assert any("خرید" in m["document"] for m in t["movements"])
    assert any("خروج انبار" in m["document"] for m in t["movements"])
    #: و مهم‌ترین بخشِ §۱۶: چه کسی گرفتش.
    assert [x["name"] for x in t["recipients"]] == ["فروشگاهِ الف"]


def test_trace_of_an_untouched_batch_is_all_zeros_not_an_error(client, db):
    wh = _main_wh(client)
    it = _item(client, "RC-EMPTY", "دست‌نخورده")
    b = client.post("/api/stock-batches", json={
        "item_id": it, "warehouse_id": wh, "batch_number": "T-0", "qty": 3, "received_date": TODAY,
    }).json()
    t = client.get(f"/api/stock-batches/{b['id']}/trace").json()
    assert float(t["sold_qty"]) == 0
    assert t["movements"] == []
    assert t["recipients"] == []


def test_trace_counts_a_sales_return_separately_from_a_receipt(client, db):
    """§۱۵ «برگشتی» را جدا از «رسید» خواسته — جمع‌کردنشان هر دو را بی‌معنا می‌کند."""
    wh = _main_wh(client)
    it = _item(client, "RC-RET", "برگشتی")
    _buy(client, wh, it, 40)
    batch = _batch(db, it)
    t = batches_svc.trace(db, batch)
    assert t["received_qty"] == 40
    assert t["returned_qty"] == 0
