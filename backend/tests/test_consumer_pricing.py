"""قیمتِ مصرف‌کننده و اشانتیون، سرتاسر (فاز ۳، §۱۷ تا §۲۷).

`test_margins.py` فرمول‌ها را از پرونده‌ی مشترک می‌سنجد؛ این‌جا سنجیده می‌شود که
همان‌ها واقعاً به پایگاه‌داده و API رسیده‌اند.
"""
from datetime import date
from decimal import Decimal

from app import margins
from app.models.invoices import PurchaseInvoiceLine

TODAY = str(date.today())


def _main_wh(client):
    return next(w["id"] for w in client.get("/api/warehouses").json() if w["code"] == "MAIN")


def _item(client, sku, name, **extra):
    """کالای تازه — **کلِ ردیف** برمی‌گردد، نه فقط شناسه.

    مسیرِ `GET /api/items/{id}` وجود ندارد (فهرست صفحه‌بندی‌شده است و تک‌خوانی
    از بارکد می‌آید)، و پاسخِ خودِ `POST` همان `ItemOut` است.
    """
    r = client.post("/api/items", json={"sku": sku, "name": name, **extra})
    assert r.status_code == 201, r.text
    return r.json()


# ── §۱۷ §۱۸ سه قیمتِ جدا ─────────────────────────────────────────────
def test_the_three_prices_are_stored_separately(client):
    row = _item(
        client, "CP-THREE", "شیر",
        has_consumer_price=True,
        printed_consumer_price=450000,
        suggested_retail_price=470000,
        maximum_retail_price=500000,
    )
    assert row["has_consumer_price"] is True
    assert float(row["printed_consumer_price"]) == 450000
    assert float(row["suggested_retail_price"]) == 470000
    assert float(row["maximum_retail_price"]) == 500000


def test_prices_are_absent_not_zero_when_unset(client):
    """§۳۰ — فیلدِ بی‌مقدار نباید صفر نشان داده شود؛ صفر مقدارِ معتبرِ دیگری است."""
    row = _item(client, "CP-NONE", "بی‌قیمت")
    assert row["has_consumer_price"] is False
    assert row["printed_consumer_price"] is None
    assert row["suggested_retail_price"] is None
    assert row["maximum_retail_price"] is None


def test_consumer_price_needs_no_new_validation(client):
    """§۲۸ — هیچ اعتبارسنجیِ اجباریِ عمومی ساخته نشود.

    کالایی که `has_consumer_price` دارد ولی هیچ قیمتی ندارد باید بی‌خطا ساخته
    شود: پیکربندیِ ناقص کارِ کاربر را متوقف نمی‌کند.
    """
    r = client.post("/api/items", json={"sku": "CP-EMPTY", "name": "خالی", "has_consumer_price": True})
    assert r.status_code == 201, r.text


# ── §۱۹ قیمتِ بار بر قیمتِ کالا می‌چربد ──────────────────────────────
def test_batch_price_overrides_the_product_price(client, db):
    wh = _main_wh(client)
    item = _item(client, "CP-OVR", "سرریز", has_consumer_price=True, printed_consumer_price=450000)
    b = client.post("/api/stock-batches", json={
        "item_id": item["id"], "warehouse_id": wh, "batch_number": "B-1",
        "qty": 10, "received_date": TODAY, "printed_consumer_price": 520000,
    })
    assert b.status_code == 201, b.text
    assert float(b.json()["printed_consumer_price"]) == 520000

    effective = margins.effective_consumer_price(
        b.json()["printed_consumer_price"], item["printed_consumer_price"]
    )
    assert effective == 520000


def test_batch_without_its_own_price_falls_back_to_the_product(client, db):
    wh = _main_wh(client)
    item = _item(client, "CP-FALL", "پیش‌فرض", has_consumer_price=True, printed_consumer_price=450000)
    b = client.post("/api/stock-batches", json={
        "item_id": item["id"], "warehouse_id": wh, "batch_number": "B-2", "qty": 5, "received_date": TODAY,
    }).json()
    assert b["printed_consumer_price"] is None

    assert margins.effective_consumer_price(
        b["printed_consumer_price"], item["printed_consumer_price"]
    ) == 450000


# ── §۲۵ اشانتیون ─────────────────────────────────────────────────────
def test_bonus_is_recorded_without_a_zero_priced_line(client, db):
    """کارتنِ رایگان میانگینِ موزون را بی‌توضیح پایین نمی‌کشد.

    ۱۲۰ کارتن پول، ۱۲ کارتن رایگان → تعداد ۱۳۲ با تخفیفی برابرِ بهای ۱۲ تا.
    آن‌وقت `post_purchase_invoice` خودش بهای واقعی را حساب می‌کند.
    """
    from app.models.inventory import Item

    wh = _main_wh(client)
    it = _item(client, "CP-BONUS", "اشانتیونی")["id"]
    unit = 300000
    r = client.post("/api/purchase-invoices", json={
        "invoice_date": TODAY, "warehouse_id": wh,
        "lines": [{
            "item_id": it, "qty": 132, "unit_cost": unit,
            "discount": unit * 12, "bonus_qty": 12,
        }],
    })
    assert r.status_code == 201, r.text

    db.expire_all()
    line = db.query(PurchaseInvoiceLine).filter(PurchaseInvoiceLine.item_id == it).one()
    assert Decimal(line.bonus_qty) == 12, "یادداشتِ اشانتیون باید بماند"

    #: و بهای میانگین دقیقاً همان `total_paid / 132`ِ §۲۵ است.
    expected = margins.effective_unit_cost(Decimal(unit) * 120, 132)
    got = Decimal(db.query(Item).filter(Item.id == it).one().average_cost)
    assert abs(got - expected) < Decimal("0.0001"), f"{got} != {expected}"


def test_a_purchase_without_bonus_is_unchanged(client, db):
    """**پیش‌فرض = رفتارِ دیروز** — خریدی که اشانتیون اعلام نکرده."""
    from app.models.inventory import Item

    wh = _main_wh(client)
    it = _item(client, "CP-PLAIN", "ساده")["id"]
    client.post("/api/purchase-invoices", json={
        "invoice_date": TODAY, "warehouse_id": wh,
        "lines": [{"item_id": it, "qty": 10, "unit_cost": 1000}],
    })
    db.expire_all()
    line = db.query(PurchaseInvoiceLine).filter(PurchaseInvoiceLine.item_id == it).one()
    assert Decimal(line.bonus_qty) == 0
    assert Decimal(db.query(Item).filter(Item.id == it).one().average_cost) == 1000


# ── §۲۵ روی کاتالوگ ──────────────────────────────────────────────────
def test_listing_carries_the_bonus_offer(client, db):
    from app.models.marketplace import MarketplaceListing, MarketplaceSettings
    from app.schemas.marketplace import ListingIn
    from app.services import marketplace as svc
    from tests.test_marketplace import _make_item, _primary_id

    primary_id = _primary_id(db)
    db.add(MarketplaceSettings(distributor_tenant_id=primary_id, is_active=True))
    item = _make_item(db, "CP-LST", "کالای کاتالوگ")

    listing = svc.create_listing(db, primary_id, ListingIn(
        kind="single", title="با اشانتیون", wholesale_price=Decimal(5000),
        item_id=item.id, bonus_threshold_qty=Decimal(10), bonus_qty=Decimal(1),
    ))
    assert Decimal(listing.bonus_threshold_qty) == 10
    assert Decimal(listing.bonus_qty) == 1

    #: و ویرایش هم نگهش می‌دارد.
    updated = svc.update_listing(db, primary_id, listing.id, ListingIn(
        kind="single", title="با اشانتیون", wholesale_price=Decimal(5000),
        item_id=item.id, bonus_threshold_qty=Decimal(20), bonus_qty=Decimal(3),
    ))
    assert Decimal(updated.bonus_threshold_qty) == 20
    assert Decimal(updated.bonus_qty) == 3
    assert db.query(MarketplaceListing).filter(MarketplaceListing.id == listing.id).one().bonus_qty == 3
