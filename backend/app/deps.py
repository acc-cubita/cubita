from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.audit import bind_session_actor
from app.config import get_settings
from app.database import get_db
from app.models.tenant import Membership
from app.observability import tenant_id_var
from app.models.user import User
from app.security import decode_access_token
from app.services.subscriptions import WRITE_ACTIONS
from app.services.subscriptions import state_for as subscription_state
from app.tenant_context import apply_tenant_to_transaction, bind_session_tenant

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

    claims = decode_access_token(credentials.credentials)
    if claims is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "توکن نامعتبر است")

    user = db.get(User, claims.user_id)
    if user is None or not user.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "کاربر یافت نشد یا غیرفعال است")

    # توکنی از نسل قبل دیگر معتبر نیست. بدون این بررسی، عوض کردن رمز — کاری که کاربر
    # دقیقاً برای بیرون کردن مهاجم انجام می‌دهد — تا انقضای طبیعی توکن هیچ اثری روی
    # نشست‌های باز نداشت.
    if claims.token_version != (user.token_version or 0):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "رمز عبور عوض شده است؛ دوباره وارد شوید")

    query = db.query(Membership).filter(Membership.user_id == user.id, Membership.status == "active")
    if claims.tenant_id is not None:
        query = query.filter(Membership.tenant_id == claims.tenant_id)
    membership = query.first()

    if membership is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "عضویت فعالی در این کسب‌وکار ندارید")

    # کسب‌وکارِ تعلیق‌شده/لغوشده دسترسی ندارد — حتی با توکنِ معتبرِ از قبل. بدون این،
    # «تعلیق» فقط جلوی ورودِ تازه را می‌گرفت و نشست‌های باز تا انقضای توکن ادامه داشتند.
    if membership.tenant.status != "active":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "این کسب‌وکار غیرفعال شده است")

    bind_session_tenant(db, membership.tenant_id)
    apply_tenant_to_transaction(db, membership.tenant_id)
    # کاربر روی همان Session می‌نشیند تا رویداد flush بداند چه کسی مسئول این تغییر
    # است. اگر اینجا نباشد، هر رکورد حسابرسی «سیستم» ثبت می‌شود — یعنی دفتری که
    # می‌گوید چیزی عوض شد ولی نمی‌گوید توسط چه کسی، که نیمی از فایده‌اش را می‌برد.
    bind_session_actor(db, user)
    # مستأجر روی زمینه‌ی لاگ هم می‌نشیند. در سیستم چندمستأجری، لاگی که نگوید کدام
    # کسب‌وکار عملاً بی‌فایده است: نمی‌شود فهمید مشکل یک مشتری است یا همه.
    tenant_id_var.set(str(membership.tenant_id))
    return Principal(user, membership)


def get_current_user(principal: Principal = Depends(get_principal)) -> User:
    return principal.user


def require_permission(module: str, action: str):
    """مجوز در سطح داده‌ی یک مستأجر. هرگز برای اندپوینت‌های کنترل‌پنل پلتفرم استفاده نشود.

    اعمال اشتراک هم اینجاست و نه در تک‌تک سرویس‌ها: یک نقطه‌ی گلوگاه یعنی مسیر
    تازه‌ای که کسی اضافه کند خودکار پوشش می‌گیرد. پخش کردنش در سرویس‌ها یعنی
    اولین اندپوینتی که فراموش شود، یک در باز است.

    **خواندن هرگز محدود نمی‌شود.** فقط اکشن‌های نوشتن. دفتر مالی سند قانونی خودِ
    مشتری است و قفل کردنش پشت پرداخت، گروگان گرفتن چیزی است که مال ما نیست.
    """

    def checker(
        principal: Principal = Depends(get_principal),
        db: Session = Depends(get_db),
    ) -> User:
        if not principal.role.has_permission(module, action):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "دسترسی کافی نیست")

        if action in WRITE_ACTIONS:
            state = subscription_state(db, principal.tenant_id)
            if not state.can_write:
                raise HTTPException(
                    status.HTTP_402_PAYMENT_REQUIRED,
                    "اشتراک این کسب‌وکار تمام شده است. دفترها و گزارش‌ها در دسترس‌اند "
                    "ولی برای ثبت سند تازه باید اشتراک تمدید شود.",
                )
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


def require_super_admin(user: User = Depends(get_current_user)) -> User:
    """مجوزِ سوپرادمینِ کلِ سامانه — سخت‌گیرانه‌تر از require_platform_admin.

    ماژولِ «مدیریت اکانت‌ها» می‌تواند اکانتِ هر مشتری را بسازد/تمدید/تعلیق/حذف کند؛
    این قدرت فقط دستِ مالکِ سامانه است، نه هر ادمینِ پلتفرم. فهرست خالی = بسته (fail closed).
    """
    allowed = get_settings().super_admin_emails_list
    if not allowed or user.email.strip().lower() not in allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "دسترسی کافی نیست")
    return user
