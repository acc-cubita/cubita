"""بازارِ عمده‌فروشی — شکلِ ورودی/خروجیِ سمتِ پخش‌کننده (M2)."""
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, field_validator, model_validator

from app.models.marketplace import LISTING_KINDS, SETTLEMENT_MODES


# ── تنظیماتِ پخش‌کننده ────────────────────────────────────────────────
class MarketplaceSettingsIn(BaseModel):
    display_name: str = ""
    settlement_mode: str = "credit"  # credit | online
    is_active: bool = False

    @field_validator("settlement_mode")
    @classmethod
    def _mode(cls, v: str) -> str:
        if v not in SETTLEMENT_MODES:
            raise ValueError("نحوه‌ی تسویه نامعتبر است")
        return v


class MarketplaceSettingsOut(BaseModel):
    display_name: str
    settlement_mode: str
    is_active: bool

    model_config = {"from_attributes": True}


# ── لیستینگِ کاتالوگ (تکی/پک) ─────────────────────────────────────────
class ListingComponentIn(BaseModel):
    item_id: UUID  # کالای خودِ پخش‌کننده
    qty: Decimal = Decimal(1)

    @field_validator("qty")
    @classmethod
    def _qty(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("تعدادِ جزء باید مثبت باشد")
        return v


class ListingComponentOut(BaseModel):
    item_id: UUID
    item_name: str
    qty: Decimal


class ListingIn(BaseModel):
    kind: str = "single"  # single | pack
    title: str
    code: str = ""
    unit: str = "عدد"
    wholesale_price: Decimal = Decimal(0)
    currency_code: str = ""
    description: str = ""
    images: list = []
    category: str = ""
    is_published: bool = False
    #: برای single: کالای متناظر. برای pack تهی (اجزا در components).
    item_id: UUID | None = None
    components: list[ListingComponentIn] = []

    @field_validator("kind")
    @classmethod
    def _kind(cls, v: str) -> str:
        if v not in LISTING_KINDS:
            raise ValueError("نوعِ لیستینگ نامعتبر است")
        return v

    @model_validator(mode="after")
    def _shape(self) -> "ListingIn":
        if not self.title.strip():
            raise ValueError("عنوانِ لیستینگ الزامی است")
        if self.wholesale_price < 0:
            raise ValueError("قیمتِ عمده نمی‌تواند منفی باشد")
        if self.kind == "single":
            if self.item_id is None:
                raise ValueError("برای کالای تکی، انتخابِ کالا الزامی است")
        else:  # pack
            if not self.components:
                raise ValueError("پک حداقل یک جزء لازم دارد")
        return self


class ListingOut(BaseModel):
    id: UUID
    kind: str
    title: str
    code: str
    unit: str
    wholesale_price: Decimal
    currency_code: str
    description: str
    images: list
    category: str
    is_published: bool
    item_id: UUID | None
    components: list[ListingComponentOut]


# ── اتصال‌ها (M3) ──────────────────────────────────────────────────────
CONNECTION_ACTIONS = ("approved", "rejected", "blocked")


class DistributorCardOut(BaseModel):
    """کارتِ یک پخش‌کننده‌ی فعال در نمای کشفِ فروشگاه + وضعیتِ اتصالِ من به او."""

    tenant_id: UUID
    display_name: str
    #: None = هنوز درخواستی نداده‌ام؛ وگرنه pending|approved|rejected|blocked.
    connection_status: str | None


class ConnectionRequestIn(BaseModel):
    distributor_tenant_id: UUID


class ConnectionStatusIn(BaseModel):
    status: str  # approved | rejected | blocked

    @field_validator("status")
    @classmethod
    def _st(cls, v: str) -> str:
        if v not in CONNECTION_ACTIONS:
            raise ValueError("وضعیتِ اتصال نامعتبر است")
        return v


class ConnectionOut(BaseModel):
    id: UUID
    distributor_tenant_id: UUID
    retailer_tenant_id: UUID
    distributor_name: str
    retailer_name: str
    status: str
    requested_by: str


# ── کاتالوگِ سمتِ فروشگاه (M3) ────────────────────────────────────────
class CatalogComponentOut(BaseModel):
    item_name: str
    qty: Decimal


class CatalogListingOut(BaseModel):
    """لیستینگِ منتشرشده آن‌گونه که فروشگاه می‌بیند — بدونِ شناسه‌های داخلیِ کالای پخش‌کننده."""

    id: UUID
    distributor_tenant_id: UUID
    distributor_name: str
    kind: str
    title: str
    code: str
    unit: str
    wholesale_price: Decimal
    currency_code: str
    description: str
    images: list
    category: str
    components: list[CatalogComponentOut]


# ── سفارش‌ها (M4) ──────────────────────────────────────────────────────
class OrderLineIn(BaseModel):
    listing_id: UUID
    qty: Decimal = Decimal(1)

    @field_validator("qty")
    @classmethod
    def _qty(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("تعدادِ سفارش باید مثبت باشد")
        return v


class OrderPlaceIn(BaseModel):
    distributor_tenant_id: UUID
    lines: list[OrderLineIn]
    note: str = ""

    @model_validator(mode="after")
    def _shape(self) -> "OrderPlaceIn":
        if not self.lines:
            raise ValueError("سفارش باید حداقل یک ردیف داشته باشد")
        return self


class OrderLineOut(BaseModel):
    listing_id: UUID | None
    title: str
    unit_price: Decimal
    qty: Decimal
    line_total: Decimal


class OrderOut(BaseModel):
    id: UUID
    distributor_tenant_id: UUID
    retailer_tenant_id: UUID
    distributor_name: str
    retailer_name: str
    order_number: int
    status: str
    settlement_mode: str
    payment_status: str
    note: str
    subtotal: Decimal
    total: Decimal
    distributor_sales_invoice_id: UUID | None
    retailer_purchase_invoice_id: UUID | None
    lines: list[OrderLineOut]
