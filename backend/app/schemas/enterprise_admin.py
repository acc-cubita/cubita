"""شِمای پنلِ ستاد برای مجوزهای کوبیتا سازمانی و فعال‌سازیِ آنلاین."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class LicenseRecordOut(BaseModel):
    id: UUID
    lic_id: str
    org_name: str
    contact: str | None
    seats: int | None
    mods: list[str] | None
    feat: list[str] | None
    expires_at: datetime | None
    grace_days: int
    code_hint: str
    status: str
    revoked_at: datetime | None
    bound: bool
    bound_at: datetime | None
    last_issued_at: datetime | None
    issue_count: int
    note: str | None
    created_by_email: str | None
    created_at: datetime

    @classmethod
    def of(cls, r) -> "LicenseRecordOut":
        return cls(
            id=r.id,
            lic_id=r.lic_id,
            org_name=r.org_name,
            contact=r.contact,
            seats=r.seats,
            mods=r.mods,
            feat=r.feat,
            expires_at=r.expires_at,
            grace_days=r.grace_days,
            code_hint=r.code_hint,
            status=r.status,
            revoked_at=r.revoked_at,
            bound=bool(r.fp),
            bound_at=r.bound_at,
            last_issued_at=r.last_issued_at,
            issue_count=r.issue_count,
            note=r.note,
            created_by_email=r.created_by_email,
            created_at=r.created_at,
        )


class LicenseEventOut(BaseModel):
    kind: str
    actor: str
    detail: dict | None
    created_at: datetime


class LicenseDetailOut(LicenseRecordOut):
    events: list[LicenseEventOut] = []


class LicenseCreatedOut(BaseModel):
    license: LicenseRecordOut
    #: فقط همین یک‌بار — در دیتابیس فقط هشش می‌ماند.
    activation_code: str


def _clean_list(v: list[str] | None) -> list[str] | None:
    if v is None:
        return None
    return sorted({x.strip() for x in v if x and x.strip()})


class LicenseCreateIn(BaseModel):
    org_name: str = Field(min_length=2, max_length=200)
    contact: str | None = Field(default=None, max_length=200)
    seats: int | None = Field(default=None, ge=1, le=10000)
    #: None = دائمی.
    days: int | None = Field(default=365, ge=1, le=36500)
    grace_days: int = Field(default=14, ge=0, le=365)
    mods: list[str] | None = None
    feat: list[str] | None = None
    note: str | None = Field(default=None, max_length=2000)

    _mods = field_validator("mods", "feat")(_clean_list)


class LicenseUpdateIn(BaseModel):
    """فقط فیلدهای فرستاده‌شده عوض می‌شوند. تغییرِ سقف یا انقضا روی سرورِ مشتری با
    **توکنِ تازه** اثر می‌کند (فعال‌سازیِ دوباره یا صدورِ آفلاین)، نه خودکار."""

    org_name: str | None = Field(default=None, min_length=2, max_length=200)
    contact: str | None = Field(default=None, max_length=200)
    seats: int | None = Field(default=None, ge=1, le=10000)
    clear_seats: bool = False
    #: روزهای افزوده از انقضای فعلی (یا از امروز اگر گذشته باشد).
    extend_days: int | None = Field(default=None, ge=1, le=36500)
    make_perpetual: bool = False
    grace_days: int | None = Field(default=None, ge=0, le=365)
    feat: list[str] | None = None
    all_features: bool = False
    note: str | None = Field(default=None, max_length=2000)

    _feat = field_validator("feat")(_clean_list)


class LicenseIssueIn(BaseModel):
    request_code: str = Field(min_length=10, max_length=4000)


class LicenseTokenOut(BaseModel):
    token: str


class ActivationCodeOut(BaseModel):
    activation_code: str


class OnlineActivateIn(BaseModel):
    code: str = Field(min_length=8, max_length=64)
    request_code: str = Field(min_length=10, max_length=4000)
