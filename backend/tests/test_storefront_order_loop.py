"""حلقه‌ی کاملِ فروشگاهِ بومی: ثبتِ سفارشِ عمومی → فیدِ برنامه → تأییدِ پرداخت →
فاکتورِ فروش + کسرِ خودکارِ موجودی.

این «حلقه‌ی طلایی» است: خریدار سفارش می‌دهد و همان سفارش با تأییدِ پرداخت به سندِ
حسابداری تبدیل می‌شود و موجودی **یک‌بار** کم می‌شود (منبعِ حقیقت = حسابداری).
"""
from datetime import date
from decimal import Decimal

import pytest

from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn
from app.services.inventory import post_purchase_invoice

from tests.conftest import PRIMARY_SLUG
from tests.factories import make_item, other_warehouse


def _hdr(key: str) -> dict:
    return {"X-Shop-Slug": PRIMARY_SLUG, "X-Shop-Key": key}


def _setup(client, db, user, *, sku, slug, price, stock):
    """فروشگاهِ منتشرشده + یک کالای لیست‌شده با موجودی در انبار ONLINE."""
    key = client.get("/api/storefront").json()["publishable_key"]
    client.post("/api/storefront/publish")
    item = make_item(db, sku=sku, name="کالای فروش", sales_price=price)
    client.put(f"/api/storefront/items/{item.id}", json={"is_listed": True, "slug": slug})
    wh = other_warehouse(db)  # ONLINE
    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=date(2026, 1, 1),
            warehouse_id=wh.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(stock), unit_cost=Decimal(max(1, price // 2)))],
        ),
        user,
    )
    return key, item


def test_full_order_to_invoice_loop(client, db, user):
    key, _ = _setup(client, db, user, sku="LOOP-1", slug="loop-1", price=500_000, stock=10)

    # ثبتِ سفارشِ عمومی برای ۳ عدد
    res = client.post(
        "/api/shop/orders",
        headers=_hdr(key),
        json={
            "customer_name": "علی خریدار",
            "customer_phone": "09120000000",
            "shipping_address": "تهران",
            "lines": [{"slug": "loop-1", "qty": 3}],
        },
    )
    assert res.status_code == 201, res.text
    order = res.json()
    assert order["payment_status"] == "pending"
    assert order["total"] == 1_500_000  # قیمتِ سمتِ سرور × ۳
    oid = order["id"]

    # در فیدِ برنامه دیده می‌شود
    feed = client.get("/api/storefront/orders").json()
    assert any(o["id"] == oid and o["payment_status"] == "pending" for o in feed)

    # هنوز موجودی کم نشده (سفارشِ در انتظار)
    cat = client.get("/api/shop/catalog", headers=_hdr(key)).json()
    assert next(p for p in cat if p["slug"] == "loop-1")["stock"] == 10

    # تأییدِ پرداخت → فاکتور + کسرِ موجودی
    confirmed = client.post(f"/api/storefront/orders/{oid}/confirm-payment")
    assert confirmed.status_code == 200, confirmed.text
    body = confirmed.json()
    assert body["payment_status"] == "paid"
    assert body["sales_invoice_id"]
    assert body["fulfillment_status"] == "confirmed"

    # موجودی ۱۰ → ۷
    cat2 = client.get("/api/shop/catalog", headers=_hdr(key)).json()
    assert next(p for p in cat2 if p["slug"] == "loop-1")["stock"] == 7


def test_confirm_payment_is_idempotent(client, db, user):
    key, _ = _setup(client, db, user, sku="IDEM-1", slug="idem-1", price=100_000, stock=5)
    oid = client.post(
        "/api/shop/orders",
        headers=_hdr(key),
        json={"customer_name": "x", "customer_phone": "0912", "lines": [{"slug": "idem-1", "qty": 2}]},
    ).json()["id"]

    inv1 = client.post(f"/api/storefront/orders/{oid}/confirm-payment").json()["sales_invoice_id"]
    inv2 = client.post(f"/api/storefront/orders/{oid}/confirm-payment").json()["sales_invoice_id"]
    assert inv1 == inv2, "تأییدِ دوباره نباید فاکتورِ تازه بسازد"

    # موجودی فقط یک‌بار کم شده: ۵ → ۳ (نه ۱)
    cat = client.get("/api/shop/catalog", headers=_hdr(key)).json()
    assert next(p for p in cat if p["slug"] == "idem-1")["stock"] == 3


def test_order_rejects_oversell(client, db, user):
    key, _ = _setup(client, db, user, sku="OS-1", slug="os-1", price=100_000, stock=2)
    res = client.post(
        "/api/shop/orders",
        headers=_hdr(key),
        json={"customer_name": "x", "customer_phone": "0912", "lines": [{"slug": "os-1", "qty": 5}]},
    )
    assert res.status_code == 400


def test_order_rejects_unknown_product(client, db, user):
    key = client.get("/api/storefront").json()["publishable_key"]
    client.post("/api/storefront/publish")
    res = client.post(
        "/api/shop/orders",
        headers=_hdr(key),
        json={"customer_name": "x", "customer_phone": "0912", "lines": [{"slug": "ghost", "qty": 1}]},
    )
    assert res.status_code == 400


def test_fulfillment_status_update(client, db, user):
    key, _ = _setup(client, db, user, sku="FF-1", slug="ff-1", price=100_000, stock=4)
    oid = client.post(
        "/api/shop/orders",
        headers=_hdr(key),
        json={"customer_name": "x", "customer_phone": "0912", "lines": [{"slug": "ff-1", "qty": 1}]},
    ).json()["id"]
    client.post(f"/api/storefront/orders/{oid}/confirm-payment")

    r = client.put(f"/api/storefront/orders/{oid}/fulfillment", json={"fulfillment_status": "shipped"})
    assert r.status_code == 200 and r.json()["fulfillment_status"] == "shipped"

    bad = client.put(f"/api/storefront/orders/{oid}/fulfillment", json={"fulfillment_status": "bogus"})
    assert bad.status_code == 400


@pytest.fixture(autouse=True)
def _grant_storefront(grant_module):
    """«اتصال فروشگاه» ماژولِ محدود است (require_module)؛ این تست‌ها با گرنت اجرا می‌شوند."""
    grant_module("integration")
