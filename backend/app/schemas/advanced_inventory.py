from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, field_validator


# ── لیستِ قیمت ──────────────────────────────────────────
class PriceListIn(BaseModel):
    name: str
    notes: str = ""

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("نامِ لیستِ قیمت نمی‌تواند خالی باشد")
        return v.strip()


class PriceListUpdateIn(BaseModel):
    name: str | None = None
    is_active: bool | None = None
    notes: str | None = None


class PriceListOut(BaseModel):
    id: UUID
    name: str
    is_active: bool
    notes: str

    model_config = {"from_attributes": True}


class PriceListItemIn(BaseModel):
    """یک قاعده‌ی قیمت — کالا + زمینه + نرخ + حدِ تغییر (§۳۷–§۴۲).

    هر سه بُعدِ زمینه اختیاری‌اند و `None` یعنی «هر مقداری»، پس ردیفِ ساده‌ی
    امروزی دقیقاً مثلِ قبل کار می‌کند.
    """

    item_id: UUID
    price: Decimal
    #: §۳۹ §۴۰ §۴۱ — از داده‌ی موجود، نه تعریفِ موازی.
    sale_type_id: UUID | None = None
    unit_id: UUID | None = None
    contact_group_id: UUID | None = None
    currency_code: str = "IRR"
    #: §۴۲ — صفر یعنی **بی‌حد**، یعنی رفتارِ امروز.
    allow_rate_change: bool = True
    max_increase_percent: Decimal = Decimal(0)
    max_decrease_percent: Decimal = Decimal(0)

    @field_validator("price")
    @classmethod
    def price_nonneg(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("قیمت نمی‌تواند منفی باشد")
        return v

    @field_validator("max_increase_percent", "max_decrease_percent")
    @classmethod
    def _sane_limit(cls, v: Decimal) -> Decimal:
        if not (0 <= v <= 100):
            raise ValueError("حدِ تغییرِ نرخ باید بینِ ۰ و ۱۰۰ باشد")
        return v


class PriceListItemOut(BaseModel):
    id: UUID
    item_id: UUID
    price: Decimal
    sale_type_id: UUID | None = None
    unit_id: UUID | None = None
    contact_group_id: UUID | None = None
    currency_code: str = "IRR"
    allow_rate_change: bool = True
    max_increase_percent: Decimal = Decimal(0)
    max_decrease_percent: Decimal = Decimal(0)

    model_config = {"from_attributes": True}


class SetPricesIn(BaseModel):
    items: list[PriceListItemIn]


# ── بچ / تاریخِ انقضا ───────────────────────────────────
class StockBatchIn(BaseModel):
    item_id: UUID
    warehouse_id: UUID
    batch_number: str
    expiry_date: date | None = None
    production_date: date | None = None
    qty: Decimal = Decimal(0)
    #: قیمتِ خرید (بهای واحد) و قیمتِ مصرف‌کننده — برای حاشیه‌ی سود. اختیاری در ورودِ دستی.
    unit_cost: Decimal = Decimal(0)
    consumer_price: Decimal = Decimal(0)
    received_date: date
    notes: str = ""

    @field_validator("batch_number")
    @classmethod
    def batch_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("شماره‌ی بچ/سری نمی‌تواند خالی باشد")
        return v.strip()


class StockBatchOut(BaseModel):
    id: UUID
    item_id: UUID
    warehouse_id: UUID
    batch_number: str
    expiry_date: date | None
    qty: Decimal
    received_qty: Decimal = Decimal(0)
    unit_cost: Decimal = Decimal(0)
    consumer_price: Decimal = Decimal(0)
    production_date: date | None = None
    source_type: str = "manual"
    source_id: UUID | None = None
    received_date: date
    notes: str
    #: مجموعِ کسری/معیوب/ضایعاتِ ثبت‌شده روی این بار = received_qty − qty (روتر پُر می‌کند).
    defect_qty: Decimal = Decimal(0)
    #: تعدادِ سریالِ کارتنِ ثبت‌شده روی این بار (روتر پُر می‌کند).
    serial_count: int = 0

    model_config = {"from_attributes": True}


# ── سریالِ کارتن ────────────────────────────────────────
class BatchSerialOut(BaseModel):
    id: UUID
    batch_id: UUID
    serial: str
    status: str
    notes: str

    model_config = {"from_attributes": True}


class BatchSerialAddIn(BaseModel):
    """افزودنِ سریال‌های کارتن به یک بار — یا فهرستِ صریح، یا تولیدِ توالیِ خودکار.

    - `serials`: فهرستِ سریال‌های دستی (وقتی توالی ندارند).
    - `prefix`+`start`+`count`: تولیدِ خودکارِ توالی (مثلاً CTN-001..CTN-050) وقتی مرتب‌اند.
    """
    serials: list[str] = []
    prefix: str = ""
    start: int | None = None
    count: int | None = None
    pad: int = 0  # صفرِ چپ برای شماره‌ی توالی (۳ → 001)

    @field_validator("serials")
    @classmethod
    def _clean(cls, v: list[str]) -> list[str]:
        return [s.strip() for s in v if s and s.strip()]


class BatchSerialStatusIn(BaseModel):
    status: str  # ok | defect

    @field_validator("status")
    @classmethod
    def _valid(cls, v: str) -> str:
        if v not in ("ok", "defect"):
            raise ValueError("وضعیت باید ok یا defect باشد")
        return v


# ── تعدیلِ بار: کسری/معیوب/ضایعات ─────────────────────────
class BatchAdjustIn(BaseModel):
    """کسری/معیوب/ضایعاتِ یک بار — از موجودی کم و به حسابداری (زیان) ثبت می‌شود."""
    qty: Decimal
    reason: str  # shortage | defect | wastage
    notes: str = ""
    adjustment_date: date

    @field_validator("qty")
    @classmethod
    def _positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("مقدارِ کسری/معیوب باید بزرگ‌تر از صفر باشد")
        return v

    @field_validator("reason")
    @classmethod
    def _reason(cls, v: str) -> str:
        if v not in ("shortage", "defect", "wastage"):
            raise ValueError("نوع باید shortage یا defect یا wastage باشد")
        return v
