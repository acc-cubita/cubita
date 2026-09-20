"""مرجوعیِ بارمحور، جایگزینی و برگه‌ی جمع‌آوری (فاز ۴، §۱۲ §۱۳ §۱۴).

سه چیزی که تا امروز ممکن نبود: برگشت نمی‌دانست از کدام بار آمده، خرابِ برگشتی
مستقیم قابلِ فروش می‌شد، و عوض‌کردنِ بار هیچ ردی نمی‌گذاشت.
"""
import uuid
from datetime import date
from decimal import Decimal

from app.models.advanced_inventory import StockBatch
from app.models.batch_substitutions import BatchSubstitution
from app.models.inventory import StockLedger
from app.services import batches as batches_svc
from app.services import reservations as reservations_svc

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


def _receiver(client, name):
    return client.post("/api/contacts", json={"name": name, "type": "customer"}).json()["id"]


def _issue(client, wh, item_id, qty, receiver, **extra):
    r = client.post("/api/warehouse-issues", json={
        "issue_date": TODAY, "issue_type": "sale", "warehouse_id": wh, "receiver_id": receiver,
        "lines": [{"item_id": item_id, "qty": qty, **extra}],
    })
    assert r.status_code == 201, r.text
    return r.json()


def _batches(db, item_id):
    return db.query(StockBatch).filter(StockBatch.item_id == item_id).order_by(StockBatch.created_at).all()


# ── §۱۲ برگه‌ی جمع‌آوری ──────────────────────────────────────────────
def test_picking_sheet_shows_batch_expiry_and_location(client, db):
    wh = _main_wh(client)
    loc = client.post("/api/warehouse-locations", json={
        "warehouse_id": wh, "code": "A-02-04", "name": "راهروی الف",
    }).json()
    it = _item(client, "BR-PICK", "شیر")
    _buy(client, wh, it, 40)
    assert client.patch(f"/api/items/{it}", json={"is_batch_tracked": True}).status_code == 200

    batch = _batches(db, it)[0]
    batch.location_id = uuid.UUID(loc["id"])
    batch.expiry_date = date.today()
    db.flush()

    issue = _issue(client, wh, it, 10, _receiver(client, "گیرنده‌ی جمع‌آوری"))
    sheet = client.get(f"/api/warehouse-issues/{issue['id']}/picking").json()
    assert len(sheet) == 1
    assert sheet[0]["batch_number"] == batch.batch_number
    assert sheet[0]["location"] == "A-02-04"
    assert float(sheet[0]["qty"]) == 10
    assert sheet[0]["expiry_date"] == str(date.today())


def test_picking_sheet_of_an_untracked_item_has_no_batch(client, db):
    """§۲۸ — برگه همان‌طور چاپ می‌شود، فقط بی ستونِ بار."""
    wh = _main_wh(client)
    it = _item(client, "BR-PLAIN", "ساده")
    _buy(client, wh, it, 20)
    issue = _issue(client, wh, it, 5, _receiver(client, "گیرنده‌ی ساده"))
    sheet = client.get(f"/api/warehouse-issues/{issue['id']}/picking").json()
    assert len(sheet) == 1
    assert sheet[0]["batch_id"] is None
    assert sheet[0]["batch_number"] == ""


# ── §۱۴ مرجوعیِ بارمحور ──────────────────────────────────────────────
def test_a_sellable_return_goes_back_to_the_same_batch(client, db):
    wh = _main_wh(client)
    it = _item(client, "BR-OK", "سالم")
    _buy(client, wh, it, 50)
    assert client.patch(f"/api/items/{it}", json={"is_batch_tracked": True}).status_code == 200
    batch = _batches(db, it)[0]
    deliverer = _receiver(client, "تحویل‌دهنده‌ی سالم")
    issue = _issue(client, wh, it, 20, deliverer)
    assert batches_svc.on_hand(db, [batch.id])[batch.id] == 30

    line_id = issue["lines"][0]["id"]
    r = client.post("/api/warehouse-issue-returns", json={
        "return_date": TODAY, "return_type": "sale", "warehouse_id": wh,
        "deliverer_id": deliverer,
        "lines": [{"warehouse_issue_line_id": line_id, "qty": 5, "return_condition": "sellable"}],
    })
    assert r.status_code == 201, r.text

    db.expire_all()
    assert batches_svc.on_hand(db, [batch.id])[batch.id] == 35, "باید به همان بار برگردد"
    #: و قابلِ فروش هم هست — هیچ ادعایی رویش نیست.
    assert reservations_svc.reserved_by_batch(db, [batch.id]).get(batch.id, Decimal(0)) == 0


def test_a_damaged_return_comes_back_but_is_not_sellable(client, db):
    """§۱۴ — «اگر خراب بود وارد موجودی قابل فروش نشود».

    فیزیکی برمی‌گردد (کالا واقعاً در انبار است) ولی از `available` بیرون است.
    """
    wh = _main_wh(client)
    it = _item(client, "BR-BAD", "خراب")
    _buy(client, wh, it, 50)
    assert client.patch(f"/api/items/{it}", json={"is_batch_tracked": True}).status_code == 200
    batch = _batches(db, it)[0]
    deliverer = _receiver(client, "تحویل‌دهنده‌ی خراب")
    issue = _issue(client, wh, it, 20, deliverer)

    r = client.post("/api/warehouse-issue-returns", json={
        "return_date": TODAY, "return_type": "sale", "warehouse_id": wh,
        "deliverer_id": deliverer,
        "lines": [{"warehouse_issue_line_id": issue["lines"][0]["id"], "qty": 8, "return_condition": "damaged"}],
    })
    assert r.status_code == 201, r.text

    db.expire_all()
    row = client.get("/api/stock-batches", params={"item_id": it}).json()[0]
    assert float(row["physical_qty"]) == 38, "فیزیکی برمی‌گردد"
    assert float(row["reserved_qty"]) == 8, "ولی مسدود می‌شود"
    assert float(row["available_qty"]) == 30, "قابلِ فروش همان ۳۰ می‌ماند"


def test_an_invalid_return_condition_is_refused(client, db):
    wh = _main_wh(client)
    it = _item(client, "BR-BADCOND", "نامعتبر")
    _buy(client, wh, it, 10)
    deliverer = _receiver(client, "تحویل‌دهنده‌ی نامعتبر")
    issue = _issue(client, wh, it, 4, deliverer)
    r = client.post("/api/warehouse-issue-returns", json={
        "return_date": TODAY, "return_type": "sale", "warehouse_id": wh,
        "deliverer_id": deliverer,
        "lines": [{"warehouse_issue_line_id": issue["lines"][0]["id"], "qty": 1, "return_condition": "nope"}],
    })
    assert r.status_code == 422


def test_return_of_an_untracked_item_is_unchanged(client, db):
    """**پیش‌فرض = رفتارِ دیروز** — نگهبانِ این گام."""
    wh = _main_wh(client)
    it = _item(client, "BR-SAME", "بی‌ردیابی")
    _buy(client, wh, it, 30)
    deliverer = _receiver(client, "تحویل‌دهنده‌ی بی‌ردیابی")
    issue = _issue(client, wh, it, 10, deliverer)
    r = client.post("/api/warehouse-issue-returns", json={
        "return_date": TODAY, "return_type": "sale", "warehouse_id": wh,
        "deliverer_id": deliverer,
        "lines": [{"warehouse_issue_line_id": issue["lines"][0]["id"], "qty": 4}],
    })
    assert r.status_code == 201, r.text

    db.expire_all()
    back = db.query(StockLedger).filter(
        StockLedger.item_id == it, StockLedger.source_type == "warehouse_issue_return"
    ).all()
    assert len(back) == 1
    assert back[0].batch_id is None


# ── §۱۳ جایگزینیِ بار ────────────────────────────────────────────────
def test_substitution_moves_stock_between_batches_with_an_audit_row(client, db):
    wh = _main_wh(client)
    it = _item(client, "BR-SUB", "جایگزینی")
    _buy(client, wh, it, 20)
    _buy(client, wh, it, 20)
    assert client.patch(f"/api/items/{it}", json={"is_batch_tracked": True}).status_code == 200
    first, second = _batches(db, it)
    issue = _issue(client, wh, it, 10, _receiver(client, "گیرنده‌ی جایگزین"),
                   batch_allocations=[{"batch_id": str(first.id), "qty": 10}])
    assert batches_svc.on_hand(db, [first.id])[first.id] == 10

    from app.services.inventory import get_total_stock_qty

    before = get_total_stock_qty(db, it)
    r = client.post("/api/stock-batches/substitute", json={
        "source_line_id": issue["lines"][0]["id"],
        "original_batch_id": str(first.id),
        "new_batch_id": str(second.id),
        "qty": 4,
        "reason": "بارِ اول ته انبار پیدا نشد",
    })
    assert r.status_code == 201, r.text

    db.expire_all()
    assert batches_svc.on_hand(db, [first.id])[first.id] == 14, "۴ تا به بارِ اول برگشت"
    assert batches_svc.on_hand(db, [second.id])[second.id] == 16, "و از بارِ دوم رفت"
    assert get_total_stock_qty(db, it) == before, "موجودیِ کالا نباید تکان بخورد"

    sub = db.query(BatchSubstitution).one()
    assert sub.original_batch_id == first.id and sub.new_batch_id == second.id
    assert Decimal(sub.qty) == 4
    assert "ته انبار" in sub.reason


def test_substitution_without_a_reason_is_refused(client, db):
    """§۱۳ — بی دلیل، گزارشی که این جدول برایش ساخته شد بی‌معنا می‌شود."""
    wh = _main_wh(client)
    it = _item(client, "BR-NOREASON", "بی‌دلیل")
    _buy(client, wh, it, 10)
    _buy(client, wh, it, 10)
    assert client.patch(f"/api/items/{it}", json={"is_batch_tracked": True}).status_code == 200
    first, second = _batches(db, it)
    issue = _issue(client, wh, it, 3, _receiver(client, "گیرنده‌ی بی‌دلیل"),
                   batch_allocations=[{"batch_id": str(first.id), "qty": 3}])
    r = client.post("/api/stock-batches/substitute", json={
        "source_line_id": issue["lines"][0]["id"],
        "original_batch_id": str(first.id), "new_batch_id": str(second.id),
        "qty": 1, "reason": "   ",
    })
    assert r.status_code == 422


def test_substitution_refuses_a_batch_of_another_item(client, db):
    wh = _main_wh(client)
    a = _item(client, "BR-A", "الف")
    b = _item(client, "BR-B", "ب")
    _buy(client, wh, a, 10)
    _buy(client, wh, b, 10)
    assert client.patch(f"/api/items/{a}", json={"is_batch_tracked": True}).status_code == 200
    batch_a = _batches(db, a)[0]
    batch_b = _batches(db, b)[0]
    issue = _issue(client, wh, a, 3, _receiver(client, "گیرنده‌ی ناهمگون"),
                   batch_allocations=[{"batch_id": str(batch_a.id), "qty": 3}])
    r = client.post("/api/stock-batches/substitute", json={
        "source_line_id": issue["lines"][0]["id"],
        "original_batch_id": str(batch_a.id), "new_batch_id": str(batch_b.id),
        "qty": 1, "reason": "اشتباهی",
    })
    assert r.status_code == 400
    assert "کالای دیگری" in r.json()["detail"]
