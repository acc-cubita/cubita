"""بازارِ عمده‌فروشی — تست‌های سمتِ پخش‌کننده (M2).

جدول‌های بازار سراسری‌اند (بدونِ RLS)؛ این‌جا گیتِ نوعِ حساب، مالکیت، و اعتبارسنجیِ
لیستینگ سنجیده می‌شود.
"""
import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.models.advanced_inventory import StockBatch
from app.models.inventory import Item, Warehouse
from app.models.invoices import PurchaseInvoice
from app.models.marketplace import (
    MarketplaceCommission,
    MarketplaceConnection,
    MarketplaceItemLink,
    MarketplaceListing,
    MarketplaceListingComponent,
    MarketplaceOrder,
    MarketplaceReturn,
    MarketplaceSettings,
)
from app.models.storefront_native import PaymentGateway
from app.models.tenant import Tenant
from app.models.treasury import TreasuryTransaction
from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn
from app.schemas.marketplace import (
    OrderLineIn,
    OrderPlaceIn,
    ReturnRequestIn,
    ReturnRequestLineIn,
)
from app.seed import provision_tenant
from app.services import inventory as inventory_service
from app.services import marketplace as svc
from app.tenant_context import apply_tenant_to_transaction, bind_session_tenant, tenant_scope
from tests.conftest import PRIMARY_SLUG


def _make_item(db, sku: str, name: str) -> Item:
    it = Item(sku=sku, name=name, unit="عدد", sales_price=0)
    db.add(it)
    db.flush()
    return it


def _primary_id(db):
    return db.query(Tenant).filter(Tenant.slug == PRIMARY_SLUG).one().id


def _bare_tenant(db, kind: str, name: str = "مستأجر") -> Tenant:
    """یک ردیفِ Tenant سراسری (بدونِ provision) — کافی برای تستِ جدول‌های سراسریِ بازار."""
    t = Tenant(name=name, slug=f"mp-{uuid.uuid4().hex[:8]}", kind=kind, status="active")
    db.add(t)
    db.flush()
    return t


def _connection(db, distributor_id, retailer_id, status="approved") -> MarketplaceConnection:
    c = MarketplaceConnection(
        distributor_tenant_id=distributor_id,
        retailer_tenant_id=retailer_id,
        status=status,
        requested_by="retailer",
    )
    db.add(c)
    db.flush()
    return c


@pytest.fixture
def as_distributor(client, db):
    """مستأجرِ اصلیِ تست را پخش‌کننده می‌کند و همان client را برمی‌گرداند."""
    tenant = db.query(Tenant).filter(Tenant.slug == PRIMARY_SLUG).one()
    tenant.kind = "distributor"
    db.flush()
    return client


@pytest.fixture
def as_retailer(client, db):
    """مستأجرِ اصلیِ تست را فروشگاه می‌کند و همان client را برمی‌گرداند."""
    tenant = db.query(Tenant).filter(Tenant.slug == PRIMARY_SLUG).one()
    tenant.kind = "retailer"
    db.flush()
    return client


@pytest.fixture
def distributor_tenant(db):
    """یک پخش‌کننده‌ی سبک درونِ همان تراکنشِ `db`: Tenant(distributor) + تنظیماتِ فعال + یک لیستینگِ منتشرشده.

    جدول‌های بازار سراسری‌اند، پس نه provision لازم است نه commit؛ همه‌چیز در تراکنشِ تست
    می‌ماند و با rollback پاک می‌شود. (تلاشِ قبلی مستأجرِ committed می‌ساخت و purge در teardown
    روی قفلِ FKِ ردیفِ اتصالِ کامیت‌نشده‌ی همین تست بی‌پایان منتظر می‌ماند.)
    """
    t = _bare_tenant(db, "distributor", "پخشِ نمونه")
    db.add(MarketplaceSettings(distributor_tenant_id=t.id, display_name="پخشِ نمونه", is_active=True))
    db.add(
        MarketplaceListing(
            distributor_tenant_id=t.id,
            kind="single",
            title="کالای پخش (عمده)",
            unit="عدد",
            wholesale_price=10000,
            is_published=True,
            distributor_item_id=None,
        )
    )
    db.flush()
    return t.id


@pytest.fixture
def retailer_tenant(db):
    """یک فروشگاهِ **کاملاً provision‌شده** درونِ همان تراکنشِ `db` (انبار/حساب‌ها/مالک دارد).

    برای تأییدِ سفارش لازم است چون فاکتورِ خرید در دفترِ فروشگاه می‌خورد و به انبار/چارتِ
    حساب/کاربرِ واقعی نیاز دارد. `provision_tenant` بایندینگِ نشست را به مستأجرِ تازه می‌برد،
    پس بعدش دوباره PRIMARY را می‌نشانیم. همه‌چیز در تراکنشِ تست می‌ماند و با rollback پاک می‌شود
    (نه commit، نه purge — تا دامِ قفلِ FKِ teardown پیش نیاید).
    """
    primary_id = _primary_id(db)
    slug = f"ret-{uuid.uuid4().hex[:8]}"
    tenant = provision_tenant(
        db,
        name="فروشگاهِ نمونه",
        slug=slug,
        owner_email=f"ret-{slug}@example.invalid",
        owner_password="RetailerPass!2026",
        kind="retailer",
    )
    db.flush()
    rid = tenant.id
    # provision_tenant بایندینگ را به فروشگاه برد؛ برای ادامه‌ی تست PRIMARY را برمی‌گردانیم.
    bind_session_tenant(db, primary_id)
    apply_tenant_to_transaction(db, primary_id)
    return rid


def test_non_distributor_is_forbidden(client):
    # مستأجرِ پیش‌فرض standard است → همه‌ی اندپوینت‌های پخش‌کننده ۴۰۳.
    assert client.get("/api/marketplace/distributor/settings").status_code == 403
    assert client.get("/api/marketplace/distributor/listings").status_code == 403


def test_settings_default_and_update(as_distributor):
    r = as_distributor.get("/api/marketplace/distributor/settings")
    assert r.status_code == 200
    assert r.json()["settlement_mode"] == "credit"
    assert r.json()["is_active"] is False

    r = as_distributor.put(
        "/api/marketplace/distributor/settings",
        json={"display_name": "پخشِ نمونه", "settlement_mode": "online", "is_active": True},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["display_name"] == "پخشِ نمونه"
    assert body["settlement_mode"] == "online"
    assert body["is_active"] is True

    # نحوه‌ی تسویه‌ی نامعتبر رد شود.
    bad = as_distributor.put(
        "/api/marketplace/distributor/settings",
        json={"display_name": "x", "settlement_mode": "wat", "is_active": True},
    )
    assert bad.status_code == 422


def test_create_single_listing(as_distributor, db):
    it = _make_item(db, "SKU-1", "کالای ۱")
    r = as_distributor.post(
        "/api/marketplace/distributor/listings",
        json={
            "kind": "single",
            "title": "کالای ۱ عمده",
            "unit": "عدد",
            "wholesale_price": 12000,
            "item_id": str(it.id),
            "is_published": True,
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["kind"] == "single"
    assert body["item_id"] == str(it.id)
    assert body["is_published"] is True
    # single یک جزء با qty=1 دارد (برای یکدستیِ باز‌کردن در تأییدِ سفارش).
    assert len(body["components"]) == 1
    assert body["components"][0]["item_id"] == str(it.id)
    assert float(body["components"][0]["qty"]) == 1


def test_create_pack_listing(as_distributor, db):
    a = _make_item(db, "SKU-A", "آ")
    b = _make_item(db, "SKU-B", "ب")
    r = as_distributor.post(
        "/api/marketplace/distributor/listings",
        json={
            "kind": "pack",
            "title": "پکِ آ+ب",
            "wholesale_price": 50000,
            "components": [
                {"item_id": str(a.id), "qty": 2},
                {"item_id": str(b.id), "qty": 3},
            ],
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["kind"] == "pack"
    assert body["item_id"] is None
    qby = {c["item_id"]: float(c["qty"]) for c in body["components"]}
    assert qby[str(a.id)] == 2 and qby[str(b.id)] == 3


def test_listing_validation(as_distributor):
    # single بدونِ item_id
    assert as_distributor.post(
        "/api/marketplace/distributor/listings",
        json={"kind": "single", "title": "x", "wholesale_price": 1},
    ).status_code == 422
    # pack بدونِ اجزا
    assert as_distributor.post(
        "/api/marketplace/distributor/listings",
        json={"kind": "pack", "title": "x", "wholesale_price": 1, "components": []},
    ).status_code == 422


def test_ownership_guard_rejects_foreign_item(as_distributor):
    # شناسه‌ی کالایی که مالِ این پخش‌کننده نیست (یا اصلاً وجود ندارد) → ۴۰۰.
    r = as_distributor.post(
        "/api/marketplace/distributor/listings",
        json={"kind": "single", "title": "x", "wholesale_price": 1, "item_id": str(uuid.uuid4())},
    )
    assert r.status_code == 400


def test_publish_update_delete(as_distributor, db):
    it = _make_item(db, "SKU-2", "کالای ۲")
    created = as_distributor.post(
        "/api/marketplace/distributor/listings",
        json={"kind": "single", "title": "قابلِ‌ویرایش", "wholesale_price": 100, "item_id": str(it.id)},
    ).json()
    lid = created["id"]

    # publish toggle
    r = as_distributor.post(f"/api/marketplace/distributor/listings/{lid}/publish?is_published=true")
    assert r.status_code == 200 and r.json()["is_published"] is True

    # update عنوان و قیمت
    r = as_distributor.put(
        f"/api/marketplace/distributor/listings/{lid}",
        json={"kind": "single", "title": "ویرایش‌شده", "wholesale_price": 200, "item_id": str(it.id)},
    )
    assert r.status_code == 200 and r.json()["title"] == "ویرایش‌شده"
    assert float(r.json()["wholesale_price"]) == 200

    # فهرست یکی دارد
    assert len(as_distributor.get("/api/marketplace/distributor/listings").json()) == 1

    # delete
    assert as_distributor.delete(f"/api/marketplace/distributor/listings/{lid}").status_code == 204
    assert len(as_distributor.get("/api/marketplace/distributor/listings").json()) == 0


# ── عکسِ لیستینگ: فشرده و سقف‌دار (تا فضای پایگاه‌داده باد نکند) ─────────
# یک PNGِ ۱×۱ (چند ده بایت) به‌عنوانِ عکسِ معتبرِ کوچک.
_TINY_PNG = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def test_listing_accepts_small_image_and_roundtrips(as_distributor, db):
    it = _make_item(db, "SKU-IMG", "کالای عکس‌دار")
    created = as_distributor.post(
        "/api/marketplace/distributor/listings",
        json={
            "kind": "single",
            "title": "عکس‌دار",
            "wholesale_price": 1000,
            "item_id": str(it.id),
            "images": [_TINY_PNG],
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert len(body["images"]) == 1
    assert body["images"][0].startswith("data:image/png;base64,")
    # روی خواندنِ دوباره هم عکس می‌ماند.
    lid = body["id"]
    listed = as_distributor.get("/api/marketplace/distributor/listings").json()
    assert listed[0]["images"] == body["images"]
    # حذفِ عکس در ویرایش.
    upd = as_distributor.put(
        f"/api/marketplace/distributor/listings/{lid}",
        json={"kind": "single", "title": "عکس‌دار", "wholesale_price": 1000, "item_id": str(it.id), "images": []},
    )
    assert upd.status_code == 200 and upd.json()["images"] == []


def test_listing_rejects_too_many_images(as_distributor, db):
    it = _make_item(db, "SKU-IMG5", "پنج‌عکس")
    r = as_distributor.post(
        "/api/marketplace/distributor/listings",
        json={
            "kind": "single", "title": "x", "wholesale_price": 1, "item_id": str(it.id),
            "images": [_TINY_PNG] * 5,  # سقف ۴ است
        },
    )
    assert r.status_code == 422


def test_listing_rejects_non_data_uri_image(as_distributor, db):
    it = _make_item(db, "SKU-IMGU", "لینک‌عکس")
    r = as_distributor.post(
        "/api/marketplace/distributor/listings",
        json={
            "kind": "single", "title": "x", "wholesale_price": 1, "item_id": str(it.id),
            "images": ["https://example.com/x.jpg"],  # فقط data URI مجاز است، نه لینک
        },
    )
    assert r.status_code == 422


def test_listing_rejects_oversize_image(as_distributor, db):
    import base64 as _b64

    it = _make_item(db, "SKU-IMGBIG", "عکسِ درشت")
    big = "data:image/jpeg;base64," + _b64.b64encode(b"\x00" * (500 * 1024)).decode()  # ~۵۰۰KB > سقف
    r = as_distributor.post(
        "/api/marketplace/distributor/listings",
        json={
            "kind": "single", "title": "x", "wholesale_price": 1, "item_id": str(it.id),
            "images": [big],
        },
    )
    assert r.status_code == 422


# ── M3: اتصال‌ها و کاتالوگِ سمتِ فروشگاه ───────────────────────────────
def test_retailer_endpoints_forbidden_for_non_retailer(client):
    # مستأجرِ پیش‌فرض standard است → اندپوینت‌های فروشگاه ۴۰۳.
    assert client.get("/api/marketplace/retailer/distributors").status_code == 403
    assert client.get("/api/marketplace/retailer/catalog").status_code == 403
    assert client.get("/api/marketplace/retailer/connections").status_code == 403


def test_retailer_discovers_distributor_and_requests_connection(as_retailer, distributor_tenant, db):
    did = distributor_tenant
    # کشف: پخش‌کننده‌ی فعال دیده می‌شود، هنوز اتصالی نیست.
    dists = as_retailer.get("/api/marketplace/retailer/distributors").json()
    card = next((d for d in dists if d["tenant_id"] == str(did)), None)
    assert card is not None, "پخش‌کننده‌ی فعال در کشف دیده نشد"
    assert card["connection_status"] is None
    assert card["display_name"] == "پخشِ نمونه"

    # درخواستِ اتصال → pending.
    r = as_retailer.post("/api/marketplace/retailer/connections", json={"distributor_tenant_id": str(did)})
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "pending"
    assert r.json()["requested_by"] == "retailer"

    # حالا کارت وضعیتِ pending دارد.
    dists = as_retailer.get("/api/marketplace/retailer/distributors").json()
    assert next(d for d in dists if d["tenant_id"] == str(did))["connection_status"] == "pending"

    # تا تأیید نشده، کاتالوگ خالی است.
    assert as_retailer.get("/api/marketplace/retailer/catalog").json() == []

    # درخواستِ دوباره idempotent است.
    again = as_retailer.post("/api/marketplace/retailer/connections", json={"distributor_tenant_id": str(did)})
    assert again.status_code == 201 and again.json()["status"] == "pending"


def test_retailer_sees_published_catalog_only_after_approval(as_retailer, distributor_tenant, db):
    did = distributor_tenant
    as_retailer.post("/api/marketplace/retailer/connections", json={"distributor_tenant_id": str(did)})

    # پخش‌کننده تأیید می‌کند — اینجا مستقیم روی جدولِ سراسری (سمتِ HTTPِ پخش‌کننده جدا تست می‌شود).
    conn = (
        db.query(MarketplaceConnection)
        .filter(
            MarketplaceConnection.distributor_tenant_id == did,
            MarketplaceConnection.retailer_tenant_id == _primary_id(db),
        )
        .one()
    )
    conn.status = "approved"
    db.flush()

    catalog = as_retailer.get("/api/marketplace/retailer/catalog").json()
    assert any(c["distributor_tenant_id"] == str(did) and c["title"] == "کالای پخش (عمده)" for c in catalog)
    # کاتالوگ نباید شناسه‌ی داخلیِ کالای پخش‌کننده را لو بدهد.
    assert "item_id" not in catalog[0]

    # فیلترِ per-distributor.
    filt = as_retailer.get(f"/api/marketplace/retailer/catalog?distributor_id={did}").json()
    assert filt and all(c["distributor_tenant_id"] == str(did) for c in filt)


def test_retailer_rejects_self_and_unknown_distributor(as_retailer, db):
    # پخش‌کننده‌ی ناموجود → ۴۰۴.
    assert (
        as_retailer.post(
            "/api/marketplace/retailer/connections", json={"distributor_tenant_id": str(uuid.uuid4())}
        ).status_code
        == 404
    )
    # اتصال به خود → ۴۰۰.
    assert (
        as_retailer.post(
            "/api/marketplace/retailer/connections", json={"distributor_tenant_id": str(_primary_id(db))}
        ).status_code
        == 400
    )


def test_blocked_retailer_cannot_rerequest(as_retailer, distributor_tenant, db):
    did = distributor_tenant
    as_retailer.post("/api/marketplace/retailer/connections", json={"distributor_tenant_id": str(did)})
    conn = (
        db.query(MarketplaceConnection)
        .filter(
            MarketplaceConnection.distributor_tenant_id == did,
            MarketplaceConnection.retailer_tenant_id == _primary_id(db),
        )
        .one()
    )
    conn.status = "blocked"
    db.flush()
    # بلاک‌شده نمی‌تواند دوباره درخواست دهد → ۴۰۳.
    assert (
        as_retailer.post(
            "/api/marketplace/retailer/connections", json={"distributor_tenant_id": str(did)}
        ).status_code
        == 403
    )


def test_distributor_lists_and_moderates_connections(as_distributor, db):
    did = _primary_id(db)
    retailer = _bare_tenant(db, "retailer", "فروشگاهِ الف")
    conn = MarketplaceConnection(
        distributor_tenant_id=did, retailer_tenant_id=retailer.id, status="pending", requested_by="retailer"
    )
    db.add(conn)
    db.flush()

    rows = as_distributor.get("/api/marketplace/distributor/connections").json()
    row = next((c for c in rows if c["id"] == str(conn.id)), None)
    assert row is not None and row["retailer_name"] == "فروشگاهِ الف"

    # تأیید.
    r = as_distributor.post(
        f"/api/marketplace/distributor/connections/{conn.id}/status", json={"status": "approved"}
    )
    assert r.status_code == 200 and r.json()["status"] == "approved"

    # بلاک.
    r = as_distributor.post(
        f"/api/marketplace/distributor/connections/{conn.id}/status", json={"status": "blocked"}
    )
    assert r.json()["status"] == "blocked"

    # وضعیتِ نامعتبر رد شود.
    assert (
        as_distributor.post(
            f"/api/marketplace/distributor/connections/{conn.id}/status", json={"status": "wat"}
        ).status_code
        == 422
    )


def test_distributor_cannot_moderate_foreign_connection(as_distributor, db):
    other_dist = _bare_tenant(db, "distributor", "پخشِ دیگر")
    retailer = _bare_tenant(db, "retailer", "فروشگاهِ ب")
    conn = MarketplaceConnection(
        distributor_tenant_id=other_dist.id, retailer_tenant_id=retailer.id, status="pending", requested_by="retailer"
    )
    db.add(conn)
    db.flush()
    # پخش‌کننده‌ی PRIMARY اتصالِ پخش‌کننده‌ی دیگری را نمی‌بیند/تأیید نمی‌کند → ۴۰۴.
    assert (
        as_distributor.post(
            f"/api/marketplace/distributor/connections/{conn.id}/status", json={"status": "approved"}
        ).status_code
        == 404
    )
    # و در فهرستِ اتصال‌هایش هم نیست.
    rows = as_distributor.get("/api/marketplace/distributor/connections").json()
    assert all(c["id"] != str(conn.id) for c in rows)


# ── M4: سفارش + تأییدِ دوطرفه ─────────────────────────────────────────
def _approve(db, distributor_id, retailer_id):
    """اتصالِ approved بینِ این دو را می‌سازد/می‌گذارد (روی جدولِ سراسری)."""
    conn = MarketplaceConnection(
        distributor_tenant_id=distributor_id, retailer_tenant_id=retailer_id, status="approved", requested_by="retailer"
    )
    db.add(conn)
    db.flush()
    return conn


def test_place_order_requires_approval_and_records_lines(as_retailer, distributor_tenant, db):
    did = distributor_tenant
    listing = db.query(MarketplaceListing).filter(MarketplaceListing.distributor_tenant_id == did).first()

    payload = {"distributor_tenant_id": str(did), "lines": [{"listing_id": str(listing.id), "qty": 3}]}

    # بدونِ اتصالِ تأییدشده → ۴۰۳.
    assert as_retailer.post("/api/marketplace/retailer/orders", json=payload).status_code == 403

    _approve(db, did, _primary_id(db))

    r = as_retailer.post("/api/marketplace/retailer/orders", json=payload)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "placed"
    assert float(body["total"]) == 30000  # ۱۰٬۰۰۰ × ۳
    assert body["lines"][0]["title"] == "کالای پخش (عمده)"

    # در «سفارش‌های من» دیده می‌شود.
    orders = as_retailer.get("/api/marketplace/retailer/orders").json()
    assert any(o["id"] == body["id"] for o in orders)


def test_order_line_carries_listing_image(as_retailer, distributor_tenant, db):
    # عکسِ نخستِ لیستینگ باید در ردیف‌های سفارش (از روی listing_id) دیده شود.
    did = distributor_tenant
    listing = db.query(MarketplaceListing).filter(MarketplaceListing.distributor_tenant_id == did).first()
    listing.images = [_TINY_PNG]
    db.flush()
    _approve(db, did, _primary_id(db))

    r = as_retailer.post(
        "/api/marketplace/retailer/orders",
        json={"distributor_tenant_id": str(did), "lines": [{"listing_id": str(listing.id), "qty": 1}]},
    )
    assert r.status_code == 201, r.text
    assert r.json()["lines"][0]["image"] == _TINY_PNG
    # از نمای فهرست هم می‌آید.
    orders = as_retailer.get("/api/marketplace/retailer/orders").json()
    line = next(o for o in orders if o["id"] == r.json()["id"])["lines"][0]
    assert line["image"] == _TINY_PNG


def test_confirm_order_posts_two_sided_and_is_idempotent(as_distributor, retailer_tenant, db, user):
    primary_id = _primary_id(db)
    retailer_id = retailer_tenant

    # پخش‌کننده‌ی PRIMARY: تنظیماتِ فعال + کالا + موجودی + لیستینگِ منتشرشده.
    db.add(MarketplaceSettings(distributor_tenant_id=primary_id, display_name="پخشِ اصلی", is_active=True))
    item = _make_item(db, "DIST-1", "کالای پخش")
    main_wh = db.query(Warehouse).filter(Warehouse.code == "MAIN").one()
    inventory_service.post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=date.today(),
            warehouse_id=main_wh.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(100), unit_cost=Decimal(5000))],
        ),
        user,
    )
    listing = MarketplaceListing(
        distributor_tenant_id=primary_id,
        kind="single",
        title="کالای پخش عمده",
        unit="عدد",
        wholesale_price=8000,
        is_published=True,
        distributor_item_id=item.id,
    )
    listing.components.append(MarketplaceListingComponent(distributor_item_id=item.id, item_name="کالای پخش", qty=1))
    db.add(listing)
    db.flush()

    _approve(db, primary_id, retailer_id)

    # فروشگاه سفارش می‌دهد (سطحِ سرویس؛ مسیرِ HTTPِ ثبت جدا تست شده).
    order = svc.place_order(
        db, retailer_id, OrderPlaceIn(distributor_tenant_id=primary_id, lines=[OrderLineIn(listing_id=listing.id, qty=Decimal(10))])
    )
    assert order.status == "placed"
    assert Decimal(order.total) == Decimal(80000)  # ۸٬۰۰۰ × ۱۰

    # پخش‌کننده تأیید می‌کند.
    r = as_distributor.post(f"/api/marketplace/distributor/orders/{order.id}/confirm")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "confirmed"
    assert body["distributor_sales_invoice_id"] and body["retailer_purchase_invoice_id"]

    # انبارِ پخش‌کننده کم شد: ۱۰۰ − ۱۰ = ۹۰. (tenant_scope چون confirm بایندینگ را روی فروشگاه گذاشته.)
    with tenant_scope(db, primary_id):
        assert inventory_service.get_stock_qty(db, item.id, main_wh.id) == Decimal(90)

    # کالا خودکار در انبارِ فروشگاه ساخته و تعدادش اضافه شد: ۱۰.
    link = (
        db.query(MarketplaceItemLink)
        .filter(
            MarketplaceItemLink.retailer_tenant_id == retailer_id,
            MarketplaceItemLink.distributor_item_id == item.id,
        )
        .one()
    )
    with tenant_scope(db, retailer_id):
        assert inventory_service.get_total_stock_qty(db, link.retailer_item_id) == Decimal(10)
        # دقیقاً یک فاکتورِ خرید در دفترِ فروشگاه.
        assert db.query(PurchaseInvoice).count() == 1

    # تأییدِ دوباره idempotent است — فاکتورِ دوم نمی‌سازد.
    r2 = as_distributor.post(f"/api/marketplace/distributor/orders/{order.id}/confirm")
    assert r2.status_code == 200
    assert r2.json()["distributor_sales_invoice_id"] == body["distributor_sales_invoice_id"]
    with tenant_scope(db, retailer_id):
        assert db.query(PurchaseInvoice).count() == 1


# ── گردشِ کارِ «تحویل با مامور حمل» (require_delivery) ───────────────────
def _setup_delivery_scenario(db, user, primary_id, retailer_id, *, require_delivery: bool):
    """پخش‌کننده‌ی PRIMARY: تنظیمات + کالا با موجودی + لیستینگِ منتشرشده + اتصالِ approved + سفارشِ ثبت‌شده."""
    db.add(MarketplaceSettings(
        distributor_tenant_id=primary_id, display_name="پخشِ اصلی", is_active=True, require_delivery=require_delivery,
    ))
    item = _make_item(db, "DIST-DLV", "کالای تحویل")
    main_wh = db.query(Warehouse).filter(Warehouse.code == "MAIN").one()
    inventory_service.post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=date.today(),
            warehouse_id=main_wh.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(100), unit_cost=Decimal(5000))],
        ),
        user,
    )
    listing = MarketplaceListing(
        distributor_tenant_id=primary_id, kind="single", title="کالای تحویل عمده", unit="عدد",
        wholesale_price=8000, is_published=True, distributor_item_id=item.id,
    )
    listing.components.append(MarketplaceListingComponent(distributor_item_id=item.id, item_name="کالای تحویل", qty=1))
    db.add(listing)
    db.flush()
    _approve(db, primary_id, retailer_id)
    order = svc.place_order(
        db, retailer_id,
        OrderPlaceIn(distributor_tenant_id=primary_id, lines=[OrderLineIn(listing_id=listing.id, qty=Decimal(10))]),
    )
    return item, main_wh, order


def test_require_delivery_defers_stock_until_deliver(as_distributor, retailer_tenant, db, user):
    """با require_delivery: تأیید فقط می‌پذیرد (بدونِ سند/انبار)؛ ورودِ کالا هنگامِ ثبتِ تحویل است."""
    primary_id = _primary_id(db)
    retailer_id = retailer_tenant
    item, main_wh, order = _setup_delivery_scenario(db, user, primary_id, retailer_id, require_delivery=True)

    # تأیید: پذیرفته می‌شود ولی هیچ سندی نمی‌خورد.
    r = as_distributor.post(f"/api/marketplace/distributor/orders/{order.id}/confirm")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "confirmed"
    assert body["distributor_sales_invoice_id"] is None
    assert body["retailer_purchase_invoice_id"] is None
    # انبارِ پخش‌کننده هنوز دست‌نخورده و فروشگاه هنوز فاکتوری ندارد.
    with tenant_scope(db, primary_id):
        assert inventory_service.get_stock_qty(db, item.id, main_wh.id) == Decimal(100)
    with tenant_scope(db, retailer_id):
        assert db.query(PurchaseInvoice).count() == 0

    # تحویل (سهمِ نقدِ ۵۰٪): اینجا سند دوطرفه + ورودِ انبارِ فروشگاه رخ می‌دهد.
    d = as_distributor.post(f"/api/marketplace/distributor/orders/{order.id}/deliver", json={"cash_percent": 50})
    assert d.status_code == 200, d.text
    db_ = d.json()
    assert db_["status"] == "delivered"
    assert db_["distributor_sales_invoice_id"] and db_["retailer_purchase_invoice_id"]
    assert db_["delivered_by_name"] and db_["delivered_at"]
    assert Decimal(db_["cash_amount"]) == Decimal(40000)  # ۵۰٪ از ۸۰٬۰۰۰

    with tenant_scope(db, primary_id):
        assert inventory_service.get_stock_qty(db, item.id, main_wh.id) == Decimal(90)
    link = (
        db.query(MarketplaceItemLink)
        .filter(MarketplaceItemLink.retailer_tenant_id == retailer_id, MarketplaceItemLink.distributor_item_id == item.id)
        .one()
    )
    with tenant_scope(db, retailer_id):
        assert inventory_service.get_total_stock_qty(db, link.retailer_item_id) == Decimal(10)
        assert db.query(PurchaseInvoice).count() == 1

    # تحویلِ دوباره idempotent — فاکتورِ دوم نمی‌سازد.
    d2 = as_distributor.post(f"/api/marketplace/distributor/orders/{order.id}/deliver", json={"cash_percent": 50})
    assert d2.status_code == 200
    assert d2.json()["retailer_purchase_invoice_id"] == db_["retailer_purchase_invoice_id"]
    with tenant_scope(db, retailer_id):
        assert db.query(PurchaseInvoice).count() == 1


def test_deliver_rejects_unconfirmed_order(as_distributor, retailer_tenant, db, user):
    """تحویلِ سفارشی که هنوز تأیید نشده → ۴۰۰."""
    primary_id = _primary_id(db)
    _, _, order = _setup_delivery_scenario(db, user, primary_id, retailer_tenant, require_delivery=True)
    r = as_distributor.post(f"/api/marketplace/distributor/orders/{order.id}/deliver")
    assert r.status_code == 400, r.text


def test_deliver_on_already_fulfilled_marks_without_reposting(as_distributor, retailer_tenant, db, user):
    """بدونِ require_delivery: تأیید سند می‌زند؛ تحویلِ بعدی فقط علامت می‌خورد، سند دوباره نمی‌سازد."""
    primary_id = _primary_id(db)
    retailer_id = retailer_tenant
    _, _, order = _setup_delivery_scenario(db, user, primary_id, retailer_id, require_delivery=False)

    r = as_distributor.post(f"/api/marketplace/distributor/orders/{order.id}/confirm")
    assert r.status_code == 200 and r.json()["retailer_purchase_invoice_id"]
    inv_id = r.json()["retailer_purchase_invoice_id"]
    with tenant_scope(db, retailer_id):
        assert db.query(PurchaseInvoice).count() == 1

    d = as_distributor.post(f"/api/marketplace/distributor/orders/{order.id}/deliver")
    assert d.status_code == 200, d.text
    assert d.json()["status"] == "delivered"
    assert d.json()["retailer_purchase_invoice_id"] == inv_id  # همان فاکتور، بدونِ ساختِ دوباره
    assert d.json()["delivered_by_name"]
    with tenant_scope(db, retailer_id):
        assert db.query(PurchaseInvoice).count() == 1


def test_delivery_agent_role_can_deliver_not_confirm():
    """نقشِ «مامور حمل» فقط deliver دارد نه approve؛ مالک با wildcard هر دو را دارد."""
    from app.models.user import DEFAULT_ROLES, Role

    da_def = next(r for r in DEFAULT_ROLES if r["key"] == "delivery_agent")
    da = Role(key="delivery_agent", name=da_def["name"], permissions=da_def["permissions"])
    assert da.has_permission("marketplace", "deliver") is True
    assert da.has_permission("marketplace", "view") is True
    assert da.has_permission("marketplace", "approve") is False  # نمی‌تواند تأیید/رد کند
    assert da.has_permission("inventory", "view") is False

    owner_def = next(r for r in DEFAULT_ROLES if r["key"] == "owner")
    owner = Role(key="owner", name=owner_def["name"], permissions=owner_def["permissions"])
    # مالک deliver اختصاصی ندارد ولی approve دارد؛ اندپوینتِ تحویل با تاپلِ (deliver, approve) بازش می‌کند.
    assert owner.has_permission("marketplace", "approve") is True


# ── محدودیت‌های سفارش‌گذاریِ لیستینگ (کف/سقف/دفعاتِ روزانه) ─────────────
def test_listing_order_limits_roundtrip(as_distributor, db):
    it = _make_item(db, "LIM-1", "کالای محدود")
    r = as_distributor.post(
        "/api/marketplace/distributor/listings",
        json={
            "kind": "single", "title": "محدود", "wholesale_price": 1000, "item_id": str(it.id),
            "min_order_qty": 5, "max_order_qty": 20, "daily_order_limit": 3,
        },
    )
    assert r.status_code == 201, r.text
    b = r.json()
    assert float(b["min_order_qty"]) == 5 and float(b["max_order_qty"]) == 20 and b["daily_order_limit"] == 3
    # حداکثر < حداقل → ۴۲۲.
    bad = as_distributor.post(
        "/api/marketplace/distributor/listings",
        json={"kind": "single", "title": "x", "wholesale_price": 1, "item_id": str(it.id), "min_order_qty": 10, "max_order_qty": 5},
    )
    assert bad.status_code == 422


def test_place_order_enforces_min_max_qty(as_retailer, distributor_tenant, db):
    did = distributor_tenant
    listing = db.query(MarketplaceListing).filter(MarketplaceListing.distributor_tenant_id == did).first()
    listing.min_order_qty = 5
    listing.max_order_qty = 20
    db.flush()
    _approve(db, did, _primary_id(db))

    def place(q):
        return as_retailer.post(
            "/api/marketplace/retailer/orders",
            json={"distributor_tenant_id": str(did), "lines": [{"listing_id": str(listing.id), "qty": q}]},
        )

    assert place(3).status_code == 400   # زیرِ حداقل
    assert place(25).status_code == 400  # بالای حداکثر
    assert place(10).status_code == 201  # مجاز


def test_place_order_enforces_daily_order_limit(as_retailer, distributor_tenant, db):
    did = distributor_tenant
    listing = db.query(MarketplaceListing).filter(MarketplaceListing.distributor_tenant_id == did).first()
    listing.daily_order_limit = 2
    db.flush()
    _approve(db, did, _primary_id(db))

    def place():
        return as_retailer.post(
            "/api/marketplace/retailer/orders",
            json={"distributor_tenant_id": str(did), "lines": [{"listing_id": str(listing.id), "qty": 1}]},
        )

    assert place().status_code == 201
    assert place().status_code == 201
    assert place().status_code == 400  # سومین سفارشِ امروز → عبور از سقفِ روزانه


# ── تقسیمِ نقد/اعتباری هنگام تأیید ──────────────────────────────────────
def test_confirm_with_cash_split_records_treasury(as_distributor, retailer_tenant, db, user):
    primary_id = _primary_id(db)
    retailer_id = retailer_tenant
    db.add(MarketplaceSettings(distributor_tenant_id=primary_id, is_active=True))
    item = _make_item(db, "CASH-1", "کالای نقد")
    main_wh = db.query(Warehouse).filter(Warehouse.code == "MAIN").one()
    inventory_service.post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=date.today(),
            warehouse_id=main_wh.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(100), unit_cost=Decimal(5000))],
        ),
        user,
    )
    listing = MarketplaceListing(
        distributor_tenant_id=primary_id, kind="single", title="نقد عمده",
        unit="عدد", wholesale_price=8000, is_published=True, distributor_item_id=item.id,
    )
    listing.components.append(MarketplaceListingComponent(distributor_item_id=item.id, item_name="کالای نقد", qty=1))
    db.add(listing)
    db.flush()
    _approve(db, primary_id, retailer_id)

    order = svc.place_order(
        db, retailer_id, OrderPlaceIn(distributor_tenant_id=primary_id, lines=[OrderLineIn(listing_id=listing.id, qty=Decimal(10))])
    )
    assert Decimal(order.total) == Decimal(80000)

    # تأیید با ۲۵٪ نقد → ۲۰٬۰۰۰ نقد، بقیه اعتباری.
    r = as_distributor.post(f"/api/marketplace/distributor/orders/{order.id}/confirm", json={"cash_percent": 25})
    assert r.status_code == 200, r.text
    assert Decimal(r.json()["cash_amount"]) == Decimal(20000)

    # سمتِ پخش‌کننده: سندِ دریافتِ نقدِ ۲۰٬۰۰۰.
    with tenant_scope(db, primary_id):
        receipts = db.query(TreasuryTransaction).filter(TreasuryTransaction.type == "receipt").all()
        assert any(Decimal(t.amount) == Decimal(20000) for t in receipts)
    # سمتِ فروشگاه: سندِ پرداختِ نقدِ ۲۰٬۰۰۰.
    with tenant_scope(db, retailer_id):
        payments = db.query(TreasuryTransaction).filter(TreasuryTransaction.type == "payment").all()
        assert any(Decimal(t.amount) == Decimal(20000) for t in payments)


def test_confirm_full_credit_records_no_treasury(as_distributor, retailer_tenant, db, user):
    # ۰٪ نقد (پیش‌فرض، بدونِ بدنه) → هیچ سندِ خزانه‌ای، cash_amount صفر.
    primary_id = _primary_id(db)
    retailer_id = retailer_tenant
    db.add(MarketplaceSettings(distributor_tenant_id=primary_id, is_active=True))
    item = _make_item(db, "CRED-1", "کالای اعتباری")
    main_wh = db.query(Warehouse).filter(Warehouse.code == "MAIN").one()
    inventory_service.post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=date.today(), warehouse_id=main_wh.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(20), unit_cost=Decimal(1000))],
        ),
        user,
    )
    listing = MarketplaceListing(
        distributor_tenant_id=primary_id, kind="single", title="اعتباری عمده",
        unit="عدد", wholesale_price=3000, is_published=True, distributor_item_id=item.id,
    )
    listing.components.append(MarketplaceListingComponent(distributor_item_id=item.id, item_name="کالای اعتباری", qty=1))
    db.add(listing)
    db.flush()
    _approve(db, primary_id, retailer_id)
    order = svc.place_order(
        db, retailer_id, OrderPlaceIn(distributor_tenant_id=primary_id, lines=[OrderLineIn(listing_id=listing.id, qty=Decimal(2))])
    )
    r = as_distributor.post(f"/api/marketplace/distributor/orders/{order.id}/confirm")  # بدونِ بدنه
    assert r.status_code == 200, r.text
    assert Decimal(r.json()["cash_amount"]) == Decimal(0)
    with tenant_scope(db, primary_id):
        assert db.query(TreasuryTransaction).count() == 0


def test_placing_fails_without_distributor_stock(as_distributor, retailer_tenant, db):
    """**این تست عمداً عوض شد.** پیش از این ادعا می‌کرد سفارش ثبت می‌شود و فقط
    *تأیید* شکست می‌خورد — یعنی رفتارِ باگ‌دار را قانونی می‌کرد.

    `place_order` اتصال، صنف، کف/سقفِ تعداد و سقفِ روزانه را می‌سنجید و انبارِ
    پخش‌کننده را **هرگز**. نتیجه: فروشگاه سفارشی می‌داد که فکر می‌کرد ثبت شده و
    روزِ بعد رد می‌شد. حالا همان‌جا رد می‌شود، با عددِ «قابلِ سفارش» در پیام.
    """

    primary_id = _primary_id(db)
    retailer_id = retailer_tenant
    db.add(MarketplaceSettings(distributor_tenant_id=primary_id, is_active=True))
    item = _make_item(db, "DIST-NOSTOCK", "بی‌موجودی")  # هیچ موجودی‌ای ندارد
    listing = MarketplaceListing(
        distributor_tenant_id=primary_id, kind="single", title="بی‌موجودی عمده",
        unit="عدد", wholesale_price=5000, is_published=True, distributor_item_id=item.id,
    )
    listing.components.append(MarketplaceListingComponent(distributor_item_id=item.id, item_name="بی‌موجودی", qty=1))
    db.add(listing)
    db.flush()
    _approve(db, primary_id, retailer_id)
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as err:
        svc.place_order(
            db, retailer_id,
            OrderPlaceIn(distributor_tenant_id=primary_id, lines=[OrderLineIn(listing_id=listing.id, qty=Decimal(5))]),
        )
    assert err.value.status_code == 400
    #: پیام عنوانِ **لیستینگ** را می‌گوید، نه نامِ کالای داخلیِ پخش‌کننده —
    #: فروشگاه آن نام را ندیده و نباید ببیند.
    assert "بی‌موجودی عمده" in err.value.detail
    assert "قابلِ سفارش" in err.value.detail


def test_distributor_rejects_placed_order_and_guards(as_distributor, db):
    primary_id = _primary_id(db)
    retailer = _bare_tenant(db, "retailer", "فروشگاهِ ج")
    order = MarketplaceOrder(
        distributor_tenant_id=primary_id, retailer_tenant_id=retailer.id, order_number=1,
        status="placed", settlement_mode="credit", payment_status="unpaid", subtotal=1000, total=1000,
    )
    db.add(order)
    db.flush()

    r = as_distributor.post(f"/api/marketplace/distributor/orders/{order.id}/reject")
    assert r.status_code == 200 and r.json()["status"] == "rejected"

    # سفارشِ ردشده قابلِ تأیید نیست → ۴۰۰.
    assert as_distributor.post(f"/api/marketplace/distributor/orders/{order.id}/confirm").status_code == 400

    # سفارشِ پخش‌کننده‌ی دیگر → ۴۰۴.
    foreign = MarketplaceOrder(
        distributor_tenant_id=_bare_tenant(db, "distributor").id, retailer_tenant_id=retailer.id, order_number=1,
        status="placed", settlement_mode="credit", payment_status="unpaid", subtotal=0, total=0,
    )
    db.add(foreign)
    db.flush()
    assert as_distributor.post(f"/api/marketplace/distributor/orders/{foreign.id}/reject").status_code == 404


# ── M5: تسویه‌ی آنلاین ─────────────────────────────────────────────────
@pytest.fixture
def mock_gateway(monkeypatch):
    """تماس‌های شبکه‌ی درگاه را mock می‌کند: start موفق با authority، verify موفق با ref."""
    from app.services import payment_providers

    def fake_post(url, *, json=None, data=None, headers=None, raise_for_status=True):
        if "request.json" in url:
            return {"data": {"authority": "AUTH123", "code": 100}}
        if "verify.json" in url:
            return {"data": {"code": 100, "ref_id": "REF-9"}}
        return {}

    monkeypatch.setattr(payment_providers, "_post", fake_post)


def test_online_payment_settles_two_sided(client, retailer_tenant, db, user, mock_gateway):
    primary_id = _primary_id(db)
    retailer_id = retailer_tenant

    # پخش‌کننده‌ی آنلاین: درگاهِ فعال + کالا + موجودی + لیستینگِ منتشرشده.
    db.add(MarketplaceSettings(distributor_tenant_id=primary_id, is_active=True, settlement_mode="online"))
    db.add(PaymentGateway(provider="zarinpal", merchant_id="M-TEST", is_active=True))
    item = _make_item(db, "ONL-1", "کالای آنلاین")
    main_wh = db.query(Warehouse).filter(Warehouse.code == "MAIN").one()
    inventory_service.post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=date.today(),
            warehouse_id=main_wh.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(50), unit_cost=Decimal(3000))],
        ),
        user,
    )
    listing = MarketplaceListing(
        distributor_tenant_id=primary_id, kind="single", title="آنلاین عمده",
        unit="عدد", wholesale_price=7000, is_published=True, distributor_item_id=item.id,
    )
    listing.components.append(MarketplaceListingComponent(distributor_item_id=item.id, item_name="کالای آنلاین", qty=1))
    db.add(listing)
    db.flush()
    _approve(db, primary_id, retailer_id)

    order = svc.place_order(
        db, retailer_id, OrderPlaceIn(distributor_tenant_id=primary_id, lines=[OrderLineIn(listing_id=listing.id, qty=Decimal(4))])
    )
    assert order.settlement_mode == "online"
    assert Decimal(order.total) == Decimal(28000)  # ۷٬۰۰۰ × ۴

    # شروعِ پرداخت (درگاهِ mock).
    url = svc.start_order_payment(db, order, "http://cb.local")
    assert url and order.payment_authority == "AUTH123" and order.payment_provider == "zarinpal"

    # callbackِ عمومی → verify + نهایی‌سازی + تسویه.
    cb = f"/api/marketplace/pay/callback?order={order.id}&provider=zarinpal&Authority=AUTH123&Status=OK"
    r = client.get(cb, follow_redirects=False)
    assert r.status_code == 303 and "mp_pay=ok" in r.headers["location"]

    # سفارش تأیید و پرداخت‌شده.
    assert order.status == "confirmed"
    assert order.payment_status == "paid"
    assert order.payment_ref == "REF-9"
    assert order.distributor_sales_invoice_id and order.retailer_purchase_invoice_id

    link = (
        db.query(MarketplaceItemLink)
        .filter(MarketplaceItemLink.retailer_tenant_id == retailer_id, MarketplaceItemLink.distributor_item_id == item.id)
        .one()
    )
    # سمتِ فروشگاه: انبار +۴، یک فاکتورِ خرید، یک پرداختِ خزانه (AP تسویه شد).
    with tenant_scope(db, retailer_id):
        assert inventory_service.get_total_stock_qty(db, link.retailer_item_id) == Decimal(4)
        assert db.query(PurchaseInvoice).count() == 1
        assert db.query(TreasuryTransaction).filter(TreasuryTransaction.type == "payment").count() == 1
    # سمتِ پخش‌کننده: انبار ۵۰−۴=۴۶، یک دریافتِ خزانه (AR تسویه شد).
    with tenant_scope(db, primary_id):
        assert inventory_service.get_stock_qty(db, item.id, main_wh.id) == Decimal(46)
        assert db.query(TreasuryTransaction).filter(TreasuryTransaction.type == "receipt").count() == 1

    # callbackِ دوباره idempotent است — فاکتور/تسویه‌ی دوم نمی‌سازد.
    r2 = client.get(cb, follow_redirects=False)
    assert r2.status_code == 303 and "mp_pay=ok" in r2.headers["location"]
    with tenant_scope(db, retailer_id):
        assert db.query(TreasuryTransaction).filter(TreasuryTransaction.type == "payment").count() == 1


def test_online_callback_failed_signal_leaves_unpaid(client, retailer_tenant, db, user, mock_gateway):
    primary_id = _primary_id(db)
    retailer_id = retailer_tenant
    db.add(MarketplaceSettings(distributor_tenant_id=primary_id, is_active=True, settlement_mode="online"))
    db.add(PaymentGateway(provider="zarinpal", merchant_id="M-TEST", is_active=True))
    item = _make_item(db, "ONL-2", "کالای آنلاین ۲")
    main_wh = db.query(Warehouse).filter(Warehouse.code == "MAIN").one()
    inventory_service.post_purchase_invoice(
        db,
        PurchaseInvoiceIn(invoice_date=date.today(), warehouse_id=main_wh.id,
                          lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(10), unit_cost=Decimal(1000))]),
        user,
    )
    listing = MarketplaceListing(distributor_tenant_id=primary_id, kind="single", title="آنلاین ۲",
                                 unit="عدد", wholesale_price=5000, is_published=True, distributor_item_id=item.id)
    listing.components.append(MarketplaceListingComponent(distributor_item_id=item.id, item_name="کالای آنلاین ۲", qty=1))
    db.add(listing)
    db.flush()
    _approve(db, primary_id, retailer_id)
    order = svc.place_order(db, retailer_id, OrderPlaceIn(distributor_tenant_id=primary_id, lines=[OrderLineIn(listing_id=listing.id, qty=Decimal(1))]))
    svc.start_order_payment(db, order, "http://cb.local")

    # کاربر پرداخت را لغو کرد (Status=NOK) → سفارش پرداخت‌نشده می‌ماند و تأیید نمی‌شود.
    cb = f"/api/marketplace/pay/callback?order={order.id}&provider=zarinpal&Authority=AUTH123&Status=NOK"
    r = client.get(cb, follow_redirects=False)
    assert r.status_code == 303 and "mp_pay=failed" in r.headers["location"]
    assert order.status == "placed" and order.payment_status == "unpaid"


def test_confirm_blocks_unpaid_online_order(as_distributor, db):
    primary_id = _primary_id(db)
    retailer = _bare_tenant(db, "retailer")
    order = MarketplaceOrder(
        distributor_tenant_id=primary_id, retailer_tenant_id=retailer.id, order_number=1,
        status="placed", settlement_mode="online", payment_status="unpaid", subtotal=1000, total=1000,
    )
    db.add(order)
    db.flush()
    # سفارشِ آنلاینِ پرداخت‌نشده را پخش‌کننده نمی‌تواند دستی تأیید کند → ۴۰۰.
    assert as_distributor.post(f"/api/marketplace/distributor/orders/{order.id}/confirm").status_code == 400


def test_pay_rejected_for_credit_order(as_retailer, distributor_tenant, db):
    did = distributor_tenant  # تنظیماتش credit است
    listing = db.query(MarketplaceListing).filter(MarketplaceListing.distributor_tenant_id == did).first()
    _approve(db, did, _primary_id(db))
    placed = as_retailer.post(
        "/api/marketplace/retailer/orders", json={"distributor_tenant_id": str(did), "lines": [{"listing_id": str(listing.id), "qty": 1}]}
    )
    assert placed.status_code == 201
    oid = placed.json()["id"]
    # سفارشِ اعتباری پرداختِ آنلاین ندارد → ۴۰۰.
    assert as_retailer.post(f"/api/marketplace/retailer/orders/{oid}/pay").status_code == 400


# ── M6: ایزولاسیونِ میان‌مستأجری ───────────────────────────────────────
# جدول‌های بازار سراسری‌اند (بدونِ RLS)، پس جداسازی فقط با فیلترِ صریحِ کد است.
# این‌ها تضمین می‌کنند هیچ مستأجری داده/عملِ رابطه‌ی دیگری را نبیند/دست‌کاری نکند.
def _order(db, distributor_id, retailer_id, number, **kw):
    o = MarketplaceOrder(
        distributor_tenant_id=distributor_id, retailer_tenant_id=retailer_id, order_number=number,
        status=kw.get("status", "placed"), settlement_mode=kw.get("settlement_mode", "credit"),
        payment_status=kw.get("payment_status", "unpaid"), subtotal=kw.get("total", 100), total=kw.get("total", 100),
    )
    db.add(o)
    db.flush()
    return o


def test_retailer_sees_only_own_orders(as_retailer, db):
    primary_id = _primary_id(db)
    dist = _bare_tenant(db, "distributor")
    other_retailer = _bare_tenant(db, "retailer")
    mine = _order(db, dist.id, primary_id, 1)
    theirs = _order(db, dist.id, other_retailer.id, 2)

    ids = {o["id"] for o in as_retailer.get("/api/marketplace/retailer/orders").json()}
    assert str(mine.id) in ids
    assert str(theirs.id) not in ids, "سفارشِ فروشگاهِ دیگری دیده شد"


def test_distributor_sees_only_own_orders(as_distributor, db):
    primary_id = _primary_id(db)
    retailer = _bare_tenant(db, "retailer")
    other_dist = _bare_tenant(db, "distributor")
    mine = _order(db, primary_id, retailer.id, 1)
    theirs = _order(db, other_dist.id, retailer.id, 2)

    ids = {o["id"] for o in as_distributor.get("/api/marketplace/distributor/orders").json()}
    assert str(mine.id) in ids
    assert str(theirs.id) not in ids, "سفارشِ پخش‌کننده‌ی دیگری دیده شد"


def test_retailer_cannot_pay_foreign_order(as_retailer, db):
    dist = _bare_tenant(db, "distributor")
    other_retailer = _bare_tenant(db, "retailer")
    theirs = _order(db, dist.id, other_retailer.id, 1, settlement_mode="online")
    # سفارشِ فروشگاهِ دیگری قابلِ پرداخت/دیدن نیست → ۴۰۴.
    assert as_retailer.post(f"/api/marketplace/retailer/orders/{theirs.id}/pay").status_code == 404


def test_distributor_cannot_confirm_or_reject_foreign_order(as_distributor, db):
    retailer = _bare_tenant(db, "retailer")
    other_dist = _bare_tenant(db, "distributor")
    theirs = _order(db, other_dist.id, retailer.id, 1)
    assert as_distributor.post(f"/api/marketplace/distributor/orders/{theirs.id}/confirm").status_code == 404
    assert as_distributor.post(f"/api/marketplace/distributor/orders/{theirs.id}/reject").status_code == 404


def test_catalog_only_from_approved_distributors(as_retailer, db):
    primary_id = _primary_id(db)
    d1 = _bare_tenant(db, "distributor", "پخش ۱")
    d2 = _bare_tenant(db, "distributor", "پخش ۲")
    for d, title in ((d1, "کالای ۱"), (d2, "کالای ۲")):
        db.add(MarketplaceSettings(distributor_tenant_id=d.id, is_active=True))
        db.add(
            MarketplaceListing(
                distributor_tenant_id=d.id, kind="single", title=title, unit="عدد",
                wholesale_price=1000, is_published=True, distributor_item_id=None,
            )
        )
    db.flush()
    _approve(db, d1.id, primary_id)  # فقط d1 تأیید شده

    catalog = as_retailer.get("/api/marketplace/retailer/catalog").json()
    dids = {c["distributor_tenant_id"] for c in catalog}
    assert str(d1.id) in dids
    assert str(d2.id) not in dids, "کاتالوگِ پخش‌کننده‌ی تأییدنشده دیده شد"
    # فیلترِ صریح به پخش‌کننده‌ی تأییدنشده → ۴۰۳.
    assert as_retailer.get(f"/api/marketplace/retailer/catalog?distributor_id={d2.id}").status_code == 403


def test_retailer_cannot_place_order_for_unapproved_listing(as_retailer, db):
    primary_id = _primary_id(db)
    # پخش‌کننده‌ی تأییدنشده با لیستینگِ منتشرشده.
    d = _bare_tenant(db, "distributor")
    db.add(MarketplaceSettings(distributor_tenant_id=d.id, is_active=True))
    listing = MarketplaceListing(
        distributor_tenant_id=d.id, kind="single", title="کالا", unit="عدد",
        wholesale_price=1000, is_published=True, distributor_item_id=None,
    )
    db.add(listing)
    db.flush()
    # بدونِ اتصالِ approved، سفارش رد می‌شود → ۴۰۳.
    r = as_retailer.post(
        "/api/marketplace/retailer/orders",
        json={"distributor_tenant_id": str(d.id), "lines": [{"listing_id": str(listing.id), "qty": 1}]},
    )
    assert r.status_code == 403


# ══════════ کمیسیونِ پلتفرم (۲٪) ══════════════════════════════════════════
@pytest.fixture
def super_client(client, user, monkeypatch):
    """همان کلاینت، ولی کاربرش سوپرادمین می‌شود (ایمیلِ کاربر در فهرست)."""
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "super_admin_emails", user.email)
    return client


def _confirm_sale(as_distributor, retailer_id, db, user, wholesale=8000, qty=10):
    """پخش‌کننده‌ی PRIMARY را آماده و یک سفارش را قطعی می‌کند؛ (order, primary_id) را می‌دهد."""
    primary_id = _primary_id(db)
    if db.query(MarketplaceSettings).filter_by(distributor_tenant_id=primary_id).first() is None:
        db.add(MarketplaceSettings(distributor_tenant_id=primary_id, display_name="پخشِ اصلی", is_active=True))
    item = _make_item(db, f"DIST-{uuid.uuid4().hex[:6]}", "کالای پخش")
    main_wh = db.query(Warehouse).filter(Warehouse.code == "MAIN").one()
    inventory_service.post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=date.today(),
            warehouse_id=main_wh.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(1000), unit_cost=Decimal(1000))],
        ),
        user,
    )
    listing = MarketplaceListing(
        distributor_tenant_id=primary_id,
        kind="single",
        title="کالای پخش عمده",
        unit="عدد",
        wholesale_price=wholesale,
        is_published=True,
        distributor_item_id=item.id,
    )
    listing.components.append(MarketplaceListingComponent(distributor_item_id=item.id, item_name="کالای پخش", qty=1))
    db.add(listing)
    db.flush()
    _approve(db, primary_id, retailer_id)
    order = svc.place_order(
        db,
        retailer_id,
        OrderPlaceIn(distributor_tenant_id=primary_id, lines=[OrderLineIn(listing_id=listing.id, qty=Decimal(qty))]),
    )
    r = as_distributor.post(f"/api/marketplace/distributor/orders/{order.id}/confirm")
    assert r.status_code == 200, r.text
    return order, primary_id


def test_commission_recorded_at_2pct_on_confirm(as_distributor, retailer_tenant, db, user):
    order, primary_id = _confirm_sale(as_distributor, retailer_tenant, db, user, wholesale=8000, qty=10)
    rows = db.query(MarketplaceCommission).filter_by(order_id=order.id).all()
    assert len(rows) == 1
    c = rows[0]
    assert Decimal(c.base_amount) == Decimal(80000)  # ۸٬۰۰۰ × ۱۰
    assert Decimal(c.amount) == Decimal(1600)  # ۲٪
    assert Decimal(c.rate) == Decimal("0.02")
    assert c.status == "pending"
    assert c.distributor_tenant_id == primary_id
    assert c.period and len(c.period) == 7


def test_commission_idempotent_on_reconfirm(as_distributor, retailer_tenant, db, user):
    order, _ = _confirm_sale(as_distributor, retailer_tenant, db, user)
    # تأییدِ دوباره idempotent است → رکوردِ دومِ کمیسیون ساخته نشود.
    as_distributor.post(f"/api/marketplace/distributor/orders/{order.id}/confirm")
    assert db.query(MarketplaceCommission).filter_by(order_id=order.id).count() == 1


def test_commission_summary_overview_and_settle(as_distributor, retailer_tenant, db, user):
    order, primary_id = _confirm_sale(as_distributor, retailer_tenant, db, user, wholesale=8000, qty=10)
    period = db.query(MarketplaceCommission).filter_by(order_id=order.id).one().period

    summary = svc.commission_summary(db)
    row = next(r for r in summary if r["distributor_tenant_id"] == primary_id and r["period"] == period)
    assert row["total_amount"] == 1600
    assert row["pending_amount"] == 1600
    assert row["status"] == "pending"

    ov = svc.commission_overview(db)
    assert ov["pending_amount"] >= 1600
    assert ov["rate"] == 0.02

    res = svc.settle_commission_period(db, primary_id, period, note="واریز شبا ۱۲۳")
    assert res["amount"] == 1600 and res["count"] == 1
    settled = db.query(MarketplaceCommission).filter_by(order_id=order.id).one()
    assert settled.status == "settled" and settled.settled_at is not None and settled.settle_note == "واریز شبا ۱۲۳"

    # بعد از تسویه، summary همان ماه را settled نشان دهد و pending صفر شود.
    row2 = next(r for r in svc.commission_summary(db) if r["distributor_tenant_id"] == primary_id and r["period"] == period)
    assert row2["pending_amount"] == 0 and row2["settled_amount"] == 1600 and row2["status"] == "settled"


def test_settle_empty_period_404(as_distributor, retailer_tenant, db, user):
    _confirm_sale(as_distributor, retailer_tenant, db, user)
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as ei:
        svc.settle_commission_period(db, _primary_id(db), "1300-01", note="")
    assert ei.value.status_code == 404


def test_admin_commission_endpoints_require_super_admin(as_distributor, retailer_tenant, db, user, client):
    _confirm_sale(as_distributor, retailer_tenant, db, user)
    # کاربرِ عادی (نه سوپرادمین) → ۴۰۳ روی همه‌ی اندپوینت‌های admin.
    assert client.get("/api/marketplace/admin/commissions").status_code == 403
    assert client.get("/api/marketplace/admin/commissions/overview").status_code == 403
    assert client.post("/api/marketplace/admin/commissions/settle", json={}).status_code in (403, 422)


# ── انتقالِ خودکارِ بارکد از پخش‌کننده به فروشگاه هنگامِ تأییدِ سفارش ─────────
def _confirm_sale_with_barcode(as_distributor, retailer_id, db, user, barcode):
    primary_id = _primary_id(db)
    if db.query(MarketplaceSettings).filter_by(distributor_tenant_id=primary_id).first() is None:
        db.add(MarketplaceSettings(distributor_tenant_id=primary_id, display_name="پخشِ اصلی", is_active=True))
    item = _make_item(db, f"DIST-{uuid.uuid4().hex[:6]}", "کالای بارکددارِ پخش")
    item.barcode = barcode  # پخش‌کننده بارکد را روی کالای خودش دارد
    db.flush()
    main_wh = db.query(Warehouse).filter(Warehouse.code == "MAIN").one()
    inventory_service.post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=date.today(),
            warehouse_id=main_wh.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(100), unit_cost=Decimal(1000))],
        ),
        user,
    )
    listing = MarketplaceListing(
        distributor_tenant_id=primary_id, kind="single", title="بارکددار", unit="عدد",
        wholesale_price=8000, is_published=True, distributor_item_id=item.id,
    )
    listing.components.append(MarketplaceListingComponent(distributor_item_id=item.id, item_name="کالای بارکددار", qty=1))
    db.add(listing)
    db.flush()
    _approve(db, primary_id, retailer_id)
    order = svc.place_order(
        db, retailer_id, OrderPlaceIn(distributor_tenant_id=primary_id, lines=[OrderLineIn(listing_id=listing.id, qty=Decimal(3))])
    )
    r = as_distributor.post(f"/api/marketplace/distributor/orders/{order.id}/confirm")
    assert r.status_code == 200, r.text
    return item, retailer_id


def test_barcode_carried_to_retailer_item_on_confirm(as_distributor, retailer_tenant, db, user):
    """بارکدِ کالای پخش‌کننده باید خودکار روی کالای متناظرِ فروشگاه بنشیند (بدونِ تنظیمِ دستی)."""
    dist_item, retailer_id = _confirm_sale_with_barcode(as_distributor, retailer_tenant, db, user, "6267777777779")
    link = (
        db.query(MarketplaceItemLink)
        .filter(MarketplaceItemLink.retailer_tenant_id == retailer_id, MarketplaceItemLink.distributor_item_id == dist_item.id)
        .one()
    )
    with tenant_scope(db, retailer_id):
        ret_item = db.get(Item, link.retailer_item_id)
        assert ret_item.barcode == "6267777777779"


def test_barcode_carry_skipped_on_collision(as_distributor, retailer_tenant, db, user):
    """اگر همان بارکد در انبارِ فروشگاه قبلاً برای کالای دیگری باشد، انتقال انجام نمی‌شود (تصادمِ یکتایی)."""
    retailer_id = retailer_tenant
    primary_id = _primary_id(db)
    # فروشگاه از قبل کالایی با همان بارکد دارد.
    with tenant_scope(db, retailer_id):
        existing = Item(sku="RET-OWN", name="کالای خودِ فروشگاه", unit="عدد", sales_price=0, barcode="6268888888886")
        db.add(existing)
        db.flush()
    # tenant_scope بایندینگِ نشست را بازنمی‌گرداند؛ صریحاً PRIMARY را برمی‌گردانیم تا
    # کالای پخش‌کننده در دفترِ خودش ساخته شود (نه در دفترِ فروشگاه).
    bind_session_tenant(db, primary_id)
    apply_tenant_to_transaction(db, primary_id)
    dist_item, _ = _confirm_sale_with_barcode(as_distributor, retailer_id, db, user, "6268888888886")
    link = (
        db.query(MarketplaceItemLink)
        .filter(MarketplaceItemLink.retailer_tenant_id == retailer_id, MarketplaceItemLink.distributor_item_id == dist_item.id)
        .one()
    )
    with tenant_scope(db, retailer_id):
        ret_item = db.get(Item, link.retailer_item_id)
        assert ret_item.barcode is None  # تصادم → بارکد منتقل نشد، ولی سفارش قطعی شد


def test_admin_can_view_and_settle_via_endpoint(as_distributor, retailer_tenant, db, user, super_client):
    order, primary_id = _confirm_sale(as_distributor, retailer_tenant, db, user, wholesale=8000, qty=10)
    period = db.query(MarketplaceCommission).filter_by(order_id=order.id).one().period

    ov = super_client.get("/api/marketplace/admin/commissions/overview")
    assert ov.status_code == 200 and ov.json()["pending_amount"] >= 1600

    lst = super_client.get("/api/marketplace/admin/commissions").json()
    assert any(r["period"] == period and r["total_amount"] == 1600 for r in lst)

    s = super_client.post(
        "/api/marketplace/admin/commissions/settle",
        json={"distributor_tenant_id": str(primary_id), "period": period, "note": "واریز نقدی"},
    )
    assert s.status_code == 200, s.text
    assert s.json()["amount"] == 1600
    assert db.query(MarketplaceCommission).filter_by(order_id=order.id).one().status == "settled"


def test_distributor_sees_only_own_commissions(as_distributor, retailer_tenant, db, user, distributor_tenant):
    order, primary_id = _confirm_sale(as_distributor, retailer_tenant, db, user)
    # کمیسیونِ یک پخش‌کننده‌ی دیگر (روی یک سفارشِ جدا) — نباید در صورتِ PRIMARY بیاید.
    other = distributor_tenant
    other_order = MarketplaceOrder(
        distributor_tenant_id=other,
        retailer_tenant_id=retailer_tenant,
        order_number=999,
        status="confirmed",
        subtotal=Decimal(500000),
        total=Decimal(500000),
    )
    db.add(other_order)
    db.flush()
    db.add(
        MarketplaceCommission(
            order_id=other_order.id,
            distributor_tenant_id=other,
            period="1405-01",
            base_amount=Decimal(500000),
            rate=Decimal("0.02"),
            amount=Decimal(10000),
            status="pending",
        )
    )
    db.flush()
    r = as_distributor.get("/api/marketplace/distributor/commissions")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body, "پخش‌کننده باید صورتِ کمیسیونِ خودش را ببیند"
    assert all(row["distributor_tenant_id"] == str(primary_id) for row in body)
    assert not any(row["distributor_tenant_id"] == str(other) for row in body)


# ── گفتگوی اتصال (فروشگاه↔پخش‌کننده) ──────────────────────────────────
def test_chat_send_and_list(as_distributor, db, retailer_tenant):
    conn = _connection(db, _primary_id(db), retailer_tenant, "approved")
    r = as_distributor.post(
        f"/api/marketplace/connections/{conn.id}/messages",
        json={"body": "سلام، سفارش آماده است"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["sender_role"] == "distributor"

    r = as_distributor.get(f"/api/marketplace/connections/{conn.id}/messages")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["my_role"] == "distributor"
    assert [m["body"] for m in body["messages"]] == ["سلام، سفارش آماده است"]


def test_chat_empty_body_rejected(as_distributor, db, retailer_tenant):
    conn = _connection(db, _primary_id(db), retailer_tenant, "approved")
    r = as_distributor.post(
        f"/api/marketplace/connections/{conn.id}/messages", json={"body": "   "}
    )
    assert r.status_code == 422


def test_chat_only_approved_can_talk(as_distributor, db, retailer_tenant):
    conn = _connection(db, _primary_id(db), retailer_tenant, "pending")
    assert as_distributor.get(f"/api/marketplace/connections/{conn.id}/messages").status_code == 409
    assert (
        as_distributor.post(
            f"/api/marketplace/connections/{conn.id}/messages", json={"body": "x"}
        ).status_code
        == 409
    )


def test_chat_isolation_third_party(as_distributor, db):
    # اتصالِ بینِ دو مستأجرِ دیگر؛ پخش‌کننده‌ی primary عضوِ آن نیست → ۴۰۴ (نه افشای وجود).
    other_d = _bare_tenant(db, "distributor")
    other_r = _bare_tenant(db, "retailer")
    conn = _connection(db, other_d.id, other_r.id, "approved")
    assert as_distributor.get(f"/api/marketplace/connections/{conn.id}/messages").status_code == 404
    assert (
        as_distributor.post(
            f"/api/marketplace/connections/{conn.id}/messages", json={"body": "x"}
        ).status_code
        == 404
    )


def test_chat_unread_then_marked_read(as_distributor, db, retailer_tenant):
    conn = _connection(db, _primary_id(db), retailer_tenant, "approved")
    # فروشگاه پیام می‌دهد (شبیه‌سازی با سرویس، چون clientِ تست فقط primary است).
    svc.post_message(
        db, conn, sender_tenant_id=retailer_tenant, sender_role="retailer",
        sender_user_id=None, body="کِی می‌رسه؟",
    )
    conns = as_distributor.get("/api/marketplace/distributor/connections").json()
    row = next(c for c in conns if c["id"] == str(conn.id))
    assert row["unread_count"] == 1
    assert row["last_message_preview"] == "کِی می‌رسه؟"

    # باز کردنِ رشته → خوانده می‌شود.
    as_distributor.get(f"/api/marketplace/connections/{conn.id}/messages")
    conns = as_distributor.get("/api/marketplace/distributor/connections").json()
    row = next(c for c in conns if c["id"] == str(conn.id))
    assert row["unread_count"] == 0


def test_chat_retailer_side(as_retailer, db, distributor_tenant):
    conn = _connection(db, distributor_tenant, _primary_id(db), "approved")
    r = as_retailer.post(
        f"/api/marketplace/connections/{conn.id}/messages", json={"body": "سفارش را ثبت کردم"}
    )
    assert r.status_code == 201, r.text
    assert r.json()["sender_role"] == "retailer"
    assert as_retailer.get(f"/api/marketplace/connections/{conn.id}/messages").json()["my_role"] == "retailer"


def test_marketplace_unread_endpoint(as_distributor, db, retailer_tenant):
    conn = _connection(db, _primary_id(db), retailer_tenant, "approved")
    assert as_distributor.get("/api/marketplace/unread").json() == 0
    svc.post_message(
        db, conn, sender_tenant_id=retailer_tenant, sender_role="retailer",
        sender_user_id=None, body="پیام",
    )
    assert as_distributor.get("/api/marketplace/unread").json() == 1


# ── گفتگوی زیرِ هر سفارش ──────────────────────────────────────────────
def test_order_chat_send_and_list(as_distributor, db, retailer_tenant):
    order = _order(db, _primary_id(db), retailer_tenant, 101)
    r = as_distributor.post(
        f"/api/marketplace/orders/{order.id}/messages", json={"body": "سفارش تأیید شد"}
    )
    assert r.status_code == 201, r.text
    assert r.json()["sender_role"] == "distributor"
    body = as_distributor.get(f"/api/marketplace/orders/{order.id}/messages").json()
    assert body["my_role"] == "distributor"
    assert [m["body"] for m in body["messages"]] == ["سفارش تأیید شد"]


def test_order_chat_works_regardless_of_status(as_distributor, db, retailer_tenant):
    # برخلافِ گفتگوی اتصال، رشته‌ی سفارش گیتِ وضعیت ندارد (حتی روی سفارشِ ردشده).
    order = _order(db, _primary_id(db), retailer_tenant, 102, status="rejected")
    assert as_distributor.get(f"/api/marketplace/orders/{order.id}/messages").status_code == 200
    assert as_distributor.post(
        f"/api/marketplace/orders/{order.id}/messages", json={"body": "چرا رد شد؟"}
    ).status_code == 201


def test_order_chat_isolation_third_party(as_distributor, db):
    other_d = _bare_tenant(db, "distributor")
    other_r = _bare_tenant(db, "retailer")
    order = _order(db, other_d.id, other_r.id, 103)
    assert as_distributor.get(f"/api/marketplace/orders/{order.id}/messages").status_code == 404
    assert as_distributor.post(
        f"/api/marketplace/orders/{order.id}/messages", json={"body": "x"}
    ).status_code == 404


def test_order_chat_unread_in_order_list(as_distributor, db, retailer_tenant):
    order = _order(db, _primary_id(db), retailer_tenant, 104)
    svc.post_order_message(
        db, order, sender_tenant_id=retailer_tenant, sender_role="retailer",
        sender_user_id=None, body="کِی ارسال می‌شه؟",
    )
    rows = as_distributor.get("/api/marketplace/distributor/orders").json()
    row = next(o for o in rows if o["id"] == str(order.id))
    assert row["unread_count"] == 1
    assert row["last_message_preview"] == "کِی ارسال می‌شه؟"
    # باز کردنِ رشته → خوانده می‌شود.
    as_distributor.get(f"/api/marketplace/orders/{order.id}/messages")
    rows = as_distributor.get("/api/marketplace/distributor/orders").json()
    row = next(o for o in rows if o["id"] == str(order.id))
    assert row["unread_count"] == 0


def test_unread_endpoint_includes_order_threads(as_distributor, db, retailer_tenant):
    order = _order(db, _primary_id(db), retailer_tenant, 105)
    assert as_distributor.get("/api/marketplace/unread").json() == 0
    svc.post_order_message(
        db, order, sender_tenant_id=retailer_tenant, sender_role="retailer",
        sender_user_id=None, body="پیامِ سفارش",
    )
    assert as_distributor.get("/api/marketplace/unread").json() == 1


# ── زونِ ارسال (پخش‌کننده) ──────────────────────────────────────────────
def test_zone_crud_and_assign(as_distributor, retailer_tenant, db):
    primary_id = _primary_id(db)
    retailer_id = retailer_tenant
    _approve(db, primary_id, retailer_id)

    # ساختِ زون
    r = as_distributor.post("/api/marketplace/distributor/zones", json={"name": "منطقهٔ شرق", "notes": "بازارِ بزرگ"})
    assert r.status_code == 201, r.text
    zone_id = r.json()["id"]
    assert r.json()["name"] == "منطقهٔ شرق"

    # نامِ تکراری → ۴۰۹
    assert as_distributor.post("/api/marketplace/distributor/zones", json={"name": "منطقهٔ شرق"}).status_code == 409

    # فهرست
    zones = as_distributor.get("/api/marketplace/distributor/zones").json()
    assert len(zones) == 1 and zones[0]["connection_count"] == 0

    # تخصیصِ اتصال به زون
    conn = db.query(MarketplaceConnection).filter(
        MarketplaceConnection.distributor_tenant_id == primary_id,
        MarketplaceConnection.retailer_tenant_id == retailer_id,
    ).one()
    r = as_distributor.post(f"/api/marketplace/distributor/connections/{conn.id}/zone", json={"zone_id": zone_id})
    assert r.status_code == 200, r.text
    assert r.json()["zone_id"] == zone_id and r.json()["zone_name"] == "منطقهٔ شرق"

    # حالا شمارشِ اتصالِ زون ۱ است
    zones = as_distributor.get("/api/marketplace/distributor/zones").json()
    assert zones[0]["connection_count"] == 1

    # ویرایش
    r = as_distributor.put(f"/api/marketplace/distributor/zones/{zone_id}", json={"name": "منطقهٔ غرب"})
    assert r.status_code == 200 and r.json()["name"] == "منطقهٔ غرب"

    # حذفِ زون → اتصال بدونِ زون می‌شود (SET NULL)
    assert as_distributor.delete(f"/api/marketplace/distributor/zones/{zone_id}").status_code == 204
    db.expire_all()
    conn2 = db.get(MarketplaceConnection, conn.id)
    assert conn2.zone_id is None


def test_zone_only_distributor(as_retailer):
    # حسابِ فروشگاه (standard→retailer) نباید به زون‌های پخش‌کننده دسترسی داشته باشد
    assert as_retailer.get("/api/marketplace/distributor/zones").status_code == 403


# ── قیمتِ مصرف‌کننده روی کاتالوگ + انتقال به بچ ──────────────────────────
def _confirm_with_consumer(as_distributor, retailer_id, db, user, wholesale=10000, consumer=14000, qty=10):
    primary_id = _primary_id(db)
    if db.query(MarketplaceSettings).filter_by(distributor_tenant_id=primary_id).first() is None:
        db.add(MarketplaceSettings(distributor_tenant_id=primary_id, display_name="پخشِ اصلی", is_active=True))
    item = _make_item(db, f"CP-{uuid.uuid4().hex[:6]}", "کالای قیمت‌دار")
    main_wh = db.query(Warehouse).filter(Warehouse.code == "MAIN").one()
    inventory_service.post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=date.today(), warehouse_id=main_wh.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(100), unit_cost=Decimal(wholesale))],
        ),
        user,
    )
    listing = MarketplaceListing(
        distributor_tenant_id=primary_id, kind="single", title="قیمت‌دار", unit="عدد",
        wholesale_price=wholesale, consumer_price=consumer, is_published=True, distributor_item_id=item.id,
    )
    listing.components.append(MarketplaceListingComponent(distributor_item_id=item.id, item_name="کالای قیمت‌دار", qty=1))
    db.add(listing)
    db.flush()
    _approve(db, primary_id, retailer_id)
    order = svc.place_order(
        db, retailer_id, OrderPlaceIn(distributor_tenant_id=primary_id, lines=[OrderLineIn(listing_id=listing.id, qty=Decimal(qty))])
    )
    r = as_distributor.post(f"/api/marketplace/distributor/orders/{order.id}/confirm")
    assert r.status_code == 200, r.text
    return item, listing, order, retailer_id


def test_consumer_price_on_catalog_and_batch(as_distributor, retailer_tenant, db, user):
    item, listing, order, retailer_id = _confirm_with_consumer(as_distributor, retailer_tenant, db, user)

    # روی کاتالوگ قیمتِ مصرف‌کننده دیده می‌شود (حاشیه‌ی سود)
    with tenant_scope(db, retailer_id):
        cat = svc.list_catalog(db, retailer_id)
    row = next(c for c in cat if c["id"] == listing.id)
    assert float(row["wholesale_price"]) == 10000 and float(row["consumer_price"]) == 14000

    # قیمتِ مصرف‌کننده خودکار روی بچِ فروشگاه نشست
    link = db.query(MarketplaceItemLink).filter(
        MarketplaceItemLink.retailer_tenant_id == retailer_id,
        MarketplaceItemLink.distributor_item_id == item.id,
    ).one()
    with tenant_scope(db, retailer_id):
        batch = db.query(StockBatch).filter(StockBatch.item_id == link.retailer_item_id).first()
        assert batch is not None
        assert float(batch.consumer_price) == 14000
        assert float(batch.unit_cost) == 10000  # قیمتِ خرید


# ── مرجوعیِ بازار (درخواستِ فروشگاه → تأییدِ پخش‌کننده) ───────────────────
def _confirm_for_return(as_distributor, retailer_id, db, user, wholesale=8000, qty=10):
    primary_id = _primary_id(db)
    if db.query(MarketplaceSettings).filter_by(distributor_tenant_id=primary_id).first() is None:
        db.add(MarketplaceSettings(distributor_tenant_id=primary_id, display_name="پخشِ اصلی", is_active=True))
    item = _make_item(db, f"RT-{uuid.uuid4().hex[:6]}", "کالای مرجوعی")
    main_wh = db.query(Warehouse).filter(Warehouse.code == "MAIN").one()
    inventory_service.post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=date.today(), warehouse_id=main_wh.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(1000), unit_cost=Decimal(5000))],
        ),
        user,
    )
    listing = MarketplaceListing(
        distributor_tenant_id=primary_id, kind="single", title="مرجوعی", unit="عدد",
        wholesale_price=wholesale, is_published=True, distributor_item_id=item.id,
    )
    listing.components.append(MarketplaceListingComponent(distributor_item_id=item.id, item_name="کالای مرجوعی", qty=1))
    db.add(listing)
    db.flush()
    _approve(db, primary_id, retailer_id)
    order = svc.place_order(
        db, retailer_id, OrderPlaceIn(distributor_tenant_id=primary_id, lines=[OrderLineIn(listing_id=listing.id, qty=Decimal(qty))])
    )
    r = as_distributor.post(f"/api/marketplace/distributor/orders/{order.id}/confirm")
    assert r.status_code == 200, r.text
    return item, order, main_wh, primary_id


def test_return_full_flow_two_sided(as_distributor, retailer_tenant, db, user):
    retailer_id = retailer_tenant
    item, order, main_wh, primary_id = _confirm_for_return(as_distributor, retailer_id, db, user, qty=10)

    # بعد از تأیید: انبارِ پخش‌کننده ۹۹۰، انبارِ فروشگاه ۱۰
    with tenant_scope(db, primary_id):
        assert inventory_service.get_stock_qty(db, item.id, main_wh.id) == Decimal(990)
    link = db.query(MarketplaceItemLink).filter(
        MarketplaceItemLink.retailer_tenant_id == retailer_id, MarketplaceItemLink.distributor_item_id == item.id,
    ).one()
    with tenant_scope(db, retailer_id):
        assert inventory_service.get_total_stock_qty(db, link.retailer_item_id) == Decimal(10)

    # فروشگاه درخواستِ مرجوعیِ ۴ تا می‌دهد (سطحِ سرویس؛ فروشگاه تنانتِ دیگری است)
    ret = svc.request_return(
        db, retailer_id,
        ReturnRequestIn(order_id=order.id, lines=[ReturnRequestLineIn(order_line_id=order.lines[0].id, qty=Decimal(4))], reason="معیوب"),
    )
    assert ret.status == "requested" and float(ret.total) == 32000  # ۸۰۰۰×۴

    # پخش‌کننده تأیید می‌کند
    r = as_distributor.post(f"/api/marketplace/distributor/returns/{ret.id}/approve")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"

    # دو طرفه اثر کرد: انبارِ پخش‌کننده ۹۹۴ (۴ برگشت)، انبارِ فروشگاه ۶
    with tenant_scope(db, primary_id):
        assert inventory_service.get_stock_qty(db, item.id, main_wh.id) == Decimal(994)
    with tenant_scope(db, retailer_id):
        assert inventory_service.get_total_stock_qty(db, link.retailer_item_id) == Decimal(6)


def test_return_over_qty_rejected(as_distributor, retailer_tenant, db, user):
    retailer_id = retailer_tenant
    item, order, main_wh, primary_id = _confirm_for_return(as_distributor, retailer_id, db, user, qty=5)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as ei:
        svc.request_return(
            db, retailer_id,
            ReturnRequestIn(order_id=order.id, lines=[ReturnRequestLineIn(order_line_id=order.lines[0].id, qty=Decimal(6))]),
        )
    assert ei.value.status_code == 400


def test_return_window_enforced(as_distributor, retailer_tenant, db, user):
    from datetime import datetime, timedelta, timezone
    retailer_id = retailer_tenant
    item, order, main_wh, primary_id = _confirm_for_return(as_distributor, retailer_id, db, user, qty=5)
    # مهلتِ ۷ روز؛ سفارش را ۱۰ روز قبل «تأییدشده» جا می‌زنیم
    svc.get_settings(db, primary_id).return_window_days = 7
    order.updated_at = datetime.now(timezone.utc) - timedelta(days=10)
    db.flush()
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as ei:
        svc.request_return(
            db, retailer_id,
            ReturnRequestIn(order_id=order.id, lines=[ReturnRequestLineIn(order_line_id=order.lines[0].id, qty=Decimal(1))]),
        )
    assert ei.value.status_code == 400 and "مهلت" in ei.value.detail


def test_return_reject(as_distributor, retailer_tenant, db, user):
    retailer_id = retailer_tenant
    item, order, main_wh, primary_id = _confirm_for_return(as_distributor, retailer_id, db, user, qty=5)
    ret = svc.request_return(
        db, retailer_id,
        ReturnRequestIn(order_id=order.id, lines=[ReturnRequestLineIn(order_line_id=order.lines[0].id, qty=Decimal(2))]),
    )
    r = as_distributor.post(f"/api/marketplace/distributor/returns/{ret.id}/reject", json={"response_note": "خارج از شرایط"})
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    # ردشده → انبار دست‌نخورده (۹۹۵ پخش‌کننده)
    with tenant_scope(db, primary_id):
        assert inventory_service.get_stock_qty(db, item.id, main_wh.id) == Decimal(995)
    db_ret = db.get(MarketplaceReturn, ret.id)
    assert db_ret.status == "rejected" and db_ret.response_note == "خارج از شرایط"


def test_return_policy_in_settings(as_distributor, db):
    r = as_distributor.put(
        "/api/marketplace/distributor/settings",
        json={"display_name": "پخش", "settlement_mode": "credit", "is_active": True,
              "return_policy": "مرجوعی تا ۷ روز، فقط سالم", "return_window_days": 7},
    )
    assert r.status_code == 200, r.text
    assert r.json()["return_policy"] == "مرجوعی تا ۷ روز، فقط سالم"
    assert r.json()["return_window_days"] == 7
