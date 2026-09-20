"""ردیابیِ بارِ ورودی: پرچمِ کالا، FEFO، تفکیکِ بار در خروج، و انتقال (۰۱۷۲).

گامِ قبل مانده‌ی بار را راست کرد؛ این‌جا خروج یاد می‌گیرد از **کدام** بار کم کند.
"""
from datetime import date, timedelta
from decimal import Decimal

from app.models.advanced_inventory import StockBatch
from app.models.inventory import Item, StockLedger
from app.services import batches as batches_svc

TODAY = str(date.today())


def _main_wh(client):
    return next(w["id"] for w in client.get("/api/warehouses").json() if w["code"] == "MAIN")


def _item(client, sku, name, **extra):
    return client.post("/api/items", json={"sku": sku, "name": name, **extra}).json()["id"]


def _buy(client, wh, item_id, qty, cost=1000, when=None):
    r = client.post("/api/purchase-invoices", json={
        "invoice_date": when or TODAY, "warehouse_id": wh,
        "lines": [{"item_id": item_id, "qty": qty, "unit_cost": cost}],
    })
    assert r.status_code == 201, r.text
    return r.json()


def _batches(db, item_id):
    return db.query(StockBatch).filter(StockBatch.item_id == item_id).all()


def _set_expiry(client, batch_id, when):
    b = client.get("/api/stock-batches").json()
    row = next(x for x in b if x["id"] == batch_id)
    r = client.patch(f"/api/stock-batches/{batch_id}", json={
        "item_id": row["item_id"], "warehouse_id": row["warehouse_id"],
        "batch_number": row["batch_number"], "expiry_date": when,
        "received_date": row["received_date"],
    })
    assert r.status_code == 200, r.text


# ── گاردِ روشن‌کردنِ پرچم ─────────────────────────────────────────────
def test_tracking_cannot_be_enabled_while_untagged_stock_exists(client, db):
    """موجودیِ بی‌برچسب یعنی جمعِ بارها هرگز با موجودیِ کالا نمی‌خواند."""
    wh = _main_wh(client)
    it = _item(client, "BA-GUARD", "گاردی")
    client.post("/api/stock-adjustments", json={
        "item_id": it, "warehouse_id": wh, "qty_diff": 10,
        "reason": "موجودیِ اولیه", "adjustment_date": TODAY,
    })
    r = client.patch(f"/api/items/{it}", json={"is_batch_tracked": True})
    assert r.status_code == 409
    #: پیام باید **راهِ عبور** را بگوید، نه فقط «نمی‌شود».
    assert "انتسابِ موجودی به بار" in r.json()["detail"]


def test_assigning_stock_to_a_batch_opens_the_gate_without_moving_stock(client, db):
    """سندِ جمعِ صفر: موجودی تکان نمی‌خورد، میانگین هم نه، ولی هویت پیدا می‌شود."""
    from app.services.inventory import get_total_stock_qty

    wh = _main_wh(client)
    it = _item(client, "BA-ALIGN", "هم‌ترازی")
    client.post("/api/stock-adjustments", json={
        "item_id": it, "warehouse_id": wh, "qty_diff": 25,
        "reason": "موجودیِ اولیه", "adjustment_date": TODAY,
    })
    before_qty = get_total_stock_qty(db, it)
    before_cost = Decimal(db.query(Item).filter(Item.id == it).one().average_cost)

    r = client.post(f"/api/items/{it}/assign-stock-to-batch", json={
        "warehouse_id": wh, "batch_number": "OPEN-1", "assigned_date": TODAY,
    })
    assert r.status_code == 201, r.text
    assert float(r.json()["qty"]) == 25

    db.expire_all()
    assert get_total_stock_qty(db, it) == before_qty, "موجودیِ کالا نباید تکان بخورد"
    assert Decimal(db.query(Item).filter(Item.id == it).one().average_cost) == before_cost
    assert batches_svc.untagged_on_hand(db, it) == 0

    #: و حالا گارد باز می‌شود.
    assert client.patch(f"/api/items/{it}", json={"is_batch_tracked": True}).status_code == 200


# ── FEFO ─────────────────────────────────────────────────────────────
def test_fefo_takes_the_nearest_expiry_first_and_undated_last(client, db):
    wh = _main_wh(client)
    it = _item(client, "BA-FEFO", "شیر", is_batch_tracked=False)
    far = _buy(client, wh, it, 10)
    soon = _buy(client, wh, it, 10)
    undated = _buy(client, wh, it, 10)

    by_src = {b.source_id: b for b in _batches(db, it)}
    _set_expiry(client, str(by_src[__import__("uuid").UUID(far["id"])].id),
                str(date.today() + timedelta(days=90)))
    _set_expiry(client, str(by_src[__import__("uuid").UUID(soon["id"])].id),
                str(date.today() + timedelta(days=5)))

    db.expire_all()
    item = db.query(Item).filter(Item.id == it).one()
    plan = batches_svc.suggest_fefo(db, item, wh, Decimal(25), date.today())
    numbers = [b.batch_number for b, _ in plan]
    taken = [q for _, q in plan]

    soon_no = by_src[__import__("uuid").UUID(soon["id"])].batch_number
    far_no = by_src[__import__("uuid").UUID(far["id"])].batch_number
    undated_no = by_src[__import__("uuid").UUID(undated["id"])].batch_number
    assert numbers == [soon_no, far_no, undated_no], "نزدیک‌ترین انقضا اول، بی‌تاریخ آخر"
    assert taken == [Decimal(10), Decimal(10), Decimal(5)]


# ── تفکیکِ بار در خروج ───────────────────────────────────────────────
def test_issue_splits_across_batches_and_tags_each_move(client, db):
    """خروجِ ۱۵تایی از دو بارِ ۱۰تایی = دو حرکتِ برچسب‌خورده، نه یک حرکتِ جمعی."""
    wh = _main_wh(client)
    it = _item(client, "BA-SPLIT", "تفکیکی")
    _buy(client, wh, it, 10)
    _buy(client, wh, it, 10)
    assert client.patch(f"/api/items/{it}", json={"is_batch_tracked": True}).status_code == 200

    r = client.post("/api/sales-invoices", json={
        "invoice_date": TODAY, "warehouse_id": wh,
        "lines": [{"item_id": it, "qty": 15, "unit_price": 3000}],
    })
    assert r.status_code == 201, r.text

    out = db.query(StockLedger).filter(
        StockLedger.item_id == it, StockLedger.qty < 0
    ).all()
    assert len(out) == 2, "باید به‌ازای هر بار یک حرکت باشد"
    assert all(m.batch_id is not None for m in out)
    assert all(m.source_line_id is not None for m in out)
    assert sorted(-Decimal(m.qty) for m in out) == [Decimal(5), Decimal(10)]

    #: و جمعِ بارها هنوز با موجودیِ کالا می‌خواند.
    from app.services.inventory import get_total_stock_qty

    ids = [b.id for b in _batches(db, it)]
    assert sum(batches_svc.on_hand(db, ids).values()) == get_total_stock_qty(db, it)


def test_untracked_item_still_writes_one_untagged_move(client, db):
    """**پیش‌فرض = رفتارِ دیروز** — نگهبانِ همیشگی."""
    wh = _main_wh(client)
    it = _item(client, "BA-PLAIN", "ساده")
    _buy(client, wh, it, 10)
    _buy(client, wh, it, 10)

    client.post("/api/sales-invoices", json={
        "invoice_date": TODAY, "warehouse_id": wh,
        "lines": [{"item_id": it, "qty": 15, "unit_price": 3000}],
    })
    out = db.query(StockLedger).filter(StockLedger.item_id == it, StockLedger.qty < 0).all()
    assert len(out) == 1, "کالای بی‌ردیابی باید یک حرکتِ جمعی بگیرد، مثلِ همیشه"
    assert out[0].batch_id is None


def test_blocked_batch_is_skipped_by_fefo(client, db):
    wh = _main_wh(client)
    it = _item(client, "BA-HOLD", "منعقد")
    _buy(client, wh, it, 10)
    _buy(client, wh, it, 10)
    first = _batches(db, it)[0]
    first.hold_status = "blocked"
    db.flush()

    db.expire_all()
    item = db.query(Item).filter(Item.id == it).one()
    plan = batches_svc.suggest_fefo(db, item, wh, Decimal(20), date.today())
    assert sum((q for _, q in plan), Decimal(0)) == 10, "بارِ مسدود نباید شمرده شود"
    assert all(b.id != first.id for b, _ in plan)


def test_tracked_item_refuses_when_sellable_is_short(client, db):
    wh = _main_wh(client)
    it = _item(client, "BA-SHORT", "کم")
    _buy(client, wh, it, 10)
    assert client.patch(f"/api/items/{it}", json={"is_batch_tracked": True}).status_code == 200
    batch = _batches(db, it)[0]
    batch.qc_status = "pending"
    db.flush()

    r = client.post("/api/sales-invoices", json={
        "invoice_date": TODAY, "warehouse_id": wh,
        "lines": [{"item_id": it, "qty": 5, "unit_price": 3000}],
    })
    assert r.status_code == 400
    assert "کنترلِ کیفیت" in r.json()["detail"]


# ── §۲۹ عمرِ مفید ────────────────────────────────────────────────────
def test_short_shelf_life_zeroes_sellable_but_not_physical(client, db):
    """موجودیِ فیزیکی سرِ جایش می‌ماند؛ فقط «قابلِ فروش» صفر می‌شود."""
    wh = _main_wh(client)
    it = _item(client, "BA-SHELF", "کم‌عمر", minimum_sellable_shelf_life_days=7)
    _buy(client, wh, it, 10)
    batch = _batches(db, it)[0]
    _set_expiry(client, str(batch.id), str(date.today() + timedelta(days=5)))

    db.expire_all()
    row = client.get("/api/stock-batches", params={"item_id": it}).json()[0]
    assert float(row["physical_qty"]) == 10, "فیزیکی نباید تکان بخورد"
    assert float(row["sellable_qty"]) == 0
    assert row["status"] == "near_expiry"
    assert row["days_to_expiry"] == 5

    #: و در فهرستِ «قابلِ فروش» اصلاً نمی‌آید.
    assert client.get("/api/stock-batches/available",
                      params={"item_id": it, "warehouse_id": wh}).json() == []


# ── انتقال بینِ انبار ────────────────────────────────────────────────
def test_transfer_creates_a_mirror_batch_in_the_destination(client, db):
    """بی بارِ آینه، کالا آن‌طرفِ مرزِ انبار بی‌بچ ظاهر می‌شد."""
    wh = _main_wh(client)
    other = client.post("/api/warehouses", json={"code": "W2", "name": "انبار دوم"}).json()["id"]
    it = _item(client, "BA-TRF", "انتقالی")
    _buy(client, wh, it, 20)
    assert client.patch(f"/api/items/{it}", json={"is_batch_tracked": True}).status_code == 200
    source = _batches(db, it)[0]

    r = client.post("/api/stock-transfers", json={
        "transfer_date": TODAY, "from_warehouse_id": wh, "to_warehouse_id": other,
        "lines": [{"item_id": it, "qty": 8}],
    })
    assert r.status_code == 201, r.text

    db.expire_all()
    mirror = db.query(StockBatch).filter(StockBatch.parent_batch_id == source.id).one()
    assert mirror.warehouse_id == __import__("uuid").UUID(other)
    assert mirror.batch_number == source.batch_number, "شناسنامه باید کپی شود"
    assert batches_svc.on_hand(db, [source.id])[source.id] == 12
    assert batches_svc.on_hand(db, [mirror.id])[mirror.id] == 8


# ── موقعیتِ انبار ────────────────────────────────────────────────────
def test_warehouse_location_crud_and_soft_delete(client, db):
    wh = _main_wh(client)
    r = client.post("/api/warehouse-locations", json={
        "warehouse_id": wh, "code": "A-02-04", "name": "راهروی الف",
    })
    assert r.status_code == 201, r.text
    loc = r.json()
    assert loc["batch_count"] == 0

    #: کد در همان انبار یکتاست.
    assert client.post("/api/warehouse-locations", json={
        "warehouse_id": wh, "code": "A-02-04",
    }).status_code == 409

    it = _item(client, "BA-LOC", "مکانی")
    b = client.post("/api/stock-batches", json={
        "item_id": it, "warehouse_id": wh, "batch_number": "L-1",
        "qty": 3, "received_date": TODAY, "location_id": loc["id"],
    })
    assert b.status_code == 201, b.text
    assert b.json()["location_id"] == loc["id"]

    listed = client.get("/api/warehouse-locations", params={"warehouse_id": wh}).json()
    assert listed[0]["batch_count"] == 1

    #: موقعیتِ دارای بار حذف نمی‌شود، غیرفعال می‌شود — وگرنه بار محلش را گم می‌کند.
    assert client.delete(f"/api/warehouse-locations/{loc['id']}").status_code == 204
    assert client.get("/api/warehouse-locations", params={"warehouse_id": wh}).json()[0]["is_active"] is False


# ── نقضِ FEFO (§۱۱) ──────────────────────────────────────────────────
def test_user_can_override_fefo_on_a_direct_issue(client, db):
    """انباردار جلوی قفسه ایستاده، نه ما — پس باید بتواند بارِ دیگری بردارد."""
    wh = _main_wh(client)
    it = _item(client, "BA-OVR", "نقض")
    _buy(client, wh, it, 10)
    _buy(client, wh, it, 10)
    assert client.patch(f"/api/items/{it}", json={"is_batch_tracked": True}).status_code == 200

    first, second = _batches(db, it)
    _set_expiry(client, str(first.id), str(date.today() + timedelta(days=5)))
    _set_expiry(client, str(second.id), str(date.today() + timedelta(days=200)))

    receiver = client.post("/api/contacts", json={"name": "گیرنده", "type": "customer"}).json()["id"]
    #: FEFO بارِ اول را می‌داد؛ ما صریح بارِ دوم را می‌خواهیم.
    r = client.post("/api/warehouse-issues", json={
        "issue_date": TODAY, "issue_type": "sale", "warehouse_id": wh, "receiver_id": receiver,
        "lines": [{
            "item_id": it, "qty": 6,
            "batch_allocations": [{"batch_id": str(second.id), "qty": 6}],
        }],
    })
    assert r.status_code == 201, r.text

    db.expire_all()
    assert batches_svc.on_hand(db, [first.id])[first.id] == 10, "بارِ نزدیک‌تر نباید لمس شود"
    assert batches_svc.on_hand(db, [second.id])[second.id] == 4


def test_override_must_add_up_to_the_line_quantity(client, db):
    wh = _main_wh(client)
    it = _item(client, "BA-SUMCHK", "جمع")
    _buy(client, wh, it, 10)
    assert client.patch(f"/api/items/{it}", json={"is_batch_tracked": True}).status_code == 200
    batch = _batches(db, it)[0]
    receiver = client.post("/api/contacts", json={"name": "گیرنده۲", "type": "customer"}).json()["id"]

    r = client.post("/api/warehouse-issues", json={
        "issue_date": TODAY, "issue_type": "sale", "warehouse_id": wh, "receiver_id": receiver,
        "lines": [{
            "item_id": it, "qty": 6,
            "batch_allocations": [{"batch_id": str(batch.id), "qty": 4}],
        }],
    })
    assert r.status_code == 400
    assert "برابر نیست" in r.json()["detail"]


def test_override_cannot_exceed_the_batch(client, db):
    wh = _main_wh(client)
    it = _item(client, "BA-OVERDRAW", "زیاده")
    _buy(client, wh, it, 5)
    _buy(client, wh, it, 20)
    assert client.patch(f"/api/items/{it}", json={"is_batch_tracked": True}).status_code == 200
    small = _batches(db, it)[0]
    receiver = client.post("/api/contacts", json={"name": "گیرنده۳", "type": "customer"}).json()["id"]

    r = client.post("/api/warehouse-issues", json={
        "issue_date": TODAY, "issue_type": "sale", "warehouse_id": wh, "receiver_id": receiver,
        "lines": [{
            "item_id": it, "qty": 9,
            "batch_allocations": [{"batch_id": str(small.id), "qty": 9}],
        }],
    })
    assert r.status_code == 400
    assert "کافی نیست" in r.json()["detail"]
