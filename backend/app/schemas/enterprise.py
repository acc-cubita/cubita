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
        )


class LicenseRequestOut(BaseModel):
    code: str


class LicenseInstallIn(BaseModel):
    token: str = Field(min_length=10, max_length=8000)
