"""سامانه مؤدیان — شناسه مالیاتی، امضای قابل‌راستی‌آزمایی، بسته، و مسیرِ ارسال.

هیچ تستی به سامانه‌ی واقعی وصل نمی‌شود: مسیرِ HTTP با MockTransport شبیه‌سازی می‌شود.
"""
from datetime import date
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi import HTTPException

from app.models.moadian import MoadianSubmission
from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn, SalesInvoiceIn, SalesInvoiceLineIn
from app.services import moadian as svc
from app.services.inventory import post_purchase_invoice, post_sales_invoice
from tests.factories import main_warehouse, make_item

TODAY = date(2026, 3, 15)

# یک‌بار ساخته می‌شود؛ تولید کلید ۲۰۴۸ بیتی برای هر تست کُند است.
_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PRIVATE_PEM = _KEY.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
).decode()


def _configure(db, *, active=True, memory_id="AB12CD"):
    s = svc.get_settings(db)
    s.memory_id = memory_id
    s.national_id = "10101010101"
    s.economic_code = "411111111111"
    s.private_key_pem = _PRIVATE_PEM
    s.is_sandbox = True
    s.is_active = active
    db.flush()
    return s


def _invoice(db, user, qty=2, price=1_000_000, tax_rate=10):
    wh = main_warehouse(db)
    item = make_item(db)
    post_purchase_invoice(
        db,
        PurchaseInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            lines=[PurchaseInvoiceLineIn(item_id=item.id, qty=Decimal(50), unit_cost=Decimal(400_000))],
        ),
        user,
    )
    return post_sales_invoice(
        db,
        SalesInvoiceIn(
            invoice_date=TODAY,
            warehouse_id=wh.id,
            tax_rate=Decimal(tax_rate),
            lines=[SalesInvoiceLineIn(item_id=item.id, qty=Decimal(qty), unit_price=Decimal(price))],
        ),
        user,
    )


def _mock_client(status_code=200, payload=None):
    def handler(_request):
        return httpx.Response(status_code, json=payload if payload is not None else {"referenceNumber": "REF-1"})

    return httpx.Client(transport=httpx.MockTransport(handler), base_url="https://sandbox.invalid")


# --- شناسه مالیاتی -----------------------------------------------------------

def test_tax_id_structure_and_determinism():
    tax_id = svc.generate_tax_id("AB12CD", date(2026, 3, 15), 7)
    assert len(tax_id) == 22
    assert tax_id.startswith("AB12CD")
    # همان ورودی → همان شناسه (سند قانونی نباید بین دو محاسبه فرق کند)
    assert tax_id == svc.generate_tax_id("AB12CD", date(2026, 3, 15), 7)
    # سریالِ متفاوت → شناسه‌ی متفاوت
    assert tax_id != svc.generate_tax_id("AB12CD", date(2026, 3, 15), 8)


def test_tax_id_rejects_bad_memory_id():
    with pytest.raises(HTTPException) as exc:
        svc.generate_tax_id("SHORT", date(2026, 3, 15), 1)
    assert exc.value.status_code == 400


# --- امضا --------------------------------------------------------------------

def test_signature_verifies_with_public_key():
    packet = {"header": {"taxid": "AB12CD00000000000000A1"}, "body": []}
    signature = svc.sign_packet(packet, _PRIVATE_PEM)

    # همان بایت‌هایی که سرویس امضا کرده باید با کلید عمومی راستی‌آزمایی شود
    _KEY.public_key().verify(
        __import__("base64").b64decode(signature),
        svc._canonical_json(packet),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )


def test_sign_rejects_invalid_key():
    with pytest.raises(HTTPException) as exc:
        svc.sign_packet({"a": 1}, "not-a-pem")
    assert exc.value.status_code == 400


# --- بسته‌ی صورتحساب ---------------------------------------------------------

def test_packet_totals_match_invoice(db, user):
    settings = _configure(db)
    inv = _invoice(db, user, qty=2, price=1_000_000, tax_rate=10)
    packet = svc.build_invoice_packet(inv, settings, "AB12CD00000000000000A1")

    assert packet["header"]["tprdis"] == 2_000_000  # خالص
    assert packet["header"]["tvam"] == 200_000  # مالیات ۱۰٪
    assert packet["header"]["tbill"] == 2_200_000  # جمع کل
    assert len(packet["body"]) == 1
    assert packet["body"][0]["tsstam"] == 2_200_000


# --- ارسال -------------------------------------------------------------------

def test_submit_records_sent_and_reference(db, user):
    _configure(db)
    inv = _invoice(db, user)
    sub = svc.submit_invoice(db, inv.id, user, client=_mock_client())

    assert sub.status == "sent"
    assert sub.reference_number == "REF-1"
    assert len(sub.tax_id) == 22
    assert sub.sent_at is not None
    assert sub.request_payload["signature"]  # امضا در ردِ درخواست ثبت شده


def test_submit_blocked_when_inactive(db, user):
    _configure(db, active=False)
    inv = _invoice(db, user)
    with pytest.raises(HTTPException) as exc:
        svc.submit_invoice(db, inv.id, user, client=_mock_client())
    assert exc.value.status_code == 400


def test_duplicate_submit_blocked(db, user):
    _configure(db)
    inv = _invoice(db, user)
    svc.submit_invoice(db, inv.id, user, client=_mock_client())
    with pytest.raises(HTTPException) as exc:
        svc.submit_invoice(db, inv.id, user, client=_mock_client())
    assert exc.value.status_code == 400


def test_server_error_is_recorded_not_raised(db, user):
    _configure(db)
    inv = _invoice(db, user)
    sub = svc.submit_invoice(db, inv.id, user, client=_mock_client(status_code=500, payload={"error": "boom"}))
    # سابقه‌ی تلاش باید بماند، نه اینکه استثنا همه‌چیز را دور بریزد
    assert sub.status == "rejected"
    assert db.get(MoadianSubmission, sub.id) is not None


def test_unknown_invoice_404(db, user):
    _configure(db)
    with pytest.raises(HTTPException) as exc:
        svc.submit_invoice(db, uuid4(), user, client=_mock_client())
    assert exc.value.status_code == 404


def test_serial_increments_per_submission(db, user):
    _configure(db)
    first = svc.submit_invoice(db, _invoice(db, user).id, user, client=_mock_client())
    second = svc.submit_invoice(db, _invoice(db, user).id, user, client=_mock_client())
    assert second.serial == first.serial + 1
    assert second.tax_id != first.tax_id


# --- نشتِ کلید ---------------------------------------------------------------

def test_settings_endpoint_never_returns_private_key(db, user, client):
    _configure(db)
    db.commit()
    res = client.get("/api/moadian/settings")
    assert res.status_code == 200
    body = res.json()
    assert body["has_private_key"] is True
    # کلید نباید در هیچ فیلدی از پاسخ باشد
    assert "private_key_pem" not in body
    assert "PRIVATE KEY" not in res.text
