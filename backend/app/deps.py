from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.tenant import Membership
from app.models.user import User
from app.security import decode_access_token
from app.tenant_context import apply_tenant_to_transaction, set_current_tenant

bearer_scheme = HTTPBearer(auto_error=False)


class Principal:
    """کاربر احرازشده به‌همراه مستأجری که در آن کار می‌کند و نقشش در همان مستأجر."""

    def __init__(self, user: User, membership: Membership):
        self.user = user
        self.membership = membership
        self.tenant_id = membership.tenant_id
        self.role = membership.role


def get_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Principal:
    """هویت را حل می‌کند و زمینه‌ی مستأجر را روی تراکنش می‌نشاند.

    ترتیب اینجا مهم است: ادعای tid داخل توکن **قبل از** اینکه به هر داده‌ای دست
    بزنیم در برابر جدول عضویت‌ها سنجیده می‌شود. اگر این کار نشود، tid چیزی جز یک
    شناسه‌ی مستأجرِ فرستاده‌شده توسط کلاینت نیست و هر کاربری می‌تواند دفتر هر
    کسب‌وکاری را باز کند — یعنی کل RLS بی‌اثر می‌شود.
    """
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "احراز هویت لازم است")

    decoded = decode_access_token(credentials.credentials)
    if decoded is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "توکن نامعتبر است")
    user_id, tenant_id = decoded

    user = db.get(User, user_id)
    if user is None or not user.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "کاربر یافت نشد یا غیرفعال است")

    query = db.query(Membership).filter(Membership.user_id == user.id, Membership.status == "active")
    if tenant_id is not None:
        query = query.filter(Membership.tenant_id == tenant_id)
    membership = query.first()

    if membership is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "عضویت فعالی در این کسب‌وکار ندارید")

    set_current_tenant(membership.tenant_id)
    apply_tenant_to_transaction(db, membership.tenant_id)
    return Principal(user, membership)


def get_current_user(principal: Principal = Depends(get_principal)) -> User:
    return principal.user


def require_permission(module: str, action: str):
    """مجوز در سطح داده‌ی یک مستأجر. هرگز برای اندپوینت‌های کنترل‌پنل پلتفرم استفاده نشود."""

    def checker(principal: Principal = Depends(get_principal)) -> User:
        if not principal.role.has_permission(module, action):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "دسترسی کافی نیست")
        return principal.user

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
