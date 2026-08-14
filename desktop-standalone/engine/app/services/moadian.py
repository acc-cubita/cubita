"""سامانه مؤدیان — پروتکلِ نسخه‌ی دوم (RC_TICS.IS_v1.6): احراز، امضا، رمزنگاری، ارسال.

فلوی کامل مطابقِ «دستورالعمل فنی اتصال به سامانه مودیان»:

1. `GET /nonce`  → رشته‌ی تصادفیِ یکبارمصرف.
2. ساختِ توکنِ **JWS** (RS256، هدرِ `x5c`/`sigT`/`crit`، بدنه‌ی `{nonce, clientId}`) و
   ارسال به‌صورتِ `Authorization: Bearer …` — برای **هر** درخواست توکنِ تازه.
3. `GET /server-information` → کلیدِ عمومیِ **رمزنگاریِ** سازمان.
4. صورتحساب: تولیدِ JSON → **امضا (JWS)** → **رمزنگاری (JWE، RSA-OAEP-256 + A256GCM)**.
5. `POST /invoice` با بدنه‌ی `[{payload, header:{requestTraceId, fiscalId}}]` → شماره‌ی پیگیری.
6. استعلامِ وضعیت با `GET /inquiry-by-reference-id`.

**مرزبندیِ اطمینان:** لایه‌ی احراز/امضا/رمزنگاری (این فایل) قطعی و طبقِ اسپک است و با
کلیدِ نمونه‌ی پیوستِ سند تستِ انطباقی می‌شود. آنچه هنوز به نسخه‌ی «قالب شناسه یکتا»
(RC_DCPS) وابسته است، فقط رقمِ کنترلیِ شناسه مالیاتی است که در `_check_character`
ایزوله شده. نگاشتِ فیلدهای بسته با «دستورالعمل صدور صورتحساب» (RC_IITP) هم‌راستاست
و نمونه‌ی صفحه‌ی ۲۰ِ سندِ اتصال آن را تأیید می‌کند. پیش‌فرضِ محیط «سندباکس» است.
"""
import base64
import json
import os
import re
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.inventory import Contact
from app.models.invoices import SalesInvoice
from app.models.moadian import MoadianSettings, MoadianSubmission
from app.models.user import User

#: آدرس‌های پایه‌ی سامانه. با `base_url_override` قابلِ بازنویسی‌اند.
SANDBOX_BASE_URL = "https://sandboxrc.tax.gov.ir"
PRODUCTION_BASE_URL = "https://tp.tax.gov.ir"
#: مسیرِ نسخه‌ی دومِ وب‌سرویسِ جمع‌آوری.
API_PREFIX = "/requestsmanager/api/v2"

REQUEST_TIMEOUT = 40.0

#: مبدأ شمارشِ روز در شناسه مالیاتی (میلادی) — روزهای سپری‌شده از ابتدای دوران یونیکس.
_TAXID_EPOCH = date(1970, 1, 1)
_MS_PER_DAY = 86_400_000


# ---------------------------------------------------------------------------
# ابزارهای رمزنگاری ── بخشِ قطعی (JWS / JWE مطابق RFC7515/RFC7516 و اسپکِ سامانه)
# ---------------------------------------------------------------------------

def _b64u(data: bytes) -> str:
    """Base64URL بدونِ padding — قالبِ استانداردِ JOSE."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _load_private_key(private_key_pem: str):
    if not (private_key_pem or "").strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "کلید خصوصی در تنظیمات مؤدیان ثبت نشده است")
    try:
        return serialization.load_pem_private_key(private_key_pem.encode("utf-8"), password=None)
    except Exception:
        # متنِ خطا عمداً کلید را بازتاب نمی‌دهد.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "کلید خصوصی معتبر نیست (فرمت PEM خوانده نشد)")


def _cert_der_from_pem(certificate_pem: str) -> bytes:
    """بایت‌های DERِ گواهی را مستقیم از بدنه‌ی PEM می‌گیرد — بدونِ پارسِ ASN.1.

    **چرا پارس نمی‌کنیم:** گواهی‌های برخی مراکز میانیِ ایرانی (ParsSign و…) فیلدهایی
    مثل CN را با کاراکترهای خارج از مجموعه‌ی مجازِ PrintableString (مثلاً `[` و `]` در
    «Omid Arash [Sign]») در همان نوعِ PrintableString کد می‌کنند. OpenSSL سهل‌گیر است و
    می‌پذیرد، ولی پارسرِ سخت‌گیرِ `cryptography` (asn1 راست) با
    `InvalidValue … PrintableString` ردش می‌کند و گواهیِ کاملاً سالمِ کاربر «نامعتبر»
    اعلام می‌شود. برای هدرِ `x5c` فقط به بایت‌های خامِ گواهی نیاز داریم، پس بدنه‌ی
    Base64 را مستقیم decode می‌کنیم و از اعتبارسنجیِ ساختاریِ ASN.1 صرف‌نظر می‌کنیم —
    خودِ سامانه‌ی مؤدیان گواهی را اعتبارسنجی می‌کند.
    """
    text = (certificate_pem or "").strip()
    if not text:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "گواهیِ امضا در تنظیمات مؤدیان ثبت نشده است")
    # نسبت به تعدادِ تیره‌های نشانگرِ PEM رواگیر است: کپی‌کردنِ گواهی از چت/ادیتور
    # گاهی یک `-` از خطِ `-----END CERTIFICATE-----` می‌اندازد (۴ تیره به‌جای ۵). چون
    # فقط بدنه‌ی Base64 برایمان مهم است، `-*` هر تعداد تیره را می‌پذیرد و صرفاً واژه‌های
    # `BEGIN/END CERTIFICATE` را لنگر می‌کند.
    match = re.search(r"BEGIN CERTIFICATE-*(.+?)-*END CERTIFICATE", text, re.DOTALL)
    if not match:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "گواهیِ امضا معتبر نیست (بلوکِ BEGIN/END CERTIFICATE یافت نشد)",
        )
    try:
        der = base64.b64decode("".join(match.group(1).split()), validate=True)
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "گواهیِ امضا معتبر نیست (Base64 خوانده نشد)")
    # کنترلِ سبک بدونِ پارسِ کامل: هر گواهیِ X.509 در DER یک SEQUENCE است (تگِ 0x30).
    if not der or der[0] != 0x30:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "گواهیِ امضا معتبر نیست (ساختارِ DER نامعتبر)")
    return der


def _cert_x5c(certificate_pem: str) -> str:
    """مقدارِ عنصرِ `x5c`: گواهی به‌صورتِ Base64ِ استاندارد از بایت‌های DER (RFC 7515)."""
    return base64.b64encode(_cert_der_from_pem(certificate_pem)).decode("ascii")


def build_jws(payload: bytes, private_key_pem: str, certificate_pem: str, *, sig_time: datetime | None = None) -> str:
    """بسته‌ی JWS compact با الگوریتم RS256 و هدرِ `x5c`/`sigT`/`crit`.

    ورودیِ امضا: ``ASCII(BASE64URL(header) || '.' || BASE64URL(payload))``.
    """
    key = _load_private_key(private_key_pem)
    x5c = _cert_x5c(certificate_pem)
    when = (sig_time or datetime.now(timezone.utc)).astimezone(timezone.utc)
    header = {
        "alg": "RS256",
        "x5c": [x5c],
        "sigT": when.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "crit": ["sigT"],
    }
    header_b64 = _b64u(json.dumps(header, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    payload_b64 = _b64u(payload)
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return f"{header_b64}.{payload_b64}.{_b64u(signature)}"


def build_jwe(plaintext: str, server_key_b64: str, kid: str) -> str:
    """بسته‌ی JWE compact — کلیدِ AES-256-GCM با RSA-OAEP-256 رمز می‌شود.

    محتوای رمزشده = رشته‌ی JWSِ صورتحساب. AAD = ``ASCII(BASE64URL(header))``.
    """
    try:
        public_key = serialization.load_der_public_key(base64.b64decode(server_key_b64))
    except Exception:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "کلید عمومیِ رمزنگاریِ سامانه خوانده نشد")

    header = {"alg": "RSA-OAEP-256", "enc": "A256GCM", "kid": kid}
    header_b64 = _b64u(json.dumps(header, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    aad = header_b64.encode("ascii")

    aes_key = os.urandom(32)  # ۲۵۶ بیت
    iv = os.urandom(12)  # ۹۶ بیت
    ct_and_tag = AESGCM(aes_key).encrypt(iv, plaintext.encode("utf-8"), aad)
    ciphertext, tag = ct_and_tag[:-16], ct_and_tag[-16:]

    encrypted_key = public_key.encrypt(
        aes_key,
        padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
    )
    return ".".join([header_b64, _b64u(encrypted_key), _b64u(iv), _b64u(ciphertext), _b64u(tag)])


# ---------------------------------------------------------------------------
# شناسه یکتای مالیاتی
# ---------------------------------------------------------------------------

# جدول‌های استانداردِ الگوریتمِ Verhoeff (کشفِ همه‌ی خطاهای تک‌رقمی و اغلبِ جابه‌جایی‌ها).
_VERHOEFF_D = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6),
    (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8),
    (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2),
    (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4),
    (9, 8, 7, 6, 5, 4, 3, 2, 1, 0),
)
_VERHOEFF_P = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2),
    (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0),
    (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5),
    (7, 0, 4, 6, 9, 1, 3, 2, 5, 8),
)
_VERHOEFF_INV = (0, 4, 3, 2, 1, 5, 6, 7, 8, 9)


def _verhoeff_check_digit(number: str) -> int:
    """رقمِ کنترلیِ Verhoeff برای یک رشته‌ی صرفاً رقمی (۰-۹)."""
    c = 0
    for i, ch in enumerate(reversed(number)):
        c = _VERHOEFF_D[c][_VERHOEFF_P[(i + 1) % 8][int(ch)]]
    return _VERHOEFF_INV[c]


def _check_character(first21: str) -> str:
    """کاراکترِ بیست‌ودومِ شناسه مالیاتی = رقمِ کنترلیِ **Verhoeff** (طبقِ RC_DCPS).

    الگوی رسمیِ سامانه برای این کاراکتر `[0-9]{1}` است (یک رقم)، نه یک کاراکترِ مبنای
    ۳۲. رشته‌ی ورودیِ Verhoeff از ۲۱ کاراکترِ اول ساخته می‌شود:
    - شناسه حافظه (۶ کاراکتر): هر **حرف** با کدِ UTF-8/اسکیِ ده‌دهی (مثلاً D→۶۸) و هر
      **رقم** با خودِ رقم جایگزین و به‌هم چسبانده می‌شود.
    - تاریخ (۵ کاراکترِ Hex) → مبنای ۱۰، صفرگذاری‌شده تا ۶ رقم.
    - سریال (۱۰ کاراکترِ Hex) → مبنای ۱۰، صفرگذاری‌شده تا ۱۲ رقم.
    نمونه‌ی مرجع: `DEF5GH`+`0481F`+`000000000C` → رقمِ کنترلی `2` (در تست قفل شده).
    """
    memory, date_hex, serial_hex = first21[:6], first21[6:11], first21[11:21]
    mem_digits = "".join(str(ord(ch)) if ch.isalpha() else ch for ch in memory)
    date_dec = str(int(date_hex, 16)).rjust(6, "0")
    serial_dec = str(int(serial_hex, 16)).rjust(12, "0")
    return str(_verhoeff_check_digit(mem_digits + date_dec + serial_dec))


def _days_since_epoch(invoice_date: date) -> int:
    days = (invoice_date - _TAXID_EPOCH).days
    if days < 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "تاریخ صورتحساب نامعتبر است")
    return days


def generate_tax_id(memory_id: str, invoice_date: date, serial: int) -> str:
    """شناسه یکتای مالیاتیِ ۲۲ کاراکتری.

    ساختار: ۶ کاراکترِ شناسه حافظه + ۵ کاراکترِ تاریخ (تعداد روز از مبدأ، مبنای ۱۶)
    + ۱۰ کاراکترِ سریال (مبنای ۱۶) + ۱ کاراکترِ کنترلی. تاریخِ این شناسه باید با
    تاریخِ فیلدِ `indatim` بسته یکی باشد (هر دو از همان روزِ میلادی مشتق می‌شوند).
    """
    memory = (memory_id or "").strip().upper()
    if len(memory) != 6:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "شناسه یکتای حافظه مالیاتی باید دقیقاً ۶ کاراکتر باشد؛ آن را در تنظیمات مؤدیان وارد کنید.",
        )
    if serial <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "سریال صورتحساب باید بزرگ‌تر از صفر باشد")

    date_part = format(_days_since_epoch(invoice_date), "X").rjust(5, "0")
    serial_part = format(serial, "X").rjust(10, "0")
    if len(date_part) > 5 or len(serial_part) > 10:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "تاریخ یا سریال از ظرفیتِ شناسه مالیاتی بیشتر است")

    first21 = f"{memory}{date_part}{serial_part}"
    return first21 + _check_character(first21)


# ---------------------------------------------------------------------------
# بسته‌ی صورتحساب ── نگاشتِ فیلدها مطابق «دستورالعمل صدور صورتحساب» (RC_IITP)
# ---------------------------------------------------------------------------

def _rial(amount) -> int:
    """مبالغِ بسته صحیح‌اند (بدونِ اعشار)؛ گردکردن اینجا متمرکز است."""
    return int(Decimal(amount).quantize(Decimal(1)))


def _buyer_type(contact: Contact | None) -> int:
    """نوعِ شخصِ خریدار: حقیقی=۱، حقوقی=۲ (مطابق RC_IITP)."""
    if contact and (contact.entity_type or "").strip().lower() == "legal":
        return 2
    return 1


def build_invoice_packet(
    invoice: SalesInvoice, settings: MoadianSettings, tax_id: str, contact: Contact | None = None
) -> dict:
    """بسته‌ی صورتحساب: `{header, body[], payments[]}` مطابقِ نمونه‌ی اسپک.

    الگوی اول (فروش)، موضوعِ اصلی. اگر خریدار شماره اقتصادی داشته باشد نوعِ اول
    (با اطلاعاتِ خریدار) و در غیرِ این‌صورت نوعِ دوم صادر می‌شود.
    """
    days = _days_since_epoch(invoice.invoice_date)
    indatim = days * _MS_PER_DAY

    net_total = _rial(invoice.total_amount)  # جمعِ پس از تخفیف
    discount_total = _rial(invoice.total_discount or 0)
    tax_total = _rial(invoice.tax_amount)
    gross_total = net_total + discount_total
    rate = Decimal(invoice.tax_rate or 0)

    body = []
    for line in invoice.lines:
        line_gross = _rial(Decimal(line.qty) * Decimal(line.unit_price))
        line_discount = _rial(line.discount or 0)
        line_net = line_gross - line_discount
        line_tax = _rial(Decimal(line_net) * rate / Decimal(100))
        body.append(
            {
                "sstid": (line.item.sku if line.item else "") or "",  # شناسه کالا/خدمت
                "sstt": (line.item.name if line.item else "") or "",  # شرح کالا/خدمت
                "mu": "164",  # واحد اندازه‌گیری (عدد) — کدِ جدولِ واحدها
                "am": float(Decimal(line.qty)),  # تعداد/مقدار
                "fee": _rial(line.unit_price),  # مبلغ واحد
                "prdis": line_gross,  # مبلغ قبل از تخفیف
                "dis": line_discount,  # مبلغ تخفیف
                "adis": line_net,  # مبلغ بعد از تخفیف
                "vra": float(rate),  # نرخ مالیات بر ارزش افزوده
                "vam": line_tax,  # مبلغ مالیات بر ارزش افزوده
                "tsstam": line_net + line_tax,  # مبلغ کل کالا/خدمت
            }
        )

    has_economic = bool(contact and (contact.economic_code or "").strip())
    header = {
        "taxid": tax_id,
        "indatim": indatim,  # تاریخ و زمان صدور (میلادی، یونیکس ms)
        "inty": 1 if has_economic else 2,  # نوع صورتحساب: ۱=نوع اول، ۲=نوع دوم
        "inno": str(invoice.number or ""),  # سریال داخلی حافظه
        "inp": 1,  # الگوی صورتحساب: ۱=فروش
        "ins": 1,  # موضوع صورتحساب: ۱=اصلی
        "tins": (settings.economic_code or settings.national_id or "").strip(),  # شماره اقتصادی فروشنده
        "tob": _buyer_type(contact),  # نوع شخص خریدار
        "tprdis": gross_total,  # جمع مبلغ قبل از کسر تخفیف
        "tdis": discount_total,  # جمع تخفیفات
        "tadis": net_total,  # جمع مبلغ پس از کسر تخفیف
        "tvam": tax_total,  # جمع مالیات بر ارزش افزوده
        "todam": 0,  # جمع سایر مالیات، عوارض و وجوه قانونی
        "tbill": net_total + tax_total,  # مجموع صورتحساب
        "setm": 1,  # روش تسویه: ۱=نقدی
    }
    if has_economic:
        header["bid"] = (contact.national_id or "").strip()  # شناسه/شماره ملی خریدار
        header["tinb"] = (contact.economic_code or "").strip()  # شماره اقتصادی خریدار
        if (contact.postal_code or "").strip():
            header["bpc"] = contact.postal_code.strip()  # کد پستی خریدار

    return {"header": header, "body": body, "payments": []}


# ---------------------------------------------------------------------------
# تنظیمات
# ---------------------------------------------------------------------------

def get_settings(db: Session) -> MoadianSettings:
    """تنظیماتِ این کسب‌وکار؛ اگر نبود یک ردیفِ خالیِ غیرفعال می‌سازد."""
    row = db.query(MoadianSettings).first()
    if row is None:
        row = MoadianSettings()
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def base_url_for(settings: MoadianSettings) -> str:
    if settings.base_url_override.strip():
        return settings.base_url_override.strip().rstrip("/")
    return SANDBOX_BASE_URL if settings.is_sandbox else PRODUCTION_BASE_URL


def _next_serial(db: Session, settings: MoadianSettings) -> int:
    settings.last_serial = int(settings.last_serial or 0) + 1
    db.flush()
    return settings.last_serial


# ---------------------------------------------------------------------------
# فراخوانیِ وب‌سرویس
# ---------------------------------------------------------------------------

def _fetch_nonce(client: httpx.Client) -> str:
    response = client.get(f"{API_PREFIX}/nonce", params={"timeToLive": 30})
    response.raise_for_status()
    nonce = (response.json() or {}).get("nonce")
    if not nonce:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "سامانه مؤدیان چالشِ تصادفی (nonce) برنگرداند")
    return nonce


def _auth_token(client: httpx.Client, settings: MoadianSettings) -> str:
    """توکنِ احرازِ یکبارمصرف: nonce را گرفته و امضا می‌کند (clientId = شناسه حافظه)."""
    nonce = _fetch_nonce(client)
    payload = json.dumps(
        {"nonce": nonce, "clientId": settings.memory_id}, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return build_jws(payload, settings.private_key_pem, settings.certificate_pem)


def _server_encryption_key(client: httpx.Client, settings: MoadianSettings) -> tuple[str, str]:
    """(کلیدِ عمومیِ Base64، شناسه‌ی کلید) از `server-information` — کلیدِ رمزنگاری (purpose=1)."""
    token = _auth_token(client, settings)
    response = client.get(
        f"{API_PREFIX}/server-information", headers={"Authorization": f"Bearer {token}"}
    )
    response.raise_for_status()
    keys = (response.json() or {}).get("publicKeys") or []
    chosen = next((k for k in keys if k.get("purpose") == 1), keys[0] if keys else None)
    if not chosen or not chosen.get("key") or not chosen.get("id"):
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "کلید عمومیِ رمزنگاریِ سامانه دریافت نشد")
    return chosen["key"], chosen["id"]


def _auth_failure_hint(status_code: int, settings: MoadianSettings) -> str:
    """پیامِ خوانا برای ۴۰۱/۴۰۳ — به‌جای `HTTPStatusError`ِ خام که چیزی به کاربر نمی‌گوید."""
    env = "سندباکس" if settings.is_sandbox else "واقعی"
    return (
        f"احراز هویت با سامانه مؤدیان ناموفق بود (HTTP {status_code}) در محیطِ {env}. "
        f"محتمل‌ترین علت‌ها: «شناسه حافظه» ({settings.memory_id or '—'}) در این محیط ثبت نشده، "
        "یا گواهیِ امضا در کارپوشه‌ی همین محیط بارگذاری نشده، "
        "یا کلید خصوصیِ واردشده جفتِ همان گواهی نیست."
    )


def test_connection(db: Session, *, client: httpx.Client | None = None) -> dict:
    """اتصال و احراز هویت را می‌سنجد: `nonce → توکنِ JWS → server-information`.

    فقط یک GETِ فقط‌خواندنی است — **نه سریالی مصرف می‌شود نه صورتحسابی ثبت**. برای
    عیب‌یابیِ اعتبارنامه/محیط پیش از ارسالِ واقعی. چون فقط می‌خوانَد، حتی روی محیطِ
    واقعی هم بی‌خطر است.
    """
    settings = get_settings(db)
    environment = "سندباکس" if settings.is_sandbox else "واقعی"
    # پیش‌شرط‌های پیکربندی؛ اگر کلید/گواهی نباشد HTTPException(400) می‌دهند.
    if not (settings.memory_id or "").strip():
        return {"ok": False, "environment": environment, "status_code": None,
                "message": "«شناسه حافظه» وارد نشده است.", "server_key_id": None}
    _load_private_key(settings.private_key_pem)
    _cert_der_from_pem(settings.certificate_pem)

    owns_client = client is None
    if owns_client:
        client = httpx.Client(base_url=base_url_for(settings), timeout=REQUEST_TIMEOUT)
    try:
        _server_key, kid = _server_encryption_key(client, settings)
        return {"ok": True, "environment": environment, "status_code": 200,
                "message": f"اتصال و احراز هویت با محیطِ {environment} موفق بود؛ کلیدِ رمزنگاریِ سامانه دریافت شد.",
                "server_key_id": kid}
    except httpx.HTTPStatusError as err:
        code = err.response.status_code
        msg = _auth_failure_hint(code, settings) if code in (401, 403) else f"سامانه با خطای HTTP {code} پاسخ داد."
        return {"ok": False, "environment": environment, "status_code": code, "message": msg, "server_key_id": None}
    except httpx.HTTPError as err:
        return {"ok": False, "environment": environment, "status_code": None,
                "message": f"خطای ارتباط با سامانه مؤدیان ({type(err).__name__}).", "server_key_id": None}
    finally:
        if owns_client:
            client.close()


def submit_invoice(
    db: Session, invoice_id: UUID, user: User, *, client: httpx.Client | None = None
) -> MoadianSubmission:
    """صورتحساب را امضا، رمز و به سامانه (API v2) ارسال می‌کند و ردِ کامل را ثبت می‌کند.

    خطاهای شبکه/سامانه به‌جای پرتاب، در وضعیتِ `failed`/`rejected` ثبت می‌شوند؛ فقط
    خطاهای پیکربندی (کلید/گواهی/شناسه‌ی نبود) جلوی ارسال را می‌گیرند.
    """
    settings = get_settings(db)
    if not settings.is_active:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "ارسال به سامانه مؤدیان فعال نیست؛ اول تنظیمات را کامل و فعال کنید.",
        )

    invoice = db.get(SalesInvoice, invoice_id)
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "فاکتور یافت نشد")
    if invoice.voided_at is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "فاکتور باطل‌شده به سامانه ارسال نمی‌شود")

    existing = (
        db.query(MoadianSubmission)
        .filter(
            MoadianSubmission.sales_invoice_id == invoice_id,
            MoadianSubmission.status.in_(("sent", "confirmed")),
        )
        .first()
    )
    if existing is not None:
        # ارسالِ دوباره‌ی همان فاکتور یعنی دو صورتحساب قانونی با دو شناسه — عمداً بسته است.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "این فاکتور قبلاً با موفقیت ارسال شده است")

    # اعتبارنامه پیش از تخصیصِ سریال بررسی می‌شود تا یک سریال بی‌جهت مصرف نشود.
    _load_private_key(settings.private_key_pem)
    _cert_der_from_pem(settings.certificate_pem)

    contact = db.get(Contact, invoice.contact_id) if invoice.contact_id else None
    serial = _next_serial(db, settings)
    tax_id = generate_tax_id(settings.memory_id, invoice.invoice_date, serial)
    packet = build_invoice_packet(invoice, settings, tax_id, contact)
    invoice_json = json.dumps(packet, separators=(",", ":"), ensure_ascii=False)

    request_trace_id = str(uuid4())
    submission = MoadianSubmission(
        sales_invoice_id=invoice.id,
        tax_id=tax_id,
        serial=serial,
        invoice_date=invoice.invoice_date,
        status="pending",
        reference_number="",
        request_payload={"requestTraceId": request_trace_id, "fiscalId": settings.memory_id, "invoice": packet},
        created_by_id=user.id,
    )
    db.add(submission)
    db.flush()

    owns_client = client is None
    if owns_client:
        client = httpx.Client(base_url=base_url_for(settings), timeout=REQUEST_TIMEOUT)
    try:
        server_key, kid = _server_encryption_key(client, settings)
        signed = build_jws(invoice_json.encode("utf-8"), settings.private_key_pem, settings.certificate_pem)
        jwe = build_jwe(signed, server_key, kid)

        token = _auth_token(client, settings)
        body = [{"payload": jwe, "header": {"requestTraceId": request_trace_id, "fiscalId": settings.memory_id}}]
        response = client.post(
            f"{API_PREFIX}/invoice",
            json=body,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        try:
            data = response.json()
        except ValueError:
            data = {"raw": response.text[:2000]}

        if response.status_code >= 400:
            submission.status = "rejected"
            submission.error_message = f"HTTP {response.status_code}"
        else:
            result = (data or {}).get("result") or []
            reference = str(result[0].get("referenceNumber")) if result and result[0].get("referenceNumber") else ""
            submission.reference_number = reference
            submission.status = "sent" if reference else "rejected"
            if not reference:
                submission.error_message = "پاسخِ سامانه شماره‌ی پیگیری نداشت"
        submission.response_payload = data
        submission.sent_at = datetime.now(timezone.utc)
    except HTTPException:
        raise
    except httpx.HTTPStatusError as err:
        submission.status = "failed"
        code = err.response.status_code
        submission.error_message = (
            _auth_failure_hint(code, settings) if code in (401, 403) else f"سامانه با خطای HTTP {code} پاسخ داد."
        )[:500]
    except httpx.HTTPError as err:
        submission.status = "failed"
        submission.error_message = f"خطای ارتباط با سامانه مؤدیان ({type(err).__name__})."[:500]
    finally:
        if owns_client:
            client.close()

    db.commit()
    db.refresh(submission)
    return submission


def inquire_status(db: Session, submission_id: UUID, *, client: httpx.Client | None = None) -> MoadianSubmission:
    """وضعیتِ یک صورتحسابِ ارسال‌شده را با شماره‌ی پیگیری استعلام و به‌روزرسانی می‌کند."""
    submission = db.get(MoadianSubmission, submission_id)
    if submission is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "رکوردِ ارسال یافت نشد")
    if not (submission.reference_number or "").strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "این ارسال شماره‌ی پیگیری ندارد")

    settings = get_settings(db)
    owns_client = client is None
    if owns_client:
        client = httpx.Client(base_url=base_url_for(settings), timeout=REQUEST_TIMEOUT)
    try:
        token = _auth_token(client, settings)
        response = client.get(
            f"{API_PREFIX}/inquiry-by-reference-id",
            params={"referenceIds": submission.reference_number},
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        rows = response.json() or []
        row = rows[0] if rows else {}
        state = (row.get("status") or "").upper()
        submission.response_payload = row or submission.response_payload
        if state == "SUCCESS":
            submission.status = "confirmed"
            submission.error_message = ""
        elif state == "FAILED":
            submission.status = "rejected"
            errors = ((row.get("data") or {}).get("error")) or []
            submission.error_message = "؛ ".join(e.get("message", "") for e in errors)[:500] or "صورتحساب رد شد"
        # IN_PROGRESS/NOT_FOUND → وضعیت دست‌نخورده می‌ماند تا استعلامِ بعدی.
    except httpx.HTTPError as err:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"استعلام ناموفق بود: {type(err).__name__}")
    finally:
        if owns_client:
            client.close()

    db.commit()
    db.refresh(submission)
    return submission


def list_submissions(db: Session) -> list[MoadianSubmission]:
    return (
        db.query(MoadianSubmission)
        .order_by(MoadianSubmission.created_at.desc())
        .all()
    )
