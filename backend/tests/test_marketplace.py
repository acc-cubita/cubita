"""بازارِ عمده‌فروشی — تست‌های سمتِ پخش‌کننده (M2).

جدول‌های بازار سراسری‌اند (بدونِ RLS)؛ این‌جا گیتِ نوعِ حساب، مالکیت، و اعتبارسنجیِ
لیستینگ سنجیده می‌شود.
"""
import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.models.inventory import Item, Warehouse
from app.models.invoices import PurchaseInvoice
from app.models.marketplace import (
    MarketplaceConnection,
    MarketplaceItemLink,
    MarketplaceListing,
    MarketplaceListingComponent,
    MarketplaceOrder,
    MarketplaceSettings,
)
from app.models.storefront_native import PaymentGateway
from app.models.tenant import Tenant
from app.models.treasury import TreasuryTransaction
from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn
from app.schemas.marketplace import OrderLineIn, OrderPlaceIn
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


def test_confirm_fails_without_distributor_stock(as_distributor, retailer_tenant, db):
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
    order = svc.place_order(
        db, retailer_id, OrderPlaceIn(distributor_tenant_id=primary_id, lines=[OrderLineIn(listing_id=listing.id, qty=Decimal(5))])
    )
    # موجودی کافی نیست → ۴۰۰، و سفارش «تأیید» نمی‌شود.
    assert as_distributor.post(f"/api/marketplace/distributor/orders/{order.id}/confirm").status_code == 400


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
