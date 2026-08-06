from uuid import UUID

from pydantic import BaseModel, EmailStr, field_validator

#: حداقل طول رمز، یک‌جا تعریف می‌شود تا ثبت‌نام، بازیابی و پذیرش دعوت نتوانند از هم
#: جدا بیفتند — سه قانون متفاوت برای یک چیز، همان‌جایی است که ضعیف‌ترینش برنده می‌شود.
MIN_PASSWORD_LENGTH = 10


def validate_password(v: str) -> str:
    if len(v) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"رمز عبور باید حداقل {MIN_PASSWORD_LENGTH} کاراکتر باشد")
    return v


class MemberOut(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    email: str
    role_key: str
    role_name: str
    status: str
    is_me: bool


class SeatsOut(BaseModel):
    """وضعیت سقف کاربران — تا رابط کاربری بتواند قبل از رد شدن، محدودیت را نشان دهد."""

    used: int
    limit: int | None  # None یعنی نامحدود


class MemberListOut(BaseModel):
    members: list[MemberOut]
    seats: SeatsOut


class InviteIn(BaseModel):
    email: EmailStr
    name: str
    role_key: str

    @field_validator("name")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("نام نمی‌تواند خالی باشد")
        return v.strip()


class InviteOut(BaseModel):
    member: MemberOut
    #: در production همیشه True؛ False یعنی عضویت ساخته شد ولی ایمیل نرفت و مدیر
    #: باید بداند، وگرنه منتظر کاربری می‌ماند که هرگز لینکی نگرفته.
    email_sent: bool


class ChangeRoleIn(BaseModel):
    role_key: str


class SetStatusIn(BaseModel):
    active: bool


class AcceptInviteIn(BaseModel):
    token: str
    password: str
    name: str | None = None

    _check = field_validator("password")(validate_password)


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str
    password: str

    _check = field_validator("password")(validate_password)


class ForgotPasswordSmsIn(BaseModel):
    """بازیابیِ رمز با پیامک: به‌جای ایمیل، شماره‌ی موبایلِ تأییدشده را می‌گیرد."""

    phone: str


class ResetPasswordSmsIn(BaseModel):
    """گامِ دومِ بازیابیِ پیامکی: کدِ ۶رقمی + رمزِ تازه، همراهِ همان شماره."""

    phone: str
    code: str
    password: str

    _check = field_validator("password")(validate_password)


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str

    _check = field_validator("new_password")(validate_password)
