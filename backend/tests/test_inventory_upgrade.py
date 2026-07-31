"""ارتقای انبار: نقطه‌ی سفارش/هشدارِ کسری، ارزشِ ریالیِ موجودی، و ویرایشِ انبار."""
from datetime import date
from decimal import Decimal

from app.models.inventory import StockLedger
from tests.factories import main_warehouse, make_item


def _add_stock(db, item, warehouse, qty, unit_cost=0):
    """یک حرکتِ ورودِ انبار مستقیم می‌زند (بدونِ عبور از فاکتور) تا موجودی بسازد."""
    db.add(
        StockLedger(
            item_id=item.id,
            warehouse_id=warehouse.id,
            qty=Decimal(qty),
            unit_cost=Decimal(unit_cost),
            entry_date=date.today(),
            source_type="opening",
        )
    )
    db.flush()


# ── نقطه‌ی سفارش روی کالا ───────────────────────────────────────────────
def test_create_item_with_reorder_point(db, user, client):
    res = client.post(
        "/api/items",
        json={"sku": "RP-001", "name": "کالای نقطه‌دار", "reorder_point": 15},
    )
    assert res.status_code == 201, res.text
    assert Decimal(res.json()["reorder_point"]) == Decimal(15)


def test_update_reorder_point(db, user, client):
    item = make_item(db)
    res = client.patch(f"/api/items/{item.id}", json={"reorder_point": 8})
    assert res.status_code == 200, res.text
    assert Decimal(res.json()["reorder_point"]) == Decimal(8)
    db.refresh(item)
    assert item.reorder_point == Decimal(8)


def test_negative_reorder_rejected(db, user, client):
    item = make_item(db)
    assert client.patch(f"/api/items/{item.id}", json={"reorder_point": -3}).status_code == 422
    assert client.post("/api/items", json={"sku": "RP-X", "name": "x", "reorder_point": -1}).status_code == 422


# ── هشدارِ کسری (/api/stock/low) ────────────────────────────────────────
def test_low_stock_flags_items_at_or_below_reorder(db, user, client):
    wh = main_warehouse(db)

    low = make_item(db, name="کم‌مانده")
    low.reorder_point = Decimal(10)
    db.flush()
    _add_stock(db, low, wh, 4)  # زیرِ نقطه‌ی سفارش

    plenty = make_item(db, name="پرمانده")
    plenty.reorder_point = Decimal(10)
    db.flush()
    _add_stock(db, plenty, wh, 25)  # بالای نقطه‌ی سفارش

    no_threshold = make_item(db, name="بدون‌آستانه")  # reorder_point=0 → هرگز هشدار
    _add_stock(db, no_threshold, wh, 0)

    rows = client.get("/api/stock/low").json()
    by_id = {r["item_id"]: r for r in rows}

    assert str(low.id) in by_id
    assert Decimal(by_id[str(low.id)]["qty_on_hand"]) == Decimal(4)
    assert Decimal(by_id[str(low.id)]["shortfall"]) == Decimal(6)  # ۱۰ − ۴
    assert str(plenty.id) not in by_id
    assert str(no_threshold.id) not in by_id


def test_low_stock_ignores_service_items(db, user, client):
    svc = make_item(db, name="خدمت", is_service=True)
    svc.reorder_point = Decimal(5)
    db.flush()
    rows = client.get("/api/stock/low").json()
    assert all(r["item_id"] != str(svc.id) for r in rows)


# ── ارزشِ ریالیِ موجودی روی /api/stock ─────────────────────────────────
def test_stock_endpoint_returns_unit_cost_and_value(db, user, client):
    wh = main_warehouse(db)
    item = make_item(db, name="ارزش‌دار", average_cost=1_000_000)
    _add_stock(db, item, wh, 3, unit_cost=1_000_000)

    row = next(r for r in client.get("/api/stock").json() if r["item_id"] == str(item.id))
    assert Decimal(row["unit_cost"]) == Decimal(1_000_000)
    assert Decimal(row["stock_value"]) == Decimal(3_000_000)  # ۳ × ۱٬۰۰۰٬۰۰۰


# ── ویرایشِ انبار (PATCH) ───────────────────────────────────────────────
def test_warehouse_rename_and_deactivate(db, user, client):
    wh = main_warehouse(db)
    res = client.patch(f"/api/warehouses/{wh.id}", json={"name": "انبارِ مرکزیِ نو", "is_active": False})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["name"] == "انبارِ مرکزیِ نو"
    assert body["is_active"] is False
    assert body["code"] == wh.code  # کد دست‌نخورده


def test_warehouse_blank_name_rejected(db, user, client):
    wh = main_warehouse(db)
    assert client.patch(f"/api/warehouses/{wh.id}", json={"name": "   "}).status_code == 422
