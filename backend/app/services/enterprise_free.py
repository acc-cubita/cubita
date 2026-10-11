"""ثبت‌نامِ رایگانِ «کوبیتا سازمانی» — سمتِ ابر.

**مدلِ رایگان (تصمیمِ مالک، ۱۴۰۵/۰۷/۱۸):** همیشگی، همه‌ی ماژول‌های حسابداری، تا سه کاربر.
کاربرِ بیشتر، قابلیت‌های پولی (`PREMIUM_FEATURES`، اول از همه مؤدیان) و پشتیبانی با مجوزِ
پولی می‌آیند — همان مسیرِ کدِ فعال‌سازیِ امروز. پس رایگان جای پولی را نمی‌گیرد، درِ ورودیِ آن است.

**چرا ثبت‌نام و نه رایگانِ بی‌نام:** فهرستِ نصب‌ها و راهِ تماس با هر مشتری پایه‌ی هر درآمدِ
بعدی است. شماره با کدِ پیامکی تأیید می‌شود تا فهرست واقعی بماند. سرورِ بی‌اینترنت همان راهِ
«کدِ درخواست» را دارد: پشتیبانی در پنل مجوزِ رایگان می‌سازد و صادر می‌کند.

**یک مسیرِ صدور:** ردیفِ رایگان هم از `enterprise_licenses.bind_and_issue` می‌گذرد، پس
گره به دستگاه و رویدادهای تاریخچه با مجوزِ پولی یکی است.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.licensing import fingerprint
from app.licensing.state import decode_request
from app.licensing.token import LicenseError
from app.models.enterprise_license_registry import EnterpriseFreeCode, EnterpriseLicenseRecord
from app.services import enterprise_licenses, sms
from app.services.tokens import _numeric_code, hash_token

TIER = "free"
FREE_SEATS = 3
#: قابلیت‌های پولی‌ای که رایگان دارد: هیچ. فهرستِ خالی (نه None) یعنی «هیچ‌کدام»؛
#: None در توکن یعنی «همه» (`licensing/state.py`).
FREE_FEATURES: list[str] = []
CODE_TTL_MINUTES = 10
MAX_ATTEMPTS = 5
#: «گیرنده‌ی» رویدادهای تاریخچه وقتی خودِ مشتری ثبت‌نام می‌کند (هم‌رده‌ی `online`).
ACTOR = "free"


def normalize_phone(raw: str) -> str:
    phone = sms.normalize_phone(raw)
    if phone is None:
        raise LicenseError("شماره‌ی همراه درست نیست؛ آن را مثلِ ۰۹۱۲۱۲۳۴۵۶۷ بنویسید.")
    return phone


def mask_phone(phone: str) -> str:
    return phone[:4] + "*" * (len(phone) - 7) + phone[-3:] if len(phone) >= 7 else phone


def _code_hash(phone: str, install: str, code: str) -> str:
    #: نصب در نمک است: کدی که برای یک سرور فرستاده شده، مجوزِ سرورِ دیگری را نمی‌سازد.
    return hash_token(f"{phone}:enterprise_free:{install}:{code}")


def send_code(db: Session, phone_raw: str, request_code: str) -> str:
    """کدِ ۶رقمی می‌سازد و پیامک می‌کند؛ شماره‌ی نرمال‌شده را برمی‌گرداند.

    کدهای قبلیِ همین شماره پاک می‌شوند تا «ارسالِ دوباره» قبلی را باطل کند.
    """
    phone = normalize_phone(phone_raw)
    request = decode_request(request_code)
    db.query(EnterpriseFreeCode).filter(EnterpriseFreeCode.phone == phone).delete()
    code = _numeric_code(6)
    db.add(
        EnterpriseFreeCode(
            phone=phone,
            code_hash=_code_hash(phone, request["install"], code),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=CODE_TTL_MINUTES),
        )
    )
    db.flush()
    if not sms.send_verification_code(phone, code):
        raise LicenseError("پیامکِ کد ارسال نشد؛ چند دقیقه‌ی دیگر دوباره امتحان کنید.")
    return phone


def _consume(db: Session, phone: str, install: str, code: str) -> bool:
    """مثلِ `consume_email_code`: بینِ «نیست»، «منقضی»، «قفل» و «غلط» فرق نمی‌گذارد."""
    row = (
        db.query(EnterpriseFreeCode)
        .filter(EnterpriseFreeCode.phone == phone)
        .order_by(EnterpriseFreeCode.created_at.desc())
        .first()
    )
    if row is None or row.expires_at <= datetime.now(timezone.utc) or row.attempts >= MAX_ATTEMPTS:
        return False
    if row.code_hash != _code_hash(phone, install, "".join(code.split())):
        row.attempts += 1
        db.flush()
        return False
    db.delete(row)
    db.flush()
    return True


def _existing(db: Session, install: str, fp: dict) -> EnterpriseLicenseRecord | None:
    """مجوزِ رایگانِ همین سرور، اگر قبلاً ثبت‌نام کرده (نصبِ دوباره، پاک‌شدنِ مجوز).

    نصبی با همان شناسه ولی رایانه‌ی دیگر (تصویرِ کپی‌شده‌ی سرور) مجوزِ خودش را می‌گیرد: رایگان
    است و «انتقال» برایش فقط مزاحمت بود.
    """
    rows = (
        db.query(EnterpriseLicenseRecord)
        .filter(
            EnterpriseLicenseRecord.tier == TIER,
            EnterpriseLicenseRecord.status == "active",
            EnterpriseLicenseRecord.install_id == install,
        )
        .order_by(EnterpriseLicenseRecord.created_at.desc())
        .all()
    )
    return next((r for r in rows if not r.fp or fingerprint.matches(r.fp, fp)), None)


def create_record(
    db: Session, *, org_name: str, contact: str | None, note: str | None, actor: str
) -> tuple[EnterpriseLicenseRecord, str]:
    """ردیفِ مجوزِ رایگان + کدِ فعال‌سازی‌اش — از ثبت‌نامِ خودِ مشتری یا از پنلِ ستاد.

    در ثبت‌نامِ پیامکی کد به کسی داده نمی‌شود (فعال‌سازی با پیامک است)؛ ستاد آن را برای
    سرورِ بی‌اینترنت به مشتری می‌دهد، تا اگر بعداً اینترنت پیدا کرد آنلاین فعال کند.
    """
    record, code = enterprise_licenses.create(
        db,
        org_name=org_name,
        contact=contact,
        seats=FREE_SEATS,
        days=None,
        grace_days=0,
        mods=None,
        feat=list(FREE_FEATURES),
        note=note,
        actor=actor,
    )
    record.tier = TIER
    db.flush()
    return record, code


def activate(db: Session, phone_raw: str, code: str, request_code: str, org: str | None) -> str:
    """کدِ پیامکی را می‌سنجد و توکنِ امضاشده‌ی رایگانِ همین سرور را برمی‌گرداند."""
    phone = normalize_phone(phone_raw)
    request = decode_request(request_code)
    if not _consume(db, phone, request["install"], code):
        raise LicenseError("کدِ تأیید درست نیست یا منقضی شده است؛ کدِ تازه بگیرید.")

    record = _existing(db, request["install"], request["fp"])
    if record is None:
        name = (org or request.get("org") or "").strip()[:200]
        record, _code = create_record(
            db,
            org_name=name if len(name) >= 2 else "بی‌نام",
            contact=phone,
            note="ثبت‌نامِ رایگان",
            actor=ACTOR,
        )
    else:
        #: آخرین شماره‌ی تأییدشده راهِ تماسِ درست است.
        record.contact = phone
    return enterprise_licenses.bind_and_issue(db, record, request_code, ACTOR)
