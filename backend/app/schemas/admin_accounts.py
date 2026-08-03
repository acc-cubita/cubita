"""ماژولِ «مدیریت اکانت‌ها» — فقط سوپرادمین. شکلِ ورودی/خروجیِ کنترل‌پنل."""
from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, field_validator, model_validator

MIN_PASSWORD = 10  # هم‌راستا با SignupIn


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

    @field_validator("password")
    @classmethod
    def pw_len(cls, v: str) -> str:
        if len(v) < MIN_PASSWORD:
            raise ValueError(f"رمز عبور باید حداقل {MIN_PASSWORD} کاراکتر باشد")
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
