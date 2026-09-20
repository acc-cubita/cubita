"""بازارِ عمده‌فروشی — شکلِ ورودی/خروجیِ سمتِ پخش‌کننده (M2)."""
import base64
import re
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, field_validator, model_validator

from app.models.marketplace import LISTING_KINDS, SETTLEMENT_MODES
from app.services.trades import clean_trades, is_valid_trade

# ── سقفِ عکسِ کاتالوگ ──────────────────────────────────────────────────
# عکس‌ها به‌صورتِ data URIِ فشرده‌شده در JSONB ذخیره می‌شوند (نه فایلِ روی دیسک)،
# پس این سقف‌ها لازم‌اند تا پایگاه‌داده باد نکند. کلاینت هم پیش از ارسال عکس را
# روی canvas کوچک/فشرده می‌کند؛ این‌ها خطِ دفاعِ سختِ سمتِ سرورند (به بار متکی نیست).
MP_MAX_LISTING_IMAGES = 4
MP_MAX_IMAGE_BYTES = 400 * 1024  # ~۴۰۰ کیلوبایت به‌ازای هر عکسِ فشرده‌شده
_IMAGE_DATA_URI_RE = re.compile(
    r"^data:image/(?P<mime>png|jpeg|jpg|webp);base64,(?P<data>[A-Za-z0-9+/=\s]+)$"
)


def _validate_listing_images(v: object) -> list[str]:
    """فهرستِ عکس‌ها را اعتبارسنجی و نرمال می‌کند (فقط data URIِ تصویرِ کوچک)."""
    if not isinstance(v, list):
        raise ValueError("فهرستِ عکس‌ها نامعتبر است")
    if len(v) > MP_MAX_LISTING_IMAGES:
        raise ValueError(f"حداکثر {MP_MAX_LISTING_IMAGES} عکس برای هر لیستینگ مجاز است")
    cleaned: list[str] = []
    for raw in v:
        if not isinstance(raw, str):
            raise ValueError("هر عکس باید data URI باشد")
        m = _IMAGE_DATA_URI_RE.match(raw.strip())
        if m is None:
            raise ValueError("قالبِ عکس نامعتبر است — فقط JPEG/PNG/WebP به‌صورتِ data URI پذیرفته می‌شود")
        b64 = re.sub(r"\s+", "", m.group("data"))
        try:
            size = len(base64.b64decode(b64, validate=True))
        except Exception as exc:  # noqa: BLE001 — دادهٔ base64ِ خراب
            raise ValueError("دادهٔ عکس خراب است") from exc
        if size > MP_MAX_IMAGE_BYTES:
            raise ValueError(
                f"حجمِ هر عکس نباید از {MP_MAX_IMAGE_BYTES // 1024} کیلوبایت بیشتر باشد؛ عکس را کوچک‌تر کنید"
            )
        mime = "jpeg" if m.group("mime") == "jpg" else m.group("mime")
        cleaned.append(f"data:image/{mime};base64,{b64}")
    return cleaned


# ── تنظیماتِ پخش‌کننده ────────────────────────────────────────────────
class MarketplaceSettingsIn(BaseModel):
    display_name: str = ""
    settlement_mode: str = "credit"  # credit | online
    is_active: bool = False
    #: گردشِ کارِ «تحویل با مامور حمل» — ورودِ کالا به انبارِ فروشگاه هنگامِ ثبتِ تحویل.
    require_delivery: bool = False
    #: سیاستِ مرجوعی که به فروشگاه نشان داده می‌شود، و مهلتِ مرجوعی به روز (۰ = بی‌محدودیت).
    return_policy: str = ""
    return_window_days: int = 0
    #: اصنافی که این پخش‌کننده به آن‌ها جنس می‌دهد. خالی = بدونِ محدودیت.
    target_trades: list[str] = []

    @field_validator("target_trades")
    @classmethod
    def _targets(cls, v: list[str]) -> list[str]:
        #: کلیدِ ناشناخته رد می‌شود نه اینکه بی‌صدا دور ریخته شود: اگر کلاینتی کلیدِ
        #: غلط بفرستد، پخش‌کننده فکر می‌کند صنفی را هدف گرفته که در واقع ذخیره نشده
        #: — و بعد نمی‌فهمد چرا آن فروشگاه‌ها سفارش نمی‌دهند.
        unknown = [k for k in v if not is_valid_trade(k)]
        if unknown:
            raise ValueError(f"صنفِ نامعتبر: {'، '.join(unknown)}")
        return clean_trades(v)

    @field_validator("settlement_mode")
    @classmethod
    def _mode(cls, v: str) -> str:
        if v not in SETTLEMENT_MODES:
            raise ValueError("نحوه‌ی تسویه نامعتبر است")
        return v

    @field_validator("return_window_days")
    @classmethod
    def _window(cls, v: int) -> int:
        if v < 0:
            raise ValueError("مهلتِ مرجوعی نمی‌تواند منفی باشد")
        return v


class MarketplaceSettingsOut(BaseModel):
    display_name: str
    settlement_mode: str
    is_active: bool
    require_delivery: bool = False
    return_policy: str = ""
    return_window_days: int = 0
    target_trades: list[str] = []

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
    #: قیمتِ مصرف‌کننده‌ی پیشنهادی (فروش) — برای نمایشِ حاشیه‌ی سود روی کاتالوگ. ۰ = اعلام‌نشده.
    consumer_price: Decimal = Decimal(0)
    currency_code: str = ""
    description: str = ""
    images: list = []
    category: str = ""
    is_published: bool = False
    #: اصنافی که این قلم **علاوه بر** اصنافِ کلیِ پخش‌کننده به آن‌ها هم نشان داده
    #: می‌شود. خالی = فقط همان اصنافِ کلی.
    extra_trades: list[str] = []
    #: محدودیت‌های سفارش‌گذاری (۰ = بدونِ محدودیت).
    min_order_qty: Decimal = Decimal(0)
    max_order_qty: Decimal = Decimal(0)
    daily_order_limit: int = 0
    #: برای single: کالای متناظر. برای pack تهی (اجزا در components).
    item_id: UUID | None = None
    components: list[ListingComponentIn] = []

    @field_validator("kind")
    @classmethod
    def _kind(cls, v: str) -> str:
        if v not in LISTING_KINDS:
            raise ValueError("نوعِ لیستینگ نامعتبر است")
        return v

    @field_validator("extra_trades")
    @classmethod
    def _extra_trades(cls, v: list[str]) -> list[str]:
        #: مثلِ `target_trades`: کلیدِ ناشناخته رد می‌شود نه اینکه بی‌صدا دور ریخته
        #: شود — وگرنه پخش‌کننده فکر می‌کند قلمش به صنفی می‌رسد که نمی‌رسد.
        unknown = [k for k in v if not is_valid_trade(k)]
        if unknown:
            raise ValueError(f"صنفِ نامعتبر: {'، '.join(unknown)}")
        return clean_trades(v)

    @field_validator("images")
    @classmethod
    def _images(cls, v: list) -> list:
        return _validate_listing_images(v)

    @model_validator(mode="after")
    def _shape(self) -> "ListingIn":
        if not self.title.strip():
            raise ValueError("عنوانِ لیستینگ الزامی است")
        if self.wholesale_price < 0:
            raise ValueError("قیمتِ عمده نمی‌تواند منفی باشد")
        if self.consumer_price < 0:
            raise ValueError("قیمتِ مصرف‌کننده نمی‌تواند منفی باشد")
        if self.min_order_qty < 0 or self.max_order_qty < 0 or self.daily_order_limit < 0:
            raise ValueError("محدودیت‌های سفارش نمی‌توانند منفی باشند")
        if self.min_order_qty > 0 and self.max_order_qty > 0 and self.max_order_qty < self.min_order_qty:
            raise ValueError("حداکثرِ سفارش نباید از حداقلِ سفارش کمتر باشد")
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
    consumer_price: Decimal = Decimal(0)
    currency_code: str
    description: str
    images: list
    category: str
    is_published: bool
    extra_trades: list[str] = []
    min_order_qty: Decimal
    max_order_qty: Decimal
    daily_order_limit: int
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
    #: تعدادِ اقلامِ منتشرشده‌ای که به صنفِ این فروشگاه می‌رسند، و کلِ اقلامِ منتشرشده.
    #: وقتی اولی از دومی کمتر است، کارت می‌گوید چند قلم به درد می‌خورد — تا فروشگاه
    #: پیش از درخواستِ اتصال بداند کاتالوگِ باریکی در انتظارش است.
    matching_listings: int = 0
    total_listings: int = 0


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
    #: زونِ ارسال که پخش‌کننده این فروشگاه را در آن گذاشته (فقط سمتِ پخش‌کننده معنا دارد).
    zone_id: UUID | None = None
    zone_name: str | None = None
    # گفتگو: برای سمتِ بیننده محاسبه می‌شود (فقط اتصالِ approved). پیش‌فرض‌ها برای پاسخ‌هایی
    # که بیننده ندارند (مثلِ تغییرِ وضعیت) امن‌اند.
    unread_count: int = 0
    last_message_at: datetime | None = None
    last_message_preview: str = ""


# ── زونِ ارسال (پخش‌کننده) ─────────────────────────────────────────────
class ZoneIn(BaseModel):
    name: str
    notes: str = ""

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("نامِ زون الزامی است")
        return v


class ZoneOut(BaseModel):
    id: UUID
    name: str
    notes: str
    #: تعدادِ فروشگاه‌های متصلِ این زون (روتر پُر می‌کند).
    connection_count: int = 0

    model_config = {"from_attributes": True}


class ConnectionZoneIn(BaseModel):
    """تخصیصِ زون به یک اتصال — None = برداشتنِ زون."""
    zone_id: UUID | None = None


# ── مرجوعیِ بازار ───────────────────────────────────────────────────────
class ReturnRequestLineIn(BaseModel):
    order_line_id: UUID
    qty: Decimal

    @field_validator("qty")
    @classmethod
    def _qty(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("مقدارِ مرجوعی باید مثبت باشد")
        return v


class ReturnRequestIn(BaseModel):
    order_id: UUID
    lines: list[ReturnRequestLineIn]
    reason: str = ""

    @model_validator(mode="after")
    def _shape(self) -> "ReturnRequestIn":
        if not self.lines:
            raise ValueError("مرجوعی باید حداقل یک ردیف داشته باشد")
        return self


class ReturnRejectIn(BaseModel):
    response_note: str = ""


class ReturnLineOut(BaseModel):
    order_line_id: UUID
    title: str
    unit_price: Decimal
    qty: Decimal
    line_total: Decimal


class ReturnOut(BaseModel):
    id: UUID
    order_id: UUID
    order_number: int
    distributor_tenant_id: UUID
    retailer_tenant_id: UUID
    distributor_name: str
    retailer_name: str
    return_number: int
    status: str  # requested | approved | rejected
    reason: str
    response_note: str
    total: Decimal
    created_at: datetime
    lines: list[ReturnLineOut]


# ── گفتگوی اتصال ──────────────────────────────────────────────────────
class MessageIn(BaseModel):
    body: str

    @field_validator("body")
    @classmethod
    def _nonempty(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("متنِ پیام خالی است")
        return v


class MessageOut(BaseModel):
    id: UUID
    sender_role: str
    sender_user_id: UUID | None = None
    body: str
    created_at: datetime


class MessagesPage(BaseModel):
    my_role: str
    messages: list[MessageOut]


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
    #: قیمتِ مصرف‌کننده‌ی پیشنهادی — فروشگاه با آن حاشیه‌ی سود را روی کاتالوگ می‌بیند. ۰ = اعلام‌نشده.
    consumer_price: Decimal = Decimal(0)
    currency_code: str
    description: str
    images: list
    category: str
    min_order_qty: Decimal
    max_order_qty: Decimal
    daily_order_limit: int
    #: §۳۰ — «موجودی قابل سفارش»، از انبارِ پخش‌کننده منهای رزروِ سفارش‌های دیگر.
    #:
    #: `None` یعنی **نامعلوم** (پخش‌کننده انبارِ فعالی ندارد) و رابط اصلاً نشانش
    #: نمی‌دهد؛ صفر یعنی واقعاً ناموجود و باید دیده شود. یکی‌کردنِ این دو یعنی
    #: کاتالوگ «ناموجود» بگوید در حالی که فقط پیکربندی ناقص است.
    orderable_qty: Decimal | None = None
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
    #: شناسه‌ی ردیفِ سفارش — برای درخواستِ مرجوعیِ پارشال لازم است.
    id: UUID | None = None
    listing_id: UUID | None
    title: str
    unit_price: Decimal
    qty: Decimal
    line_total: Decimal
    #: عکسِ نخستِ لیستینگ (data URI) یا None — از روی listing_id در زمانِ خواندن.
    image: str | None = None


class OrderOut(BaseModel):
    id: UUID
    # گفتگوی سفارش: برای سمتِ بیننده محاسبه می‌شود؛ پیش‌فرض‌ها برای پاسخ‌هایی که بیننده ندارند امن‌اند.
    unread_count: int = 0
    last_message_at: datetime | None = None
    last_message_preview: str = ""
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
    #: سهمِ نقدِ تسویه‌شده هنگام تأیید (ریال)؛ بقیه اعتباری/طلب است.
    cash_amount: Decimal
    #: تحویلِ بار (گردشِ کارِ مامور حمل) — زمان و ثبت‌کننده‌ی تحویل. تا تحویل ثبت نشده خالی‌اند.
    delivered_at: datetime | None = None
    delivered_by_name: str = ""
    #: سیاست/مهلتِ مرجوعیِ پخش‌کننده (برای نمایش به فروشگاه هنگامِ ثبتِ مرجوعی).
    return_policy: str = ""
    return_window_days: int = 0
    distributor_sales_invoice_id: UUID | None
    retailer_purchase_invoice_id: UUID | None
    lines: list[OrderLineOut]


class OrderConfirmIn(BaseModel):
    """بدنه‌ی اختیاریِ تأییدِ سفارش — درصدِ نقد که پخش‌کننده تعیین می‌کند (۰..۱۰۰)."""

    cash_percent: Decimal = Decimal(0)

    @field_validator("cash_percent")
    @classmethod
    def _pct(cls, v: Decimal) -> Decimal:
        if v < 0 or v > 100:
            raise ValueError("درصدِ نقد باید بین ۰ تا ۱۰۰ باشد")
        return v


class OrderDeliverIn(BaseModel):
    """بدنه‌ی اختیاریِ ثبتِ تحویل — سهمِ نقدِ دریافت‌شده هنگامِ تحویل (COD)، ۰..۱۰۰."""

    cash_percent: Decimal = Decimal(0)

    @field_validator("cash_percent")
    @classmethod
    def _pct(cls, v: Decimal) -> Decimal:
        if v < 0 or v > 100:
            raise ValueError("درصدِ نقد باید بین ۰ تا ۱۰۰ باشد")
        return v


# ── کمیسیونِ پلتفرم (۲٪) ───────────────────────────────────────────────
class CommissionPeriodOut(BaseModel):
    distributor_tenant_id: UUID
    distributor_name: str
    period: str  # "1405-05"
    order_count: int
    total_base: int
    total_amount: int
    pending_amount: int
    settled_amount: int
    status: str  # pending | settled


class CommissionOverviewOut(BaseModel):
    total_amount: int
    pending_amount: int
    settled_amount: int
    distributor_count: int
    rate: float


class CommissionSettleIn(BaseModel):
    distributor_tenant_id: UUID
    period: str
    note: str = ""


class CommissionSettleOut(BaseModel):
    distributor_tenant_id: UUID
    period: str
    count: int
    amount: int
