from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, field_validator

from app.models.crm import ACTIVITY_KINDS, LEAD_STATUSES


# ── سرنخ‌ها ─────────────────────────────────────────────
class LeadIn(BaseModel):
    name: str
    phone: str = ""
    email: str = ""
    company: str = ""
    source: str = ""
    status: str = "new"
    estimated_value: Decimal = Decimal(0)
    notes: str = ""
    next_action_date: date | None = None
    assigned_to_id: UUID | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("نام سرنخ نمی‌تواند خالی باشد")
        return v.strip()

    @field_validator("status")
    @classmethod
    def status_valid(cls, v: str) -> str:
        if v not in LEAD_STATUSES:
            raise ValueError("وضعیتِ سرنخ نامعتبر است")
        return v


class LeadUpdateIn(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    company: str | None = None
    source: str | None = None
    status: str | None = None
    estimated_value: Decimal | None = None
    notes: str | None = None
    next_action_date: date | None = None
    assigned_to_id: UUID | None = None

    @field_validator("status")
    @classmethod
    def status_valid(cls, v: str | None) -> str | None:
        if v is not None and v not in LEAD_STATUSES:
            raise ValueError("وضعیتِ سرنخ نامعتبر است")
        return v


class LeadOut(BaseModel):
    id: UUID
    name: str
    phone: str
    email: str
    company: str
    source: str
    status: str
    estimated_value: Decimal
    notes: str
    next_action_date: date | None
    assigned_to_id: UUID | None
    converted_contact_id: UUID | None

    model_config = {"from_attributes": True}


class ConvertLeadOut(BaseModel):
    contact_id: UUID


# ── فعالیت/پیگیری ───────────────────────────────────────
class ActivityIn(BaseModel):
    kind: str = "call"
    subject: str
    body: str = ""
    activity_date: date
    done: bool = False
    lead_id: UUID | None = None
    contact_id: UUID | None = None
    assigned_to_id: UUID | None = None

    @field_validator("kind")
    @classmethod
    def kind_valid(cls, v: str) -> str:
        if v not in ACTIVITY_KINDS:
            raise ValueError("نوعِ فعالیت نامعتبر است")
        return v

    @field_validator("subject")
    @classmethod
    def subject_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("موضوعِ فعالیت نمی‌تواند خالی باشد")
        return v.strip()


class ActivityUpdateIn(BaseModel):
    subject: str | None = None
    body: str | None = None
    activity_date: date | None = None
    done: bool | None = None


class ActivityOut(BaseModel):
    id: UUID
    kind: str
    subject: str
    body: str
    activity_date: date
    done: bool
    lead_id: UUID | None
    contact_id: UUID | None
    assigned_to_id: UUID | None

    model_config = {"from_attributes": True}


# ── امتیازِ وفاداری (باشگاه مشتریان) ───────────────────
class LoyaltyTxnIn(BaseModel):
    contact_id: UUID
    points: int
    reason: str = ""
    txn_date: date

    @field_validator("points")
    @classmethod
    def points_nonzero(cls, v: int) -> int:
        if v == 0:
            raise ValueError("امتیاز نمی‌تواند صفر باشد")
        return v


class LoyaltyTxnOut(BaseModel):
    id: UUID
    contact_id: UUID
    points: int
    reason: str
    txn_date: date

    model_config = {"from_attributes": True}


class LoyaltyBalanceOut(BaseModel):
    contact_id: UUID
    contact_name: str
    balance: int
