from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AssuranceRequestIn(BaseModel):
    """درخواستِ حسابرسی از سمتِ مشتری."""

    period_from: date | None = None
    period_to: date | None = None
    contact_phone: str = Field(default="", max_length=30)
    note: str = Field(default="", max_length=2000)

    @field_validator("contact_phone")
    @classmethod
    def _phone(cls, value: str) -> str:
        clean = (value or "").strip()
        if clean and not clean.replace("+", "").replace("-", "").replace(" ", "").isdigit():
            raise ValueError("شماره‌ی تماس فقط رقم می‌پذیرد")
        return clean


class EngagementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    status: str
    requested_at: datetime
    period_from: date | None
    period_to: date | None
    contact_phone: str
    request_note: str
    decided_at: datetime | None
    reject_reason: str
    access_expires_at: datetime | None
    last_score: Decimal | None
    last_run_at: datetime | None
    last_run_id: UUID | None
    closed_at: datetime | None
    close_note: str
    #: نامِ حسابرس — مشتری باید بداند چه کسی دفترش را می‌بیند.
    auditor_name: str = ""
    auditor_email: str = ""


class StaffEngagementOut(EngagementOut):
    """همان قرارداد، به‌علاوه‌ی شناسه‌ی کسب‌وکار — فقط برای کارتابلِ ستاد."""

    tenant_name: str = ""
    owner_email: str = ""


class CheckScoreOut(BaseModel):
    """یک ردیفِ جدولِ توضیحِ نمره. این جدول **خودِ نمره** است."""

    key: str
    title: str
    description: str = ""
    severity: str
    family: str = "ledger"
    count: int
    weight: int
    lost: float


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    number: int
    ran_at: datetime
    trigger: str
    date_from: date | None
    date_to: date | None
    score: Decimal
    grade: str
    error_count: int
    warning_count: int
    finding_count: int
    total_debit: Decimal
    total_credit: Decimal
    summary: list[CheckScoreOut]


class FindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    check_key: str
    severity: str
    seq: int
    label: str
    detail: str
    debit: Decimal
    credit: Decimal
    difference: Decimal
    entry_id: UUID | None
    account_id: UUID | None
    item_id: UUID | None


# ── ورودی‌های ستاد ───────────────────────────────────────────────────────────


class ApproveIn(BaseModel):
    auditor_email: str
    days: int = Field(default=90, ge=1, le=730)
    period_from: date | None = None
    period_to: date | None = None


class RejectIn(BaseModel):
    reason: str = Field(default="", max_length=1000)


class AssignIn(BaseModel):
    auditor_email: str
    days: int | None = Field(default=None, ge=1, le=730)


class ExtendIn(BaseModel):
    days: int = Field(ge=1, le=730)


class RefreshIn(BaseModel):
    """بدنه‌ی خالیِ اجرای دوباره.

    `idempotent()` یک مدلِ Pydantic می‌خواهد تا اثرانگشتِ درخواست را بسازد؛ اجرای
    دوباره ورودی ندارد، ولی بدونِ این، محافظتِ دوکلیک اصلاً کار نمی‌کرد.
    """


class CloseIn(BaseModel):
    note: str = Field(default="", max_length=1000)
