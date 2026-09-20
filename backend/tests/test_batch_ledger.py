"""مانده‌ی بارِ ورودی از دفترِ انبار مشتق می‌شود (مهاجرتِ ۰۱۷۱).

پیش از این `stock_batches.qty` یک ستونِ شمارنده بود که **فروش و خروج اصلاً کمش
نمی‌کردند**؛ بارِ تمام‌فروخته هنوز مقدارِ اولش را نشان می‌داد. این تست‌ها می‌سنجند
که هر حرکتِ انبار برچسبِ بارش را بگیرد و عدد از دفتر دربیاید.
"""
from datetime import date
from decimal import Decimal

from app.models.advanced_inventory import StockBatch
from app.models.inventory import StockLedger
from app.services import batches as batches_svc

TODAY = str(date.today())


def _main_wh(client):
    return next(w["id"] for w in client.get("/api/warehouses").json() if w["code"] == "MAIN")


def _item(client, sku, name, **extra):
    return client.post("/api/items", json={"sku": sku, "name": name, **extra}).json()["id"]


def _moves(db, item_id):
    return db.query(StockLedger).filter(StockLedger.item_id == item_id).order_by(StockLedger.seq).all()


# ── برچسب‌خوردنِ ورودی ────────────────────────────────────────────────
def test_purchase_tags_each_inbound_move_with_its_batch(client, db):
    """هر ردیفِ خرید یک بار می‌سازد و حرکتِ همان ردیف باید به همان بار وصل شود."""
    wh = _main_wh(client)
    a = _item(client, "BL-A", "الف")
    b = _item(client, "BL-B", "ب")
    r = client.post("/api/purchase-invoices", json={
        "invoice_date": TODAY, "warehouse_id": wh,
        "lines": [
            {"item_id": a, "qty": 100, "unit_cost": 5000},
            {"item_id": b, "qty": 40, "unit_cost": 8000},
        ],
    })
    assert r.status_code == 201, r.text

    #: کلیدها رشته‌اند چون شناسه‌ها از API آمده‌اند، نه از ORM.
    batches = {str(x.item_id): x for x in db.query(StockBatch).all()}
    for item_id, qty in ((a, 100), (b, 40)):
        moves = _moves(db, item_id)
        assert len(moves) == 1
        assert moves[0].batch_id == batches[item_id].id, "حرکتِ ورودی باید برچسبِ بارِ خودش را بگیرد"
        #: ردیفِ سند هم باید معلوم باشد، وگرنه فاکتوری با دو ردیفِ یک کالا
        #: برگشت‌ناپذیر مبهم می‌شود.
        assert moves[0].source_line_id is not None
        assert batches_svc.on_hand(db, [batches[item_id].id])[batches[item_id].id] == qty


def test_purchase_with_two_lines_of_one_item_keeps_them_apart(client, db):
    """دو ردیفِ یک کالا در یک فاکتور = دو بارِ جدا، و هر حرکت به بارِ خودش.

    همان حالتی که مهاجرتِ ۰۱۷۱ عمداً از پرکردنِ خودکارش پرهیز می‌کند، چون در
    داده‌ی قدیمی قابلِ تفکیک نیست. در ثبتِ **تازه** باید دقیق باشد.
    """
    wh = _main_wh(client)
    it = _item(client, "BL-TWIN", "دوقلو")
    r = client.post("/api/purchase-invoices", json={
        "invoice_date": TODAY, "warehouse_id": wh,
        "lines": [
            {"item_id": it, "qty": 10, "unit_cost": 1000},
            {"item_id": it, "qty": 25, "unit_cost": 1000},
        ],
    })
    assert r.status_code == 201, r.text

    moves = _moves(db, it)
    assert len(moves) == 2
    assert moves[0].batch_id != moves[1].batch_id, "دو ردیف نباید به یک بار بخورند"
    assert moves[0].source_line_id != moves[1].source_line_id
    on_hand = batches_svc.on_hand(db, [m.batch_id for m in moves])
    assert sorted(on_hand.values()) == [Decimal(10), Decimal(25)]


def test_derived_qty_matches_item_stock(client, db):
    """قاعده‌ی تطابق: جمعِ مانده‌ی بارها = موجودیِ کالا."""
    from app.services.inventory import get_total_stock_qty

    wh = _main_wh(client)
    it = _item(client, "BL-SUM", "جمع")
    client.post("/api/purchase-invoices", json={
        "invoice_date": TODAY, "warehouse_id": wh,
        "lines": [{"item_id": it, "qty": 60, "unit_cost": 1000}],
    })
    ids = [b.id for b in db.query(StockBatch).filter(StockBatch.item_id == it).all()]
    assert sum(batches_svc.on_hand(db, ids).values()) == get_total_stock_qty(db, it)


# ── ابطال ────────────────────────────────────────────────────────────
def test_void_carries_the_batch_back(client, db):
    """ابطال باید برچسبِ بار را با خودش ببرد، وگرنه مانده بالاتر از واقع می‌ماند.

    این همان خطایی است که هیچ پیامی نمی‌داد: موجودیِ کالا درست برمی‌گشت و
    مانده‌ی بار همان‌جا می‌ماند.
    """
    wh = _main_wh(client)
    it = _item(client, "BL-VOID", "ابطالی")
    inv = client.post("/api/purchase-invoices", json={
        "invoice_date": TODAY, "warehouse_id": wh,
        "lines": [{"item_id": it, "qty": 70, "unit_cost": 2000}],
    }).json()
    batch = db.query(StockBatch).filter(StockBatch.item_id == it).one()
    assert batches_svc.on_hand(db, [batch.id])[batch.id] == 70

    r = client.post(f"/api/purchase-invoices/{inv['id']}/void", json={"reason": "اشتباهِ ثبت"})
    assert r.status_code == 200, r.text

    moves = _moves(db, it)
    assert len(moves) == 2
    assert moves[1].batch_id == batch.id, "حرکتِ قرینه باید همان برچسب را داشته باشد"
    assert batches_svc.on_hand(db, [batch.id])[batch.id] == 0


# ── تعدیل و کسری ─────────────────────────────────────────────────────
def test_batch_adjust_tags_its_move_and_derives_defect(client, db):
    wh = _main_wh(client)
    it = _item(client, "BL-ADJ", "تعدیلی")
    client.post("/api/purchase-invoices", json={
        "invoice_date": TODAY, "warehouse_id": wh,
        "lines": [{"item_id": it, "qty": 50, "unit_cost": 1000}],
    })
    batch = db.query(StockBatch).filter(StockBatch.item_id == it).one()

    r = client.post(f"/api/stock-batches/{batch.id}/adjust", json={
        "qty": 8, "reason": "defect", "adjustment_date": TODAY,
    })
    assert r.status_code == 200, r.text

    moves = _moves(db, it)
    assert moves[-1].source_type == "adjustment"
    assert moves[-1].batch_id == batch.id, "تعدیلِ بارمحور باید از مانده‌ی همان بار کم کند"
    assert batches_svc.on_hand(db, [batch.id])[batch.id] == 42
    #: کسری از سندِ تعدیل مشتق می‌شود، نه از `received_qty − qty` — چون حالا
    #: فروش هم مانده را کم می‌کند و فروش کسری نیست.
    assert batches_svc.defect_qty(db, [batch.id])[batch.id] == 8
    assert float(r.json()["qty"]) == 42
    assert float(r.json()["defect_qty"]) == 8


# ── منشأِ عدد ────────────────────────────────────────────────────────
def test_manual_batch_is_reported_as_legacy_not_zero(client, db):
    """بارِ دستی هیچ حرکتِ انباری نمی‌سازد؛ مشتق‌کردنش یعنی صفرِ دروغین.

    عددِ ستونِ قدیمی نشان داده می‌شود و `qty_source` صریح می‌گوید که نامطمئن
    است — «گزارش، نه گارد».
    """
    wh = _main_wh(client)
    it = _item(client, "BL-MAN", "دستی")
    r = client.post("/api/stock-batches", json={
        "item_id": it, "warehouse_id": wh, "batch_number": "M-1",
        "qty": 33, "received_date": TODAY,
    })
    assert r.status_code == 201, r.text
    assert r.json()["qty_source"] == "legacy"
    assert float(r.json()["qty"]) == 33
    assert float(r.json()["ledger_qty"]) == 0

    rec = client.get("/api/stock-batches/reconciliation").json()
    row = next(x for x in rec if x["batch_number"] == "M-1")
    assert row["reason"] == "manual"
    assert float(row["delta"]) == 33


def test_purchased_batch_is_reported_as_ledger(client, db):
    wh = _main_wh(client)
    it = _item(client, "BL-SRC", "خریدی")
    client.post("/api/purchase-invoices", json={
        "invoice_date": TODAY, "warehouse_id": wh,
        "lines": [{"item_id": it, "qty": 12, "unit_cost": 1000}],
    })
    row = client.get("/api/stock-batches", params={"item_id": it}).json()[0]
    assert row["qty_source"] == "ledger"
    assert float(row["qty"]) == 12
    #: بارِ سالم در گزارشِ مغایرت نمی‌آید.
    assert not [x for x in client.get("/api/stock-batches/reconciliation").json()
                if x["batch_id"] == row["id"]]


# ── نگهبانِ اصلی ─────────────────────────────────────────────────────
def test_item_without_batch_tracking_behaves_exactly_like_yesterday(client, db):
    """**پیش‌فرض = رفتارِ دیروز.**

    کالایی که ردیابیِ بار ندارد — یعنی همه‌ی کالاهای موجود — باید مثلِ همیشه
    بفروشد و حرکتِ خروجش بی‌برچسب بماند. اگر این تست بشکند، یعنی تغییرِ ما به
    مسیرِ کاربرانی نشت کرده که چیزی از بچ نخواسته‌اند.
    """
    wh = _main_wh(client)
    it = _item(client, "BL-PLAIN", "ساده")
    client.post("/api/purchase-invoices", json={
        "invoice_date": TODAY, "warehouse_id": wh,
        "lines": [{"item_id": it, "qty": 20, "unit_cost": 1000}],
    })
    r = client.post("/api/sales-invoices", json={
        "invoice_date": TODAY, "warehouse_id": wh,
        "lines": [{"item_id": it, "qty": 5, "unit_price": 3000}],
    })
    assert r.status_code == 201, r.text

    outbound = [m for m in _moves(db, it) if Decimal(m.qty) < 0]
    assert outbound, "فروش باید حرکتِ خروجی بسازد"
    assert all(m.batch_id is None for m in outbound), "خروجِ کالای بی‌ردیابی نباید برچسب بگیرد"


# ── گاردِ حذف ────────────────────────────────────────────────────────
def test_batch_with_ledger_history_cannot_be_deleted(client, db):
    wh = _main_wh(client)
    it = _item(client, "BL-DEL", "حذفی")
    client.post("/api/purchase-invoices", json={
        "invoice_date": TODAY, "warehouse_id": wh,
        "lines": [{"item_id": it, "qty": 5, "unit_cost": 1000}],
    })
    batch = db.query(StockBatch).filter(StockBatch.item_id == it).one()
    r = client.delete(f"/api/stock-batches/{batch.id}")
    assert r.status_code == 409
    assert "گردش" in r.json()["detail"]


def test_manual_batch_without_history_is_still_deletable(client, db):
    wh = _main_wh(client)
    it = _item(client, "BL-DEL2", "حذفیِ دستی")
    b = client.post("/api/stock-batches", json={
        "item_id": it, "warehouse_id": wh, "batch_number": "M-DEL", "qty": 1, "received_date": TODAY,
    }).json()
    assert client.delete(f"/api/stock-batches/{b['id']}").status_code == 204


# ── انتساب‌نشده‌ها ───────────────────────────────────────────────────
def test_untagged_on_hand_sees_stock_that_belongs_to_no_batch(client, db):
    """گاردِ آینده‌ی «ردیابیِ بار» روی همین عدد می‌نشیند."""
    wh = _main_wh(client)
    it = _item(client, "BL-UNTAG", "بی‌برچسب")
    client.post("/api/stock-adjustments", json={
        "item_id": it, "warehouse_id": wh, "qty_diff": 15,
        "reason": "موجودیِ اولیه", "adjustment_date": TODAY,
    })
    assert batches_svc.untagged_on_hand(db, it) == 15

    client.post("/api/purchase-invoices", json={
        "invoice_date": TODAY, "warehouse_id": wh,
        "lines": [{"item_id": it, "qty": 4, "unit_cost": 1000}],
    })
    #: خرید برچسب‌دار است، پس عددِ بی‌برچسب تکان نمی‌خورد.
    assert batches_svc.untagged_on_hand(db, it) == 15
