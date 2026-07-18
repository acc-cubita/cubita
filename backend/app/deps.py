from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.user import User
from app.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "احراز هویت لازم است")
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "توکن نامعتبر است")
    user = db.get(User, user_id)
    if user is None or not user.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "کاربر یافت نشد یا غیرفعال است")
    return user


def require_permission(module: str, action: str):
    """مجوز در سطح داده‌ی یک مستأجر. هرگز برای اندپوینت‌های کنترل‌پنل پلتفرم استفاده نشود."""

    def checker(user: User = Depends(get_current_user)) -> User:
        if not user.role.has_permission(module, action):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "دسترسی کافی نیست")
        return user

    return checker


def require_platform_admin(user: User = Depends(get_current_user)) -> User:
    """مجوز کنترل‌پنل فروش خودِ کوبیتا — عمداً به RBAC مستأجر وابسته نیست.

    اندپوینت‌های /api/admin/purchases داده‌ی هویتی همه‌ی مشتریان پولی را برمی‌گردانند.
    وقتی این‌ها پشت require_permission("billing", ...) بودند، هر نقشی که permissions
    آن شامل wildcard "*" بود — از جمله نقش عمومی «دمو» — به آن‌ها دسترسی می‌گرفت.
    فهرست خالی یعنی دسترسی برای همه بسته است (fail closed).
    """
    allowed = get_settings().platform_admin_emails_list
    if not allowed or user.email.strip().lower() not in allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "دسترسی کافی نیست")
    return user
