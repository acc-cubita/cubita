from datetime import datetime, timezone

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
from app.services.subscriptions import trial_info
from app.tenant_context import apply_tenant_to_transaction, bind_session_tenant

bearer_scheme = HTTPBearer(auto_error=False)


class Principal:
    """کاربر احرازشده به‌همراه مستأجری که در آن کار می‌کند و نقشش در همان مستأجر."""

    def __init__(self, user: User, membership: Membership):
        self.user = user
        self.membership = membership
        self.tenant_id = membership.tenant_id
        self.role = membership.role
        #: مجوزِ **مؤثر**: اگر برای این عضویت مجوزِ اختصاصی تعریف شده باشد همان،
        #: وگرنه مجوزِ نقش. هر بررسیِ دسترسی باید از این عبور کند نه از role.
        self.permissions: dict = membership.permissions or (membership.role.permissions or {})

    def has_permission(self, module: str, action: str) -> bool:
        """همان معناشناسیِ `Role.has_permission`، ولی روی مجوزِ مؤثر."""
        for key in (module, "*"):
            actions = self.permissions.get(key)
            if actions and (action in actions or "*" in actions):
                return True
        return False


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

    # عضویتِ مهلت‌دار (امروز: حسابرسِ گماشته‌شده). این تنها نقطه‌ای است که هر
    # درخواست از آن رد می‌شود، پس تنها جایی است که انقضا دورزدنی نیست — و چون
    # ردیفِ عضویت همین بالا بارگذاری شده، هزینه‌اش یک مقایسه است نه یک کوئری.
    if membership.expires_at is not None and membership.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "مهلتِ دسترسیِ شما به این کسب‌وکار تمام شده است"
        )

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


def require_permission(module: "str | tuple[str, ...]", action: "str | tuple[str, ...]"):
    """مجوز در سطح داده‌ی یک مستأجر. هرگز برای اندپوینت‌های کنترل‌پنل پلتفرم استفاده نشود.

    اعمال اشتراک هم اینجاست و نه در تک‌تک سرویس‌ها: یک نقطه‌ی گلوگاه یعنی مسیر
    تازه‌ای که کسی اضافه کند خودکار پوشش می‌گیرد. پخش کردنش در سرویس‌ها یعنی
    اولین اندپوینتی که فراموش شود، یک در باز است.

    `action` می‌تواند یک اکشن باشد یا چند اکشنِ جایگزین (تاپل): اگر نقشِ کاربر **هر یک**
    از آن‌ها را داشته باشد کافی است — مثلاً اندپوینتِ «تحویل» که هم با اکشنِ اختصاصیِ
    `deliver` (مامور حمل) و هم با `approve` (مالک/مدیر) باز می‌شود.

    `module` هم می‌تواند چند ماژولِ جایگزین باشد، برای سندی که واقعاً مالِ دو ماژول
    است — اعلامیه‌ی بدهکار/بستانکار هم از فروش صادر می‌شود هم از خرید، و نباید
    کاربرِ خرید را پشتِ مجوزِ فروش نگه دارد.

    **خواندن هرگز محدود نمی‌شود.** فقط اکشن‌های نوشتن. دفتر مالی سند قانونی خودِ
    مشتری است و قفل کردنش پشت پرداخت، گروگان گرفتن چیزی است که مال ما نیست.
    """
    actions: tuple[str, ...] = (action,) if isinstance(action, str) else tuple(action)
    modules: tuple[str, ...] = (module,) if isinstance(module, str) else tuple(module)

    def checker(
        principal: Principal = Depends(get_principal),
        db: Session = Depends(get_db),
    ) -> User:
        if not any(principal.has_permission(m, a) for m in modules for a in actions):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "دسترسی کافی نیست")

        # آزمایشیِ منقضی: کلِ دفتر قفل می‌شود (خواندن هم)، نه فقط نوشتن. این عمداً
        # سخت‌گیرانه‌تر از انقضای مشتریِ واقعی است — داده‌ی آزمایشی سندِ قانونیِ کسی
        # نیست، و هدفِ قفلِ کامل، سوق دادن به خرید است. /me و /subscription و
        # /billing از require_permission رد نمی‌شوند، پس صفحه‌ی خرید همچنان باز می‌ماند.
        if principal.membership.tenant.is_trial and trial_info(db, principal.membership.tenant).expired:
            raise HTTPException(
                status.HTTP_402_PAYMENT_REQUIRED,
                "دوره‌ی آزمایشیِ رایگان تمام شده است؛ برای ادامه و حفظِ اطلاعات یک پلن تهیه کنید.",
            )

        if any(a in WRITE_ACTIONS for a in actions):
            state = subscription_state(db, principal.tenant_id)
            if not state.can_write:
                raise HTTPException(
                    status.HTTP_402_PAYMENT_REQUIRED,
                    "اشتراک این کسب‌وکار تمام شده است. دفترها و گزارش‌ها در دسترس‌اند "
                    "ولی برای ثبت سند تازه باید اشتراک تمدید شود.",
                )
        return principal.user

    return checker


#: قابلیت‌هایی که در نسخه‌ی آزمایشی قفل‌اند و فقط با پلنِ خریداری‌شده باز می‌شوند.
#: کلیدها با locked_features در MeOut و گیتِ فرانت یکی‌اند.
PREMIUM_FEATURES = ("moadian", "storefront")


def require_feature(feature: str):
    """قابلیتِ فقط-پلن. حسابِ آزمایشی را با ۴۰۲ رد می‌کند تا فرانت باکسِ «خرید پلن» را نشان دهد.

    روی کلِ روترِ مودیان و اتصال‌فروشگاه به‌صورتِ dependencyِ سطحِ روتر می‌نشیند، پس هر
    اندپوینتِ تازه‌ای هم که به آن روترها اضافه شود خودکار قفل می‌ماند.
    """

    def checker(principal: Principal = Depends(get_principal)) -> User:
        if principal.membership.tenant.is_trial:
            raise HTTPException(
                status.HTTP_402_PAYMENT_REQUIRED,
                "این قابلیت در نسخه‌ی آزمایشی فعال نیست؛ برای استفاده یک پلن تهیه کنید.",
            )
        return principal.user

    return checker


def require_module(module: str):
    """گیتِ «حقِ دسترسی»ِ ماژول‌های محدود (مثلِ تولید) در بک‌اند.

    خواسته‌ی «ترکیبی»: خاموش‌کردنِ ماژول‌های عادی فقط منو را پنهان می‌کند، ولی ماژولی که
    سوپرادمین نداده باید در سرور هم بسته باشد. روی روترِ ماژولِ محدود به‌صورتِ dependencyِ
    سطحِ روتر می‌نشیند (مثلِ require_feature). ماژولِ گرنت‌نشده → ۴۰۳.
    """
    from app.services import modules as modules_service

    def checker(
        principal: Principal = Depends(get_principal), db: Session = Depends(get_db)
    ) -> User:
        #: ماژولِ **مشتق** در هیچ ستونی ذخیره نیست و از رکوردِ سرویس مشتق می‌شود؛
        #: کوئری‌اش فقط وقتی زده می‌شود که این روتر واقعاً مشتق باشد، پس گیتِ
        #: «تولید» و «اتصال فروشگاه» هیچ هزینه‌ای نمی‌دهند.
        #:
        #: محاسبه‌ی `derived` **این‌جا** انجام می‌شود، نه در فراخوان: اگر روتر و منو
        #: هرکدام جداگانه حساب می‌کردند، می‌توانستند اختلاف پیدا کنند — منو باز و
        #: سرور بسته، یا بدتر، برعکس.
        derived: frozenset[str] = frozenset()
        if module in modules_service.DERIVED_MODULES:
            from app.services import assurance_access

            derived = assurance_access.derived_modules(db, principal.tenant_id)

        if module not in modules_service.allowed_modules(
            principal.membership.tenant, derived=derived
        ):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "این ماژول برای حسابِ شما فعال نیست؛ برای فعال‌سازی با پشتیبانی تماس بگیرید.",
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
