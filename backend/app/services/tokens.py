"""صدور و مصرف توکن‌های یک‌بارمصرف (بازیابی رمز، دعوت).

این ماژول کوچک است ولی تنها چیزی است که بین یک غریبه و حساب یک مشتری ایستاده، پس
هر تصمیمش عمدی است:

- **راز فقط یک بار وجود دارد.** `issue()` مقدار خام را برمی‌گرداند و فقط hash آن را
  ذخیره می‌کند. اگر مقدار خام ذخیره می‌شد، یک نشتِ خواندنی از دیتابیس (یا یک پشتیبان
  گم‌شده) به تصاحب همه‌ی حساب‌ها تبدیل می‌شد.
- **۲۵۶ بیت آنتروپی.** حدس زدن غیرممکن است، پس نیازی به سقف نرخ روی خودِ مصرف نیست.
- **یک‌بارمصرف و زماندار.** لینکی که در تاریخچه‌ی مرورگر یا لاگ پراکسی می‌ماند نباید
  برای همیشه کار کند.
- **صدور تازه، قبلی‌ها را می‌کشد.** اگر کاربر سه بار «رمزم را فراموش کردم» بزند،
  فقط آخرین لینک کار می‌کند؛ وگرنه هر لینک قدیمیِ رهاشده یک راه ورود باز است.

`consume()` عمداً بین «توکن وجود ندارد»، «منقضی شده» و «قبلاً مصرف شده» فرق نمی‌گذارد
و در هر سه حالت None برمی‌گرداند — تفکیکشان به مهاجم می‌گوید کدام حدسش نزدیک بوده.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.auth_token import AuthToken

#: طول راز به بایت. ۳۲ بایت = ۲۵۶ بیت، که پس از base64 حدود ۴۳ کاراکتر می‌شود.
TOKEN_BYTES = 32

PASSWORD_RESET_HOURS = 1
#: دعوت باید بلندمدت‌تر باشد: گیرنده معمولاً منتظر آن نیست و ممکن است ایمیل را
#: چند روز بعد ببیند. یک ساعت برای دعوت یعنی بیشتر دعوت‌ها منقضی می‌رسند.
INVITE_DAYS = 7


def hash_token(raw: str) -> str:
    """SHA-256 بدون salt — عمدی.

    این‌جا برخلاف رمز عبور، salt و KDF کند لازم نیست: ورودی خودش ۲۵۶ بیت تصادفی
    است، پس نه فرهنگ‌لغتی برای حمله وجود دارد و نه rainbow table‌ای معنا دارد.
    hash سریع اینجا درست است چون در هر درخواست ورودی باید سریع جست‌وجو شود.
    """
    return hashlib.sha256(raw.encode()).hexdigest()


def issue(
    db: Session,
    *,
    user_id: UUID,
    purpose: str,
    tenant_id: UUID | None = None,
    lifetime: timedelta,
) -> str:
    """توکن تازه می‌سازد و مقدار خامش را برمی‌گرداند. این تنها لحظه‌ای است که خام وجود دارد."""
    invalidate_outstanding(db, user_id=user_id, purpose=purpose, tenant_id=tenant_id)

    raw = secrets.token_urlsafe(TOKEN_BYTES)
    db.add(
        AuthToken(
            purpose=purpose,
            token_hash=hash_token(raw),
            user_id=user_id,
            tenant_id=tenant_id,
            expires_at=datetime.now(timezone.utc) + lifetime,
        )
    )
    db.flush()
    return raw


def invalidate_outstanding(db: Session, *, user_id: UUID, purpose: str, tenant_id: UUID | None = None) -> int:
    """توکن‌های مصرف‌نشده‌ی همین کاربر و همین هدف را باطل می‌کند."""
    query = db.query(AuthToken).filter(
        AuthToken.user_id == user_id,
        AuthToken.purpose == purpose,
        AuthToken.used_at.is_(None),
    )
    if tenant_id is not None:
        query = query.filter(AuthToken.tenant_id == tenant_id)

    now = datetime.now(timezone.utc)
    count = 0
    for token in query.all():
        token.used_at = now
        count += 1
    db.flush()
    return count


def consume(db: Session, raw: str, *, purpose: str) -> AuthToken | None:
    """توکن را می‌سنجد و همان‌جا مصرفش می‌کند. None یعنی نامعتبر — بدون توضیح بیشتر.

    `purpose` اجباری است تا توکن دعوت را نتوان به‌جای توکن بازیابی رمز خرج کرد؛
    بدون این بررسی، دو جریان با عمر و سطح اعتماد متفاوت به هم وصل می‌شدند.

    مصرف قبل از بازگشت انجام می‌شود (نه بعد از اینکه فراخواننده کارش را تمام کرد)
    تا دو درخواست هم‌زمان با یک لینک، دو بار عمل نکنند. تراکنش تنها چیزی است که
    این را واقعاً اتمی می‌کند، و `get_db` کل درخواست را یک تراکنش نگه می‌دارد.
    """
    if not raw:
        return None

    token = db.query(AuthToken).filter(AuthToken.token_hash == hash_token(raw)).first()
    if token is None or token.purpose != purpose or token.used_at is not None:
        return None

    # مقایسه با زمانِ آگاه از منطقه: ستون timezone=True است، ولی اگر روزی مقدار
    # naive برگردد مقایسه با خطا می‌شکند نه با نتیجه‌ی غلط — که حالت درستِ شکست است.
    if token.expires_at <= datetime.now(timezone.utc):
        return None

    token.used_at = datetime.now(timezone.utc)
    db.flush()
    return token


#: عمرِ کدِ کوتاهِ پیامکی و سقفِ تلاشِ راستی‌آزمایی. کوتاه چون کد حدس‌زدنی است و
#: نباید پنجره‌ی حمله باز بماند؛ کاربر هم معمولاً کد را در همان دقیقه وارد می‌کند.
CODE_TTL_MINUTES = 5
MAX_CODE_ATTEMPTS = 5


def _numeric_code(digits: int = 6) -> str:
    """کدِ عددیِ تصادفیِ امن. secrets نه random — تا قابلِ پیش‌بینی نباشد."""
    return "".join(secrets.choice("0123456789") for _ in range(digits))


def _code_hash(user_id: UUID, purpose: str, code: str) -> str:
    """hashِ کد، نمک‌خورده با کاربر و هدف.

    دو دلیل: (۱) `token_hash` یکتاست و اگر خامِ کد را hash می‌کردیم، دو کاربر با کدِ
    ۶رقمیِ یکسان به تصادمِ یکتایی می‌خوردند؛ user_id هر hash را جدا می‌کند. (۲) بدونِ
    نمک، یک جدولِ آماده‌ی یک‌میلیون کد کلِ hashها را برمی‌گرداند.
    """
    return hash_token(f"{user_id}:{purpose}:{code}")


def issue_code(
    db: Session,
    *,
    user_id: UUID,
    purpose: str,
    lifetime: timedelta = timedelta(minutes=CODE_TTL_MINUTES),
    digits: int = 6,
) -> str:
    """کدِ کوتاهِ عددیِ تازه می‌سازد و مقدارِ خامش را برمی‌گرداند (برای ارسالِ پیامکی).

    کدهای قبلیِ همین کاربر و همین هدف حذف می‌شوند (نه فقط باطل): این‌ها گذرا و
    یک‌بارمصرف‌اند، ماندگاری‌شان ارزشِ ممیزی ندارد و حذف، تصادمِ `token_hash` را هم
    (وقتی کدِ تازه اتفاقی با کدِ قبلی یکی شود) کاملاً حذف می‌کند.
    """
    db.query(AuthToken).filter(
        AuthToken.user_id == user_id,
        AuthToken.purpose == purpose,
    ).delete()

    code = _numeric_code(digits)
    db.add(
        AuthToken(
            purpose=purpose,
            token_hash=_code_hash(user_id, purpose, code),
            user_id=user_id,
            expires_at=datetime.now(timezone.utc) + lifetime,
        )
    )
    db.flush()
    return code


def consume_code(db: Session, *, user_id: UUID, purpose: str, code: str) -> bool:
    """کد را می‌سنجد و در صورتِ درستی مصرفش می‌کند. False یعنی نامعتبر — بدون تفکیک.

    مثلِ consume، بین «کدی نیست»، «منقضی شده»، «قفل شده» و «غلط است» فرق نمی‌گذارد.
    هر تلاشِ غلط `attempts` را بالا می‌برد و بعد از سقف، حتی کدِ درست هم رد می‌شود تا
    حمله‌ی حدسِ کدِ کوتاه بی‌اثر بماند.
    """
    token = (
        db.query(AuthToken)
        .filter(
            AuthToken.user_id == user_id,
            AuthToken.purpose == purpose,
            AuthToken.used_at.is_(None),
        )
        .order_by(AuthToken.created_at.desc())
        .first()
    )
    if token is None:
        return False
    if token.expires_at <= datetime.now(timezone.utc):
        return False
    if token.attempts >= MAX_CODE_ATTEMPTS:
        return False
    if token.token_hash != _code_hash(user_id, purpose, code):
        token.attempts += 1
        db.flush()
        return False

    token.used_at = datetime.now(timezone.utc)
    db.flush()
    return True


def issue_password_reset(db: Session, user_id: UUID) -> str:
    from app.models.auth_token import PURPOSE_PASSWORD_RESET

    return issue(
        db,
        user_id=user_id,
        purpose=PURPOSE_PASSWORD_RESET,
        lifetime=timedelta(hours=PASSWORD_RESET_HOURS),
    )


def issue_invite(db: Session, user_id: UUID, tenant_id: UUID) -> str:
    from app.models.auth_token import PURPOSE_INVITE

    return issue(
        db,
        user_id=user_id,
        purpose=PURPOSE_INVITE,
        tenant_id=tenant_id,
        lifetime=timedelta(days=INVITE_DAYS),
    )
