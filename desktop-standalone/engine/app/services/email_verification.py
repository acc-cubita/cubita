"""صدور و مصرفِ کدِ تأییدِ ایمیل برای ثبت‌نام (verify-before-create).

قرینه‌ی `tokens.issue_code`/`consume_code`ِ پیامکی، ولی کلیدش **ایمیل** است نه کاربر —
چون هنوز کاربری ساخته نشده. کد پیش از ساختِ حساب تأیید می‌شود، پس هیچ حسابی با ایمیلِ
تأییدنشده به‌وجود نمی‌آید.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.email_verification import EmailVerificationCode
from app.services.tokens import _numeric_code, hash_token

#: عمرِ کد. کمی بلندتر از پیامک (۵ دقیقه) چون تحویلِ ایمیل گاهی چند دقیقه تأخیر دارد.
CODE_TTL_MINUTES = 15
MAX_ATTEMPTS = 5


def _norm(email: str) -> str:
    return email.strip().lower()


def _code_hash(email: str, code: str) -> str:
    """hashِ نمک‌خورده با ایمیل و هدف — تا کدِ یکسانِ دو ایمیل hashِ یکسان ندهد."""
    return hash_token(f"{_norm(email)}:email_verify:{code}")


def issue_email_code(db: Session, email: str, *, digits: int = 6) -> str:
    """کدِ عددیِ تازه می‌سازد و خامش را برمی‌گرداند (برای ارسال به ایمیل).

    کدهای قبلیِ همین ایمیل حذف می‌شوند: گذرا و یک‌بارمصرف‌اند و «ارسالِ دوباره» باید
    قبلی را باطل کند تا فقط تازه‌ترین کد کار کند.
    """
    e = _norm(email)
    db.query(EmailVerificationCode).filter(EmailVerificationCode.email == e).delete()

    code = _numeric_code(digits)
    db.add(
        EmailVerificationCode(
            email=e,
            code_hash=_code_hash(e, code),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=CODE_TTL_MINUTES),
        )
    )
    db.flush()
    return code


def consume_email_code(db: Session, email: str, code: str) -> bool:
    """کد را می‌سنجد و در صورتِ درستی مصرف (حذف) می‌کند. False یعنی نامعتبر — بدون تفکیک.

    مثلِ consume_code بین «نیست»، «منقضی»، «قفل» و «غلط» فرق نمی‌گذارد؛ هر تلاشِ غلط
    attempts را بالا می‌برد و بعد از سقف حتی کدِ درست هم رد می‌شود.
    """
    e = _norm(email)
    row = (
        db.query(EmailVerificationCode)
        .filter(EmailVerificationCode.email == e)
        .order_by(EmailVerificationCode.created_at.desc())
        .first()
    )
    if row is None:
        return False
    if row.expires_at <= datetime.now(timezone.utc):
        return False
    if row.attempts >= MAX_ATTEMPTS:
        return False
    if row.code_hash != _code_hash(e, code):
        row.attempts += 1
        db.flush()
        return False

    db.delete(row)
    db.flush()
    return True
