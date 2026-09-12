"""شکلِ ورودی/خروجیِ عملیاتِ ماژولِ فروش."""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.sales_ops import COMMISSION_BASES, FACTOR_KINDS, FACTOR_MODES, FACTOR_SCOPES, NOTE_KINDS


class _Named(BaseModel):
    model_config = {"from_attributes": True}


# ─────────────────────────── نوعِ فروش ───────────────────────────


class SaleTypeIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    due_days: int = Field(default=0, ge=0, le=3650)
    default_tax_rate: Decimal | None = Field(default=None, ge=0, le=100)
    goods_revenue_account_id: UUID | None = None
    service_revenue_account_id: UUID | None = None
    goods_discount_account_id: UUID | None = None
    service_discount_account_id: UUID | None = None
    addition_account_id: UUID | None = None
    description: str = ""
    is_active: bool = True


class SaleTypeOut(_Named):
    id: UUID
    name: str
    due_days: int
    default_tax_rate: Decimal | None
    goods_revenue_account_id: UUID | None
    service_revenue_account_id: UUID | None
    goods_discount_account_id: UUID | None
    service_discount_account_id: UUID | None
    addition_account_id: UUID | None
    description: str
    is_active: bool


# ────────────────────── گروهِ کالای تخفیف ───────────────────────


class DiscountGroupIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    is_active: bool = True
    #: اعضا با هر ذخیره کاملاً جایگزین می‌شوند — «این گروه دقیقاً این کالاهاست».
    item_ids: list[UUID] = []


class DiscountGroupOut(_Named):
    id: UUID
    name: str
    description: str
    is_active: bool
    item_ids: list[UUID] = []
    item_count: int = 0


# ─────────────────── تخفیف / عاملِ افزاینده ────────────────────


class PricingFactorIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: str
    mode: str = "percent"
    value: Decimal = Field(ge=0)
    scope: str = "all"
    item_id: UUID | None = None
    group_id: UUID | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    is_active: bool = True
    description: str = ""

    @field_validator("kind")
    @classmethod
    def _kind(cls, v: str) -> str:
        if v not in FACTOR_KINDS:
            raise ValueError("نوعِ عامل نامعتبر است")
        return v

    @field_validator("mode")
    @classmethod
    def _mode(cls, v: str) -> str:
        if v not in FACTOR_MODES:
            raise ValueError("مبنای عامل نامعتبر است")
        return v

    @field_validator("scope")
    @classmethod
    def _scope(cls, v: str) -> str:
        if v not in FACTOR_SCOPES:
            raise ValueError("دامنه‌ی عامل نامعتبر است")
        return v

    @field_validator("value")
    @classmethod
    def _percent_range(cls, v: Decimal, info) -> Decimal:
        # درصدِ بالای ۱۰۰ یعنی تخفیفِ بیش از کلِ مبلغ یا افزایشِ دوبرابری — تقریباً
        # همیشه اشتباهِ تایپی است، و اگر عمدی باشد با «مبلغ» بیانِ درست‌تری دارد.
        if info.data.get("mode") == "percent" and v > 100:
            raise ValueError("درصد نمی‌تواند بیشتر از ۱۰۰ باشد")
        return v


class PricingFactorOut(_Named):
    id: UUID
    name: str
    kind: str
    mode: str
    value: Decimal
    scope: str
    item_id: UUID | None
    group_id: UUID | None
    valid_from: date | None
    valid_to: date | None
    is_active: bool
    description: str


# ─────────────────────── اعلامیه‌ی قیمت ────────────────────────


class PriceListLineIn(BaseModel):
    item_id: UUID
    price: Decimal = Field(ge=0)


class PriceAnnouncementIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    effective_from: date
    notes: str = ""
    is_active: bool = True
    lines: list[PriceListLineIn] = []


class PriceAnnouncementOut(_Named):
    id: UUID
    name: str
    effective_from: date
    notes: str
    is_active: bool
    line_count: int = 0
    lines: list[dict] = []


# ─────────────────────── بسته‌ی محصول ─────────────────────────


class BundleLineIn(BaseModel):
    item_id: UUID
    qty: Decimal = Field(gt=0)


class ProductBundleIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    bundle_price: Decimal | None = Field(default=None, ge=0)
    is_active: bool = True
    description: str = ""
    lines: list[BundleLineIn] = []


class ProductBundleOut(_Named):
    id: UUID
    name: str
    bundle_price: Decimal | None
    is_active: bool
    description: str
    lines: list[dict] = []


# ──────────────────────────── پورسانت ──────────────────────────


class CommissionRuleIn(BaseModel):
    salesperson_id: UUID
    rate: Decimal = Field(ge=0, le=100)
    basis: str = "net"
    is_active: bool = True
    description: str = ""

    @field_validator("basis")
    @classmethod
    def _basis(cls, v: str) -> str:
        if v not in COMMISSION_BASES:
            raise ValueError("مبنای پورسانت نامعتبر است")
        return v


class CommissionRuleOut(_Named):
    id: UUID
    salesperson_id: UUID
    salesperson_name: str = "—"
    rate: Decimal
    basis: str
    is_active: bool
    description: str


class CommissionRowOut(BaseModel):
    salesperson_id: UUID
    salesperson_name: str
    invoice_count: int
    base_amount: Decimal
    rate: Decimal
    basis: str
    amount: Decimal


class CommissionPreviewOut(BaseModel):
    date_from: date
    date_to: date
    total_amount: Decimal
    rows: list[CommissionRowOut]


class CommissionRunIn(BaseModel):
    date_from: date
    date_to: date
    note: str = ""


class CommissionRunOut(BaseModel):
    id: UUID
    date_from: date
    date_to: date
    total_amount: Decimal
    note: str
    created_at: datetime
    rows: list[CommissionRowOut] = []


# ───────────────────── اظهارنامه‌ی گمرکی ──────────────────────


class CustomsIn(BaseModel):
    declaration_no: str = Field(min_length=1, max_length=40)
    declaration_date: date
    customs_office: str = ""
    hs_code: str = ""
    destination_country: str = ""
    declared_value: Decimal = Field(default=0, ge=0)
    currency_code: str = "IRR"
    invoice_id: UUID | None = None
    description: str = ""


class CustomsOut(_Named):
    id: UUID
    declaration_no: str
    declaration_date: date
    customs_office: str
    hs_code: str
    destination_country: str
    declared_value: Decimal
    currency_code: str
    invoice_id: UUID | None
    invoice_number: int | None = None
    description: str


# ──────────────── اعلامیه‌ی بدهکار / بستانکار ─────────────────


class NoteIn(BaseModel):
    kind: str
    note_date: date
    contact_id: UUID
    amount: Decimal = Field(gt=0)
    reason: str = ""
    invoice_id: UUID | None = None

    @field_validator("kind")
    @classmethod
    def _kind(cls, v: str) -> str:
        if v not in NOTE_KINDS:
            raise ValueError("نوعِ اعلامیه نامعتبر است")
        return v


class NoteOut(_Named):
    id: UUID
    number: int | None
    kind: str
    note_date: date
    contact_id: UUID
    contact_name: str = "—"
    amount: Decimal
    reason: str
    invoice_id: UUID | None
    journal_entry_id: UUID | None
    voided_at: datetime | None


class VoidNoteIn(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


# ──────────────────────── بستنِ فاکتور ───────────────────────


class CloseInvoicesIn(BaseModel):
    invoice_ids: list[UUID] = []
    date_from: date | None = None
    date_to: date | None = None


class CloseInvoicesOut(BaseModel):
    count: int
    first_date: date
    last_date: date
    total: Decimal


# ───────────────────── پیشنهادِ قیمت‌گذاری ────────────────────


class PricingSuggestionOut(BaseModel):
    unit_price: Decimal
    gross: Decimal
    discount: Decimal
    net: Decimal
    #: از کجا آمده — تا کاربر بداند چرا این عدد پیشنهاد شده.
    applied: list[dict]
