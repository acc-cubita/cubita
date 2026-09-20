from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, field_validator, model_validator

from app.models.company import ADDRESS_TYPES, CHANNEL_TYPES
from app.models.inventory import (
    CREDIT_ACTIONS,
    GENDERS,
    MARITAL_STATUSES,
    TAX_MINISTRY_CLASSES,
)


class WarehouseIn(BaseModel):
    code: str
    name: str
    #: عنوانِ دوم (§۵) — فیلدِ مستقل، نه پیوستِ نام.
    name2: str = ""
    #: مشخصاتِ اجرایی (§۳ §۶ §۷ §۸). `responsible` متن است نه کاربر/پرسنل:
    #: §۶ چنین الزامی را نشان نمی‌دهد و انبارِ برون‌سپاری‌شده ممکن است مسئولی
    #: داشته باشد که اصلاً کاربرِ سیستم نیست.
    responsible: str = ""
    phone: str = ""
    address: str = ""
    address2: str = ""
    #: معینِ انبار — **اختیاری** (§۱۳). خالی یعنی حسابِ پیش‌فرضِ موجودیِ کالا،
    #: که همان رفتارِ امروزِ همه‌ی انبارهاست.
    gl_account_id: UUID | None = None


class WarehouseUpdateIn(BaseModel):
    """ویرایشِ انبار — فقط فیلدهای ارسال‌شده تغییر می‌کنند. کد پس از ساخت ثابت است
    (روی حرکاتِ انبار و اسناد نشسته)، پس اینجا نمی‌آید."""

    name: str | None = None
    name2: str | None = None
    responsible: str | None = None
    phone: str | None = None
    address: str | None = None
    address2: str | None = None
    gl_account_id: UUID | None = None
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not v.strip():
            raise ValueError("نام انبار نمی‌تواند خالی باشد")
        return v.strip()


class WarehouseOut(BaseModel):
    id: UUID
    code: str
    name: str
    name2: str = ""
    responsible: str = ""
    phone: str = ""
    address: str = ""
    address2: str = ""
    is_active: bool
    gl_account_id: UUID | None = None
    #: کد و عنوانِ حسابِ معین برای فهرست (§۲۹). وقتی نگاشت خالی است، حسابِ
    #: پیش‌فرض نشان داده می‌شود و `is_default` می‌گوید انتخابِ کاربر نبوده —
    #: نشان‌ندادنش یعنی کاربر فکر کند این انبار به هیچ حسابی نمی‌نشیند.
    gl_account_code: str = ""
    gl_account_name: str = ""
    gl_account_is_default: bool = True

    model_config = {"from_attributes": True}


class WarehouseStockPositionOut(BaseModel):
    """اثرِ غیرفعال‌سازی (§۱۷) — چند قلم کالا با موجودیِ غیرصفر."""

    item_count: int
    items: list[dict] = []


class StockReservationIn(BaseModel):
    """ادعای دستی روی موجودی — نگه‌داشت یا انسدادِ جزئی.

    رزروِ سفارش را سرور خودش می‌سازد؛ این مسیر برای کارهایی است که سندی ندارند:
    «این ۲۰ تا را برای مشتریِ فلان کنار بگذار» یا «این ۵۰ تا قرنطینه است».
    """

    item_id: UUID
    warehouse_id: UUID
    qty: Decimal
    entry_date: date
    #: تهی = «ادعا هست، بارش هنوز انتخاب نشده» (§۷).
    batch_id: UUID | None = None
    kind: str = "hold"
    notes: str = ""

    @field_validator("kind")
    @classmethod
    def _valid_kind(cls, v: str) -> str:
        #: «سفارش» از این مسیر ساخته نمی‌شود — آن را جریانِ سفارش می‌سازد و
        #: دست‌سازش یعنی ادعایی که هیچ سندی پشتش نیست.
        if v not in ("hold", "blocked"):
            raise ValueError("نوعِ ادعا باید «نگه‌داشت» یا «انسداد» باشد")
        return v

    @model_validator(mode="after")
    def _positive(self) -> "StockReservationIn":
        if self.qty <= 0:
            raise ValueError("مقدارِ رزرو باید بزرگ‌تر از صفر باشد")
        return self


class StockReservationOut(BaseModel):
    """ادعای بازِ یک سند — جمعِ ردیف‌های دفتر، نه یک ردیفِ خام."""

    source_type: str
    source_id: UUID | None = None
    kind: str
    qty: Decimal
    since: date


class AssignStockToBatchIn(BaseModel):
    """انتسابِ موجودیِ موجودِ یک کالا به یک بارِ اول‌دوره — راهِ عبورِ گاردِ ردیابی."""

    warehouse_id: UUID
    batch_number: str
    assigned_date: date
    expiry_date: date | None = None
    production_date: date | None = None

    @field_validator("batch_number")
    @classmethod
    def _number_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("شماره‌ی بار نمی‌تواند خالی باشد")
        return v.strip()


class WarehouseLocationIn(BaseModel):
    """موقعیتِ قرارگیری داخلِ انبار — فقط `code` اجباری است (§۲۸)."""

    warehouse_id: UUID
    code: str
    name: str = ""
    aisle: str = ""
    rack: str = ""
    level: str = ""
    notes: str = ""

    @field_validator("code")
    @classmethod
    def _code_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("کدِ موقعیت نمی‌تواند خالی باشد")
        return v.strip()


class WarehouseLocationUpdateIn(BaseModel):
    """ویرایش — کد پس از ساخت ثابت است چون روی بارها نشسته."""

    name: str | None = None
    aisle: str | None = None
    rack: str | None = None
    level: str | None = None
    notes: str | None = None
    is_active: bool | None = None


class WarehouseLocationOut(BaseModel):
    id: UUID
    warehouse_id: UUID
    code: str
    name: str = ""
    aisle: str = ""
    rack: str = ""
    level: str = ""
    is_active: bool = True
    notes: str = ""
    #: تعدادِ بارهایی که روی این موقعیت نشسته‌اند — رابط پیش از غیرفعال‌کردن
    #: می‌پرسد تا بتواند **قبل** از خطا بگوید چه چیزی سرِ راه است.
    batch_count: int = 0

    model_config = {"from_attributes": True}


ENTITY_TYPES = ("real", "legal")


class ContactIn(BaseModel):
    name: str
    #: **نگه داشته شد تا فراخوان‌های موجود نشکنند.** از مهاجرتِ ۰۱۶۴ منبعِ حقیقت
    #: دو پرچمِ زیر است و `type` از آن‌ها مشتق می‌شود؛ ولی ورودِ گروهی، موبایل و
    #: چند فرمِ قدیمی هنوز همین را می‌فرستند. اگر پرچم‌ها بیایند، **آن‌ها برنده‌اند**
    #: — تصمیمش در روتر است، نه این‌جا، چون PATCH باید بداند کاربر چه فرستاده.
    type: str = "customer"
    #: `None` یعنی «نفرستادم»، نه «نه». تنها راهِ بیانِ «این طرف‌حساب نه مشتری
    #: است نه تأمین‌کننده» — چیزی که `type` هرگز نمی‌توانست بگوید.
    is_customer: bool | None = None
    is_supplier: bool | None = None
    #: **تا امروز این فیلد این‌جا نبود، پس ستونش مرده بود.** `Contact.is_active`
    #: در ساخت `True` می‌شد و هیچ مسیری عوضش نمی‌کرد — نه API، نه رابط. در حالی
    #: که `ContactOut` نمایشش می‌داد، یعنی کاربر یک وضعیت می‌دید که نمی‌توانست
    #: تغییرش دهد.
    #:
    #: بدونِ این، پیامِ «به‌جای حذف غیرفعالش کنید» در `delete_contact` به مسیری
    #: اشاره می‌کرد که وجود نداشت.
    is_active: bool = True
    phone: str | None = None
    email: str | None = None
    address: str = ""
    tax_id: str | None = None
    birthday: date | None = None
    credit_limit: Decimal = Decimal(0)
    default_price_list_id: UUID | None = None
    entity_type: str = "real"
    national_id: str | None = None
    economic_code: str | None = None
    postal_code: str | None = None
    #: دسته‌بندیِ سطحِ شرکت — هر دو اختیاری، NULL = دسته‌بندی‌نشده.
    group_id: UUID | None = None
    geo_location_id: UUID | None = None

    # ── هویتِ تفکیک‌شده ────────────────────────────────────────────────────────
    #: نام و نام خانوادگی. اگر پر باشند `name` از آن‌ها ساخته می‌شود؛ اگر نه،
    #: `name` همان است که فرستاده شده (شرکت، که نامِ یک‌تکه دارد).
    first_name: str = ""
    last_name: str = ""
    first_name2: str = ""
    last_name2: str = ""
    sub_type: str = ""
    website: str = ""
    registration_no: str | None = None
    passport_no: str | None = None
    marriage_date: date | None = None
    is_blacklisted: bool = False
    discount_rate: Decimal = Decimal(0)
    tax_ministry_class: str = "normal"
    credit_action: str = "none"
    is_broker: bool = False
    commission_rate: Decimal = Decimal(0)
    #: کارمندِ متناظر در ماژولِ حقوق و دستمزد — پیوند، نه کپی.
    employee_id: UUID | None = None

    # ── تفصیلی ────────────────────────────────────────────────────────────────
    #: کد و عنوانِ تفصیلی. **ستونِ طرف‌حساب نیستند**: سرویس از آن‌ها یک
    #: `analytic_account` می‌سازد یا موجود را به‌روز می‌کند و فقط `analytic_id` را
    #: روی طرف‌حساب می‌نشاند. اجباری بودنشان به سطحِ اجبارِ تفصیلی بستگی دارد.
    tafsili_code: str | None = None
    tafsili_title: str | None = None
    tafsili_title2: str = ""

    # ── مانده‌ی اول دوره ──
    #: مبلغ همیشه نامنفی است؛ سمت جدا می‌آید چون مانده‌ی خلافِ انتظار واقعاً پیش
    #: می‌آید (پیش‌دریافت از مشتری، پیش‌پرداخت به تأمین‌کننده).
    opening_ar_amount: Decimal = Decimal(0)
    opening_ar_side: str = "debit"
    opening_ap_amount: Decimal = Decimal(0)
    opening_ap_side: str = "credit"

    # ── مشخصاتِ شخصی و نقشِ سهامدار ──
    gender: str = ""
    marital_status: str = ""
    marital_status_date: date | None = None
    children_count: int = 0
    dependents_count: int = 0
    education_level: str = ""
    education_field: str = ""
    is_employee: bool = False
    is_shareholder: bool = False
    share_percent: Decimal = Decimal(0)

    @field_validator("gender")
    @classmethod
    def _valid_gender(cls, v: str) -> str:
        if v not in GENDERS:
            raise ValueError("جنسیت نامعتبر است")
        return v

    @field_validator("marital_status")
    @classmethod
    def _valid_marital(cls, v: str) -> str:
        if v not in MARITAL_STATUSES:
            raise ValueError("وضعیتِ تأهل نامعتبر است")
        return v

    @model_validator(mode="after")
    def _person_counts(self) -> "ContactIn":
        if self.children_count < 0 or self.dependents_count < 0:
            raise ValueError("تعداد نمی‌تواند منفی باشد")
        if not (0 <= self.share_percent <= 100):
            raise ValueError("درصدِ سهام باید بینِ ۰ و ۱۰۰ باشد")
        return self

    @field_validator("opening_ar_side", "opening_ap_side")
    @classmethod
    def _valid_side(cls, v: str) -> str:
        if v not in ("debit", "credit"):
            raise ValueError("سمتِ مانده باید بدهکار یا بستانکار باشد")
        return v

    @model_validator(mode="after")
    def _opening_not_negative(self) -> "ContactIn":
        if self.opening_ar_amount < 0 or self.opening_ap_amount < 0:
            raise ValueError("مانده‌ی اول دوره نمی‌تواند منفی باشد؛ سمت را عوض کنید")
        return self

    @field_validator("credit_action")
    @classmethod
    def _valid_credit_action(cls, v: str) -> str:
        if v not in CREDIT_ACTIONS:
            raise ValueError("نحوه‌ی کنترلِ اعتبار نامعتبر است")
        return v

    @field_validator("tax_ministry_class")
    @classmethod
    def _valid_tax_class(cls, v: str) -> str:
        if v not in TAX_MINISTRY_CLASSES:
            raise ValueError("دسته‌بندیِ وزارت دارایی نامعتبر است")
        return v

    @model_validator(mode="after")
    def _compose_name(self) -> "ContactIn":
        #: نامِ نمایشی از نام و نام خانوادگی ساخته می‌شود تا فاکتور و گزارشِ فصلی
        #: — که همه `name` را می‌خوانند — با فرمِ تفکیک‌شده هم بخوانند.
        joined = " ".join(p for p in (self.first_name.strip(), self.last_name.strip()) if p)
        if joined:
            self.name = joined
        return self

    @model_validator(mode="after")
    def _check_rates(self) -> "ContactIn":
        for label, value in (("نرخ تخفیف", self.discount_rate), ("نرخ پورسانت", self.commission_rate)):
            if value < 0 or value > 100:
                raise ValueError(f"{label} باید بینِ ۰ و ۱۰۰ باشد")
        return self

    @field_validator("entity_type")
    @classmethod
    def _valid_entity_type(cls, v: str) -> str:
        if v not in ENTITY_TYPES:
            raise ValueError("نوعِ شخص باید حقیقی یا حقوقی باشد")
        return v

    @field_validator("national_id", "economic_code", "postal_code")
    @classmethod
    def _blank_to_null(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None

    @model_validator(mode="after")
    def _check_credit_limit(self) -> "ContactIn":
        if self.credit_limit < 0:
            raise ValueError("سقف اعتبار نمی‌تواند منفی باشد")
        return self


class ContactPatch(ContactIn):
    """ویرایشِ جزئیِ طرف حساب — همان فیلدها، ولی `name` هم اجباری نیست.

    **چرا جدا شد.** `ContactIn` ورودیِ *ساخت* است و آن‌جا نام واقعاً اجباری است.
    ولی مسیرِ `PATCH` معنایش «همین‌ها را عوض کن» است و با `exclude_unset` دقیقاً
    همین را پیاده کرده — پس اجباری‌بودنِ `name` قولِ خودِ مسیر را نقض می‌کرد:
    برای عوض‌کردنِ یک شماره‌تلفن باید نام هم دوباره فرستاده می‌شد، وگرنه ۴۲۲.

    **نفرستادن با `null`ِ صریح فرق دارد.** `_compose_name` که از `ContactIn` به
    ارث می‌رسد، اگر نام و نام‌خانوادگی بیایند `name` را می‌سازد و همان هم
    «set‌شده» حساب می‌شود — پس ویرایشِ تفکیک‌شده هنوز نام را به‌روز می‌کند. ولی
    `{"name": null}` هم «set‌شده» است و بدونِ گاردِ زیر تا قیدِ NOT NULL می‌رفت و
    کاربر به‌جای پیامِ روشن یک ۵۰۰ می‌دید.
    """

    name: str | None = None

    @model_validator(mode="after")
    def _name_not_blanked(self) -> "ContactPatch":
        if "name" in self.model_fields_set and not (self.name or "").strip():
            raise ValueError("نامِ طرف حساب نمی‌تواند خالی باشد")
        return self


class ContactOut(BaseModel):
    id: UUID
    name: str
    #: مشتق از دو پرچمِ بعدی. در پاسخ می‌ماند چون موبایل و ده‌ها جای رابط رویش
    #: تکیه دارند؛ مقدارِ چهارمش (`none`) از مهاجرتِ ۰۱۶۴ ممکن شد.
    type: str
    is_customer: bool
    is_supplier: bool
    phone: str | None
    email: str | None
    address: str
    tax_id: str | None
    birthday: date | None
    is_active: bool
    credit_limit: Decimal
    default_price_list_id: UUID | None
    entity_type: str
    national_id: str | None
    economic_code: str | None
    postal_code: str | None
    group_id: UUID | None
    geo_location_id: UUID | None
    first_name: str
    last_name: str
    first_name2: str
    last_name2: str
    sub_type: str
    website: str
    registration_no: str | None
    passport_no: str | None
    marriage_date: date | None
    is_blacklisted: bool
    discount_rate: Decimal
    tax_ministry_class: str
    credit_action: str
    is_broker: bool
    commission_rate: Decimal
    employee_id: UUID | None
    #: تفصیلیِ متصل — سه‌تای پایین از خودِ `analytic_account` خوانده می‌شوند نه از
    #: ستونی روی طرف‌حساب، پس همیشه با فهرستِ تفصیلی‌ها یکی‌اند.
    analytic_id: UUID | None = None
    tafsili_code: str | None = None
    tafsili_title: str | None = None
    tafsili_title2: str = ""
    opening_ar_amount: Decimal
    opening_ar_side: str
    opening_ap_amount: Decimal
    opening_ap_side: str
    gender: str
    marital_status: str
    marital_status_date: date | None
    children_count: int
    dependents_count: int
    education_level: str
    education_field: str
    is_employee: bool
    is_shareholder: bool
    share_percent: Decimal

    model_config = {"from_attributes": True}


class ContactChannelIn(BaseModel):
    #: تلفنِ *اضافه*. نشانی از ۰۰۹۲ جدولِ خودش را دارد (`ContactAddressIn`).
    kind: str = "phone"
    #: نوعِ کنترل‌شده (دفتر، انبار، همراه…)؛ `label` متنِ آزادِ کاربر است.
    channel_type: str = "other"
    label: str = ""
    value: str
    #: «اصلی» — سرویس تضمین می‌کند در هر طرف‌حساب حداکثر یکی باشد.
    is_primary: bool = False
    notes: str = ""
    is_active: bool = True

    @field_validator("channel_type")
    @classmethod
    def _valid_channel_type(cls, v: str) -> str:
        if v not in CHANNEL_TYPES:
            raise ValueError("نوعِ تلفن نامعتبر است")
        return v

    @field_validator("kind")
    @classmethod
    def _valid_kind(cls, v: str) -> str:
        if v not in ("phone", "address", "email"):
            raise ValueError("نوعِ کانال نامعتبر است")
        return v

    @field_validator("value")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("مقدار نمی‌تواند خالی باشد")
        return v.strip()


class ContactChannelOut(BaseModel):
    id: UUID
    contact_id: UUID
    kind: str
    channel_type: str
    label: str
    value: str
    is_primary: bool
    notes: str
    is_active: bool

    model_config = {"from_attributes": True}


class ContactAddressIn(BaseModel):
    """یکی از نشانی‌های طرف‌حساب. هیچ فیلدی اجباری نیست جز نوع — نشانیِ نیمه‌کاره
    (مثلاً فقط مختصات، یا فقط کدِ مسیر) هم به کارِ مأمورِ ارسال می‌آید."""

    address_type: str = "official"
    is_primary: bool = False
    geo_location_id: UUID | None = None
    title: str = ""
    address: str = ""
    address2: str = ""
    postal_code: str = ""
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    #: «زون»ِ توزیع. وقتی موجودیتِ زون ساخته شد، این کلیدِ خارجی می‌شود.
    route_code: str = ""
    route_title: str = ""
    route_title2: str = ""
    region_code: str = ""
    region_title: str = ""
    region_title2: str = ""
    branch_code: str = ""
    notes: str = ""
    is_active: bool = True

    @field_validator("address_type")
    @classmethod
    def _valid_address_type(cls, v: str) -> str:
        if v not in ADDRESS_TYPES:
            raise ValueError("نوعِ نشانی نامعتبر است")
        return v

    @model_validator(mode="after")
    def _coords_come_in_pairs(self) -> "ContactAddressIn":
        #: نیم‌مختصات روی نقشه هیچ نقطه‌ای نیست؛ رد کردنش بهتر از ذخیره‌ی داده‌ای است
        #: که مأمورِ ارسال نمی‌تواند استفاده کند.
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("عرض و طولِ جغرافیایی باید با هم وارد شوند")
        return self


class ContactAddressOut(ContactAddressIn):
    id: UUID
    contact_id: UUID

    model_config = {"from_attributes": True}


class CreditStatusOut(BaseModel):
    contact_id: UUID
    name: str
    credit_limit: Decimal
    outstanding: Decimal
    available: Decimal
    over_limit: bool


class UnitIn(BaseModel):
    """واحدِ سنجش — داده‌ی پایه (§۱۹)."""

    name: str
    name2: str = ""

    @field_validator("name")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("نامِ واحد نمی‌تواند خالی باشد")
        return v.strip()


class UnitUpdateIn(BaseModel):
    name: str | None = None
    name2: str | None = None
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def _not_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("نامِ واحد نمی‌تواند خالی باشد")
        return v.strip() if v is not None else v


class UnitOut(BaseModel):
    id: UUID
    name: str
    name2: str = ""
    is_active: bool
    #: چند قلم کالا رویش نشسته — تا فهرست پیش از غیرفعال‌سازی خبر بدهد.
    item_count: int = 0

    model_config = {"from_attributes": True}


class ItemGroupIn(BaseModel):
    """گروه‌بندیِ کالا/خدمت (§۳۴)."""

    code: str = ""
    name: str
    name2: str = ""
    notes: str = ""

    @field_validator("name")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("نامِ گروه نمی‌تواند خالی باشد")
        return v.strip()


class ItemGroupUpdateIn(BaseModel):
    code: str | None = None
    name: str | None = None
    name2: str | None = None
    notes: str | None = None
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def _not_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("نامِ گروه نمی‌تواند خالی باشد")
        return v.strip() if v is not None else v


class ItemGroupOut(BaseModel):
    id: UUID
    code: str = ""
    name: str
    name2: str = ""
    notes: str = ""
    is_active: bool
    item_count: int = 0

    model_config = {"from_attributes": True}


class ItemAttributeIn(BaseModel):
    """تعریفِ یک مشخصه (§۳۵ §۳۶) — «رنگ»، «سایز»، «کشور سازنده».

    **نوعِ داده عمداً نیست.** فصل نوع را تثبیت نمی‌کند و می‌گوید با فصلِ
    اختصاصیِ مشخصات هماهنگ شود؛ اختراعِ نوع‌بندی این‌جا یعنی چیزی که بعداً باید
    بازنویسی شود.
    """

    name: str
    name2: str = ""

    @field_validator("name")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("نامِ مشخصه نمی‌تواند خالی باشد")
        return v.strip()


class ItemAttributeUpdateIn(BaseModel):
    name: str | None = None
    name2: str | None = None
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def _not_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("نامِ مشخصه نمی‌تواند خالی باشد")
        return v.strip() if v is not None else v


class ItemAttributeOut(BaseModel):
    id: UUID
    name: str
    name2: str = ""
    is_active: bool

    model_config = {"from_attributes": True}


class ItemAttributeValueIn(BaseModel):
    attribute_id: UUID
    value: str = ""


class ItemAttributeValueOut(BaseModel):
    attribute_id: UUID
    attribute_name: str
    value: str


class ItemWarehouseIn(BaseModel):
    """یک انبارِ مرتبط (§۲۹ §۳۱). `is_default` فقط پیشنهادِ فرم است، نه مالکیت."""

    warehouse_id: UUID
    is_default: bool = False
    #: override‌های انبارمحورِ کنترلِ موجودی (§۲۸). `None` = «همان عددِ کالا».
    min_stock: Decimal | None = None
    max_stock: Decimal | None = None


class ItemWarehouseOut(BaseModel):
    warehouse_id: UUID
    warehouse_code: str
    warehouse_name: str
    is_default: bool
    min_stock: Decimal | None = None
    max_stock: Decimal | None = None


class ItemIn(BaseModel):
    sku: str
    name: str
    #: عنوانِ دوم (§۵) — فیلدِ مستقل، نه پیوستِ نام.
    name2: str = ""
    category: str = ""
    unit: str = "عدد"
    is_service: bool = False
    sales_price: Decimal = Decimal(0)
    barcode: str | None = None
    #: سه شناسه‌ی جدا (§۴ §۱۱ §۱۲): `sku` کدِ داخلی، `barcode` خطی، `iran_code`
    #: و `barcode2` هرکدام مفهومِ خودشان. یکی‌شان نمی‌کنیم.
    iran_code: str = ""
    barcode2: str = ""
    #: §۷ — «فعال» و «قابل فروش» دو چیزند. موادِ اولیه فعال‌اند و فروختنی نیستند.
    is_sellable: bool = True
    #: §۸ — کالا سریال‌محور است یا نه.
    is_serial_tracked: bool = False
    #: ردیابیِ بارِ ورودی. پیش‌فرض خاموش = رفتارِ دیروز برای هر کالای موجود.
    is_batch_tracked: bool = False
    #: حداقلِ عمرِ مفیدِ لازم برای فروش (روز). تهی = بدونِ قاعده.
    minimum_sellable_shelf_life_days: int | None = None
    #: §۱۳ — نرخِ کالا. صفر = «نرخِ سرِ فاکتور»، نه معافیت (معافیت پرچمِ جداست).
    tax_rate: Decimal = Decimal(0)
    duty_rate: Decimal = Decimal(0)
    #: §۱۳ — وضعیتِ مالیاتیِ سمتِ خرید، مستقل از فروش.
    purchase_vat_status: str = "taxable"
    #: §۱۵ — معینِ هزینه‌ی خریدِ خدمت. خالی = حسابِ پیش‌فرضِ «هزینه خرید خدمات».
    expense_account_id: UUID | None = None
    #: §۱۷ §۱۸ — واحدِ اصلی از داده‌ی پایه. اگر فرستاده نشود، از نوشتارِ `unit`
    #: ساخته/پیدا می‌شود؛ این‌طور مسیرهای قدیمی (ورودِ گروهی، بازار، بازیابیِ
    #: پشتیبان) نمی‌شکنند و متنِ آزاد هم دیگر سرگردان نمی‌ماند.
    primary_unit_id: UUID | None = None
    #: §۲۰ §۲۱ §۲۲ — واحدِ فرعی و نسبتش.
    secondary_unit_id: UUID | None = None
    conversion_factor: Decimal = Decimal(0)
    conversion_mode: str = "fixed"
    #: §۲۳ — متادیتای حمل‌ونقل، نه موجودی.
    unit_weight: Decimal = Decimal(0)
    unit_volume: Decimal = Decimal(0)
    #: §۲۴ §۲۵ §۲۶ — قاعده‌ی برنامه‌ریزی، نه سدِ تراکنش.
    min_stock: Decimal = Decimal(0)
    max_stock: Decimal = Decimal(0)
    #: §۲۹ §۳۰ — فهرستِ خالی یعنی «همه‌ی انبارها»، نه «هیچ انباری».
    warehouses: list[ItemWarehouseIn] = []
    #: §۳۴ — گروه‌بندی. اگر فرستاده نشود، از نوشتارِ `category` ساخته/پیدا می‌شود.
    group_id: UUID | None = None
    #: §۳۵ — مقدارِ مشخصه‌ها. مقدارِ خالی یعنی «این مشخصه را ندارد».
    attributes: list[ItemAttributeValueIn] = []

    @field_validator("conversion_mode")
    @classmethod
    def _known_mode(cls, v: str) -> str:
        from app.models.inventory import CONVERSION_MODES

        if v not in CONVERSION_MODES:
            raise ValueError("نحوه‌ی تبدیلِ واحد نامعتبر است")
        return v

    @field_validator("conversion_factor", "unit_weight", "unit_volume")
    @classmethod
    def _non_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("این مقدار نمی‌تواند منفی باشد")
        return v
    #: نقطه‌ی سفارشِ مجدد (حداقلِ موجودی). ۰ = بدونِ هشدار.
    reorder_point: Decimal = Decimal(0)
    #: شناسه‌ی کالا/خدمتِ مالیاتی (sstid، ۱۳رقمیِ مؤدیان). خالی = پیش‌فرضِ کسب‌وکار.
    tax_stuff_id: str = ""
    #: `taxable` (مشمول) یا `exempt` (معاف). پیش‌فرض مشمول = رفتارِ امروز.
    vat_status: str = "taxable"

    @field_validator("barcode")
    @classmethod
    def _blank_barcode_is_null(cls, v: str | None) -> str | None:
        # بارکدِ خالی = بدونِ بارکد (NULL)، تا با یکتاییِ منطقی جور باشد
        if v is None:
            return None
        v = v.strip()
        return v or None

    @field_validator("reorder_point")
    @classmethod
    def _non_negative_reorder(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("نقطه‌ی سفارش نمی‌تواند منفی باشد")
        return v

    @field_validator("vat_status", "purchase_vat_status")
    @classmethod
    def _known_vat_status(cls, v: str) -> str:
        from app.models.inventory import VAT_STATUSES

        if v not in VAT_STATUSES:
            raise ValueError("وضعیت مالیاتی باید «مشمول» یا «معاف» باشد")
        return v

    @field_validator("tax_rate", "duty_rate")
    @classmethod
    def _sane_rate(cls, v: Decimal) -> Decimal:
        if not (0 <= v <= 100):
            raise ValueError("نرخ باید بینِ ۰ و ۱۰۰ باشد")
        return v


class ItemOut(BaseModel):
    id: UUID
    sku: str
    name: str
    name2: str = ""
    category: str
    unit: str
    is_service: bool
    sales_price: Decimal
    average_cost: Decimal
    is_active: bool
    barcode: str | None
    storefront_product_id: int | None
    reorder_point: Decimal
    tax_stuff_id: str
    vat_status: str
    iran_code: str = ""
    barcode2: str = ""
    is_sellable: bool = True
    is_serial_tracked: bool = False
    is_batch_tracked: bool = False
    minimum_sellable_shelf_life_days: int | None = None
    tax_rate: Decimal = Decimal(0)
    duty_rate: Decimal = Decimal(0)
    purchase_vat_status: str = "taxable"
    expense_account_id: UUID | None = None
    #: کد و عنوانِ معینِ هزینه — برای خدمتِ بی‌نگاشت، حسابِ پیش‌فرض نشان داده
    #: می‌شود و `is_default` می‌گوید انتخابِ کاربر نبوده. برای کالا خالی است،
    #: چون بهای خرید به موجودیِ انبار می‌نشیند نه به حسابِ هزینه.
    expense_account_code: str = ""
    expense_account_name: str = ""
    expense_account_is_default: bool = True
    primary_unit_id: UUID | None = None
    primary_unit_name: str = ""
    secondary_unit_id: UUID | None = None
    secondary_unit_name: str = ""
    conversion_factor: Decimal = Decimal(0)
    conversion_mode: str = "fixed"
    unit_weight: Decimal = Decimal(0)
    unit_volume: Decimal = Decimal(0)
    min_stock: Decimal = Decimal(0)
    max_stock: Decimal = Decimal(0)
    warehouses: list[ItemWarehouseOut] = []
    #: انبارِ پیش‌فرض — پیشنهادِ فرمِ فروش/خرید، نه قفل (§۳۲).
    default_warehouse_id: UUID | None = None
    group_id: UUID | None = None
    group_name: str = ""
    attributes: list[ItemAttributeValueOut] = []

    model_config = {"from_attributes": True}


class ItemUpdateIn(BaseModel):
    """آپدیت جزئی کالا؛ فقط فیلدهای ارسال‌شده تغییر می‌کنند (بقیه دست‌نخورده می‌مانند).

    `average_cost` را می‌توان دستی ویرایش کرد (بهای تمام‌شده‌ی جاری برای محاسبه‌ی سود/بهای
    فروش‌رفته). توجه: این فقط مبنای بهای رو به جلو را عوض می‌کند و ارزشِ ثبت‌شده‌ی موجودی در
    دفترِ کل را بازارزیابی نمی‌کند؛ برای افتتاحیه، سندِ جداگانه‌ی موجودی/سرمایه زده می‌شود.
    """

    name: str | None = None
    #: §۴ — کد یک شناسه‌ی کسب‌وکاری است و کاربر می‌تواند اصلاحش کند؛ روابطِ
    #: داخلی روی `id` بسته‌اند و ردیفِ فاکتور کدِ روزِ خودش را snapshot دارد.
    sku: str | None = None
    name2: str | None = None
    category: str | None = None
    unit: str | None = None
    iran_code: str | None = None
    barcode2: str | None = None
    is_sellable: bool | None = None
    is_serial_tracked: bool | None = None
    is_batch_tracked: bool | None = None
    minimum_sellable_shelf_life_days: int | None = None
    tax_rate: Decimal | None = None
    duty_rate: Decimal | None = None
    purchase_vat_status: str | None = None
    expense_account_id: UUID | None = None
    primary_unit_id: UUID | None = None
    secondary_unit_id: UUID | None = None
    conversion_factor: Decimal | None = None
    conversion_mode: str | None = None
    unit_weight: Decimal | None = None
    unit_volume: Decimal | None = None
    min_stock: Decimal | None = None
    max_stock: Decimal | None = None
    #: `None` = دست‌نزن؛ فهرستِ خالی = همه‌ی انبارها.
    warehouses: list[ItemWarehouseIn] | None = None
    group_id: UUID | None = None
    attributes: list[ItemAttributeValueIn] | None = None
    sales_price: Decimal | None = None
    average_cost: Decimal | None = None
    is_active: bool | None = None
    barcode: str | None = None
    storefront_product_id: int | None = None
    reorder_point: Decimal | None = None
    tax_stuff_id: str | None = None
    #: تغییرِ وضعیت فقط روی فروش‌های **بعدی** اثر دارد؛ ردیف‌های ثبت‌شده وضعیتِ
    #: لحظه‌ی معامله‌ی خودشان را نگه می‌دارند.
    vat_status: str | None = None

    @field_validator("vat_status", "purchase_vat_status")
    @classmethod
    def _known_vat_status(cls, v: str | None) -> str | None:
        from app.models.inventory import VAT_STATUSES

        if v is not None and v not in VAT_STATUSES:
            raise ValueError("وضعیت مالیاتی باید «مشمول» یا «معاف» باشد")
        return v

    @field_validator("tax_rate", "duty_rate")
    @classmethod
    def _sane_rate(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and not (0 <= v <= 100):
            raise ValueError("نرخ باید بینِ ۰ و ۱۰۰ باشد")
        return v

    @field_validator("conversion_mode")
    @classmethod
    def _known_mode(cls, v: str | None) -> str | None:
        from app.models.inventory import CONVERSION_MODES

        if v is not None and v not in CONVERSION_MODES:
            raise ValueError("نحوه‌ی تبدیلِ واحد نامعتبر است")
        return v

    @field_validator("sku", "name", "unit")
    @classmethod
    def _not_blank(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not v.strip():
            raise ValueError("این فیلد نمی‌تواند خالی باشد")
        return v.strip()

    @field_validator("barcode")
    @classmethod
    def _blank_barcode_is_null(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None

    @model_validator(mode="after")
    def _non_negative(self) -> "ItemUpdateIn":
        if self.average_cost is not None and self.average_cost < 0:
            raise ValueError("بهای تمام‌شده نمی‌تواند منفی باشد")
        if self.reorder_point is not None and self.reorder_point < 0:
            raise ValueError("نقطه‌ی سفارش نمی‌تواند منفی باشد")
        return self


class StockLevelOut(BaseModel):
    item_id: UUID
    item_sku: str
    item_name: str
    warehouse_id: UUID
    warehouse_name: str
    qty: Decimal
    #: بهای میانگین موزونِ هر واحد و ارزشِ ریالیِ همین ردیف (qty × unit_cost).
    unit_cost: Decimal = Decimal(0)
    stock_value: Decimal = Decimal(0)


class LowStockRowOut(BaseModel):
    """کالایی که موجودیِ کلش به/زیرِ نقطه‌ی سفارش یا حداقلِ موجودی رسیده."""

    item_id: UUID
    sku: str
    name: str
    unit: str
    qty_on_hand: Decimal
    reorder_point: Decimal
    shortfall: Decimal  # کمبود تا آستانه = max(threshold − qty, 0)
    #: کدام آستانه این ردیف را آورده: `reorder` یا `min`. §۲۵ این دو را جدا
    #: می‌داند و یکی‌کردنشان یعنی کاربر نفهمد چرا هشدار گرفته.
    trigger: str = "reorder"
    min_stock: Decimal = Decimal(0)


class OverStockRowOut(BaseModel):
    """§۲۶ — موجودی از حداکثر گذشته.

    **سدِ تراکنش نیست، سیگنالِ برنامه‌ریزی است:** حداکثرِ موجودی جلوی ورودِ کالا
    را نمی‌گیرد؛ فقط می‌گوید مازاد داریم.
    """

    item_id: UUID
    sku: str
    name: str
    unit: str
    qty_on_hand: Decimal
    max_stock: Decimal
    excess: Decimal


class StockAdjustmentIn(BaseModel):
    item_id: UUID
    warehouse_id: UUID
    qty_diff: Decimal
    reason: str = ""
    adjustment_date: date
    #: کدام **بارِ ورودی** کم/زیاد شد. تهی = تعدیلِ کلیِ کالا (رفتارِ پیش‌فرض).
    #: وقتی پر باشد، حرکتِ دفتر هم همان برچسب را می‌گیرد — وگرنه تعدیل از موجودیِ
    #: کالا کم می‌کرد ولی از مانده‌ی بار نه، و آن دو از هم جدا می‌افتادند.
    batch_id: UUID | None = None

    @model_validator(mode="after")
    def validate_nonzero(self) -> "StockAdjustmentIn":
        if self.qty_diff == 0:
            raise ValueError("مقدار تعدیل نمی‌تواند صفر باشد")
        return self


class StockAdjustmentOut(BaseModel):
    id: UUID
    item_id: UUID
    warehouse_id: UUID
    qty_diff: Decimal
    unit_cost: Decimal
    reason: str
    adjustment_date: date
    journal_entry_id: UUID | None
    #: بدونِ این دو، فهرست یک تعدیلِ باطل را دقیقاً مثلِ تعدیلِ معتبر نشان می‌داد.
    voided_at: datetime | None = None
    void_reason: str = ""

    model_config = {"from_attributes": True}
