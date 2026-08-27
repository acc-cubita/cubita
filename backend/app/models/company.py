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

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, String, Text
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
    #: سمت/نقش نزدِ آن طرف‌حساب («مدیر خرید»، «حسابدار»، «راننده»).
    role: Mapped[str] = mapped_column(String(120), default="", server_default="")
    phone: Mapped[str] = mapped_column(String(30), default="", server_default="")
    email: Mapped[str] = mapped_column(String(150), default="", server_default="")
    #: نفرِ اصلیِ تماس. سرویس تضمین می‌کند در هر طرف‌حساب حداکثر یکی باشد.
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))


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
