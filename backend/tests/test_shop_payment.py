"""پرداختِ آنلاینِ سایت با درگاهِ مستأجر (زرین‌پال/زیبال/آی‌دی‌پی) — با mockِ HTTP.

تماسِ واقعیِ شبکه (`payment_providers._post`) monkeypatch می‌شود تا بدونِ مرچنتِ
واقعی، منطقِ request/verify/callback + تبدیلِ سفارش به فاکتور برای هر سه درگاه سنجیده شود.
"""
from datetime import date
from decimal import Decimal

import pytest

from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn
from app.services import payment_providers
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


def _setup_payable(client, db, user, *, gateway="zarinpal"):
    client.put(
        "/api/storefront",
        json={"theme_id": "general", "theme_config": {"currency": "toman"}, "seo_title": "", "seo_description": "", "contact_block": {}, "allowed_origin": "https://myshop.test"},
    )
    if gateway:
        client.put(f"/api/storefront/gateways/{gateway}", json={"merchant_id": "M-TEST", "is_active": True})
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


# ── mockِ HTTP برای هر درگاه (بر پایه‌ی URL) ──────────────────────────────────────
def _mock_post(seen: dict):
    """یک fake برای `payment_providers._post` که پاسخِ موفقِ هر درگاه را بازمی‌گرداند
    و payloadها را در `seen` نگه می‌دارد تا مبلغ/پارامترها بررسی شوند."""

    def fake(url, *, json=None, data=None, headers=None, raise_for_status=True):
        seen[url] = json
        if url.endswith("/request.json"):  # zarinpal request
            return {"data": {"authority": "AUTH123"}}
        if url.endswith("/verify.json"):  # zarinpal verify
            return {"data": {"code": 100, "ref_id": "REF9"}}
        if url == "https://gateway.zibal.ir/v1/request":
            return {"result": 100, "trackId": 12345}
        if url == "https://gateway.zibal.ir/v1/verify":
            return {"result": 100, "refNumber": 777}
        if url == "https://api.idpay.ir/v1.1/payment":
            return {"id": "IDP123", "link": "https://idpay.ir/pay/IDP123"}
        if url == "https://api.idpay.ir/v1.1/payment/verify":
            return {"status": 100, "track_id": 999}
        raise AssertionError(f"URLِ mockنشده: {url}")

    return fake


# ── زرین‌پال ─────────────────────────────────────────────────────────────────────
def test_info_reports_online_payment(client, db, user):
    key, _ = _setup_payable(client, db, user)
    assert client.get("/api/shop/info", headers=_hdr(key)).json()["has_online_payment"] is True


def test_info_no_gateway_no_online_payment(client, db, user):
    key, _ = _setup_payable(client, db, user, gateway="")
    assert client.get("/api/shop/info", headers=_hdr(key)).json()["has_online_payment"] is False


def test_pay_returns_gateway_redirect_with_rial_amount(client, db, user, monkeypatch):
    key, order = _setup_payable(client, db, user)
    seen = {}
    monkeypatch.setattr(payment_providers, "_post", _mock_post(seen))
    res = client.post(f"/api/shop/orders/{order['id']}/pay", headers=_hdr(key))
    assert res.status_code == 200
    url = res.json()["redirect_url"]
    assert "AUTH123" in url and "StartPay" in url
    # total = ۲ × ۱۰۰٬۰۰۰ تومان = ۲۰۰٬۰۰۰ تومان → ۲٬۰۰۰٬۰۰۰ ریال
    req = next(v for k, v in seen.items() if k.endswith("/request.json"))
    assert req["amount"] == 2_000_000


def test_callback_verifies_and_creates_invoice(client, db, user, monkeypatch):
    key, order = _setup_payable(client, db, user)
    monkeypatch.setattr(payment_providers, "_post", _mock_post({}))
    client.post(f"/api/shop/orders/{order['id']}/pay", headers=_hdr(key))

    res = client.get(
        "/api/shop/pay/callback",
        params={"Authority": "AUTH123", "Status": "OK", "shop": PRIMARY_SLUG, "provider": "zarinpal"},
        follow_redirects=False,
    )
    assert res.status_code in (302, 303, 307)
    assert "status=ok" in res.headers["location"]
    assert "myshop.test" in res.headers["location"]

    o = next(o for o in client.get("/api/storefront/orders").json() if o["id"] == order["id"])
    assert o["payment_status"] == "paid" and o["sales_invoice_id"]


def test_callback_failed_status_marks_failed(client, db, user, monkeypatch):
    key, order = _setup_payable(client, db, user)
    monkeypatch.setattr(payment_providers, "_post", _mock_post({}))
    client.post(f"/api/shop/orders/{order['id']}/pay", headers=_hdr(key))

    res = client.get(
        "/api/shop/pay/callback",
        params={"Authority": "AUTH123", "Status": "NOK", "shop": PRIMARY_SLUG, "provider": "zarinpal"},
        follow_redirects=False,
    )
    assert "status=failed" in res.headers["location"]
    o = next(o for o in client.get("/api/storefront/orders").json() if o["id"] == order["id"])
    assert o["payment_status"] == "failed"


def test_pay_without_gateway_is_400(client, db, user):
    key, order = _setup_payable(client, db, user, gateway="")
    res = client.post(f"/api/shop/orders/{order['id']}/pay", headers=_hdr(key))
    assert res.status_code == 400


# ── زیبال ───────────────────────────────────────────────────────────────────────
def test_zibal_pay_and_callback_creates_invoice(client, db, user, monkeypatch):
    key, order = _setup_payable(client, db, user, gateway="zibal")
    seen = {}
    monkeypatch.setattr(payment_providers, "_post", _mock_post(seen))

    res = client.post(f"/api/shop/orders/{order['id']}/pay", headers=_hdr(key))
    assert res.status_code == 200
    assert "gateway.zibal.ir/start/12345" in res.json()["redirect_url"]
    assert seen["https://gateway.zibal.ir/v1/request"]["amount"] == 2_000_000

    res = client.get(
        "/api/shop/pay/callback",
        params={"trackId": "12345", "success": "1", "shop": PRIMARY_SLUG, "provider": "zibal"},
        follow_redirects=False,
    )
    assert "status=ok" in res.headers["location"]
    o = next(o for o in client.get("/api/storefront/orders").json() if o["id"] == order["id"])
    assert o["payment_status"] == "paid" and o["sales_invoice_id"]


def test_zibal_callback_unsuccessful_marks_failed(client, db, user, monkeypatch):
    key, order = _setup_payable(client, db, user, gateway="zibal")
    monkeypatch.setattr(payment_providers, "_post", _mock_post({}))
    client.post(f"/api/shop/orders/{order['id']}/pay", headers=_hdr(key))

    res = client.get(
        "/api/shop/pay/callback",
        params={"trackId": "12345", "success": "0", "shop": PRIMARY_SLUG, "provider": "zibal"},
        follow_redirects=False,
    )
    assert "status=failed" in res.headers["location"]
    o = next(o for o in client.get("/api/storefront/orders").json() if o["id"] == order["id"])
    assert o["payment_status"] == "failed"


# ── آی‌دی‌پی (callback به‌صورت POSTِ فرم) ─────────────────────────────────────────
def test_idpay_pay_and_post_callback_creates_invoice(client, db, user, monkeypatch):
    key, order = _setup_payable(client, db, user, gateway="idpay")
    seen = {}
    monkeypatch.setattr(payment_providers, "_post", _mock_post(seen))

    res = client.post(f"/api/shop/orders/{order['id']}/pay", headers=_hdr(key))
    assert res.status_code == 200
    assert res.json()["redirect_url"] == "https://idpay.ir/pay/IDP123"
    assert seen["https://api.idpay.ir/v1.1/payment"]["amount"] == 2_000_000

    res = client.post(
        "/api/shop/pay/callback",
        params={"shop": PRIMARY_SLUG, "provider": "idpay"},
        data={"id": "IDP123", "status": "100", "order_id": order["tracking_code"]},
        follow_redirects=False,
    )
    assert "status=ok" in res.headers["location"]
    o = next(o for o in client.get("/api/storefront/orders").json() if o["id"] == order["id"])
    assert o["payment_status"] == "paid" and o["sales_invoice_id"]


@pytest.mark.parametrize("provider", ["zarinpal", "zibal", "idpay"])
def test_provider_registered(provider):
    assert payment_providers.get_provider(provider) is not None
