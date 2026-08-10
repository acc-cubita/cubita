"""سامانه مؤدیان (پروتکل v2) — شناسه مالیاتی، JWS، JWE، و مسیرِ ارسال.

هیچ تستی به سامانه‌ی واقعی وصل نمی‌شود: سه اندپوینتِ v2 (`nonce`،
`server-information`، `invoice`) و استعلام با MockTransport شبیه‌سازی می‌شوند.
لایه‌ی رمزنگاری به‌صورتِ انطباقی راستی‌آزمایی می‌شود: امضای JWS با کلید عمومی
verify، و بسته‌ی JWE با کلید خصوصیِ سرور رمزگشایی و با متنِ اصلی مقایسه می‌شود.
"""
import base64
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from cryptography.x509.oid import NameOID
from fastapi import HTTPException

from app.models.moadian import MoadianSubmission
from app.schemas.invoices import PurchaseInvoiceIn, PurchaseInvoiceLineIn, SalesInvoiceIn, SalesInvoiceLineIn
from app.services import moadian as svc
from app.services.inventory import post_purchase_invoice, post_sales_invoice
from tests.factories import main_warehouse, make_item

TODAY = date(2026, 3, 15)

# یک‌بار ساخته می‌شوند؛ تولید کلید ۲۰۴۸ بیتی برای هر تست کُند است.
_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PRIVATE_PEM = _KEY.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
).decode()


def _self_signed_cert(key) -> x509.Certificate:
    name = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, "Cubita Test"),
            x509.NameAttribute(NameOID.SERIAL_NUMBER, "10101010101"),
        ]
    )
    now = datetime.now(timezone.utc)
    return (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=3650))
        .sign(key, hashes.SHA256())
    )


_CERT_PEM = _self_signed_cert(_KEY).public_bytes(Encoding.PEM).decode()

# کلیدِ «سرورِ» شبیه‌سازی‌شده — بسته‌ی JWE با کلید عمومیِ آن رمز و اینجا رمزگشایی می‌شود.
_SERVER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_SERVER_PUB_B64 = base64.b64encode(
    _SERVER_KEY.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
).decode()


def _b64u_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _configure(db, *, active=True, memory_id="AB12CD"):
    s = svc.get_settings(db)
    s.memory_id = memory_id
    s.national_id = "10101010101"
    s.economic_code = "411111111111"
    s.private_key_pem = _PRIVATE_PEM
    s.certificate_pem = _CERT_PEM
    # پیش‌فرضِ کالا/خدمتِ ۱۳رقمی تا مسیرِ ارسال (که حالا sstid را الزامی می‌کند) بگذرد.
    s.default_stuff_id = "1111111111111"
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


def _mock_client(*, invoice_status=200, invoice_payload=None, inquiry_status="SUCCESS", server_info_status=200):
    """کلاینتی که سه اندپوینتِ v2 و استعلام را پاسخ می‌دهد."""

    def handler(request):
        path = request.url.path
        if path.endswith("/nonce"):
            return httpx.Response(200, json={"nonce": "nonce-xyz", "expDate": "2030-01-01T00:00:00Z"})
        if path.endswith("/server-information"):
            if server_info_status >= 400:
                return httpx.Response(server_info_status)
            return httpx.Response(
                200,
                json={
                    "serverTime": 1,
                    "publicKeys": [{"key": _SERVER_PUB_B64, "id": "KID-1", "algorithm": "RSA", "purpose": 1}],
                },
            )
        if path.endswith("/invoice"):
            if invoice_payload is not None or invoice_status >= 400:
                return httpx.Response(invoice_status, json=invoice_payload if invoice_payload is not None else {"error": "boom"})
            return httpx.Response(
                200,
                json={"timestamp": 1, "result": [{"uid": "u1", "referenceNumber": "REF-1", "packetType": None, "data": None}]},
            )
        if path.endswith("/inquiry-by-reference-id"):
            return httpx.Response(
                200,
                json=[
                    {
                        "referenceNumber": "REF-1",
                        "uid": "u1",
                        "status": inquiry_status,
                        "data": {
                            "error": [] if inquiry_status == "SUCCESS" else [{"code": "012802", "message": "روش تسویه نامعتبر"}],
                            "warning": [],
                            "success": inquiry_status == "SUCCESS",
                        },
                        "packetType": "receive_invoice_confirm",
                        "fiscalId": "AB12CD",
                        "sign": "",
                    }
                ],
            )
        return httpx.Response(404, json={"error": "not found"})

    return httpx.Client(transport=httpx.MockTransport(handler), base_url="https://sandbox.invalid")


# --- شناسه مالیاتی -----------------------------------------------------------

def test_tax_id_structure_and_determinism():
    tax_id = svc.generate_tax_id("AB12CD", date(2026, 3, 15), 7)
    assert len(tax_id) == 22
    assert tax_id.startswith("AB12CD")
    assert tax_id == svc.generate_tax_id("AB12CD", date(2026, 3, 15), 7)
    assert tax_id != svc.generate_tax_id("AB12CD", date(2026, 3, 15), 8)


def test_tax_id_date_part_matches_spec_example():
    # نمونه‌ی سند: memory=A11216، indatim=1683997837988ms → روزِ ۱۹۴۹۰ → تاریخِ هگز 04C22
    d = date(1970, 1, 1) + timedelta(days=19490)
    tax_id = svc.generate_tax_id("A11216", d, 1)
    assert tax_id[:11] == "A1121604C22"  # ۶ حافظه + ۵ تاریخ


def test_tax_id_check_digit_is_verhoeff_matching_official_example():
    """کاراکترِ بیست‌ودوم = رقمِ کنترلیِ Verhoeff و باید یک رقم `[0-9]` باشد (نه حرف).
    نمونه‌ی مرجعِ رسمی: DEF5GH + تاریخِ هگزِ 0481F + سریالِ 0xC → `DEF5GH0481F000000000C2`."""
    d = date(1970, 1, 1) + timedelta(days=0x0481F)
    tax_id = svc.generate_tax_id("DEF5GH", d, 0x0C)
    assert tax_id == "DEF5GH0481F000000000C2"
    assert tax_id[-1].isdigit()


def test_tax_id_rejects_bad_memory_id():
    with pytest.raises(HTTPException) as exc:
        svc.generate_tax_id("SHORT", date(2026, 3, 15), 1)
    assert exc.value.status_code == 400


# --- JWS (توکنِ احراز / امضای صورتحساب) --------------------------------------

def test_build_jws_verifies_and_has_correct_structure():
    payload = json.dumps({"nonce": "n1", "clientId": "AB12CD"}).encode("utf-8")
    jws = svc.build_jws(payload, _PRIVATE_PEM, _CERT_PEM)
    header_b64, payload_b64, sig_b64 = jws.split(".")

    # امضا روی همان signing-input با کلید عمومی راستی‌آزمایی می‌شود
    _KEY.public_key().verify(
        _b64u_decode(sig_b64),
        f"{header_b64}.{payload_b64}".encode("ascii"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )

    header = json.loads(_b64u_decode(header_b64))
    assert header["alg"] == "RS256"
    assert header["crit"] == ["sigT"]
    assert "sigT" in header and len(header["x5c"]) == 1
    assert json.loads(_b64u_decode(payload_b64)) == {"nonce": "n1", "clientId": "AB12CD"}


def test_build_jws_rejects_missing_credentials():
    with pytest.raises(HTTPException) as exc:
        svc.build_jws(b"{}", "not-a-pem", _CERT_PEM)
    assert exc.value.status_code == 400
    with pytest.raises(HTTPException) as exc2:
        svc.build_jws(b"{}", _PRIVATE_PEM, "")
    assert exc2.value.status_code == 400


def test_cert_x5c_matches_der_bytes_for_valid_cert():
    """برای گواهیِ سالم، مقدارِ `x5c` باید دقیقاً Base64ِ همان بایت‌های DER باشد
    (هم‌رفتار با نسخه‌ی قبلی که از x509.public_bytes می‌گرفت)."""
    # DERِ مرجع از خودِ همان PEM (نه یک گواهیِ تازه با سریالِ تصادفیِ متفاوت).
    der = x509.load_pem_x509_certificate(_CERT_PEM.encode()).public_bytes(Encoding.DER)
    assert svc._cert_der_from_pem(_CERT_PEM) == der
    assert base64.b64decode(svc._cert_x5c(_CERT_PEM)) == der


def test_cert_accepts_noncompliant_printablestring_that_x509_rejects():
    """رگرسیون: گواهیِ مراکز میانیِ ایرانی (مثلِ ParsSign) گاهی CN را با کاراکترهای
    خارج از PrintableString (مثلِ `[`/`]`) کد می‌کند؛ پارسرِ سخت‌گیرِ `cryptography`
    ردش می‌کند ولی گواهی سالم است. ما فقط بایت‌های DER را می‌خواهیم، پس باید بپذیریم."""
    # SEQUENCE { PrintableString "A[B]" } — یک DERِ ساختاری‌درست با کاراکترِ نامعتبرِ
    # PrintableString. گواهیِ واقعیِ X.509 نیست، پس x509 به هر دلیل ردش می‌کند —
    # نکته این است که استخراجِ ما اصلاً پارس نمی‌کند.
    bad_der = bytes([0x30, 0x06, 0x13, 0x04]) + b"A[B]"
    pem = "-----BEGIN CERTIFICATE-----\n" + base64.b64encode(bad_der).decode() + "\n-----END CERTIFICATE-----\n"
    with pytest.raises(Exception):
        x509.load_pem_x509_certificate(pem.encode())
    assert svc._cert_der_from_pem(pem) == bad_der
    assert base64.b64decode(svc._cert_x5c(pem)) == bad_der


def test_cert_der_from_pem_tolerates_malformed_dash_markers():
    """رگرسیون (کاربرِ واقعی): کپی از چت یک `-` از خطِ END انداخت
    (`-----END CERTIFICATE----` با ۴ تیره)؛ استخراج باید همچنان کار کند، چون فقط
    بدنه‌ی Base64 مهم است."""
    der = x509.load_pem_x509_certificate(_CERT_PEM.encode()).public_bytes(Encoding.DER)
    body = base64.b64encode(der).decode()
    # نشانگرها با تعدادِ تیره‌ی نامتقارن/ناقص (۴ و ۶ به‌جای ۵):
    mangled = f"----BEGIN CERTIFICATE------\n{body}\n-----END CERTIFICATE----"
    assert svc._cert_der_from_pem(mangled) == der


def test_cert_der_from_pem_rejects_empty_and_garbage():
    with pytest.raises(HTTPException) as e1:
        svc._cert_der_from_pem("")
    assert e1.value.status_code == 400
    with pytest.raises(HTTPException) as e2:  # بدونِ بلوکِ گواهی
        svc._cert_der_from_pem("just some text, no PEM here")
    assert e2.value.status_code == 400


# --- JWE (رمزنگاری صورتحساب) -------------------------------------------------

def test_build_jwe_roundtrips_to_plaintext():
    plaintext = "signed.invoice.jws"
    jwe = svc.build_jwe(plaintext, _SERVER_PUB_B64, "KID-1")
    parts = jwe.split(".")
    assert len(parts) == 5  # header . encKey . iv . ciphertext . tag

    header = json.loads(_b64u_decode(parts[0]))
    assert header == {"alg": "RSA-OAEP-256", "enc": "A256GCM", "kid": "KID-1"}

    aes_key = _SERVER_KEY.decrypt(
        _b64u_decode(parts[1]),
        padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
    )
    aad = parts[0].encode("ascii")
    recovered = AESGCM(aes_key).decrypt(_b64u_decode(parts[2]), _b64u_decode(parts[3]) + _b64u_decode(parts[4]), aad)
    assert recovered.decode("utf-8") == plaintext


# --- بسته‌ی صورتحساب ---------------------------------------------------------

def test_packet_field_names_and_totals(db, user):
    settings = _configure(db)
    inv = _invoice(db, user, qty=2, price=1_000_000, tax_rate=10)
    packet = svc.build_invoice_packet(inv, settings, "AB12CD00000000000000A1")

    assert packet["header"]["taxid"] == "AB12CD00000000000000A1"
    assert packet["header"]["tprdis"] == 2_000_000
    assert packet["header"]["tvam"] == 200_000
    assert packet["header"]["tbill"] == 2_200_000
    assert packet["header"]["inp"] == 1 and packet["header"]["ins"] == 1
    assert packet["payments"] == []
    row = packet["body"][0]
    assert {"sstid", "sstt", "mu", "am", "fee", "prdis", "dis", "adis", "vra", "vam", "tsstam"} <= set(row)
    assert row["tsstam"] == 2_200_000
    # کلِ بسته باید امضاپذیر و رمزپذیر باشد (JSON معتبر با UTF-8 فارسی)
    signed = svc.build_jws(json.dumps(packet, ensure_ascii=False).encode("utf-8"), _PRIVATE_PEM, _CERT_PEM)
    assert svc.build_jwe(signed, _SERVER_PUB_B64, "KID-1").count(".") == 4


# --- ارسال (مسیرِ کاملِ nonce→token→server-info→sign→encrypt→POST) ----------

def test_submit_records_sent_and_reference(db, user):
    _configure(db)
    inv = _invoice(db, user)
    sub = svc.submit_invoice(db, inv.id, user, client=_mock_client())

    assert sub.status == "sent"
    assert sub.reference_number == "REF-1"
    assert len(sub.tax_id) == 22
    assert sub.sent_at is not None
    # ردِ درخواست بسته‌ی صورتحساب و شناسه‌ی ردیابی را نگه می‌دارد
    assert sub.request_payload["invoice"]["header"]["taxid"] == sub.tax_id
    assert sub.request_payload["requestTraceId"]


def test_connection_ok_returns_server_key_id(db, user):
    _configure(db, active=False)  # تستِ اتصال به «فعال» نیاز ندارد
    res = svc.test_connection(db, client=_mock_client())
    assert res["ok"] is True
    assert res["status_code"] == 200
    assert res["server_key_id"] == "KID-1"


def test_connection_auth_failure_gives_friendly_message(db, user):
    _configure(db, memory_id="A44DOG")
    res = svc.test_connection(db, client=_mock_client(server_info_status=401))
    assert res["ok"] is False
    assert res["status_code"] == 401
    # پیامِ خوانا، نه HTTPStatusErrorِ خام؛ و راهنماییِ محیط/شناسه‌حافظه
    assert "احراز هویت" in res["message"] and "A44DOG" in res["message"]


def test_connection_requires_memory_id(db, user):
    s = _configure(db)
    s.memory_id = ""
    db.flush()
    res = svc.test_connection(db, client=_mock_client())
    assert res["ok"] is False and res["status_code"] is None


def test_submit_auth_401_recorded_with_friendly_message(db, user):
    _configure(db, memory_id="A44DOG")
    inv = _invoice(db, user)
    sub = svc.submit_invoice(db, inv.id, user, client=_mock_client(server_info_status=401))
    assert sub.status == "failed"
    assert "احراز هویت" in sub.error_message and "HTTPStatusError" not in sub.error_message


def test_submit_blocked_when_inactive(db, user):
    _configure(db, active=False)
    inv = _invoice(db, user)
    with pytest.raises(HTTPException) as exc:
        svc.submit_invoice(db, inv.id, user, client=_mock_client())
    assert exc.value.status_code == 400


def test_submit_requires_certificate(db, user):
    s = _configure(db)
    s.certificate_pem = ""
    db.flush()
    inv = _invoice(db, user)
    with pytest.raises(HTTPException) as exc:
        svc.submit_invoice(db, inv.id, user, client=_mock_client())
    assert exc.value.status_code == 400
    # سریال نباید بی‌جهت مصرف شده باشد
    assert svc.get_settings(db).last_serial == 0


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
    sub = svc.submit_invoice(db, inv.id, user, client=_mock_client(invoice_status=500))
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


# --- استعلامِ وضعیت ----------------------------------------------------------

def test_inquiry_confirms_success(db, user):
    _configure(db)
    inv = _invoice(db, user)
    sub = svc.submit_invoice(db, inv.id, user, client=_mock_client())
    updated = svc.inquire_status(db, sub.id, client=_mock_client(inquiry_status="SUCCESS"))
    assert updated.status == "confirmed"


def test_inquiry_marks_failed_with_message(db, user):
    _configure(db)
    inv = _invoice(db, user)
    sub = svc.submit_invoice(db, inv.id, user, client=_mock_client())
    updated = svc.inquire_status(db, sub.id, client=_mock_client(inquiry_status="FAILED"))
    assert updated.status == "rejected"
    assert "روش تسویه" in updated.error_message


# --- نشتِ کلید ---------------------------------------------------------------

def test_settings_endpoint_never_returns_secrets(db, user, client):
    _configure(db)
    db.commit()
    res = client.get("/api/moadian/settings")
    assert res.status_code == 200
    body = res.json()
    assert body["has_private_key"] is True
    assert "private_key_pem" not in body
    assert "PRIVATE KEY" not in res.text


# --- شناسه‌ی کالا/خدمت (sstid) ------------------------------------------------

def test_packet_sstid_uses_item_code(db, user):
    settings = _configure(db)
    inv = _invoice(db, user)
    inv.lines[0].item.tax_stuff_id = "1234567890123"
    db.flush()
    packet = svc.build_invoice_packet(inv, settings, "AB12CD00000000000000A1")
    assert packet["body"][0]["sstid"] == "1234567890123"


def test_packet_sstid_falls_back_to_business_default(db, user):
    settings = _configure(db)
    settings.default_stuff_id = "9999999999999"
    db.flush()
    inv = _invoice(db, user)  # کالا کدِ خودش را ندارد → پیش‌فرضِ کسب‌وکار می‌نشیند
    assert (inv.lines[0].item.tax_stuff_id or "") == ""
    packet = svc.build_invoice_packet(inv, settings, "AB12CD00000000000000A1")
    assert packet["body"][0]["sstid"] == "9999999999999"


def test_assert_stuff_ids_blocks_when_missing(db, user):
    settings = _configure(db)
    settings.default_stuff_id = ""  # پیش‌فرض را هم بردار تا واقعاً «بدونِ کد» باشد
    db.flush()
    inv = _invoice(db, user)  # نه کدِ کالا، نه پیش‌فرض
    with pytest.raises(HTTPException) as e:
        svc._assert_stuff_ids(inv, settings)
    assert e.value.status_code == 400
    # با کدِ ۱۳رقمیِ معتبر دیگر مانع نمی‌شود
    inv.lines[0].item.tax_stuff_id = "1234567890123"
    db.flush()
    svc._assert_stuff_ids(inv, settings)


def test_assert_stuff_ids_rejects_non_13_digits(db, user):
    settings = _configure(db)
    inv = _invoice(db, user)
    inv.lines[0].item.tax_stuff_id = "12345"  # کوتاه‌تر از ۱۳ رقم
    db.flush()
    with pytest.raises(HTTPException):
        svc._assert_stuff_ids(inv, settings)
