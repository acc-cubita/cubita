from uuid import UUID

from pydantic import BaseModel, EmailStr, field_validator


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeOut(BaseModel):
    id: UUID
    name: str
    email: str
    phone: str | None = None
    #: آیا شماره‌ی موبایلِ فعلی با کدِ پیامکی تأیید شده — تا فرانت نشانِ «تأییدشده» و
    #: امکانِ بازیابیِ رمز با پیامک را نشان دهد.
    phone_verified: bool = False
    role_key: str
    role_name: str
    permissions: dict
    tenant_id: UUID
    tenant_name: str
    #: آیا این کاربر روی allowlist کنترل‌پنل فروش خودِ کوبیتاست — مستقل از نقش
    #: تنانت. بدون این، فرانت فقط راه چک کردنش را با role_key == "owner" حدس
    #: می‌زد، که یعنی هر صاحب کسب‌وکاری (نه فقط خودِ کوبیتا) تب «خریدهای سایت
    #: تجاری» را در ساید‌بار می‌دید.
    is_platform_admin: bool = False
    #: سوپرادمینِ کلِ سامانه (فقط مالک) — گیتِ ماژولِ «مدیریت اکانت‌ها». سخت‌گیرانه‌تر
    #: از is_platform_admin و مستقل از آن.
    is_super_admin: bool = False

    #: حسابِ آزمایشیِ رایگان — فرانت با این نوارِ «X روز مانده»، باکسِ خرید و صفحه‌ی قفل
    #: را نشان می‌دهد بی‌آنکه منتظرِ ۴۰۲ بماند.
    is_trial: bool = False
    #: روزهای مانده تا انقضای آزمایشی (منفی = گذشته). برای مشتریِ واقعی None.
    trial_days_left: int | None = None
    #: دوره‌ی آزمایشی تمام شده — فرانت فقط صفحه‌ی خرید را نشان می‌دهد.
    trial_expired: bool = False
    #: قابلیت‌های قفل‌شده در آزمایشی (مثلِ moadian/storefront) — فرانت با این باکسِ «خرید پلن»
    #: را جای ماژول می‌گذارد. برای مشتریِ واقعی خالی.
    locked_features: list[str] = []

    model_config = {"from_attributes": True}


class TenantMembershipOut(BaseModel):
    """یکی از کسب‌وکارهایی که کاربر به آن دسترسی دارد."""

    tenant_id: UUID
    tenant_name: str
    tenant_slug: str
    role_key: str
    role_name: str
    is_current: bool


class SwitchTenantIn(BaseModel):
    tenant_id: UUID


class ProfileUpdateIn(BaseModel):
    """ویرایشِ پروفایلِ کاربرِ واردشده. هر فیلدِ نیامده دست‌نخورده می‌ماند.

    ایمیل هویتِ ورود است؛ تغییرش رمزِ فعلی می‌خواهد، وگرنه یک نشستِ ربوده‌شده می‌توانست
    ایمیل را عوض کند و بعد با «فراموشی رمز» کلِ حساب را بگیرد — همان دلیلی که تغییرِ رمز
    هم رمزِ فعلی می‌پرسد.
    """

    name: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    current_password: str | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not v.strip():
            raise ValueError("نام نمی‌تواند خالی باشد")
        return v.strip()


class PhoneSendCodeIn(BaseModel):
    """درخواستِ کدِ تأییدِ شماره. شماره ذخیره می‌شود (تأییدنشده) و کد پیامک می‌شود."""

    phone: str


class PhoneVerifyIn(BaseModel):
    """راستی‌آزماییِ کدِ تأییدِ شماره."""

    code: str

    @field_validator("code")
    @classmethod
    def digits_only(cls, v: str) -> str:
        v = v.strip()
        if not v.isdigit():
            raise ValueError("کد فقط عدد است")
        return v


class BusinessUpdateIn(BaseModel):
    """ویرایشِ نامِ کسب‌وکارِ جاری — فقط مالک."""

    name: str

    @field_validator("name")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("نام کسب‌وکار نمی‌تواند خالی باشد")
        return v.strip()


class SignupIn(BaseModel):
    """ثبت‌نام self-serve: کاربر و کسب‌وکارش با هم ساخته می‌شوند."""

    business_name: str
    owner_name: str
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_is_long_enough(cls, v: str) -> str:
        # حداقلی و عمدی: سخت‌گیری بیشتر بدون بازیابی رمز، کاربر را قفل بیرون می‌کند.
        if len(v) < 10:
            raise ValueError("رمز عبور باید حداقل ۱۰ کاراکتر باشد")
        return v

    @field_validator("business_name", "owner_name")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("این فیلد نمی‌تواند خالی باشد")
        return v.strip()
