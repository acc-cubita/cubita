"""پرداختِ آنلاینِ سایت با زرین‌پالِ مستأجر — با mockِ فراخوانیِ HTTP.

تماسِ واقعی به زرین‌پال (`shop_payment._zp_call`) monkeypatch می‌شود تا بدونِ مرچنتِ
واقعی، منطقِ request/verify/callback + تبدیلِ سفارش به فاکتور سنجیده شود.
"""
from datetime import date
from decimal import Decimal

from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn
from app.services import shop_payment
from app.services.inventory import post_purchase_invoice

from tests.conftest import PRIMARY_SLUG
from tests.factories import make_item, other_warehouse


def _hdr(key: str) -> dict:
    return {"X-Shop-Slug": PRIMARY_SLUG, "X-Shop-Key": key}


def _stock(db, user, item, qty):
    wh = other_warehouse(db)
    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=date(2026, 1, 1),
            warehouse_id=wh.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(qty), unit_cost=Decimal(1000))],
        ),
        user,
    )


def _setup_payable(client, db, user, *, with_gateway=True):
    client.put(
        "/api/storefront",
        json={"theme_id": "general", "theme_config": {"currency": "toman"}, "seo_title": "", "seo_description": "", "contact_block": {}, "allowed_origin": "https://myshop.test"},
    )
    if with_gateway:
        client.put("/api/storefront/gateways/zarinpal", json={"merchant_id": "M-TEST", "is_active": True})
    client.post("/api/storefront/publish")
    key = client.get("/api/storefront").json()["publishable_key"]
    item = make_item(db, sku="PAY-1", name="کالای پرداخت", sales_price=100_000)
    client.put(f"/api/storefront/items/{item.id}", json={"is_listed": True, "slug": "pay-1"})
    _stock(db, user, item, 5)
    order = client.post(
        "/api/shop/orders",
        headers=_hdr(key),
        json={"customer_name": "x", "customer_phone": "0912", "lines": [{"slug": "pay-1", "qty": 2}]},
    ).json()
    return key, order


def test_info_reports_online_payment(client, db, user):
    key, _ = _setup_payable(client, db, user)
    assert client.get("/api/shop/info", headers=_hdr(key)).json()["has_online_payment"] is True


def test_info_no_gateway_no_online_payment(client, db, user):
    key, _ = _setup_payable(client, db, user, with_gateway=False)
    assert client.get("/api/shop/info", headers=_hdr(key)).json()["has_online_payment"] is False


def test_pay_returns_gateway_redirect_with_rial_amount(client, db, user, monkeypatch):
    key, order = _setup_payable(client, db, user)
    seen = {}

    def fake(base, path, payload):
        seen[path] = payload
        return {"data": {"authority": "AUTH123"}}

    monkeypatch.setattr(shop_payment, "_zp_call", fake)
    res = client.post(f"/api/shop/orders/{order['id']}/pay", headers=_hdr(key))
    assert res.status_code == 200
    url = res.json()["redirect_url"]
    assert "AUTH123" in url and "StartPay" in url
    # total = ۲ × ۱۰۰٬۰۰۰ تومان = ۲۰۰٬۰۰۰ تومان → ۲٬۰۰۰٬۰۰۰ ریال
    assert seen["request"]["amount"] == 2_000_000


def test_callback_verifies_and_creates_invoice(client, db, user, monkeypatch):
    key, order = _setup_payable(client, db, user)

    def fake(base, path, payload):
        if path == "request":
            return {"data": {"authority": "AUTH123"}}
        return {"data": {"code": 100, "ref_id": "REF9"}}

    monkeypatch.setattr(shop_payment, "_zp_call", fake)
    client.post(f"/api/shop/orders/{order['id']}/pay", headers=_hdr(key))

    res = client.get(
        "/api/shop/pay/callback",
        params={"Authority": "AUTH123", "Status": "OK", "shop": PRIMARY_SLUG},
        follow_redirects=False,
    )
    assert res.status_code in (302, 303, 307)
    assert "status=ok" in res.headers["location"]
    assert "myshop.test" in res.headers["location"]

    o = next(o for o in client.get("/api/storefront/orders").json() if o["id"] == order["id"])
    assert o["payment_status"] == "paid" and o["sales_invoice_id"]


def test_callback_failed_status_marks_failed(client, db, user, monkeypatch):
    key, order = _setup_payable(client, db, user)
    monkeypatch.setattr(shop_payment, "_zp_call", lambda *a: {"data": {"authority": "AUTH123"}})
    client.post(f"/api/shop/orders/{order['id']}/pay", headers=_hdr(key))

    res = client.get(
        "/api/shop/pay/callback",
        params={"Authority": "AUTH123", "Status": "NOK", "shop": PRIMARY_SLUG},
        follow_redirects=False,
    )
    assert "status=failed" in res.headers["location"]
    o = next(o for o in client.get("/api/storefront/orders").json() if o["id"] == order["id"])
    assert o["payment_status"] == "failed"


def test_pay_without_gateway_is_400(client, db, user):
    key, order = _setup_payable(client, db, user, with_gateway=False)
    res = client.post(f"/api/shop/orders/{order['id']}/pay", headers=_hdr(key))
    assert res.status_code == 400
