import logging
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.audit import bind_session_actor
from app.config import get_settings
from app.database import get_db
from app.models.tenant import Membership, PlatformAdmin
from app.observability import request_id_var, tenant_id_var
from app.models.user import User
from app.security import TOKEN_TYPE_STAFF, TOKEN_TYPE_TENANT, decode_access_token
from app import staff_roles
from app.services.subscriptions import WRITE_ACTIONS
from app.services.subscriptions import state_for as subscription_state
from app.services.subscriptions import trial_info
from app.tenant_context import apply_tenant_to_transaction, bind_session_tenant

bearer_scheme = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)


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

    # توکنِ ستاد اینجا کارِ درستی ندارد، و ترتیبِ این بررسی حیاتی است: توکنِ ستادی
    # `tid` ندارد، پس اگر از اینجا رد می‌شد کوئریِ پایین به «اولین عضویتِ فعال»
    # می‌افتاد و یک کارمندِ ستاد ناخواسته داخلِ دفترِ یک مشتری می‌نشست.
    if claims.typ != TOKEN_TYPE_TENANT:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "این توکن برای ورود به کسب‌وکار نیست")

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


# ───────────────────────── هویتِ ستاد (admin.cubita.ir) ─────────────────────────


class StaffPrincipal:
    """کارمندِ ستادِ احرازشده. **هیچ مستأجری ندارد و هیچ مستأجری نمی‌بندد.**

    این «نداشتن» خودِ سازوکارِ ایمنی است، نه یک کمبود: سیاستِ RLS روی
    `current_setting('app.tenant_id', true)::uuid` می‌نشیند و بدونِ مقدار هیچ
    ردیفی رد نمی‌کند. نشستِ ستاد **نمی‌تواند** تصادفی به جدولِ مستأجری دست بزند،
    و هر کارِ میان‌مستأجری باید یک `with tenant_scope(db, tenant_id):`ِ صریح و
    grep‌شدنی باشد.

    **شکلِ شکست دو حالت دارد و هر دو بسته‌اند** — این را دقیق بدان، وگرنه وقت
    عیب‌یابی گمراه می‌شوی: روی اتصالی که تازه است `current_setting` مقدارِ NULL
    می‌دهد و کوئری **صفر ردیف** برمی‌گرداند؛ ولی روی اتصالی که پیش‌تر درخواستِ
    مستأجری سرو کرده، مقدار بعد از پایانِ آن تراکنش به رشته‌ی **خالی** برمی‌گردد
    (نه NULL)، و `''::uuid` خطای `invalid input syntax for type uuid: ""`
    می‌دهد — همان خطایی که `app/migration_utils.py` مستندش کرده. هیچ‌کدام داده
    بیرون نمی‌دهد؛ دومی فقط پیامِ گیج‌کننده‌تری دارد.

    مدلِ قبلی (بستنِ مستأجرِ خودِ ادمین) دقیقاً برعکس بود: `tenant_scope`ِ
    فراموش‌شده بی‌صدا در دفترِ خودِ ادمین می‌نوشت.
    """

    def __init__(
        self,
        user: User,
        admin: PlatformAdmin | None,
        *,
        via: str = "staff",
        ip: str | None = None,
        request_id: str | None = None,
    ):
        self.user = user
        self.admin = admin
        #: مسیرِ سازگاریِ کوچ نقشِ `owner` می‌گیرد — دارنده‌ی توکن همان مالکِ سامانه است.
        self.role = admin.role if admin is not None else "owner"
        self.permissions = staff_roles.permissions_for(
            self.role, admin.permissions if admin is not None else None
        )
        self.via = via
        self.ip = ip
        self.request_id = request_id

    @property
    def email(self) -> str:
        return self.user.email

    def has(self, area: str, action: str) -> bool:
        return staff_roles.has_permission(self.permissions, area, action)


def _staff_from_token(db: Session, claims, request: Request) -> StaffPrincipal:
    user = db.get(User, claims.user_id)
    if user is None or not user.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "دسترسی نامعتبر است")
    if claims.token_version != (user.token_version or 0):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "رمز عبور عوض شده است؛ دوباره وارد شوید")

    admin = (
        db.query(PlatformAdmin)
        .filter(PlatformAdmin.user_id == user.id, PlatformAdmin.is_active.is_(True))
        .first()
    )
    if admin is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "دسترسی نامعتبر است")

    # actor برای ردِ کارها لازم است. عمداً **بدونِ** bind_session_tenant —
    # توضیحش در docstringِ StaffPrincipal.
    bind_session_actor(db, user)
    return StaffPrincipal(
        user,
        admin,
        ip=client_ip(request),
        request_id=request_id_var.get(),
    )


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return request.client.host[:64] if request.client else None


def get_staff_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> StaffPrincipal:
    """هویتِ ستاد، با یک پلِ سازگاریِ موقت برای کوچ.

    دو مسیر:

    - **توکنِ ستادی** (`typ=staff`): مسیرِ اصلی. هیچ عضویتی لازم نیست و هیچ
      مستأجری بسته نمی‌شود.
    - **توکنِ مستأجریِ سوپرادمینِ قدیمی**: فقط تا وقتی `legacy_admin_allowlist`
      روشن است. این پل وجود دارد چون اپِ ستاد و اپِ مشتری در دو لحظه‌ی متفاوت
      مستقر می‌شوند و باندلِ مستقرِ acc.cubita.ir نباید در آن فاصله بشکند.
      خاموش‌کردنش یک ویرایشِ `.env` و ری‌استارت است، نه یک استقرار.
    """
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "احراز هویت لازم است")

    claims = decode_access_token(credentials.credentials)
    if claims is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "توکن نامعتبر است")

    if claims.typ == TOKEN_TYPE_STAFF:
        return _staff_from_token(db, claims, request)

    settings = get_settings()
    if not settings.legacy_admin_allowlist:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "برای این بخش باید از پنلِ مدیریت وارد شوید")

    # مسیرِ قدیمی: عیناً همان سنجشِ امروز — عضویتِ فعال، مستأجرِ فعال، و ایمیل روی
    # allowlist. `get_principal` صدا زده می‌شود تا زمینه‌ی مستأجر مثلِ قبل بسته
    # شود و اندپوینت‌های موجود بی‌تغییر کار کنند.
    principal = get_principal(credentials=credentials, db=db)
    allowed = settings.super_admin_emails_list
    if not allowed or principal.user.email.strip().lower() not in allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "دسترسی کافی نیست")

    logger.warning(
        "staff access via legacy tenant token",
        extra={"email": principal.user.email},
    )
    return StaffPrincipal(
        principal.user,
        None,
        via="legacy",
        ip=client_ip(request),
        request_id=request_id_var.get(),
    )


def require_staff(
    area: str | None = None,
    action: str = "view",
    *,
    role: str | None = None,
):
    """گاردِ اندپوینت‌های ستاد.

    به‌صورتِ وابستگیِ **سطحِ روتر** بسته می‌شود تا مسیرِ تازه‌ای که کسی اضافه می‌کند
    خودکار گیت بخورد — همان دلیلی که `require_module` روی روترِ تولید نشسته.
    `area=None` یعنی «فقط کارمندِ ستاد بودن کافی است» (مثلِ `/auth/me`).
    """

    def checker(staff: StaffPrincipal = Depends(get_staff_principal)) -> StaffPrincipal:
        if role is not None and staff.role != role:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "این کار فقط از دستِ مالکِ سامانه برمی‌آید"
            )
        if area is not None and not staff.has(area, action):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "دسترسی کافی نیست")
        return staff

    return checker
