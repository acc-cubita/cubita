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
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


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
    category: Mapped[str] = mapped_column(String(100), default="")
    unit: Mapped[str] = mapped_column(String(20), default="عدد")
    is_service: Mapped[bool] = mapped_column(Boolean, default=False)
    sales_price: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    average_cost: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

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

    # نگاشت به کالای متناظر روی سایت فروشگاهی (ipnetcity.ir) برای فاز Integration
    storefront_product_id: Mapped[int | None] = mapped_column(nullable=True)


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
    unit_cost: Mapped[float] = mapped_column(Numeric(18, 0))
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
