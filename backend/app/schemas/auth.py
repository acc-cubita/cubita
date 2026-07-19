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
    role_key: str
    role_name: str
    permissions: dict
    tenant_id: UUID
    tenant_name: str

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
