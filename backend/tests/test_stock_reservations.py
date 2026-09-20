"""رزروِ موجودی و جلوگیری از فروشِ بیش از موجودی (مهاجرتِ ۰۱۷۳).

پیش از این، موجودی فقط **لحظه‌ی ثبتِ خروج** سنجیده می‌شد؛ هیچ سندی نمی‌توانست
کالایی را برای خودش کنار بگذارد.
"""
from datetime import date
from decimal import Decimal

from app.models.inventory import Item
from app.models.stock_reservations import StockReservation
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


def _reserve(client, wh, item_id, qty, kind="hold"):
    return client.post("/api/stock-reservations", json={
        "item_id": item_id, "warehouse_id": wh, "qty": qty, "entry_date": TODAY, "kind": kind,
    })


# ── حسابِ ساده ───────────────────────────────────────────────────────
def test_reserving_does_not_touch_physical_stock(client, db):
    """§۸ — تا خروجِ قطعی، فقط `reserved` بالا می‌رود."""
    from app.services.inventory import get_total_stock_qty

    wh = _main_wh(client)
    it = _item(client, "RS-PHYS", "فیزیکی")
    _buy(client, wh, it, 800)

    r = _reserve(client, wh, it, 200)
    assert r.status_code == 201, r.text

    db.expire_all()
    assert get_total_stock_qty(db, it) == 800, "موجودیِ فیزیکی نباید تکان بخورد"
    assert reservations_svc.reserved_for_item(db, it, wh) == 200
    assert reservations_svc.available_for(db, it, wh) == 600


def test_reserving_more_than_available_is_refused(client, db):
    wh = _main_wh(client)
    it = _item(client, "RS-OVER", "زیاده")
    _buy(client, wh, it, 100)

    assert _reserve(client, wh, it, 80).status_code == 201
    r = _reserve(client, wh, it, 30)
    assert r.status_code == 400
    assert "کافی نیست" in r.json()["detail"]
    #: ادعای دوم نباید هیچ ردیفی گذاشته باشد.
    db.expire_all()
    assert reservations_svc.reserved_for_item(db, it, wh) == 80


# ── لغو، کامل و جزئی ─────────────────────────────────────────────────
def test_releasing_frees_exactly_what_was_asked(client, db):
    """§۱۰ — لغوِ جزئی فقط یک ردیفِ دیگر است، نه بازنویسیِ ردیفِ اول."""
    wh = _main_wh(client)
    it = _item(client, "RS-REL", "لغوی")
    _buy(client, wh, it, 500)
    handle = _reserve(client, wh, it, 150).json()["source_id"]

    r = client.delete(f"/api/stock-reservations/{handle}", params={"qty": 50})
    assert r.status_code == 200, r.text
    assert float(r.json()["released"]) == 50

    db.expire_all()
    assert reservations_svc.reserved_for_item(db, it, wh) == 100
    #: ردیفِ اول دست‌نخورده مانده و ردیفِ منفی کنارش نشسته — تاریخچه کامل است.
    rows = db.query(StockReservation).filter(StockReservation.item_id == it).all()
    assert sorted(Decimal(x.qty) for x in rows) == [Decimal(-50), Decimal(150)]

    #: و لغوِ باقی‌مانده بدونِ مقدار، همه را آزاد می‌کند.
    assert float(client.delete(f"/api/stock-reservations/{handle}").json()["released"]) == 100
    db.expire_all()
    assert reservations_svc.reserved_for_item(db, it, wh) == 0


def test_releasing_an_unknown_handle_is_a_404(client):
    import uuid

    assert client.delete(f"/api/stock-reservations/{uuid.uuid4()}").status_code == 404


# ── تکرارناپذیری ────────────────────────────────────────────────────
def test_the_same_claim_twice_writes_one_row(client, db):
    """§۳۵.۶ — تلاشِ دوباره‌ی شبکه نباید ادعای دوم بسازد."""
    wh = _main_wh(client)
    it = _item(client, "RS-IDEM", "تکراری")
    _buy(client, wh, it, 60)
    item = db.query(Item).filter(Item.id == it).one()
    from app.models.user import User

    user = db.query(User).first()
    import uuid

    handle = uuid.uuid4()
    for _ in range(2):
        reservations_svc.reserve(
            db, item=item, warehouse_id=wh, qty=Decimal(10), on=date.today(),
            source_type="marketplace_order", source_id=handle, user=user,
        )
    db.flush()
    rows = db.query(StockReservation).filter(StockReservation.source_id == handle).all()
    assert len(rows) == 1, "همان (سند، رویداد) دو بار → یک ردیف"
    assert reservations_svc.reserved_for_item(db, it, wh) == 10


# ── اثر روی خروج ─────────────────────────────────────────────────────
def test_another_documents_reservation_blocks_the_issue(client, db):
    wh = _main_wh(client)
    it = _item(client, "RS-BLOCK", "مسدودشده")
    _buy(client, wh, it, 100)
    _reserve(client, wh, it, 90)

    r = client.post("/api/sales-invoices", json={
        "invoice_date": TODAY, "warehouse_id": wh,
        "lines": [{"item_id": it, "qty": 20, "unit_price": 3000}],
    })
    assert r.status_code == 400
    assert "رزروِ سندهای دیگر" in r.json()["detail"]

    #: و به‌اندازه‌ی آزاد، فروش همچنان ممکن است.
    ok = client.post("/api/sales-invoices", json={
        "invoice_date": TODAY, "warehouse_id": wh,
        "lines": [{"item_id": it, "qty": 10, "unit_price": 3000}],
    })
    assert ok.status_code == 201, ok.text


def test_without_any_reservation_nothing_changes(client, db):
    """**پیش‌فرض = رفتارِ دیروز** — نگهبانِ این گام."""
    wh = _main_wh(client)
    it = _item(client, "RS-PLAIN", "ساده")
    _buy(client, wh, it, 40)
    db.expire_all()
    from app.services.inventory import get_stock_qty

    assert reservations_svc.available_for(db, it, wh) == get_stock_qty(db, it, wh)
    r = client.post("/api/sales-invoices", json={
        "invoice_date": TODAY, "warehouse_id": wh,
        "lines": [{"item_id": it, "qty": 40, "unit_price": 3000}],
    })
    assert r.status_code == 201, r.text


# ── اثر روی بار ──────────────────────────────────────────────────────
def test_batch_numbers_subtract_the_reservation(client, db):
    """رزروِ بار‌دار از `available`ِ همان بار کم می‌شود، نه از `physical`."""
    wh = _main_wh(client)
    it = _item(client, "RS-BATCH", "باری")
    _buy(client, wh, it, 30)
    from app.models.advanced_inventory import StockBatch

    batch = db.query(StockBatch).filter(StockBatch.item_id == it).one()
    r = client.post("/api/stock-reservations", json={
        "item_id": it, "warehouse_id": wh, "qty": 12, "entry_date": TODAY,
        "kind": "hold", "batch_id": str(batch.id),
    })
    assert r.status_code == 201, r.text

    row = client.get("/api/stock-batches", params={"item_id": it}).json()[0]
    assert float(row["physical_qty"]) == 30, "فیزیکی تکان نمی‌خورد"
    assert float(row["reserved_qty"]) == 12
    assert float(row["available_qty"]) == 18
    assert float(row["sellable_qty"]) == 18
    assert row["status"] == "partially_reserved"


def test_fully_reserved_batch_is_reported_as_such(client, db):
    wh = _main_wh(client)
    it = _item(client, "RS-FULL", "پُر")
    _buy(client, wh, it, 25)
    from app.models.advanced_inventory import StockBatch

    batch = db.query(StockBatch).filter(StockBatch.item_id == it).one()
    client.post("/api/stock-reservations", json={
        "item_id": it, "warehouse_id": wh, "qty": 25, "entry_date": TODAY,
        "kind": "hold", "batch_id": str(batch.id),
    })
    row = client.get("/api/stock-batches", params={"item_id": it}).json()[0]
    assert row["status"] == "fully_reserved"
    assert float(row["available_qty"]) == 0


# ── فهرستِ ادعاها ────────────────────────────────────────────────────
def test_open_reservations_are_grouped_by_document(client, db):
    wh = _main_wh(client)
    it = _item(client, "RS-LIST", "فهرستی")
    _buy(client, wh, it, 200)
    a = _reserve(client, wh, it, 30).json()["source_id"]
    _reserve(client, wh, it, 45)
    client.delete(f"/api/stock-reservations/{a}", params={"qty": 10})

    rows = client.get("/api/stock-reservations", params={"item_id": it, "warehouse_id": wh}).json()
    assert len(rows) == 2, "یک ردیف به‌ازای هر سند، نه به‌ازای هر رویداد"
    assert sorted(float(x["qty"]) for x in rows) == [20, 45]


def test_order_kind_cannot_be_created_by_hand(client):
    wh = _main_wh(client)
    it = _item(client, "RS-KIND", "نوع")
    r = _reserve(client, wh, it, 1, kind="order")
    assert r.status_code == 422


# ── همزمانی ──────────────────────────────────────────────────────────
def test_two_concurrent_claims_cannot_both_take_the_last_units(tenant_id, db):
    """§۹ — دو تراکنشِ **واقعی** که هم‌زمان آخرین ۱۰ تا را می‌خواهند.

    Barrier اجباری است و تزئینی نیست: بی آن دو نخ عملاً پشتِ سرِ هم اجرا می‌شوند
    و تست حتی وقتی هیچ قفلی وجود ندارد سبز می‌ماند — یعنی چیزی را که ادعا
    می‌کند نمی‌سنجد.

    fixtureِ `db` این‌جا به‌کار نمی‌رود چون همه‌چیز را برمی‌گرداند و برای نخِ دیگر
    نامرئی است؛ هر نخ Session و تراکنشِ خودش را می‌گیرد.
    """
    import threading

    from app.models.advanced_inventory import StockBatch
    from app.models.inventory import StockLedger, Warehouse
    from app.models.user import User
    from app.schemas.invoices import PurchaseInvoiceIn
    from app.services.inventory import post_purchase_invoice
    from tests.conftest import SEED_OWNER_EMAIL, tenant_session

    with tenant_session(tenant_id) as setup:
        wh = setup.query(Warehouse).filter(Warehouse.code == "MAIN").one()
        user = setup.query(User).filter(User.email == SEED_OWNER_EMAIL).one()
        it = Item(sku="RS-RACE", name="رقابتی", unit="عدد", sales_price=1000)
        setup.add(it)
        setup.flush()
        invoice = post_purchase_invoice(
            setup,
            PurchaseInvoiceIn.model_validate({
                "invoice_date": TODAY, "warehouse_id": str(wh.id), "contact_id": None,
                "lines": [{"item_id": str(it.id), "qty": 10, "unit_cost": 100, "description": ""}],
            }),
            user,
        )
        setup.commit()
        item_id, wh_id, invoice_id = it.id, wh.id, invoice.id

    barrier = threading.Barrier(2)
    ok: list = []
    refused: list = []

    def claim(tag: str):
        try:
            with tenant_session(tenant_id) as session:
                item = session.query(Item).filter(Item.id == item_id).one()
                actor = session.query(User).filter(User.email == SEED_OWNER_EMAIL).one()
                barrier.wait(timeout=10)  # هر دو نخ دقیقاً با هم شروع کنند
                reservations_svc.reserve(
                    session, item=item, warehouse_id=wh_id, qty=Decimal(10),
                    on=date.today(), source_type="manual", source_id=__import__("uuid").uuid4(),
                    kind="hold", user=actor,
                )
                session.commit()
                ok.append(tag)
        except Exception as exc:  # noqa: BLE001
            refused.append(exc)

    threads = [threading.Thread(target=claim, args=(f"t{i}",)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    try:
        assert len(ok) + len(refused) == 2, f"نخ‌ها تمام نشدند: {refused}"
        assert len(ok) == 1, f"هر دو ادعا پذیرفته شد — قفل کار نکرد ({ok})"
        assert "کافی نیست" in str(refused[0]), f"خطای نامنتظر: {refused[0]!r}"
        with tenant_session(tenant_id) as check:
            assert reservations_svc.reserved_for_item(check, item_id, wh_id) == 10
    finally:
        with tenant_session(tenant_id) as cleanup:
            from app.models.invoices import PurchaseInvoice
            from app.models.stock_reservations import StockReservation

            #: ترتیب اجباری است: رزرو و دفتر به بار FK دارند (`RESTRICT`)، و ردیفِ
            #: فاکتور به کالا. `flush` بینِ سند و کالا لازم است چون حذفِ انبوهِ
            #: کالا بلافاصله SQL می‌زند و منتظرِ حذفِ ORMِ سند نمی‌ماند.
            cleanup.query(StockReservation).filter(StockReservation.item_id == item_id).delete()
            cleanup.query(StockLedger).filter(StockLedger.item_id == item_id).delete()
            cleanup.query(StockBatch).filter(StockBatch.item_id == item_id).delete()
            invoice = cleanup.get(PurchaseInvoice, invoice_id)
            if invoice is not None:
                cleanup.delete(invoice)
            cleanup.flush()
            cleanup.query(Item).filter(Item.id == item_id).delete()
            cleanup.commit()
