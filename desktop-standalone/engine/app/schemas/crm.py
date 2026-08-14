from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, field_validator

from app.models.crm import ACTIVITY_KINDS, LEAD_STATUSES, REWARD_KINDS, TIER_BASES


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
    reward_id: UUID | None = None

    model_config = {"from_attributes": True}


class LoyaltyBalanceOut(BaseModel):
    contact_id: UUID
    contact_name: str
    balance: int


class LoyaltySettingsIn(BaseModel):
    is_enabled: bool = False
    #: چند تومان خرید = ۱ امتیاز (۰ = بدون کسبِ خودکار)
    amount_per_point: Decimal = Decimal(0)
    tier_basis: str = "points"
    tier_discount_auto: bool = False
    birthday_gift_points: int = 0

    @field_validator("amount_per_point")
    @classmethod
    def nonneg(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("مقدار نمی‌تواند منفی باشد")
        return v

    @field_validator("tier_basis")
    @classmethod
    def basis_valid(cls, v: str) -> str:
        if v not in TIER_BASES:
            raise ValueError("مبنای سطح نامعتبر است")
        return v

    @field_validator("birthday_gift_points")
    @classmethod
    def gift_nonneg(cls, v: int) -> int:
        if v < 0:
            raise ValueError("امتیازِ تولد نمی‌تواند منفی باشد")
        return v


class LoyaltySettingsOut(BaseModel):
    is_enabled: bool
    amount_per_point: Decimal
    tier_basis: str = "points"
    tier_discount_auto: bool = False
    birthday_gift_points: int = 0

    model_config = {"from_attributes": True}


# ── سطوحِ باشگاه ────────────────────────────────────────
class TierIn(BaseModel):
    name: str
    threshold: Decimal = Decimal(0)
    discount_percent: Decimal = Decimal(0)
    sort_order: int = 0

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("نامِ سطح نمی‌تواند خالی باشد")
        return v.strip()

    @field_validator("discount_percent")
    @classmethod
    def discount_range(cls, v: Decimal) -> Decimal:
        if v < 0 or v > 100:
            raise ValueError("درصدِ تخفیف باید بینِ ۰ تا ۱۰۰ باشد")
        return v


class TierOut(BaseModel):
    id: UUID
    name: str
    threshold: Decimal
    discount_percent: Decimal
    sort_order: int

    model_config = {"from_attributes": True}


class TierMemberOut(BaseModel):
    contact_id: UUID
    contact_name: str
    value: Decimal
    tier_id: UUID
    tier_name: str
    discount_percent: Decimal


class ContactTierOut(BaseModel):
    basis: str
    value: Decimal
    tier_id: UUID | None
    tier_name: str | None
    discount_percent: Decimal


# ── کاتالوگِ جوایز ─────────────────────────────────────
class RewardIn(BaseModel):
    name: str
    points_cost: int = 0
    kind: str = "gift"
    value: str = ""
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("نامِ جایزه نمی‌تواند خالی باشد")
        return v.strip()

    @field_validator("points_cost")
    @classmethod
    def cost_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("امتیازِ لازم باید بزرگ‌تر از صفر باشد")
        return v

    @field_validator("kind")
    @classmethod
    def kind_valid(cls, v: str) -> str:
        if v not in REWARD_KINDS:
            raise ValueError("نوعِ جایزه نامعتبر است")
        return v


class RewardOut(BaseModel):
    id: UUID
    name: str
    points_cost: int
    kind: str
    value: str
    is_active: bool

    model_config = {"from_attributes": True}


class RedeemIn(BaseModel):
    contact_id: UUID
    reward_id: UUID
    txn_date: date | None = None


# ── بخش‌بندیِ RFM ──────────────────────────────────────
class SegmentCustomerOut(BaseModel):
    contact_id: UUID
    contact_name: str
    recency_days: int
    frequency: int
    monetary: Decimal
    last_purchase: date | None
    r: int
    f: int
    m: int
    segment: str


class SegmentSummaryOut(BaseModel):
    segment: str
    count: int
    monetary: Decimal


class RfmOut(BaseModel):
    customers: list[SegmentCustomerOut]
    summary: list[SegmentSummaryOut]
    total_customers: int


# ── تولد ────────────────────────────────────────────────
class BirthdayOut(BaseModel):
    contact_id: UUID
    contact_name: str
    birthday: date
    next_birthday: date
    days_until: int
    turning_age: int
