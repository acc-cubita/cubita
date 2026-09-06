"""موجودیت‌های سطحِ «شرکت» — دسته‌بندی و شناسنامه‌ی طرف‌حساب‌ها.

سه چیزِ کوچک که تا امروز جایشان خالی بود و هر سه به یک نیاز برمی‌گردند: طرف‌حساب
بیش از یک نام و یک شماره‌ی تلفن است.

* **گروه** — طرف‌حساب‌ها را دسته می‌کند (عمده‌فروش، خرده‌فروش، همکار…). گزارشِ فروش
  به تفکیکِ گروه بدونِ این ستون یعنی خواندنِ نامِ تک‌تکِ مشتری‌ها.
* **محلِ جغرافیایی** — درختِ کشور ← استان ← شهر ← منطقه. درختی است نه سه ستونِ متنی،
  چون «تهران» در دو ردیفِ متنی دو چیزِ متفاوت است و هر گزارشِ منطقه‌ای را می‌شکند.
* **فردِ مرتبط** — آدم‌های واقعیِ پشتِ یک طرف‌حسابِ حقوقی (مدیر خرید، حسابدار، راننده).
  شماره‌ی این‌ها امروز در فیلدِ «توضیحات» می‌نشیند و جست‌وجوپذیر نیست.
"""
import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin

#: سطح‌های درختِ جغرافیایی، از کل به جزء.
GEO_KINDS = ("country", "province", "city", "district")
GEO_KIND_LABELS = {
    "country": "کشور",
    "province": "استان",
    "city": "شهر",
    "district": "منطقه",
}


class ContactGroup(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """گروهِ طرف‌حساب — برچسبِ دسته‌بندی برای گزارش‌گیری و قیمت‌گذاری."""

    __tablename__ = "contact_groups"

    #: کدِ کوتاهِ اختیاری برای مرتب‌سازی/ارجاع؛ مثلِ مرکزِ هزینه یکتا نیست چون برچسبِ کاربر است.
    code: Mapped[str] = mapped_column(String(30), default="", server_default="")
    name: Mapped[str] = mapped_column(String(120))
    #: گروهِ بسته‌شده در فرم‌ها پیشنهاد نمی‌شود ولی طرف‌حساب‌های قبلی‌اش دست‌نخورده می‌مانند.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))


class GeoLocation(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """محلِ جغرافیایی — درختِ کشور ← استان ← شهر ← منطقه.

    `parent_id` خالی یعنی ریشه. سطح (`kind`) جدا از پدر نگه داشته می‌شود چون بعضی
    کشورها استان ندارند و درخت باید بتواند یک سطح را رد کند بی‌آنکه معنایش گم شود.
    """

    __tablename__ = "geo_locations"
    __table_args__ = (
        CheckConstraint(f"kind IN {GEO_KINDS}", name="ck_geo_locations_kind"),
        Index("ix_geo_locations_tenant_parent", "tenant_id", "parent_id"),
    )

    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(20), default="city", server_default="city")
    #: کدِ اختیاری (کدِ پستیِ پیش‌شماره، کدِ استان و…).
    code: Mapped[str] = mapped_column(String(30), default="", server_default="")
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("geo_locations.id", ondelete="RESTRICT"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))


class RelatedPerson(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """فردِ مرتبط با یک طرف‌حساب — آدمِ واقعیِ پشتِ یک شرکت.

    به طرف‌حساب گره خورده و با حذفِ آن حذف می‌شود (`CASCADE`): بدونِ طرف‌حساب،
    «مدیرِ خریدِ کیست؟» معنایی ندارد.
    """

    __tablename__ = "related_persons"
    __table_args__ = (Index("ix_related_persons_tenant_contact", "tenant_id", "contact_id"),)

    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200))
    #: سمت/نقش نزدِ آن طرف‌حساب. برای شرکت سمتِ سازمانی است («مدیر خرید»، «حسابدار»)
    #: و برای شخص نسبت («پدر»، «همسر»، «فرزند») یا «معرف».
    role: Mapped[str] = mapped_column(String(120), default="", server_default="")
    #: نام و سمتِ دوم (لاتین) — «(۲)»ِ فرمِ سپیدار. اختیاری و بی‌اثر بر فارسی.
    name2: Mapped[str] = mapped_column(String(200), default="", server_default="")
    role2: Mapped[str] = mapped_column(String(200), default="", server_default="")
    phone: Mapped[str] = mapped_column(String(30), default="", server_default="")
    email: Mapped[str] = mapped_column(String(150), default="", server_default="")
    #: نفرِ اصلیِ تماس. سرویس تضمین می‌کند در هر طرف‌حساب حداکثر یکی باشد.
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))


#: کانالِ تماسِ *اضافه*. کانالِ اصلی روی خودِ طرف‌حساب است (`phone` / `address`).
#: `address` از ۰۰۹۲ به `contact_addresses` منتقل شد و این‌جا فقط برای سازگاریِ
#: ردیف‌های قدیمی می‌ماند — نشانیِ تازه آن‌جا ثبت می‌شود، نه این‌جا.
CHANNEL_KINDS = ("phone", "address", "email")
CHANNEL_KIND_LABELS = {"phone": "تلفن", "address": "نشانی", "email": "ایمیل"}

#: نوعِ تلفن — فهرستِ کنترل‌شده، چون «نوع» در فرمِ سپیدار کشویی است نه متنِ آزاد.
CHANNEL_TYPES = ("office", "warehouse", "mobile", "fax", "home", "other")
CHANNEL_TYPE_LABELS = {
    "office": "تلفن دفتر",
    "warehouse": "تلفن انبار",
    "mobile": "همراه",
    "fax": "فکس",
    "home": "منزل",
    "other": "سایر",
}

#: نوعِ نشانی — همان فهرستِ کشوییِ تبِ «نشانی»ِ سپیدار. هرکدام کاربردِ عملیاتی دارد:
#: «ارسال کالا» همانی است که به مأمورِ ارسال داده می‌شود، «ارسال صورتحساب» جایی که
#: فاکتور می‌رود، و «رسمی» نشانیِ حقوقیِ روی اسناد.
#: «سایر» درِ خروجِ فهرست است، نه دعوت به متنِ آزاد: کارگاه، نمایشگاه، دفترِ موقت.
#: بی آن، کاربر مجبور می‌شد یکی از هفت‌تای دیگر را دروغ انتخاب کند و از آن به بعد
#: فیلترِ «ارسال کالا» نشانی‌هایی را برمی‌گرداند که نشانیِ ارسال نبودند. عنوانِ نشانی
#: (`title`) همان‌جاست تا کاربر بنویسد دقیقاً چیست.
ADDRESS_TYPES = (
    "official", "business", "billing", "shipping", "warehouse", "home", "postal", "other",
)
ADDRESS_TYPE_LABELS = {
    "official": "رسمی",
    "business": "محل فعالیت",
    "billing": "ارسال صورتحساب",
    "shipping": "ارسال کالا",
    "warehouse": "انبار",
    "home": "منزل",
    "postal": "پستی",
    "other": "سایر",
}


class ContactChannel(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """تلفن یا نشانیِ **اضافه‌ی** یک طرف‌حساب.

    یک جدول برای هر سه نوع، چون ساختارشان یکی است (برچسب + مقدار) و دو جدولِ همسان
    فقط دو مسیرِ نگهداری می‌سازد.

    **کانالِ اصلی این‌جا نیست.** `contacts.phone` و `contacts.address` سرِ جایشان
    می‌مانند و «اصلی» هستند، چون ده‌ها جا (فاکتور، صورت‌حساب، پیامک، گزارشِ فصلی)
    مستقیم آن‌ها را می‌خوانند. این جدول فقط شماره‌ها و نشانی‌های *بعدی* را نگه
    می‌دارد — پس هیچ ردیفی این‌جا کپیِ چیزی نیست و دو نمای یک داده ساخته نمی‌شود.
    """

    __tablename__ = "contact_channels"
    __table_args__ = (
        CheckConstraint(f"kind IN {CHANNEL_KINDS}", name="ck_contact_channels_kind"),
        Index("ix_contact_channels_tenant_contact", "tenant_id", "contact_id"),
    )

    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(10))
    #: برچسبِ آزادِ کاربر: «دفتر مرکزی»، «انبار»، «همراهِ مدیر».
    label: Mapped[str] = mapped_column(String(100), default="", server_default="")
    value: Mapped[str] = mapped_column(Text)
    #: نوعِ کنترل‌شده (دفتر، انبار، همراه…) — جدا از `label` که متنِ آزادِ کاربر است.
    channel_type: Mapped[str] = mapped_column(String(20), default="other", server_default="other")
    #: کدام شماره «اصلی» است. سرویس تضمین می‌کند در هر طرف‌حساب و هر نوع، حداکثر یکی.
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class ContactAddress(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """یکی از نشانی‌های یک طرف‌حساب.

    جدا از `ContactChannel` است چون شکلش واقعاً فرق دارد: تلفن سه فیلد دارد و نشانی
    شانزده. ریختنشان در یک جدول یعنی سیزده ستونِ همیشه‌خالی برای هر شماره.

    **کاربردِ عملیاتی‌اش ارسالِ کالاست.** نشانیِ نوعِ «ارسال کالا» به‌همراه مختصات و
    کدِ مسیر همان چیزی است که به مأمورِ ارسال داده می‌شود؛ بدونِ این، هر تحویل یک
    تماسِ تلفنی لازم داشت.

    `route_code` همان «زون»ِ توزیع است. فعلاً متن است چون موجودیتِ زون هنوز ساخته
    نشده؛ **وقتی ساخته شد باید کلیدِ خارجی شود**، نه اینکه فهرستی متنی موازیِ آن بماند.
    """

    __tablename__ = "contact_addresses"
    __table_args__ = (
        CheckConstraint(f"address_type IN {ADDRESS_TYPES}", name="ck_contact_addresses_type"),
        Index("ix_contact_addresses_tenant_contact", "tenant_id", "contact_id"),
    )

    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False
    )
    address_type: Mapped[str] = mapped_column(String(20), default="official", server_default="official")
    #: نشانیِ پیش‌فرضِ این طرف‌حساب. سرویس تضمین می‌کند حداکثر یکی باشد.
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    #: شهر از درختِ `geo_locations` می‌آید، نه متنِ آزاد: «تهران» و «طهران» و «تهران »
    #: سه شهر نمی‌شوند و گزارشِ منطقه‌ای درست درمی‌آید.
    geo_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("geo_locations.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(150), default="", server_default="")
    address: Mapped[str] = mapped_column(Text, default="", server_default="")
    address2: Mapped[str] = mapped_column(Text, default="", server_default="")
    postal_code: Mapped[str] = mapped_column(String(20), default="", server_default="")
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    route_code: Mapped[str] = mapped_column(String(30), default="", server_default="")
    route_title: Mapped[str] = mapped_column(String(150), default="", server_default="")
    route_title2: Mapped[str] = mapped_column(String(150), default="", server_default="")
    region_code: Mapped[str] = mapped_column(String(30), default="", server_default="")
    region_title: Mapped[str] = mapped_column(String(150), default="", server_default="")
    region_title2: Mapped[str] = mapped_column(String(150), default="", server_default="")
    branch_code: Mapped[str] = mapped_column(String(30), default="", server_default="")
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class SavedReport(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """گزارشِ ساخته‌شده‌ی کاربر — تعریف، نه نتیجه.

    فقط *دستورِ ساخت* ذخیره می‌شود (منبعِ داده، ستون‌ها، فیلترها، مرتب‌سازی) و
    نتیجه هر بار زنده اجرا می‌شود. ذخیره‌ی خروجی یعنی گزارشی که با گذشتِ زمان
    دروغ می‌گوید؛ ذخیره‌ی تعریف یعنی گزارشی که همیشه تازه است.

    `config` عمداً JSONB است: شکلِ تعریف با هر ستونِ تازه‌ای که به منابع اضافه شود
    عوض می‌شود، و مهاجرتِ اسکیمابه‌ازای هر تغییرِ رابط کاربری هزینه‌ای است که این
    قابلیت نمی‌ارزد. اعتبارسنجی سمتِ کلاینت و در زمانِ اجرا انجام می‌شود.
    """

    __tablename__ = "saved_reports"

    name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    #: کلیدِ منبعِ داده («sales.invoices»، «inventory.products»…) — با رجیستریِ فرانت یکی است.
    source: Mapped[str] = mapped_column(String(80))
    #: ستون‌ها، فیلترها، مرتب‌سازی و گروه‌بندی.
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    #: گزارشِ نشان‌شده بالای فهرست می‌آید.
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
