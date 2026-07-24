"""سامانه مؤدیان — تولید شناسه مالیاتی، ساخت و امضای بسته‌ی صورتحساب، و ارسال.

**مرزبندیِ اطمینان (مهم):**

آنچه قطعی است و اینجا کامل پیاده شده: امضای دیجیتال (RSA/SHA-256، PKCS#1 v1.5،
خروجی base64)، مدیریت و نگه‌داریِ کلید، شمارنده‌ی سریال، ردیابیِ وضعیتِ ارسال، و
مدیریتِ خطا/timeout.

آنچه به نسخه‌ی دستورالعملِ سازمان امور مالیاتی وابسته است و باید با PDF نسخه‌ی
جاریِ خودتان تطبیق داده شود: ترکیبِ دقیقِ «شناسه یکتای مالیاتی» (به‌ویژه کاراکترِ
کنترلی) و نامِ دقیقِ فیلدهای بسته. این دو عمداً در `generate_tax_id` و
`build_invoice_packet` ایزوله شده‌اند تا اصلاحشان یک تغییرِ کوچک و موضعی باشد و
بقیه‌ی ماژول دست‌نخورده بماند. تست‌ها رفتارِ فعلی را پین می‌کنند تا هر اصلاحی
آگاهانه باشد. پیش‌فرضِ محیط «سندباکس» است تا ارسالِ ناخواسته به سامانه‌ی واقعی
ممکن نباشد.
"""
import base64
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.invoices import SalesInvoice
from app.models.moadian import MoadianSettings, MoadianSubmission
from app.models.user import User

#: آدرس‌های پایه‌ی سامانه. با `base_url_override` قابلِ بازنویسی‌اند.
SANDBOX_BASE_URL = "https://sandboxrc.tax.gov.ir"
PRODUCTION_BASE_URL = "https://tp.tax.gov.ir"
SUBMIT_PATH = "/req/api/self-tsp/sync/invoices"

REQUEST_TIMEOUT = 30.0

#: مبدأ شمارشِ روز در شناسه مالیاتی (میلادی) — مطابق مستندات، روزهای سپری‌شده از
#: ابتدای دوران یونیکس.
_TAXID_EPOCH = date(1970, 1, 1)


# ---------------------------------------------------------------------------
# شناسه یکتای مالیاتی  ── بخشِ وابسته به نسخه‌ی دستورالعمل
# ---------------------------------------------------------------------------

def _check_character(first21: str) -> str:
    """کاراکترِ کنترلیِ شناسه مالیاتی (کاراکتر بیست‌ودوم).

    ⚠️ این تابع را با دستورالعملِ نسخه‌ی جاریِ خودتان تطبیق بدهید. پیاده‌سازیِ فعلی
    روشِ «جمعِ وزن‌دار به پیمانه‌ی ۳۲» است: هر کاراکتر به عددش نگاشته می‌شود (رقم‌ها
    ۰..۹ و حروف A..Z به ۱۰..۳۵)، در وزنِ موقعیتش ضرب و جمع می‌شود، و باقیمانده به
    یک کاراکترِ الفبای ۳۲تایی برمی‌گردد.
    """
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUV"  # ۳۲ کاراکتر
    total = 0
    for position, char in enumerate(first21, start=1):
        value = int(char, 36) if char.isalnum() else 0
        total += value * position
    return alphabet[total % len(alphabet)]


def generate_tax_id(memory_id: str, invoice_date: date, serial: int) -> str:
    """شناسه یکتای مالیاتیِ ۲۲ کاراکتری.

    ساختار: ۶ کاراکترِ شناسه حافظه + ۵ کاراکترِ تاریخ (تعداد روز از مبدأ، مبنای ۱۶)
    + ۱۰ کاراکترِ سریال (مبنای ۱۶) + ۱ کاراکترِ کنترلی.
    """
    memory = (memory_id or "").strip().upper()
    if len(memory) != 6:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "شناسه یکتای حافظه مالیاتی باید دقیقاً ۶ کاراکتر باشد؛ آن را در تنظیمات مؤدیان وارد کنید.",
        )
    if serial <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "سریال صورتحساب باید بزرگ‌تر از صفر باشد")

    days = (invoice_date - _TAXID_EPOCH).days
    if days < 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "تاریخ صورتحساب نامعتبر است")

    date_part = format(days, "X").rjust(5, "0")
    serial_part = format(serial, "X").rjust(10, "0")
    if len(date_part) > 5 or len(serial_part) > 10:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "تاریخ یا سریال از ظرفیتِ شناسه مالیاتی بیشتر است")

    first21 = f"{memory}{date_part}{serial_part}"
    return first21 + _check_character(first21)


# ---------------------------------------------------------------------------
# بسته‌ی صورتحساب ── بخشِ وابسته به نسخه‌ی دستورالعمل
# ---------------------------------------------------------------------------

def _rial(amount) -> int:
    """مبالغِ بسته صحیح‌اند؛ گردکردن اینجا متمرکز است تا همه‌جا یکسان باشد."""
    return int(Decimal(amount).quantize(Decimal(1)))


def build_invoice_packet(invoice: SalesInvoice, settings: MoadianSettings, tax_id: str) -> dict:
    """بسته‌ی صورتحساب مطابق ساختارِ «سرآیند + اقلام» سامانه.

    ⚠️ نامِ فیلدها را با دستورالعملِ نسخه‌ی جاریِ خودتان تطبیق بدهید.
    """
    net = _rial(invoice.total_amount)  # پس از تخفیف
    discount = _rial(invoice.total_discount or 0)
    tax = _rial(invoice.tax_amount)

    body = []
    for line in invoice.lines:
        line_gross = _rial(Decimal(line.qty) * Decimal(line.unit_price))
        line_discount = _rial(line.discount or 0)
        line_net = line_gross - line_discount
        rate = Decimal(invoice.tax_rate or 0)
        line_tax = _rial(Decimal(line_net) * rate / Decimal(100))
        body.append(
            {
                "sstid": line.item.sku if line.item else "",  # شناسه کالا/خدمت
                "sstt": line.item.name if line.item else "",  # شرح کالا/خدمت
                "am": float(Decimal(line.qty)),  # مقدار
                "fee": _rial(line.unit_price),  # مبلغ واحد
                "am_ir": line_gross,  # مبلغ قبل از تخفیف
                "dis": line_discount,  # تخفیف
                "adis": line_net,  # مبلغ پس از تخفیف
                "vra": float(rate),  # نرخ مالیات بر ارزش افزوده
                "vam": line_tax,  # مبلغ مالیات
                "tsstam": line_net + line_tax,  # جمعِ قلم
            }
        )

    header = {
        "taxid": tax_id,
        "indatim": int(datetime.combine(invoice.invoice_date, datetime.min.time()).timestamp() * 1000),
        "inty": 1,  # نوع صورتحساب: ۱ = الگوی اول (فروش)
        "inno": str(invoice.number or ""),  # شماره صورتحساب داخلی
        "tins": settings.national_id,  # شناسه ملی/اقتصادی فروشنده
        "tob": 2,  # نوع شخص خریدار
        "tprdis": net + discount,  # جمع مبلغ قبل از تخفیف
        "tdis": discount,  # جمع تخفیف
        "tadis": net,  # جمع مبلغ پس از تخفیف
        "tvam": tax,  # جمع مالیات بر ارزش افزوده
        "tbill": net + tax,  # جمع کل صورتحساب
    }

    return {"header": header, "body": body}


# ---------------------------------------------------------------------------
# امضای دیجیتال ── بخشِ قطعی
# ---------------------------------------------------------------------------

def _canonical_json(packet: dict) -> bytes:
    """نمایشِ قطعیِ بسته برای امضا.

    ترتیبِ کلیدها ثابت و فاصله‌ها حذف می‌شوند: امضا روی بایت‌ها انجام می‌شود، پس اگر
    همان بسته دوباره با ترتیبِ دیگری سریال شود، امضا دیگر تطبیق نمی‌کند.
    """
    return json.dumps(packet, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sign_packet(packet: dict, private_key_pem: str) -> str:
    """امضای RSA/SHA-256 (PKCS#1 v1.5) روی بسته، خروجی base64."""
    if not (private_key_pem or "").strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "کلید خصوصی در تنظیمات مؤدیان ثبت نشده است")
    try:
        key = serialization.load_pem_private_key(private_key_pem.encode("utf-8"), password=None)
    except Exception:
        # متنِ خطا عمداً کلید را بازتاب نمی‌دهد.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "کلید خصوصی معتبر نیست (فرمت PEM خوانده نشد)")

    signature = key.sign(_canonical_json(packet), padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(signature).decode("ascii")


# ---------------------------------------------------------------------------
# تنظیمات و ارسال
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


def submit_invoice(db: Session, invoice_id: UUID, user: User, *, client: httpx.Client | None = None) -> MoadianSubmission:
    """صورتحساب را امضا و به سامانه ارسال می‌کند و ردِ کامل را ثبت می‌کند.

    هر خطای شبکه/سامانه به‌جای پرتاب‌شدن، در وضعیتِ `failed` ثبت می‌شود تا سابقه‌ی
    تلاش گم نشود؛ فقط خطاهای پیکربندی (کلید/شناسه‌ی نبود) جلوی ارسال را می‌گیرند.
    """
    settings = get_settings(db)
    if not settings.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ارسال به سامانه مؤدیان فعال نیست؛ اول تنظیمات را کامل و فعال کنید.")

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

    serial = _next_serial(db, settings)
    tax_id = generate_tax_id(settings.memory_id, invoice.invoice_date, serial)
    packet = build_invoice_packet(invoice, settings, tax_id)
    signature = sign_packet(packet, settings.private_key_pem)

    envelope = {"payload": packet, "signature": signature, "signatureKeyId": settings.memory_id}

    submission = MoadianSubmission(
        sales_invoice_id=invoice.id,
        tax_id=tax_id,
        serial=serial,
        invoice_date=invoice.invoice_date,
        status="pending",
        request_payload=envelope,
        created_by_id=user.id,
    )
    db.add(submission)
    db.flush()

    owns_client = client is None
    if owns_client:
        client = httpx.Client(base_url=base_url_for(settings), timeout=REQUEST_TIMEOUT)
    try:
        response = client.post(SUBMIT_PATH, json=envelope)
        try:
            data = response.json()
        except ValueError:
            data = {"raw": response.text[:2000]}
        if response.status_code >= 400:
            submission.status = "rejected"
            submission.error_message = f"HTTP {response.status_code}"
        else:
            submission.status = "sent"
            submission.reference_number = str(data.get("referenceNumber") or data.get("uid") or "")
        submission.response_payload = data
        submission.sent_at = datetime.now(timezone.utc)
    except httpx.HTTPError as err:
        submission.status = "failed"
        submission.error_message = f"{type(err).__name__}: {err}"[:500]
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
