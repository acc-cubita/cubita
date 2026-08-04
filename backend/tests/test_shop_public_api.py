"""API عمومیِ فروشگاه — ایزولاسیون، پنهان‌سازیِ کاست، و اعتبارسنجیِ کلید.

مهم‌ترین خاصیتِ این سطح: عمومی است (روی هاستِ مستأجر، در مرورگرِ خریدار) پس
**هیچ عددِ داخلی نباید لو برود** و **کلیدِ یک فروشگاه نباید به فروشگاهِ دیگر راه بدهد**.

نکته: نشتِ ساختاریِ RLS روی ۷ جدولِ تازه از قبل با تستِ پارامتریِ
test_cross_tenant_leak پوشش داده می‌شود؛ این‌جا *رفتارِ* سطحِ عمومی سنجیده می‌شود.
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.database import SessionLocal
from app.models.storefront_native import ItemStorefront, Storefront
from app.models.user import User
from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn
from app.seed import provision_tenant
from app.services.inventory import post_purchase_invoice
from app.services.provisioning import purge_tenant
from app.services.shop import list_catalog, resolve_storefront
from app.tenant_context import set_current_tenant

from tests.conftest import PRIMARY_SLUG, tenant_session
from tests.factories import make_item, other_warehouse


def _publish(db, key: str, status: str = "published") -> Storefront:
    sf = Storefront(publishable_key=key, status=status)  # tenant_id خودکار مهر می‌شود
    db.add(sf)
    db.flush()
    return sf


def _list_item(db, item, *, slug: str, is_listed: bool = True) -> ItemStorefront:
    isf = ItemStorefront(item_id=item.id, slug=slug, is_listed=is_listed)
    db.add(isf)
    db.flush()
    return isf


# ── تک‌مستأجری: پنهان‌سازیِ کاست + فیلترِ لیست‌شده + موجودی ──────────────────────


def test_catalog_hides_cost_and_filters_unlisted(db, user):
    _publish(db, "K")
    listed = make_item(db, sku="L1", sales_price=500_000, average_cost=333_333)
    _list_item(db, listed, slug="l1", is_listed=True)
    hidden = make_item(db, sku="H1", sales_price=700_000, average_cost=111_111)
    _list_item(db, hidden, slug="h1", is_listed=False)

    products = list_catalog(db)
    slugs = {p.slug for p in products}
    assert "l1" in slugs, "کالای لیست‌شده باید در کاتالوگ باشد"
    assert "h1" not in slugs, "کالای لیست‌نشده نباید دیده شود"

    p = next(p for p in products if p.slug == "l1")
    dumped = p.model_dump()
    assert "average_cost" not in dumped and "cost" not in dumped, "بهای تمام‌شده نباید در خروجی باشد"
    assert 333_333 not in dumped.values(), "مقدارِ کاست نباید در هیچ فیلدی نشت کند"
    assert p.price == 500_000
    assert p.out_of_stock is True and p.stock == 0  # هنوز موجودی ندارد


def test_catalog_reports_stock(db, user):
    _publish(db, "K")
    item = make_item(db, sku="S1")
    _list_item(db, item, slug="s1")
    wh = other_warehouse(db)  # انبار ONLINE
    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=date(2026, 1, 1),
            warehouse_id=wh.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(5), unit_cost=Decimal(1000))],
        ),
        user,
    )
    p = next(p for p in list_catalog(db) if p.slug == "s1")
    assert p.stock == 5 and p.out_of_stock is False


# ── اعتبارسنجیِ کلید و انتشار ────────────────────────────────────────────────────


def test_resolve_accepts_right_key_rejects_wrong(db):
    _publish(db, "RIGHT")
    ctx = resolve_storefront(db, PRIMARY_SLUG, "RIGHT")
    assert ctx.tenant_id is not None

    with pytest.raises(HTTPException) as e:
        resolve_storefront(db, PRIMARY_SLUG, "WRONG")
    assert e.value.status_code == 401


def test_resolve_rejects_unpublished(db):
    _publish(db, "K2", status="draft")
    with pytest.raises(HTTPException) as e:
        resolve_storefront(db, PRIMARY_SLUG, "K2")
    assert e.value.status_code == 403


def test_resolve_unknown_shop_is_401(db):
    with pytest.raises(HTTPException) as e:
        resolve_storefront(db, "no-such-shop-xyz", "anything")
    assert e.value.status_code == 401


def test_resolve_missing_credentials_is_401(db):
    with pytest.raises(HTTPException) as e:
        resolve_storefront(db, "", "")
    assert e.value.status_code == 401


# ── HTTP end-to-end (روتر + main.py + response_model) ───────────────────────────


def test_catalog_endpoint_http(db, user, client):
    _publish(db, "HK")
    item = make_item(db, sku="HTTP1", average_cost=222_222)
    _list_item(db, item, slug="http1")

    res = client.get("/api/shop/catalog", headers={"X-Shop-Slug": PRIMARY_SLUG, "X-Shop-Key": "HK"})
    assert res.status_code == 200
    data = res.json()
    assert any(p["slug"] == "http1" for p in data)
    assert all("average_cost" not in p and "cost" not in p for p in data), "کاست نباید در JSON باشد"

    bad = client.get("/api/shop/catalog", headers={"X-Shop-Slug": PRIMARY_SLUG, "X-Shop-Key": "BAD"})
    assert bad.status_code == 401


# ── نشتِ بین دو مستأجرِ واقعی ─────────────────────────────────────────────────────


@dataclass
class _Shop:
    tenant_id: object
    slug: str
    key: str
    listed_slug: str


def _provision_shop(key: str) -> _Shop:
    """یک مستأجرِ کامل با فروشگاهِ منتشرشده + یک کالای لیست‌شده‌ی دارای موجودی می‌سازد."""
    slug = f"shop-{uuid4().hex[:8]}"
    email = f"owner-{slug}@example.invalid"
    session = SessionLocal()
    try:
        tenant = provision_tenant(
            session, name="فروشگاه تست", slug=slug, owner_email=email, owner_password="ShopPass!2026"
        )
        session.commit()
        tenant_id = tenant.id
    finally:
        session.close()

    listed_slug = f"prod-{slug}"
    with tenant_session(tenant_id) as s:
        owner = s.query(User).filter(User.email == email).one()
        _publish(s, key)
        item = make_item(s, sku=f"SKU-{slug}", name=f"کالای {slug}")
        _list_item(s, item, slug=listed_slug)
        wh = other_warehouse(s)
        post_purchase_invoice(
            s,
            PurchaseInvoiceIn(
                invoice_date=date(2026, 1, 1),
                warehouse_id=wh.id,
                lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(3), unit_cost=Decimal(1000))],
            ),
            owner,
        )
        s.commit()
    return _Shop(tenant_id=tenant_id, slug=slug, key=key, listed_slug=listed_slug)


def test_key_cannot_read_another_tenants_catalog():
    shop_b = _provision_shop("KEY-B")
    shop_c = _provision_shop("KEY-C")
    try:
        # با کلید/شناسه‌ی B فقط کاتالوگِ B دیده می‌شود، نه C
        with SessionLocal() as db:
            resolve_storefront(db, shop_b.slug, shop_b.key)
            slugs = {p.slug for p in list_catalog(db)}
        assert shop_b.listed_slug in slugs
        assert shop_c.listed_slug not in slugs, "کاتالوگِ مستأجرِ دیگر نشت کرد"

        # کلیدِ B روی شناسه‌ی C پذیرفته نمی‌شود
        with SessionLocal() as db:
            with pytest.raises(HTTPException) as e:
                resolve_storefront(db, shop_c.slug, shop_b.key)
            assert e.value.status_code == 401
    finally:
        set_current_tenant(None)
        cleanup = SessionLocal()
        try:
            purge_tenant(cleanup, shop_b.tenant_id)
            purge_tenant(cleanup, shop_c.tenant_id)
            cleanup.commit()
        finally:
            cleanup.close()
