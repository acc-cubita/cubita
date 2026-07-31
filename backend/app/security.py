from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def record_login(user) -> None:
    """آخرین ورودِ موفق را ثبت می‌کند — برای «آخرین فعالیت» در پنلِ مدیریت.

    فقط از مسیرهای اعتبارسنجی‌شده‌ی ورود صدا زده می‌شود (login، بازیابیِ رمز،
    پذیرشِ دعوت). commit را get_db در پایانِ درخواست انجام می‌دهد.
    """
    user.last_login_at = datetime.now(timezone.utc)


def set_password(user, password: str) -> None:
    """تنها مسیر مجاز برای عوض کردن رمز.

    نسل توکن همراه رمز جلو می‌رود، و همین است که نشست‌های باز را باطل می‌کند. اگر
    جایی مستقیم `hashed_password` را بنویسد، رمز عوض می‌شود ولی مهاجمی که توکن
    دارد بیرون نمی‌رود — یعنی همان چیزی که کاربر انتظارش را دارد اتفاق نمی‌افتد.
    """
    user.hashed_password = hash_password(password)
    user.token_version = (user.token_version or 0) + 1


@dataclass(frozen=True)
class TokenClaims:
    user_id: UUID
    tenant_id: UUID | None
    token_version: int


def create_access_token(user, tenant_id: UUID | None = None) -> str:
    """توکن برای یک کاربر.

    عمداً خودِ شیء کاربر را می‌گیرد و نه فقط شناسه‌اش: نسل توکن باید داخلش برود، و
    اگر پارامتر جدایی بود اولین فراخوانی‌ای که فراموشش می‌کرد توکنی می‌ساخت که
    بی‌صدا از بررسی ابطال رد می‌شد.
    """
    now = datetime.now(timezone.utc)
    payload: dict = {
        "sub": str(user.id),
        "tv": user.token_version or 0,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    if tenant_id is not None:
        payload["tid"] = str(tenant_id)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> TokenClaims | None:
    """ادعاهای توکن، یا None اگر امضا/ساختار معتبر نباشد.

    ادعای مستأجر داخل توکن **به‌تنهایی معتبر نیست** و حتماً باید در برابر جدول
    عضویت‌ها سنجیده شود؛ وگرنه صرفاً یک شناسه‌ی مستأجرِ تأمین‌شده توسط کلاینت است و
    کل ایزوله‌سازی را بی‌اثر می‌کند.

    نبودِ `tv` برابر صفر گرفته می‌شود، نه نامعتبر. توکن‌هایی که قبل از این تغییر صادر
    شده‌اند این ادعا را ندارند و همه‌ی کاربران موجود هم نسل صفرند، پس معتبر می‌مانند —
    و به محض اولین تغییر رمز، نسل به ۱ می‌رود و همان توکن‌ها باطل می‌شوند. یعنی
    استقرار هیچ‌کس را بیرون نمی‌اندازد ولی محافظت از همان لحظه برقرار است.
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        tid = payload.get("tid")
        return TokenClaims(
            user_id=UUID(payload["sub"]),
            tenant_id=UUID(tid) if tid else None,
            token_version=int(payload.get("tv", 0)),
        )
    except (JWTError, KeyError, ValueError, TypeError):
        return None
