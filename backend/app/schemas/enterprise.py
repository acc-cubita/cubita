"""شِمای مجوزِ «کوبیتا سازمانی» — فقط در نسخه‌ی سازمانی پر می‌شود."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.licensing.state import LicenseStatus


class LicenseOut(BaseModel):
    #: trial | trial_expired | active | grace | expired | clock | mismatch | invalid
    mode: str
    #: false یعنی ثبتِ سندِ تازه بسته است (خواندن همیشه باز است).
    writable: bool
    message: str | None = None
    days_left: int | None = None
    expires_at: datetime | None = None
    org: str | None = None
    seats: int | None = None
    #: حساب‌های فعلی — فقط در `/api/license`، نه در `/me`.
    seats_used: int | None = None
    mods: list[str] | None = None
    feat: list[str] | None = None
    license_id: str | None = None
    #: paid | free؛ None یعنی هنوز مجوزی نصب نشده (آزمایشی).
    tier: str | None = None

    @classmethod
    def of(cls, s: LicenseStatus, seats_used: int | None = None) -> "LicenseOut":
        return cls(
            mode=s.mode,
            writable=s.writable,
            message=s.message,
            days_left=s.days_left,
            expires_at=s.expires_at,
            org=s.org,
            seats=s.seats,
            seats_used=seats_used,
            mods=sorted(s.mods) if s.mods is not None else None,
            feat=sorted(s.feat) if s.feat is not None else None,
            license_id=s.license_id,
            tier=s.tier,
        )


class LicenseRequestOut(BaseModel):
    code: str


class LicenseActivateIn(BaseModel):
    #: کدِ فعال‌سازیِ خریداری‌شده (XXXX-XXXX-XXXX-XXXX).
    code: str = Field(min_length=8, max_length=64)


class LicenseInstallIn(BaseModel):
    token: str = Field(min_length=10, max_length=8000)


class LicenseFreeCodeIn(BaseModel):
    """ثبت‌نامِ رایگان، قدمِ اول: کدِ پیامکی به این شماره."""

    phone: str = Field(min_length=10, max_length=32)


class LicenseFreeCodeOut(BaseModel):
    #: شماره‌ی پوشیده، همان‌طور که ابر برگرداند.
    phone: str
    expires_in: int


class LicenseFreeActivateIn(BaseModel):
    phone: str = Field(min_length=10, max_length=32)
    code: str = Field(min_length=4, max_length=12)
    #: نامِ سازمان روی مجوز؛ خالی = نامِ کسب‌وکار.
    org: str | None = Field(default=None, max_length=200)
