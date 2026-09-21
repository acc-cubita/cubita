"""شکلِ داده‌ی هویتِ ستاد."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class StaffLoginIn(BaseModel):
    email: EmailStr
    password: str


class StaffTokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class StaffMeOut(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    #: عمداً `str` و نه `EmailStr`. این خروجی است نه ورودی: ایمیل از قبل در
    #: دیتابیس نشسته، و اعتبارسنجیِ دوباره‌اش فقط یک راه برای ۵۰۰ دادن روی
    #: داده‌ی سالم است (دامنه‌هایی که `email-validator` «رزرو‌شده» می‌داند).
    email: str
    role: str
    role_label: str
    permissions: dict
    last_login_at: datetime | None = None
    #: از کدام راه وارد شده — `staff` یا `legacy`. اپِ ستاد وقتی `legacy` باشد
    #: هشدار نشان می‌دهد، چون یعنی کوچ هنوز تمام نشده.
    via: str = "staff"


class StaffChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class DiagnosticsOut(BaseModel):
    """کاوشی که خرابیِ استقرارِ دمو لازم داشت.

    `/api/health` فقط `{"status":"ok"}` می‌دهد و دو بک‌اندِ متفاوت را از هم
    تشخیص نمی‌دهد — همان چیزی که باعث شد یک vhostِ اشتباه هفته‌ها زنده بماند.
    """

    env: str
    database_name: str
    alembic_version: str | None
    tenant_count: int
    staff_count: int
    legacy_admin_allowlist: bool


class StaffRowOut(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    #: مثلِ `StaffMeOut.email` عمداً `str` است — خروجی است نه ورودی.
    email: str
    role: str
    role_label: str
    is_active: bool
    last_login_at: datetime | None = None
    created_at: datetime


def _known_role(v: str) -> str:
    from app.staff_roles import STAFF_ROLES

    if v not in STAFF_ROLES:
        raise ValueError(f"نقشِ ناشناخته: {v}")
    return v


class StaffCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    role: str = "support"

    @field_validator("role")
    @classmethod
    def valid(cls, v: str) -> str:
        return _known_role(v)


class StaffRoleIn(BaseModel):
    role: str

    @field_validator("role")
    @classmethod
    def valid(cls, v: str) -> str:
        return _known_role(v)


class StaffStatusIn(BaseModel):
    active: bool


class StaffResetPasswordIn(BaseModel):
    password: str = Field(min_length=10, max_length=128)
