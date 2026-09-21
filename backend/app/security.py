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


#: نوعِ توکن. `tenant` = کاربرِ یک کسب‌وکار در اپِ حسابداری؛ `staff` = کارمندِ ستاد
#: در admin.cubita.ir. جداسازیِ این دو **ساختاری** است نه قراردادی: بدونِ آن، توکنِ
#: ستاد (که `tid` ندارد) در `get_principal` به «اولین عضویتِ فعال» می‌افتاد و یک
#: کارمندِ ستاد ناخواسته به دفترِ یک مشتری می‌رسید.
TOKEN_TYPE_TENANT = "tenant"
TOKEN_TYPE_STAFF = "staff"


@dataclass(frozen=True)
class TokenClaims:
    user_id: UUID
    tenant_id: UUID | None
    token_version: int
    #: پیش‌فرضِ `tenant` عمدی است — «۱. سازگاریِ عقب‌رو» در docstringِ decode.
    typ: str = TOKEN_TYPE_TENANT


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
        "typ": TOKEN_TYPE_TENANT,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    if tenant_id is not None:
        payload["tid"] = str(tenant_id)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_staff_token(user) -> str:
    """توکنِ کارمندِ ستاد — **عمداً بدونِ `tid`**.

    نبودِ مستأجر تزئینی نیست، خودِ سازوکارِ ایمنی است: `get_staff_principal` هیچ
    `app.tenant_id`ی روی تراکنش نمی‌نشاند، و سیاستِ RLS در نبودِ آن صفر ردیف
    می‌دهد. یعنی نشستِ ستاد **نمی‌تواند** تصادفی به جدولِ مستأجری دست بزند و هر
    کارِ میان‌مستأجری باید یک `tenant_scope`ِ صریح باشد.

    مدتش از `jwt_staff_expire_minutes` می‌آید نه `jwt_expire_minutes`. همان
    `token_version` را حمل می‌کند، پس تغییرِ رمز نشست‌های ستاد را هم باطل می‌کند.
    """
    now = datetime.now(timezone.utc)
    payload: dict = {
        "sub": str(user.id),
        "tv": user.token_version or 0,
        "typ": TOKEN_TYPE_STAFF,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_staff_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> TokenClaims | None:
    """ادعاهای توکن، یا None اگر امضا/ساختار معتبر نباشد.

    ادعای مستأجر داخل توکن **به‌تنهایی معتبر نیست** و حتماً باید در برابر جدول
    عضویت‌ها سنجیده شود؛ وگرنه صرفاً یک شناسه‌ی مستأجرِ تأمین‌شده توسط کلاینت است و
    کل ایزوله‌سازی را بی‌اثر می‌کند.

    نبودِ `typ` برابر `tenant` گرفته می‌شود، به همان دلیلِ `tv` در بندِ بعد: توکن‌هایی
    که پیش از افزودنِ ادعا صادر شده‌اند این کلید را ندارند و همه‌شان مستأجری‌اند، پس
    استقرار هیچ‌کس را بیرون نمی‌اندازد ولی از همان لحظه هیچ توکنِ تازه‌ای نمی‌تواند
    خودش را ستادی جا بزند.

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
            typ=str(payload.get("typ", TOKEN_TYPE_TENANT)),
        )
    except (JWTError, KeyError, ValueError, TypeError):
        return None
