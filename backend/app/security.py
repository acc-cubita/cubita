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


def create_access_token(user_id: UUID, tenant_id: UUID | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload: dict = {"sub": str(user_id), "exp": expire}
    if tenant_id is not None:
        payload["tid"] = str(tenant_id)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> tuple[UUID, UUID | None] | None:
    """(شناسه‌ی کاربر، شناسه‌ی مستأجر) یا None اگر توکن معتبر نباشد.

    ادعای مستأجر داخل توکن **به‌تنهایی معتبر نیست** و حتماً باید در برابر جدول
    عضویت‌ها سنجیده شود؛ وگرنه صرفاً یک شناسه‌ی مستأجرِ تأمین‌شده توسط کلاینت است و
    کل ایزوله‌سازی را بی‌اثر می‌کند.
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        tid = payload.get("tid")
        return UUID(payload["sub"]), (UUID(tid) if tid else None)
    except (JWTError, KeyError, ValueError):
        return None
