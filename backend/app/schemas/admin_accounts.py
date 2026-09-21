"""ماژولِ «مدیریت اکانت‌ها» — فقط سوپرادمین. شکلِ ورودی/خروجیِ کنترل‌پنل."""
from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

MIN_PASSWORD = 10  # هم‌راستا با SignupIn

#: نوعِ حسابِ بازارِ عمده‌فروشی (انحصاری). standard = کسب‌وکارِ عادی.
MARKETPLACE_KINDS = ("standard", "distributor", "retailer")


class AccountUserOut(BaseModel):
    """یک کاربرِ اکانت به‌همراه آخرین فعالیت — برای بخشِ «کاربرها» در پنلِ مدیریت."""
    name: str
    email: str
    status: str  # وضعیتِ عضویت: active | invited | disabled
    is_owner: bool
    last_login_at: datetime | None


class AccountRowOut(BaseModel):
    tenant_id: UUID
    name: str
    slug: str
    status: str  # active | suspended | cancelled (وضعیتِ کسب‌وکار)
    kind: str = "standard"  # standard | distributor | retailer
    #: صنف (قالبِ ماژول‌ها) و ماژول‌های محدودِ گرنت‌شده — کنترل‌پنلِ شخصی‌سازیِ سوپرادمین.
    industry: str = "general"
    granted_modules: list[str] = []
    owner_name: str
    owner_email: str
    created_at: datetime
    user_count: int
    max_users: int | None
    subscription_status: str  # active | grace | expired | cancelled | none
    expires_at: datetime | None
    days_left: int | None
    plan_name: str
    #: حسابِ آزمایشیِ رایگانِ ۱۴روزه؟ روزهای مانده با منطقِ ceilِ ترایال (روزِ صفر = ۱۴).
    is_trial: bool = False
    trial_days_left: int | None = None
    trial_expired: bool = False
    #: آخرین ورودِ مالک، و آخرین ورودِ هر کاربرِ اکانت (بیشینه‌ی همه) — NULL یعنی هرگز.
    owner_last_login_at: datetime | None
    last_activity_at: datetime | None
    users: list[AccountUserOut]


class CreateAccountIn(BaseModel):
    business_name: str
    owner_name: str
    email: EmailStr
    password: str
    #: طولِ اشتراکِ اولیه به روز. ۰ = بدونِ اشتراک (وضعیتِ «none»؛ نوشتن باز است).
    days: int = 365
    #: نوعِ حسابِ بازار: standard | distributor | retailer.
    kind: str = "standard"

    @field_validator("password")
    @classmethod
    def pw_len(cls, v: str) -> str:
        if len(v) < MIN_PASSWORD:
            raise ValueError(f"رمز عبور باید حداقل {MIN_PASSWORD} کاراکتر باشد")
        return v

    @field_validator("kind")
    @classmethod
    def kind_valid(cls, v: str) -> str:
        if v not in MARKETPLACE_KINDS:
            raise ValueError("نوعِ حساب نامعتبر است")
        return v

    @field_validator("business_name", "owner_name")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("این فیلد نمی‌تواند خالی باشد")
        return v.strip()

    @field_validator("days")
    @classmethod
    def days_range(cls, v: int) -> int:
        if v < 0 or v > 3650:
            raise ValueError("تعداد روز نامعتبر است")
        return v


class ExtendIn(BaseModel):
    """تمدید (افزودنِ روز) یا تعیینِ تاریخِ انقضای مشخص. یکی الزامی است."""
    days: int | None = None
    expires_at: date | None = None

    @model_validator(mode="after")
    def one_required(self) -> "ExtendIn":
        if self.days is None and self.expires_at is None:
            raise ValueError("یا تعداد روز یا تاریخ انقضا لازم است")
        if self.days is not None and (self.days <= 0 or self.days > 3650):
            raise ValueError("تعداد روز نامعتبر است")
        return self


class SetKindIn(BaseModel):
    """تغییرِ نوعِ حسابِ بازار (سوپرادمین)."""
    kind: str

    @field_validator("kind")
    @classmethod
    def valid(cls, v: str) -> str:
        if v not in MARKETPLACE_KINDS:
            raise ValueError("نوعِ حساب نامعتبر است")
        return v


class SetIndustryIn(BaseModel):
    """تغییرِ صنف (بازنشانیِ ماژول‌ها به قالبِ صنف) — سوپرادمین."""
    industry: str

    @field_validator("industry")
    @classmethod
    def valid(cls, v: str) -> str:
        from app.services.modules import INDUSTRY_TEMPLATES

        if v not in INDUSTRY_TEMPLATES:
            raise ValueError("صنفِ نامعتبر است")
        return v


class SetGrantsIn(BaseModel):
    """گرنتِ ماژول‌های محدود به اکانت — سوپرادمین. فهرستِ کاملِ محدودهای مجاز (نه افزایشی)."""
    granted: list[str]

    @field_validator("granted")
    @classmethod
    def valid(cls, v: list[str]) -> list[str]:
        from app.services.modules import RESTRICTED_MODULES

        bad = [k for k in v if k not in RESTRICTED_MODULES]
        if bad:
            raise ValueError("ماژولِ محدودِ نامعتبر: " + ", ".join(bad))
        return v


class StatusIn(BaseModel):
    status: str  # active | suspended

    @field_validator("status")
    @classmethod
    def valid(cls, v: str) -> str:
        if v not in ("active", "suspended"):
            raise ValueError("وضعیت نامعتبر است")
        return v


class ResetPasswordIn(BaseModel):
    password: str

    @field_validator("password")
    @classmethod
    def pw_len(cls, v: str) -> str:
        if len(v) < MIN_PASSWORD:
            raise ValueError(f"رمز عبور باید حداقل {MIN_PASSWORD} کاراکتر باشد")
        return v


class DeleteAccountIn(BaseModel):
    """تأییدِ حذفِ برگشت‌ناپذیر.

    تایپ‌کردنِ شناسه‌ی کسب‌وکار تنها گاردی است که هم جلوی کلیکِ اشتباه را می‌گیرد و
    هم جلوی ارسالِ دوباره. دلیلِ اینکه از `idempotent()` استفاده نشده در
    docstringِ `admin_accounts.delete_account` نوشته شده.
    """

    confirm_slug: str
    #: دلیل در ردِ ستاد می‌نشیند. حذفی که دلیلش ثبت نشده، شش ماه بعد قابلِ دفاع نیست.
    reason: str = Field(min_length=10, max_length=300)
