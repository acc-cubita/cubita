from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, EmailStr, model_validator


class PlanOut(BaseModel):
    id: UUID
    key: str
    name: str
    description: str
    price_toman: Decimal
    billing_period: str
    #: نگاشتِ دوره→قیمت (تومان). سایت با کلیدِ دوره‌ی انتخابی از این می‌خواند.
    prices: dict[str, Decimal] = {}
    max_users: int | None
    features: list[str]
    is_active: bool
    sort_order: int
    highlighted: bool

    model_config = {"from_attributes": True}


class PurchaseRequestIn(BaseModel):
    plan_key: str
    customer_name: str
    customer_email: EmailStr
    customer_phone: str = ""
    business_name: str = ""
    #: دوره‌ی انتخابیِ مشتری. قیمت و طولِ اشتراک از همین تعیین می‌شوند.
    billing_period: str = "yearly"

    @model_validator(mode="after")
    def validate_required(self) -> "PurchaseRequestIn":
        if not self.customer_name.strip():
            raise ValueError("نام الزامی است")
        if self.billing_period not in ("monthly", "semiannual", "yearly"):
            raise ValueError("دوره‌ی صورتحساب نامعتبر است")
        return self


class PurchaseRequestOut(BaseModel):
    purchase_id: UUID
    payment_url: str


class PurchaseOut(BaseModel):
    id: UUID
    plan_id: UUID
    plan_name: str
    customer_name: str
    customer_email: str
    customer_phone: str
    business_name: str
    amount_toman: Decimal
    status: str
    zarinpal_ref_id: str | None
    admin_notes: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PurchaseFulfillIn(BaseModel):
    admin_notes: str = ""
