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

    @model_validator(mode="after")
    def validate_required(self) -> "PurchaseRequestIn":
        if not self.customer_name.strip():
            raise ValueError("نام الزامی است")
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
