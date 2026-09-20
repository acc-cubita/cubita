from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.advanced_inventory import QC_STATUSES


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
    #: تاریخِ اجرا از قبل روی مدل بود ولی هیچ‌وقت بیرون داده نمی‌شد — یعنی
    #: مصرف‌کننده نمی‌توانست بفهمد اعلامیه‌ای که می‌بیند امروز اثر دارد یا نه.
    effective_from: date

    model_config = {"from_attributes": True}


class PriceListItemIn(BaseModel):
    """یک قاعده‌ی قیمت — هدف + زمینه + نرخ + سیاستِ تغییر.

    هر بُعدِ زمینه اختیاری است و `None` یعنی «هر مقداری»، پس ردیفِ ساده‌ی
    امروزی دقیقاً مثلِ قبل کار می‌کند.
    """

    #: هدف: یا یک کالای مشخص، یا یک گروهِ فروشِ کالا (§۱۴). دستِ‌کم یکی لازم است —
    #: قاعده‌ای بی‌هدف روی *همه‌ی* کالاها می‌نشیند، که یک قیمتِ سراسریِ ناخواسته است.
    item_id: UUID | None = None
    item_group_id: UUID | None = None
    price: Decimal
    #: §۳۹ §۴۰ §۴۱ — از داده‌ی موجود، نه تعریفِ موازی.
    sale_type_id: UUID | None = None
    unit_id: UUID | None = None
    contact_group_id: UUID | None = None
    currency_code: str = "IRR"
    #: §۲۲ — ذخیره و نمایش، بدونِ اعمال (§۲۳ ربطش را باز نگذاشته).
    addition_percent: Decimal = Decimal(0)
    #: §۲۴ §۲۵ — دو سیاستِ مستقل، نه یک پرچمِ مشترک.
    allow_rate_change: bool = True
    allow_discount_change: bool = True
    #: §۲۷ §۲۸ — صفر یعنی **بی‌حد**، یعنی رفتارِ امروز. نامتقارن‌اند.
    max_increase_percent: Decimal = Decimal(0)
    max_decrease_percent: Decimal = Decimal(0)

    @field_validator("price")
    @classmethod
    def price_nonneg(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("قیمت نمی‌تواند منفی باشد")
        return v

    @field_validator("max_increase_percent", "max_decrease_percent", "addition_percent")
    @classmethod
    def _sane_limit(cls, v: Decimal) -> Decimal:
        if not (0 <= v <= 100):
            raise ValueError("درصد باید بینِ ۰ و ۱۰۰ باشد")
        return v

    @model_validator(mode="after")
    def _needs_a_target(self) -> "PriceListItemIn":
        if self.item_id is None and self.item_group_id is None:
            raise ValueError("قاعده‌ی قیمت باید کالا یا گروهِ فروشِ کالا را مشخص کند")
        return self


class PriceListItemOut(BaseModel):
    id: UUID
    item_id: UUID | None = None
    item_group_id: UUID | None = None
    price: Decimal
    sale_type_id: UUID | None = None
    unit_id: UUID | None = None
    contact_group_id: UUID | None = None
    currency_code: str = "IRR"
    addition_percent: Decimal = Decimal(0)
    allow_rate_change: bool = True
    allow_discount_change: bool = True
    max_increase_percent: Decimal = Decimal(0)
    max_decrease_percent: Decimal = Decimal(0)

    model_config = {"from_attributes": True}


class ResolvedPriceOut(BaseModel):
    """پاسخِ «فیِ این کالا در این زمینه چند است، و چرا؟» (§۲۱ §۹۱).

    حدها این‌جا می‌آیند چون در دامنه حساب شده‌اند؛ رابط نباید دوباره حسابشان کند
    — دو محاسبه‌ی مستقل یعنی رابط یک حد نشان دهد و سرور حدِ دیگری را اعمال کند.
    """

    rule_id: UUID
    announcement_id: UUID
    announcement_name: str
    effective_from: date
    unit_price: Decimal
    currency_code: str
    addition_percent: Decimal
    allow_rate_change: bool
    allow_discount_change: bool
    max_increase_percent: Decimal
    max_decrease_percent: Decimal
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    #: §۳۵ §۳۷ — چند قاعده با همین درجه‌ی مشخص‌بودن خواندند. برنده پایدار است،
    #: ولی پیکربندی مبهم است و کاربر باید بداند.
    ambiguous: bool = False

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
    #: شناسنامه‌ی بار — همه اختیاری (§۲۸). کسب‌وکاری که این‌ها را ندارد
    #: هیچ‌وقت نمی‌بیندشان و هیچ اعتبارسنجیِ تازه‌ای نمی‌خورد.
    supplier_batch_code: str = ""
    supplier_id: UUID | None = None
    location_id: UUID | None = None
    qc_status: str = "passed"

    @field_validator("qc_status")
    @classmethod
    def _valid_qc(cls, v: str) -> str:
        if v not in QC_STATUSES:
            raise ValueError("وضعیتِ کنترلِ کیفیت نامعتبر است")
        return v

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
    #: مجموعِ کسری/معیوب/ضایعاتِ ثبت‌شده روی این بار — از سندِ **تعدیل** مشتق
    #: می‌شود، نه از `received_qty − qty`: حالا فروش هم مانده را کم می‌کند و
    #: فروش کسری نیست (روتر پُر می‌کند).
    defect_qty: Decimal = Decimal(0)
    #: تعدادِ سریالِ کارتنِ ثبت‌شده روی این بار (روتر پُر می‌کند).
    serial_count: int = 0

    #: `ledger` = مانده از دفترِ انبار مشتق شد و دقیق است.
    #: `legacy` = این بار ردیفِ ورودیِ برچسب‌خورده ندارد (بارِ دستی، یا سندی که
    #: مهاجرتِ ۰۱۷۱ به‌خاطرِ ابهام از آن رد شد)، پس عددِ ستونِ قدیمی نشان داده
    #: می‌شود و رابط باید نشانه بگذارد — نه اینکه مثلِ عددِ دقیق جلوه‌اش دهد.
    qty_source: str = "legacy"
    #: هر دو عددِ خام، کنارِ هم: گزارشِ مغایرت از همین اختلاف ساخته می‌شود.
    ledger_qty: Decimal = Decimal(0)
    legacy_qty: Decimal = Decimal(0)

    #: شناسنامه و وضعیت (مهاجرتِ ۰۱۷۲).
    supplier_batch_code: str = ""
    supplier_id: UUID | None = None
    location_id: UUID | None = None
    parent_batch_id: UUID | None = None
    qc_status: str = "passed"
    hold_status: str = "none"
    hold_reason: str = ""
    is_closed: bool = False

    #: چهار عددِ §۴ به‌علاوه‌ی وضعیتِ مشتق (روتر پُر می‌کند).
    #:
    #: `physical` هرگز با نزدیک‌شدنِ انقضا تکان نمی‌خورد؛ `sellable` است که صفر
    #: می‌شود. §۲۹ صریح است که این دو یکی نیستند.
    physical_qty: Decimal = Decimal(0)
    reserved_qty: Decimal = Decimal(0)
    available_qty: Decimal = Decimal(0)
    sellable_qty: Decimal = Decimal(0)
    days_to_expiry: int | None = None
    #: از واژگانِ §۳، ولی **محاسبه‌شده** — هیچ ستونی نگهش نمی‌دارد تا کهنه شود.
    status: str = "available"

    model_config = {"from_attributes": True}


class BatchReconciliationOut(BaseModel):
    """یک بار که مانده‌اش از دفتر درنمی‌آید — گزارش است، نه خطا."""

    batch_id: UUID
    item_id: UUID
    warehouse_id: UUID
    batch_number: str
    received_date: date
    legacy_qty: Decimal
    ledger_qty: Decimal
    delta: Decimal
    #: manual | ambiguous | pre_tracking — برچسبِ فارسی سمتِ رابط است.
    reason: str


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


class SerialAssignIn(BaseModel):
    """چسباندنِ چند سریال به یک سند.

    سریال با **نامش** می‌آید چون کاربر همان را از روی جعبه می‌خوانَد. گامِ جداست
    و نه بخشی از ثبتِ فاکتور: فاکتور مقدار می‌داند و نمی‌داند کدام سه تا از پنج
    تا رفت — آن را انسان با اسکنر می‌گوید.
    """

    item_id: UUID
    serials: list[str] = Field(min_length=1)
    source_type: str
    source_id: UUID
    entry_date: date
    #: receipt | issue | return_in | return_out | adjust
    event_type: str = "issue"


class SerialAssignOut(BaseModel):
    assigned: int
    created: int
    #: تلاشِ دوباره‌ی همان تخصیص — رویدادِ تازه‌ای نساخت.
    replayed: int


class SerialEventOut(BaseModel):
    event_type: str
    event_label: str
    entry_date: date
    source_type: str
    source_label: str
    source_id: UUID | None
    source_number: int | None
    counterparty: str
    notes: str


class SerialTraceOut(BaseModel):
    """یک سریال با **کلِ تاریخچه‌اش** — موقعیتِ فعلی مشتق است، نه ذخیره‌شده."""

    serial_id: UUID
    serial: str
    status: str
    item_id: UUID | None
    item_sku: str
    item_name: str
    batch_number: str
    in_stock: bool
    last_event_type: str | None
    last_event_label: str
    last_source_type: str | None
    last_source_id: UUID | None
    last_entry_date: date | None
    events: list[SerialEventOut]
