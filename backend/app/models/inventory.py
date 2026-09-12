import uuid
from datetime import date as date_

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Index,
    Numeric,
    Sequence,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin

CONTACT_TYPES = ("customer", "supplier", "both")

#: وضعیتِ مالیات بر ارزش افزوده. «معاف» عمداً از «نرخِ صفر» جداست — نرخِ صفر
#: نمی‌گوید کالا معاف بوده یا فقط آن فاکتور بی‌مالیات صادر شده.
VAT_STATUSES = ("taxable", "exempt")

#: با عبور از سقفِ اعتبار چه شود. `none` پیش‌فرض است تا سقف‌هایی که از قبل ثبت
#: شده‌اند یک‌شبه جلوی فروش را نگیرند.
CREDIT_ACTIONS = ("none", "warn", "block")
CREDIT_ACTION_LABELS = {
    "none": "بدون کنترل",
    "warn": "هشدار بده",
    "block": "جلوگیری کن",
}

#: جنسیت و وضعیتِ تأهل. رشته‌ی خالی = وارد نشده، چون در فرمِ سپیدار هم اجباری نیست
#: و مجبورکردنِ کاربر به انتخاب برای یک مشتریِ حقوقی بی‌معناست.
GENDERS = ("", "male", "female")
GENDER_LABELS = {"male": "مرد", "female": "زن"}
MARITAL_STATUSES = ("", "single", "married", "divorced", "widowed")
MARITAL_STATUS_LABELS = {
    "single": "مجرد",
    "married": "متأهل",
    "divorced": "مطلقه",
    "widowed": "همسر فوت‌شده",
}

#: دسته‌بندیِ وزارت دارایی برای گزارشِ معاملاتِ فصلی.
TAX_MINISTRY_CLASSES = ("normal", "gold", "currency", "estate")
TAX_MINISTRY_CLASS_LABELS = {
    "normal": "عادی",
    "gold": "طلا و جواهر",
    "currency": "ارز",
    "estate": "املاک",
}


class Warehouse(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "warehouses"

    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_warehouses_tenant_code"),
    )

    code: Mapped[str] = mapped_column(String(20), index=True)
    name: Mapped[str] = mapped_column(String(200))
    #: عنوانِ دوم (§۵) — فیلدِ مستقل، نه پیوستِ نام. همان الگویی که طرف‌حساب و
    #: حسابِ بانکی دارند.
    name2: Mapped[str] = mapped_column(String(200), default="", server_default="")

    #: مشخصاتِ اجراییِ انبار (§۳ §۶ §۷ §۸). این‌ها **متادیتا**ی عملیاتی‌اند و هیچ
    #: نقشی در موجودی ندارند؛ عوض‌شدنشان هیچ حرکتِ انباری را تغییر نمی‌دهد (§۳۶).
    #:
    #: `responsible` عمداً متن است نه کلیدِ خارجی به کاربر/پرسنل: §۶ می‌گوید این
    #: فصل چنین الزامی را نشان نمی‌دهد، و انبارِ برون‌سپاری‌شده ممکن است مسئولی
    #: داشته باشد که اصلاً در سیستم کاربر نیست.
    responsible: Mapped[str] = mapped_column(String(200), default="", server_default="")
    phone: Mapped[str] = mapped_column(String(30), default="", server_default="")
    address: Mapped[str] = mapped_column(Text, default="", server_default="")
    address2: Mapped[str] = mapped_column(Text, default="", server_default="")

    #: **معینِ انبار (§۹ §۱۰ §۱۱).** انبار خودش حساب نیست؛ این فقط نگاشتی به
    #: حسابِ موجودِ چارت است.
    #:
    #: `NULL` یعنی «حسابِ پیش‌فرضِ موجودیِ کالا» — همان چیزی که امروز همه‌ی
    #: انبارها از نقشِ `inventory` می‌گیرند. پس هیچ مستأجری با این مهاجرت رفتارش
    #: عوض نمی‌شود؛ فقط کسی که صریحاً نگاشت بگذارد، رفتارِ تازه می‌گیرد (§۱۳:
    #: این فیلد در فرم اجباری نیست).
    #:
    #: §۱۴ عمداً باز است: چند انبار می‌توانند به یک حساب اشاره کنند (سیاستِ
    #: تجمیعی) یا هرکدام به حسابِ خودش. قیدِ یکتایی نمی‌گذاریم چون فصل چنین
    #: محدودیتی را تثبیت نمی‌کند.
    gl_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


#: نحوه‌ی تبدیلِ واحدِ فرعی به اصلی (§۲۲).
#:
#: `fixed` — نسبت همیشه ثابت است: یک کارتن همیشه ۲۴ عدد.
#: `variable` — نسبت هر بار فرق می‌کند (طاقه‌ی پارچه، شاخه‌ی میلگرد، بارِ فله).
#:
#: فصل می‌گوید مدلِ کالا باید **تفاوتِ این دو را بشناسد**، ولی رفتارِ ورودِ نسبتِ
#: متغیر در تراکنش را «تا وقتی workflowهای اختصاصی تثبیتش کنند» نهایی نکن. پس
#: این‌جا فقط اعلام می‌شود؛ موتورِ تبدیل نسبتِ متغیر را رد می‌کند نه اینکه عددی
#: از خودش دربیاورد.
CONVERSION_MODES = ("fixed", "variable")
CONVERSION_MODE_LABELS = {"fixed": "نسبت ثابت", "variable": "نسبت متغیر"}


class UnitOfMeasure(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """واحدِ سنجش به‌عنوان داده‌ی پایه (§۱۹).

    **چرا موجودیت شد.** تا امروز واحد یک `String(20)`ِ آزاد روی کالا بود. یعنی
    «کیلوگرم» و «كيلوگرم» (با ک و ی عربی) دو واحدِ متفاوت بودند، و نگاشتِ کدِ
    واحدِ سامانه‌ی مؤدیان — که روی همان نوشتار کلید می‌خورد — برای هر املا جدا
    لازم می‌شد. فصل صریح است: «Unit نباید Text آزاد داخل کالا باشد».

    `name` کلیدِ کسب‌وکاری است چون همان چیزی است که تا امروز روی کالا نشسته و
    مهاجرت از رویش پیوند می‌زند.
    """

    __tablename__ = "units_of_measure"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_units_of_measure_tenant_name"),
    )

    name: Mapped[str] = mapped_column(String(20))
    #: عنوانِ دوم — همان الگوی انبار و طرف‌حساب و کالا.
    name2: Mapped[str] = mapped_column(String(50), default="", server_default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class Contact(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """طرف حساب: مشتری، تأمین‌کننده، واسطه یا سهامدار — و هر ترکیبی از این چهار.

    `type` فقط دو نقشِ *معاملاتی* را نگه می‌دارد (مشتری/تأمین‌کننده/هردو) چون فیلترها
    و گزارش‌های موجود روی همان تکیه دارند. واسطه و سهامدار پرچمِ مستقل‌اند، پس هر
    چهار نقش هم‌زمان ممکن‌اند بی‌آنکه چیزی از قبل بشکند.
    """

    __tablename__ = "contacts"
    __table_args__ = (
        CheckConstraint(f"type IN {CONTACT_TYPES}", name="ck_contacts_type"),
        CheckConstraint(f"credit_action IN {CREDIT_ACTIONS}", name="ck_contacts_credit_action"),
        CheckConstraint(
            "discount_rate >= 0 AND discount_rate <= 100 "
            "AND commission_rate >= 0 AND commission_rate <= 100",
            name="ck_contacts_rates",
        ),
        CheckConstraint(
            "opening_ar_amount >= 0 AND opening_ap_amount >= 0 "
            "AND opening_ar_side IN ('debit', 'credit') "
            "AND opening_ap_side IN ('debit', 'credit')",
            name="ck_contacts_opening",
        ),
        CheckConstraint(
            "children_count >= 0 AND dependents_count >= 0 "
            "AND share_percent >= 0 AND share_percent <= 100 "
            f"AND gender IN {GENDERS} "
            f"AND marital_status IN {MARITAL_STATUSES}",
            name="ck_contacts_person",
        ),
    )

    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(20), default="customer")
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    address: Mapped[str] = mapped_column(Text, default="")
    tax_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    #: طرف‌حسابِ سیستمی (خودکار ساخته‌شده، مثلِ «فروشِ کارتیِ گذری») — از فهرست/فرم‌های
    #: کاربر پنهان می‌ماند تا با مشتریانِ واقعی قاطی نشود.
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    #: تاریخِ تولدِ مشتری (باشگاه مشتریان: هدیه/یادآوریِ تولد). NULL = وارد نشده.
    birthday: Mapped[date_ | None] = mapped_column(Date, nullable=True)
    #: سقفِ مجازِ مانده‌ی مطالبات از این مشتری (ریال). صفر = بدون سقف / بدون هشدار.
    credit_limit: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    #: لیستِ قیمتِ پیش‌فرضِ این مشتری — در فاکتورِ فروش و صندوق خودکار اعمال می‌شود.
    default_price_list_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("price_lists.id"), nullable=True
    )

    # ── هویتِ مالیاتیِ طرف حساب (برای گزارشِ معاملاتِ فصلی، ماده ۱۶۹ ق.م.م) ──
    #: نوعِ شخص: real = حقیقی، legal = حقوقی. پیش‌فرض حقیقی.
    entity_type: Mapped[str] = mapped_column(String(10), default="real", server_default="real")
    #: کد ملی (حقیقی، ۱۰ رقم) یا شناسه‌ی ملی (حقوقی، ۱۱ رقم). NULL = وارد نشده.
    national_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    #: کد اقتصادیِ طرف حساب. NULL = وارد نشده.
    economic_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    #: کد پستیِ ۱۰رقمی — سامانه‌ی معاملاتِ فصلی می‌خواهد. NULL = وارد نشده.
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # ── دسته‌بندیِ سطحِ شرکت (اختیاری؛ NULL = دسته‌بندی‌نشده) ──
    #: گروهِ طرف‌حساب — برای گزارش‌گیریِ گروهی.
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contact_groups.id", ondelete="SET NULL"), nullable=True
    )
    #: محلِ جغرافیایی (برگِ درخت: معمولاً شهر یا منطقه).
    geo_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("geo_locations.id", ondelete="SET NULL"), nullable=True
    )

    # ── هویتِ تفکیک‌شده ────────────────────────────────────────────────────────
    #: نام و نام خانوادگی جدا. `name` بالا **نامِ نمایشی** است و دست‌نخورده می‌ماند —
    #: روی فاکتور، گزارشِ فصلی و صورت‌حساب نشسته و شکستنش تغییرِ شکننده‌ای بود.
    #: سرویس `name` را از این دو می‌سازد؛ خالی بودنشان یعنی نامِ یک‌تکه (شرکت).
    first_name: Mapped[str] = mapped_column(String(100), default="", server_default="")
    last_name: Mapped[str] = mapped_column(String(100), default="", server_default="")
    #: نام و نام خانوادگیِ دوم (معمولاً انگلیسی) برای اسنادِ دوزبانه.
    first_name2: Mapped[str] = mapped_column(String(100), default="", server_default="")
    last_name2: Mapped[str] = mapped_column(String(100), default="", server_default="")
    #: نوعِ فرعی — دسته‌بندیِ آزادِ کاربر زیرِ حقیقی/حقوقی («سایر»، «دولتی»، «خیریه»).
    sub_type: Mapped[str] = mapped_column(String(50), default="", server_default="")
    website: Mapped[str] = mapped_column(String(200), default="", server_default="")
    #: شماره ثبت (حقوقی) و شماره گذرنامه (حقیقیِ خارجی). NULL = وارد نشده.
    registration_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    passport_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    marriage_date: Mapped[date_ | None] = mapped_column(Date, nullable=True)
    #: لیستِ سیاه — جدا از `is_active`: غیرفعال یعنی «دیگر کار نمی‌کنیم»، لیستِ سیاه
    #: یعنی «کار می‌کنیم ولی با احتیاط». هر دو با هم هم ممکن‌اند.
    is_blacklisted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    #: نرخِ تخفیفِ پیش‌فرضِ این مشتری (درصد). صفر = بدونِ تخفیف.
    discount_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=0, server_default="0")
    #: دسته‌بندیِ وزارت دارایی («عادی»، «طلا و جواهر»، …) — برای گزارشِ فصلی.
    tax_ministry_class: Mapped[str] = mapped_column(
        String(30), default="normal", server_default="normal"
    )

    # ── کنترلِ اعتبار ─────────────────────────────────────────────────────────
    #: `credit_limit` بالا تا امروز ذخیره می‌شد ولی **هیچ‌جا اعمال نمی‌شد**. این
    #: ستون می‌گوید با عبور از سقف چه شود: none = هیچ (پیش‌فرض، همان رفتارِ قبلی)،
    #: warn = هشدار بده ولی بگذار، block = جلوی عملیات را بگیر.
    credit_action: Mapped[str] = mapped_column(String(10), default="none", server_default="none")

    # ── نقشِ سوم ──────────────────────────────────────────────────────────────
    #: واسطه. پرچمِ مستقل است نه مقدارِ تازه‌ی `type`: ده‌ها فیلتر و گزارش روی
    #: (customer, supplier, both) تکیه دارند و افزودنِ مقدار به آن یعنی بازبینیِ
    #: همه‌شان. این‌طور، فرم همان سه تیکِ مستقل را می‌دهد بی‌آنکه چیزی بشکند.
    is_broker: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    commission_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=0, server_default="0")

    # ── دو پیوند، نه دو کپی ───────────────────────────────────────────────────
    #: تفصیلیِ این طرف‌حساب — همان «کد/عنوان تفصیلی»ِ فرمِ سپیدار. به جدولِ موجود
    #: وصل می‌شود تا ردیفِ سند و گزارشِ تفصیلی از یک منبع بخوانند.
    analytic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analytic_accounts.id", ondelete="SET NULL"), nullable=True
    )
    #: کارمندِ متناظر در ماژولِ حقوق و دستمزد — تبِ «مشخصات کارمند». پیوند است نه
    #: کپی: نام و کد ملی و تاریخِ استخدام همان‌جا می‌مانند. یک آدم، یک رکورد.
    employee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id", ondelete="SET NULL"), nullable=True
    )

    # ── مانده‌ی اول دوره ──────────────────────────────────────────────────────
    #: مانده‌ی طرف‌حساب در ابتدای دوره، به تفکیکِ نقش. دو مبلغِ جدا چون حسابِ
    #: دریافتنی و پرداختنی دو حسابِ متفاوت‌اند و یک طرف‌حساب می‌تواند هم‌زمان هر دو
    #: باشد. سمت جداست چون مانده‌ی خلافِ انتظار واقعاً پیش می‌آید (پیش‌دریافت از
    #: مشتری، پیش‌پرداخت به تأمین‌کننده).
    #:
    #: همان الگویِ «موجودیِ اول دوره»ی کالا: عدد این‌جا می‌نشیند و سندِ افتتاحیه از
    #: رویش ساخته می‌شود. **پس از ثبتِ افتتاحیه قفل می‌شوند** — وگرنه عددِ این‌جا و
    #: ردیفِ سند از هم جدا می‌افتند و گزارش دو حقیقت می‌گوید.
    opening_ar_amount: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    opening_ar_side: Mapped[str] = mapped_column(String(6), default="debit", server_default="debit")
    opening_ap_amount: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    opening_ap_side: Mapped[str] = mapped_column(String(6), default="credit", server_default="credit")

    # ── مشخصاتِ شخصی ─────────────────────────────────────────────────────────
    # این‌ها واقعیت‌های *شخص*اند نه شغلش؛ چه کارمند باشد چه مشتری درست‌اند. اگر روی
    # `employees` می‌نشستند، مشتریِ غیرکارمند هیچ‌وقت نمی‌توانست داشته باشدشان.
    # واقعیت‌های *استخدام* (حکم، تاریخ استخدام، شماره حساب، مرخصی) سرِ جایشان در
    # ماژولِ حقوق و دستمزد می‌مانند و `employee_id` پلِ این دو است.
    gender: Mapped[str] = mapped_column(String(10), default="", server_default="")
    marital_status: Mapped[str] = mapped_column(String(20), default="", server_default="")
    marital_status_date: Mapped[date_ | None] = mapped_column(Date, nullable=True)
    children_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    #: افرادِ تحتِ تکفل — مبنای معافیتِ مالیاتی و بیمه، پس جدا از تعدادِ فرزند.
    dependents_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    education_level: Mapped[str] = mapped_column(String(50), default="", server_default="")
    education_field: Mapped[str] = mapped_column(String(150), default="", server_default="")
    #: تیکِ «کارمند» در فرم. `employee_id` می‌گوید *کدام* کارمند؛ این می‌گوید آیا
    #: کاربر این طرف‌حساب را کارمند می‌داند — دو چیزِ متفاوت، چون ممکن است تیک بزند
    #: و هنوز رکوردِ حقوق و دستمزدش را نساخته باشد.
    is_employee: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    #: نقشِ چهارم، مثلِ `is_broker` پرچمِ مستقل و نه مقدارِ تازه‌ی `type`.
    is_shareholder: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    share_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=0, server_default="0")

    #: کد و عنوانِ تفصیلی از همین رابطه خوانده می‌شوند، نه از ستونی روی طرف‌حساب.
    analytic: Mapped["AnalyticAccount | None"] = relationship(lazy="joined")  # noqa: F821


class Item(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """کالا یا خدمت. average_cost فقط برای کالا به‌روزرسانی می‌شود (روش میانگین موزون)."""

    __tablename__ = "items"

    __table_args__ = (
        UniqueConstraint("tenant_id", "sku", name="uq_items_tenant_sku"),
        # بارکد در سطحِ مستأجر یکتاست — دو کالا نباید بارکدِ یکسان بگیرند، وگرنه اسکن
        # مبهم می‌شود و «آخرین کالای ذخیره‌شده» را می‌آورد. ایندکسِ جزئی چون بارکدِ
        # خالی NULL است و چند کالای بی‌بارکد مجازند (فقط ردیف‌های دارای بارکد یکتا).
        Index(
            "uq_items_tenant_barcode",
            "tenant_id",
            "barcode",
            unique=True,
            postgresql_where=text("barcode IS NOT NULL"),
        ),
    )

    sku: Mapped[str] = mapped_column(String(50), index=True)
    #: بارکد (EAN/Code128/…) برای اسکن در صندوقِ فروشگاهی (POS). اختیاری و nullable؛
    #: کالاهایی که بارکد ندارند NULL می‌مانند (چند NULL مجاز است).
    barcode: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(300))
    #: عنوانِ دوم (§۵) — فیلدِ مستقل، نه پیوستِ نام. فصل صریح است: این دو را در یک
    #: رشته ادغام نکن.
    name2: Mapped[str] = mapped_column(String(300), default="", server_default="")
    category: Mapped[str] = mapped_column(String(100), default="")
    unit: Mapped[str] = mapped_column(String(20), default="عدد")
    is_service: Mapped[bool] = mapped_column(Boolean, default=False)
    sales_price: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    #: **چهار رقم اعشار، و این تزئینی نیست.** بهای تمام‌شده نتیجه‌ی یک تقسیم
    #: است (مبلغِ ردیف ÷ تعداد) و با ریالِ صحیح، `مقدار × میانگین` از مبلغِ
    #: واقعی فاصله می‌گرفت — روی نمونه‌ی واقعی ۵۰ ریال، بی‌آنکه ترازی به‌هم
    #: بخورد. چهار رقم اختلاف را به کسری از ریال می‌برد (مهاجرت ۰۱۳۰).
    average_cost: Mapped[float] = mapped_column(Numeric(18, 4), default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    #: **«قابل فروش» جدا از «فعال» (§۷).** هرچه در انبار داریم الزاماً فروختنی
    #: نیست: موادِ اولیه، قطعاتِ مصرفی و موادِ بسته‌بندی موجودی دارند و گردش
    #: می‌کنند، ولی نباید در فاکتورِ فروش و صندوق انتخاب شوند.
    #:
    #: غیرفعال یعنی «دیگر با این کالا کار نمی‌کنیم»؛ غیرقابل‌فروش یعنی «کار
    #: می‌کنیم ولی نمی‌فروشیمش». هر دو هم‌زمان ممکن‌اند.
    is_sellable: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    #: ثبتِ سریالی (§۸). امروز فقط *اعلام* می‌کند که این کالا سریال‌محور است؛
    #: دفترِ سریال از قبل زیرِ `stock_batch_serials` هست و این پرچم می‌گوید کدام
    #: کالا انتظارِ سریال دارد.
    #:
    #: §۹: روشن/خاموش‌کردنش **پس از وجودِ گردشِ انباری** کنترل‌شده است، چون
    #: موجودیِ قدیمی سریال ندارد و مبهم می‌شود.
    is_serial_tracked: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    #: ایران‌کد (§۱۱) و بارکدِ دوبعدی (§۱۲) — **سه شناسه‌ی جدا** با `sku` و
    #: `barcode`. فصل صریح است که یکی‌شان نکنیم. بارکدِ دوبعدی متنِ بلند است (QR)
    #: پس اندازه‌اش با بارکدِ خطی یکی نیست.
    iran_code: Mapped[str] = mapped_column(String(30), default="", server_default="")
    barcode2: Mapped[str] = mapped_column(String(300), default="", server_default="")

    #: نقطه‌ی سفارشِ مجدد (حداقلِ موجودی). وقتی موجودیِ کلِ کالا ≤ این عدد باشد، در
    #: «نیازمندِ سفارش» هشدار داده می‌شود. صفر = بدونِ هشدار (پیش‌فرض). فقط برای کالا
    #: معنا دارد، نه خدمت. اعشاری‌پذیر چون واحد می‌تواند متر/کیلوگرم باشد.
    reorder_point: Mapped[float] = mapped_column(Numeric(18, 3), default=0, server_default="0")

    #: وضعیتِ مالیات بر ارزش افزوده: `taxable` (مشمول) یا `exempt` (معاف).
    #:
    #: **چرا پرچمِ جدا و نه `tax_rate = 0`:** نرخِ صفر مبهم است — سالِ بعد کسی
    #: نمی‌تواند بگوید این کالا واقعاً معاف بوده یا فقط نرخش صفر ثبت شده. گزارشِ
    #: ارزش افزوده باید «فروشِ معاف» را از «فروشِ مشمول با نرخِ صفر» تفکیک کند.
    #:
    #: این *تنظیم* است؛ آنچه در گزارش شمرده می‌شود `vat_status`ِ **ردیفِ فاکتور**
    #: است که لحظه‌ی ثبت از همین‌جا کپی می‌شود. همان الگوی `tax_rate`/`tax_amount`.
    vat_status: Mapped[str] = mapped_column(String(10), default="taxable", server_default="taxable")

    #: شناسه‌ی کالا/خدمتِ مالیاتی (sstid) — کدِ رسمیِ ۱۳رقمیِ سامانه مؤدیان برای این کالا.
    #: خالی = از «شناسه‌ی پیش‌فرض»ِ تنظیماتِ مؤدیان استفاده می‌شود. راز نیست.
    tax_stuff_id: Mapped[str] = mapped_column(String(20), default="", server_default="")

    #: **وضعیتِ مالیاتیِ سمتِ خرید — جدا از فروش (§۱۳).**
    #:
    #: فصل صریح است: `item.tax_exempt = true` به‌تنهایی کافی نیست، چون وضعیتِ
    #: مالیاتیِ خرید و فروشِ یک قلم الزاماً یکی نیست. `vat_status` بالا از این
    #: پس فقط سمتِ *فروش* را می‌گوید و این سمتِ *خرید* را.
    #:
    #: مهاجرت مقدارِ `vat_status` را در این می‌ریزد، نه «مشمول» را — وگرنه کالایی
    #: که امروز معاف است یک‌شبه در خرید مشمول می‌شد.
    purchase_vat_status: Mapped[str] = mapped_column(
        String(10), default="taxable", server_default="taxable"
    )

    #: نرخِ مالیات و عوارضِ **خودِ کالا** (§۱۳). صفر = «نرخِ سرِ فاکتور».
    #:
    #: **چرا صفر یعنی وراثت و نه معافیت:** معافیت مفهومِ جدایی است و جایش
    #: `vat_status`/`purchase_vat_status` است. صفر گذاشتن روی همه‌ی کالاهای
    #: موجود یعنی رفتارِ امروز (نرخِ یکتای فاکتور) بی‌تغییر می‌ماند.
    #:
    #: §۱۴: این *تنظیمِ جاری* است. آنچه در فاکتور می‌ماند `tax_rate_snapshot` و
    #: `tax_amount_snapshot`ِ ردیف است؛ عوض‌شدنِ این نرخ فاکتورِ پارسال را
    #: بازنویسی نمی‌کند.
    tax_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=0, server_default="0")
    duty_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=0, server_default="0")

    #: **واحدِ اصلی و فرعی (§۱۷ §۱۸ §۲۰).**
    #:
    #: `unit` بالا از این پس **پرتوِ نامِ واحدِ اصلی** است، نه منبعِ حقیقت: سرویس
    #: هر بار که واحد عوض شود آن را هم‌گام می‌کند. نگه‌داشتنش عمدی است — ردیفِ
    #: فاکتور، بسته‌ی مؤدیان، بازار و فروشگاه همه `unit_snapshot`/`unit` را
    #: می‌خوانند و شکستنِ همه‌شان ارزشی اضافه نمی‌کرد.
    primary_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("units_of_measure.id"), nullable=True
    )
    secondary_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("units_of_measure.id"), nullable=True
    )
    #: §۲۱ — «۱ کارتن = ۲۴ عدد». صفر یعنی نسبت هنوز تعریف نشده.
    conversion_factor: Mapped[float] = mapped_column(
        Numeric(18, 6), default=0, server_default="0"
    )
    conversion_mode: Mapped[str] = mapped_column(
        String(10), default="fixed", server_default="fixed"
    )

    #: §۲۳ — وزن و حجمِ **یک واحدِ اصلی**. متادیتای کالا برای حمل‌ونقل و توزین
    #: است، **نه موجودی**: هیچ‌جا از این‌ها مانده‌ای مشتق نمی‌شود.
    unit_weight: Mapped[float] = mapped_column(Numeric(18, 6), default=0, server_default="0")
    unit_volume: Mapped[float] = mapped_column(Numeric(18, 6), default=0, server_default="0")

    #: **گروه‌بندی (§۳۴).** `category` بالا از این پس پرتوِ نامِ این گروه است.
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("item_groups.id", ondelete="SET NULL"), nullable=True
    )

    #: **کنترلِ موجودی (§۲۴ §۲۵ §۲۶).**
    #:
    #: `reorder_point` از قبل بود و «نیازمندِ سفارش» رویش تکیه دارد؛ دست‌نخورده
    #: می‌ماند. این دو کنارش می‌نشینند چون فصل سه مفهومِ **جدا** می‌شناسد:
    #: حداقل، حداکثر، و نقطه‌ی سفارش.
    #:
    #: §۲۶ صریح است: این‌ها **قاعده‌ی برنامه‌ریزی‌اند، نه سدِ تراکنش**. حداکثر
    #: موجودی جلوی ورودِ کالا را نمی‌گیرد؛ فقط هشدار می‌سازد.
    #:
    #: §۲۸ می‌گوید انبارمحور یا سراسری‌بودنشان را **فرض نکن**. پس عددِ این‌جا
    #: سراسری است (همان رفتارِ امروزِ `reorder_point`) و ردیفِ `item_warehouses`
    #: می‌تواند برای یک انبارِ خاص override بگذارد. هیچ‌کدام تحمیل نشده.
    min_stock: Mapped[float] = mapped_column(Numeric(18, 3), default=0, server_default="0")
    max_stock: Mapped[float] = mapped_column(Numeric(18, 3), default=0, server_default="0")

    #: **معینِ هزینه‌ی خرید (§۱۵).** برای خدمت: «مشاوره حقوقی» هنگام خرید به یک
    #: حسابِ هزینه می‌نشیند، نه به موجودیِ کالا.
    #:
    #: `NULL` یعنی حسابِ پیش‌فرضِ نقشِ `service_expense`. مثلِ معینِ انبار، نگاشت
    #: اختیاری است و از چارتِ موجود حل می‌شود — کد و نامِ حساب hard-code نمی‌شود.
    expense_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=True
    )

    # نگاشت به کالای متناظر روی سایت فروشگاهی (ipnetcity.ir) برای فاز Integration
    storefront_product_id: Mapped[int | None] = mapped_column(nullable=True)


class ItemGroup(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """گروه‌بندیِ کالا/خدمت (§۳۴).

    **چرا رکورد شد و نه همان متنِ `category`:** متنِ آزاد گزارشِ گروهی را
    غیرقابل‌اعتماد می‌کند («لوازم خانگی» و «لوازم‌خانگی» دو گروه می‌شوند) و
    نمی‌شود گروهی را بست بی‌آنکه کالاهای قدیمی‌اش گم شوند.

    **شکلش عمداً همان `ContactGroup` است.** §۳۴ می‌گوید «ساختارِ نهاییِ
    گروه‌بندی را فقط از این فصل تثبیت نکن» و «مفاهیمِ گروه‌بندیِ موجودِ کوبیتا را
    بازاستفاده کن» — پس الگوی موجود تکرار می‌شود، نه یک طرحِ تازه.

    `Item.category` می‌ماند ولی از این پس **پرتوِ نامِ گروه** است؛ فروشگاه،
    گزارش‌ها و ورودِ گروهی همه آن را می‌خوانند.
    """

    __tablename__ = "item_groups"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_item_groups_tenant_name"),
    )

    code: Mapped[str] = mapped_column(String(30), default="", server_default="")
    name: Mapped[str] = mapped_column(String(100))
    name2: Mapped[str] = mapped_column(String(100), default="", server_default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")


class ItemAttribute(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """تعریفِ یک مشخصه‌ی کالا (§۳۵ §۳۶) — «رنگ»، «سایز»، «کشور سازنده».

    **چرا ستونِ ثابت نساختیم:** §۳۶ صریح است — اگر امروز «رنگ» لازم است و فردا
    «توان موتور»، نباید برای هر مشخصه ستونِ تازه‌ای روی `items` بنشیند. الگو
    همان چیزی است که فصل می‌خواهد: *تعریفِ مشخصه* ← *مقدارِ مشخصه‌ی کالا*.

    **و نوعِ داده عمداً نیست.** فصل نوع (متن/عدد/فهرست) را تثبیت نمی‌کند و
    می‌گوید با فصلِ اختصاصیِ «تعریف مشخصات کالا/خدمت» هماهنگ شود. اختراعِ
    نوع‌بندی این‌جا یعنی همان چیزی که بعداً باید بازنویسی شود.
    """

    __tablename__ = "item_attributes"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_item_attributes_tenant_name"),
    )

    name: Mapped[str] = mapped_column(String(100))
    name2: Mapped[str] = mapped_column(String(100), default="", server_default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class ItemAttributeValue(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """مقدارِ یک مشخصه برای یک کالا (§۳۵)."""

    __tablename__ = "item_attribute_values"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "item_id", "attribute_id", name="uq_item_attribute_values_pair"
        ),
    )

    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), index=True
    )
    attribute_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("item_attributes.id", ondelete="CASCADE"), index=True
    )
    value: Mapped[str] = mapped_column(Text, default="", server_default="")


class ItemWarehouse(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """انبارهای مرتبطِ یک کالا (§۲۹ §۳۰ §۳۱).

    **رابطه ذاتاً چندبه‌چند است (§۳۰):** یک کالا در چند انبار، و یک انبار پرِ
    چند کالا.

    **فهرستِ خالی یعنی «همه‌ی انبارها»** — یعنی دقیقاً رفتارِ امروزِ کوبیتا. پس
    این جدول هیچ کالای موجودی را محدود نمی‌کند؛ فقط کسی که صریحاً فهرست بگذارد
    محدودیت می‌گیرد.

    **`is_default` مالکیت نیست (§۳۲):** فقط پیشنهادِ اولیه‌ی فرم است. کالا به
    انبارِ پیش‌فرضش قفل نمی‌شود.

    **و حذفِ رابطه گذشته را پاک نمی‌کند (§۳۳):** حرکاتِ انبار و کاردکس جای دیگری
    زندگی می‌کنند و این جدول فقط *آینده* را می‌گوید.
    """

    __tablename__ = "item_warehouses"
    __table_args__ = (
        UniqueConstraint("tenant_id", "item_id", "warehouse_id", name="uq_item_warehouses_pair"),
        #: یک انبارِ پیش‌فرض برای هر کالا — نه صفر، نه دو تا. ایندکسِ جزئی چون
        #: نبودِ پیش‌فرض مجاز است.
        Index(
            "uq_item_warehouses_default",
            "tenant_id",
            "item_id",
            unique=True,
            postgresql_where=text("is_default"),
        ),
    )

    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), index=True
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="CASCADE"), index=True
    )
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    #: override‌های انبارمحورِ کنترلِ موجودی (§۲۸). `NULL` = «همان عددِ کالا».
    #: فصل تصمیم نمی‌گیرد که کنترل سراسری باشد یا انبارمحور؛ این ساختار هر دو را
    #: می‌پذیرد بی‌آنکه یکی را تحمیل کند.
    min_stock: Mapped[float | None] = mapped_column(Numeric(18, 3), nullable=True)
    max_stock: Mapped[float | None] = mapped_column(Numeric(18, 3), nullable=True)

    warehouse: Mapped["Warehouse"] = relationship()


class StockLedger(TenantMixin, UUIDPKMixin, Base):
    """دفتر موجودی: هر رکورد یک حرکت ورود(+)/خروج(-) است. موجودی فعلی = SUM(qty) به تفکیک کالا/انبار."""

    __tablename__ = "stock_ledger"

    #: ترتیب قطعیِ ثبت. کلید اصلی UUID تصادفی است و مرتب کردن بر اساسش بی‌معناست،
    #: و `entry_date` فقط روز را دارد — پس چند حرکت در یک روز هیچ ترتیب مشخصی
    #: ندارند. برای موجودی (که جمع ساده است) مهم نیست، ولی بهای تمام‌شده‌ی میانگین
    #: موزون به ترتیب وابسته است: خرید-فروش-خرید عدد متفاوتی از خرید-خرید-فروش
    #: می‌دهد. بدون این ستون، بازمحاسبه هر بار می‌توانست عدد دیگری بدهد.
    #:
    #: ایندکس عمداً یکتا نیست: خودِ SEQUENCE تضمین می‌کند مقدار تکراری صادر نشود، و
    #: یکتای سراسری روی جدول مستأجرمحور دقیقاً همان الگویی است که تست انحراف
    #: (به‌درستی) رد می‌کند.
    seq: Mapped[int] = mapped_column(
        BigInteger, Sequence("stock_ledger_seq"), nullable=False, index=True
    )

    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"), index=True)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id"), index=True)
    qty: Mapped[float] = mapped_column(Numeric(18, 3))
    #: بهای تمام‌شده‌ی واحد — چهار رقم اعشار، به همان دلیلِ `Item.average_cost`:
    #: `recompute_average_cost` میانگین را از همین ستون بازمی‌سازد، پس گِردکردنش
    #: مستقیماً به ارزش‌گذاری سرایت می‌کرد.
    unit_cost: Mapped[float] = mapped_column(Numeric(18, 4))
    entry_date: Mapped[date_] = mapped_column(Date, default=date_.today)

    source_type: Mapped[str] = mapped_column(String(50))  # sales_invoice | purchase_invoice | adjustment
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    item: Mapped["Item"] = relationship()
    warehouse: Mapped["Warehouse"] = relationship()


class StockAdjustment(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """انبارگردانی/تعدیل موجودی دستی (کسری یا اضافی) با سند حسابداری خودکار متناظر."""

    __tablename__ = "stock_adjustments"

    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"))
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id"))
    qty_diff: Mapped[float] = mapped_column(Numeric(18, 3))  # مثبت = اضافه‌شدن به موجودی، منفی = کسری
    unit_cost: Mapped[float] = mapped_column(Numeric(18, 0))  # از average_cost کالا در لحظه‌ی ثبت snapshot می‌شود
    reason: Mapped[str] = mapped_column(Text, default="")
    adjustment_date: Mapped[date_] = mapped_column(Date, default=date_.today)
    #: اگر این تعدیل بابتِ کسری/معیوب/ضایعاتِ یک بارِ مشخص است، به همان بچ گره می‌خورد
    #: تا معلوم شود کدام بار مشکل داشته. NULL = تعدیلِ عمومی (انبارگردانی).
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stock_batches.id", ondelete="SET NULL"), nullable=True, index=True
    )

    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True, index=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    item: Mapped["Item"] = relationship()
    warehouse: Mapped["Warehouse"] = relationship()
