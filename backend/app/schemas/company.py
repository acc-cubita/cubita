"""اسکیمای موجودیت‌های «شرکت» — گروه، محلِ جغرافیایی، فردِ مرتبط."""
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.company import GEO_KINDS


class ContactGroupIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    code: str = Field(default="", max_length=30)
    notes: str = ""
    is_active: bool = True


class ContactGroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    code: str
    notes: str
    is_active: bool
    #: شمارِ طرف‌حساب‌های این گروه — تا فهرست بدونِ کوئریِ جدا معنا داشته باشد.
    contact_count: int = 0


class GeoLocationIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: str = "city"
    code: str = Field(default="", max_length=30)
    parent_id: UUID | None = None
    is_active: bool = True

    @field_validator("kind")
    @classmethod
    def valid_kind(cls, v: str) -> str:
        if v not in GEO_KINDS:
            raise ValueError("سطحِ نامعتبر؛ یکی از: " + "، ".join(GEO_KINDS))
        return v


class GeoLocationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    kind: str
    code: str
    parent_id: UUID | None
    is_active: bool
    #: مسیرِ کاملِ خوانا («ایران / تهران / تهران / منطقه ۳») — برای نمایش در فهرست و انتخابگر.
    path: str = ""
    contact_count: int = 0


class RelatedPersonIn(BaseModel):
    contact_id: UUID
    name: str = Field(min_length=1, max_length=200)
    role: str = Field(default="", max_length=120)
    #: «(۲)»ِ فرمِ سپیدار — نسخه‌ی دومِ لاتین. اختیاری و بی‌اثر بر فارسی.
    name2: str = Field(default="", max_length=200)
    role2: str = Field(default="", max_length=200)
    phone: str = Field(default="", max_length=30)
    email: str = Field(default="", max_length=150)
    is_primary: bool = False
    is_active: bool = True
    notes: str = ""


class RelatedPersonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    contact_id: UUID
    name: str
    role: str
    name2: str = ""
    role2: str = ""
    phone: str
    email: str
    is_primary: bool
    is_active: bool
    notes: str
    #: نامِ طرف‌حساب — فهرستِ «افرادِ مرتبط» بدونِ آن فقط ستونی از نام‌های بی‌زمینه است.
    contact_name: str = ""


class SavedReportIn(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str = ""
    source: str = Field(min_length=1, max_length=80)
    config: dict = Field(default_factory=dict)
    is_pinned: bool = False


class SavedReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str
    source: str
    config: dict
    is_pinned: bool
