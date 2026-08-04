"""مدیریتِ فروشگاهِ بومی (`/api/storefront/*`) + حلقه‌ی سرتاسری تا API عمومی.

مهم‌ترین تست این‌جا: مالک از داخلِ برنامه فروشگاه را می‌سازد/کالا را لیست و منتشر
می‌کند، و بعد همان کالا از سطحِ عمومیِ `/api/shop/*` با کلیدِ همان فروشگاه دیده می‌شود.
و: مرچنتِ درگاه هرگز در پاسخ برنمی‌گردد.
"""
from tests.conftest import PRIMARY_SLUG
from tests.factories import make_item


def test_settings_created_with_slug_and_key(client):
    res = client.get("/api/storefront")
    assert res.status_code == 200
    body = res.json()
    assert body["slug"] == PRIMARY_SLUG
    assert body["publishable_key"], "کلیدِ publishable باید خودکار ساخته شود"
    assert body["status"] == "draft"


def test_settings_update_roundtrip(client):
    res = client.put(
        "/api/storefront",
        json={
            "theme_id": "general",
            "theme_config": {"primary": "#E31F24"},
            "seo_title": "فروشگاهِ تست",
            "seo_description": "توضیح",
            "contact_block": {"phone": "021"},
            "allowed_origin": "https://myshop.ir",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["theme_config"] == {"primary": "#E31F24"}
    assert body["seo_title"] == "فروشگاهِ تست"
    assert body["allowed_origin"] == "https://myshop.ir"


def test_key_rotate_changes_key(client):
    k1 = client.get("/api/storefront").json()["publishable_key"]
    k2 = client.post("/api/storefront/key/rotate").json()["publishable_key"]
    assert k1 and k2 and k1 != k2


def test_publish_flow_makes_item_visible_on_public_api(client, db):
    # کلید را از تنظیمات بگیر
    key = client.get("/api/storefront").json()["publishable_key"]

    # یک کالا بساز و روی سایت لیست کن
    item = make_item(db, sku="PUB-1", name="کالای منتشرشده")
    listing = client.put(
        f"/api/storefront/items/{item.id}",
        json={"is_listed": True, "slug": "pub-1", "badge": "جدید"},
    )
    assert listing.status_code == 200
    assert listing.json()["slug"] == "pub-1"

    # پیش از انتشار: API عمومی ۴۰۳ می‌دهد
    before = client.get("/api/shop/catalog", headers={"X-Shop-Slug": PRIMARY_SLUG, "X-Shop-Key": key})
    assert before.status_code == 403

    # انتشار
    assert client.post("/api/storefront/publish").json()["status"] == "published"

    # حالا کالا در کاتالوگِ عمومی دیده می‌شود
    after = client.get("/api/shop/catalog", headers={"X-Shop-Slug": PRIMARY_SLUG, "X-Shop-Key": key})
    assert after.status_code == 200
    data = after.json()
    assert any(p["slug"] == "pub-1" for p in data)
    assert all("average_cost" not in p for p in data)


def test_unlisted_item_not_public(client, db):
    key = client.get("/api/storefront").json()["publishable_key"]
    client.post("/api/storefront/publish")
    item = make_item(db, sku="HID-1")
    client.put(f"/api/storefront/items/{item.id}", json={"is_listed": False, "slug": "hid-1"})

    data = client.get("/api/shop/catalog", headers={"X-Shop-Slug": PRIMARY_SLUG, "X-Shop-Key": key}).json()
    assert all(p["slug"] != "hid-1" for p in data)


def test_gateway_merchant_is_secret(client):
    res = client.put("/api/storefront/gateways/zarinpal", json={"merchant_id": "MERCHANT-XYZ", "is_active": True})
    assert res.status_code == 200
    body = res.json()
    assert body["has_merchant"] is True and body["is_active"] is True
    assert "merchant_id" not in body, "مرچنت نباید در پاسخ باشد"
    assert "MERCHANT-XYZ" not in res.text

    listed = client.get("/api/storefront/gateways").json()
    zp = next(g for g in listed if g["provider"] == "zarinpal")
    assert zp["has_merchant"] is True
    assert all("merchant_id" not in g for g in listed)

    # به‌روزرسانیِ بعدی بدونِ مرچنت → مرچنتِ فعلی حفظ می‌شود
    client.put("/api/storefront/gateways/zarinpal", json={"merchant_id": "", "is_active": False})
    zp2 = next(g for g in client.get("/api/storefront/gateways").json() if g["provider"] == "zarinpal")
    assert zp2["has_merchant"] is True and zp2["is_active"] is False


def test_unknown_gateway_rejected(client):
    assert client.put("/api/storefront/gateways/paypal", json={"merchant_id": "x"}).status_code == 400
