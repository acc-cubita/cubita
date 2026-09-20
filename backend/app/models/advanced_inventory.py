"""انبار پیشرفته — لیستِ قیمت و ردیابیِ بچ/تاریخِ انقضا.

سه جدولِ مستأجرمحور (RLS):
  - price_lists: لیست‌های قیمت (عمده، خرده، ویژه، ...).
  - price_list_items: قیمتِ هر کالا در هر لیست (جایگزینِ قیمتِ پایه هنگام فروش/صندوق).
  - stock_batches: ثبتِ بچ/سریِ کالا با تاریخِ انقضا — برای دیده‌بانی و هشدارِ انقضا.

**این توضیح تا مهاجرتِ ۰۱۷۱ درست بود و دیگر نیست.** `stock_batches` یک «دفترِ
ثبت» بود که فروش و خروج اصلاً لمسش نمی‌کردند، پس مانده‌اش از اولین فروش به بعد
دروغ می‌گفت. حالا مانده از `stock_ledger.batch_id` مشتق می‌شود و ستونِ `qty`
فقط برای بارهای پیش از ردیابی زنده مانده — شرحِ کامل در
[services/batches.py](../services/batches.py).

موتورِ **بها** همان میانگینِ موزونِ سراسری است و عوض نشده: بچ *مقدار* را ردیابی
می‌کند، نه قیمت.
"""
import uuid
from datetime import date as date_, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin


class PriceList(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """یک لیستِ قیمت (مثلاً «عمده» یا «خرده»)."""

    __tablename__ = "price_lists"

    name: Mapped[str] = mapped_column(String(200))
    #: تاریخِ اجرای اعلامیه. قیمتِ دیروز باید بماند تا فاکتورهای گذشته قابلِ توضیح
    #: بمانند، پس اعلامیه‌ی تازه کنارِ قبلی می‌نشیند نه به‌جایش.
    effective_from: Mapped[date_] = mapped_column(Date, default=date_.today, server_default=func.current_date())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    items: Mapped[list["PriceListItem"]] = relationship(
        back_populates="price_list", cascade="all, delete-orphan"
    )


class PriceListItem(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """قیمتِ یک کالا در یک لیستِ قیمت — **در یک زمینه‌ی مشخص** (§۳۷–§۴۲).

    **چرا دیگر «هر کالا یک قیمت» نیست.** §۳۸ صریح است: `product.sale_price = 100`
    مدلِ کافی‌ای نیست. یک کالا می‌تواند هم‌زمان قیمتِ عمده به ریال، قیمتِ خرده به
    ریال و قیمتِ صادراتی به دلار داشته باشد — و قیمتِ کارتن با قیمتِ عدد یکی
    نیست (§۴۱).

    `NULL` در هر بُعد یعنی «هر مقداری» — پس ردیف‌های موجود، که هر چهار بُعدشان
    خالی است، دقیقاً مثلِ امروز روی همه‌ی زمینه‌ها می‌نشینند.

    **نوعِ فروش، ارز و گروهِ مشتری از داده‌ی موجود می‌آیند (§۳۹ §۴۰).** فصل منع
    می‌کند که زیرسیستمِ قیمت تعریفِ موازیِ خودش را بسازد.

    و §۴۳: این *سیاست* است. قیمتِ واقعیِ ثبت‌شده روی ردیفِ فاکتور snapshot خودش
    را دارد و با عوض‌شدنِ این جدول تغییر نمی‌کند.
    """

    __tablename__ = "price_list_items"
    # tenant_id در قید هست تا با گاردِ «ایندکسِ یکتا باید مستأجر داشته باشد» بخواند
    # (price_list خودش مستأجرمحور است، ولی قید باید صراحتاً مستأجر را ببیند).
    #
    # یکتایی روی **کلِ زمینه** است، نه فقط کالا. `COALESCE` لازم است چون در
    # Postgres دو `NULL` در ایندکسِ یکتا با هم برابر شمرده نمی‌شوند — بی آن،
    # همان ردیفِ «بی‌زمینه» می‌توانست بی‌نهایت بار تکرار شود.
    __table_args__ = (
        Index(
            "uq_price_list_items_context",
            "tenant_id",
            "price_list_id",
            text("COALESCE(item_id, '00000000-0000-0000-0000-000000000000'::uuid)"),
            text("COALESCE(item_group_id, '00000000-0000-0000-0000-000000000000'::uuid)"),
            text("COALESCE(sale_type_id, '00000000-0000-0000-0000-000000000000'::uuid)"),
            text("COALESCE(unit_id, '00000000-0000-0000-0000-000000000000'::uuid)"),
            text("COALESCE(contact_group_id, '00000000-0000-0000-0000-000000000000'::uuid)"),
            "currency_code",
            unique=True,
        ),
        #: قاعده‌ای که نه کالا را نام می‌برد نه گروهش را، روی *همه‌ی* کالاها می‌نشیند —
        #: یعنی یک قیمتِ سراسریِ ناخواسته. این قید جلوی ساختنش را می‌گیرد.
        CheckConstraint(
            "item_id IS NOT NULL OR item_group_id IS NOT NULL",
            name="ck_price_list_items_has_target",
        ),
    )

    price_list_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("price_lists.id", ondelete="CASCADE"), index=True
    )
    #: قاعده یا یک کالای مشخص را هدف می‌گیرد یا یک **گروهِ فروشِ کالا** (§۱۴) — نه هیچ‌کدام.
    #: قاعده‌ی کالامحور بر قاعده‌ی گروه می‌چربد، چون یک بُعدِ صریح‌ترِ بیشتر نام برده؛
    #: همان معیاری که از قبل بینِ چهار بُعدِ دیگر داوری می‌کند، نه ترتیبی تازه.
    item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id"), nullable=True, index=True
    )
    item_group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("discount_item_groups.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    price: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")

    #: ابعادِ زمینه (§۳۹ §۴۰ §۴۱). `NULL` = «هر مقداری».
    sale_type_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sale_types.id", ondelete="CASCADE"), nullable=True
    )
    unit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("units_of_measure.id", ondelete="CASCADE"), nullable=True
    )
    contact_group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contact_groups.id", ondelete="CASCADE"), nullable=True
    )
    #: ارز صریح است، نه محاسبه‌ی تسعیر (§۴۰): شرکت می‌تواند واقعاً لیستِ دلاریِ
    #: مستقل داشته باشد که با نرخِ روز از ریال درنمی‌آید.
    currency_code: Mapped[str] = mapped_column(String(3), default="IRR", server_default="IRR")

    #: **کنترلِ تغییرِ نرخ (§۴۲).**
    #:
    #: صفر یعنی **بی‌حد** — یعنی رفتارِ امروز، پس هیچ فروشی یک‌شبه مسدود نمی‌شود.
    #: فقط کسی که صریحاً حد بگذارد کنترل می‌گیرد.
    allow_rate_change: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    #: §۲۵ — «امکانِ تغییرِ تخفیف در فاکتور» پرچمِ **جدایی** است.
    #:
    #: قفل‌کردنِ نرخ و قفل‌کردنِ تخفیف یک چیز نیستند: فروشنده‌ای که حق ندارد فی را
    #: عوض کند ممکن است حقِ تخفیف‌دادن داشته باشد، و برعکس. یک پرچمِ مشترک یعنی
    #: هر دو سیاست با هم باز یا بسته شوند — که هیچ‌کدامِ آن دو خواسته نیست.
    allow_discount_change: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    max_increase_percent: Mapped[float] = mapped_column(
        Numeric(5, 2), default=0, server_default="0"
    )
    max_decrease_percent: Mapped[float] = mapped_column(
        Numeric(5, 2), default=0, server_default="0"
    )

    #: §۲۲ «درصدِ اضافات» — **ذخیره و نمایش داده می‌شود، اعمال نمی‌شود.**
    #:
    #: §۲۳ صریح است که ربطش به «اضافاتِ فاکتور» و «عاملِ افزاینده» هنوز معلوم
    #: نیست. تا آن روز اضافه‌کردنش به مبلغِ ردیف یعنی حدس‌زدنِ یک قاعده‌ی مالی —
    #: پس این‌جا فقط پیکربندیِ ساخت‌یافته می‌ماند و به کاربر نشان داده می‌شود.
    addition_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=0, server_default="0")

    price_list: Mapped["PriceList"] = relationship(back_populates="items")


#: وضعیتِ کنترلِ کیفیت و وضعیتِ انسداد — دو محورِ مستقل (مهاجرتِ ۰۱۷۲).
QC_STATUSES = ("passed", "pending", "failed")
HOLD_STATUSES = ("none", "blocked", "recalled")
QC_STATUS_LABELS = {"passed": "تأییدشده", "pending": "در انتظارِ کنترل", "failed": "مردود"}
HOLD_STATUS_LABELS = {"none": "آزاد", "blocked": "مسدود", "recalled": "فراخوان‌شده"}


class StockBatch(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """یک **بارِ ورودیِ کالا** (بچ/سری) — هر خرید جداگانه ثبت می‌شود تا اگر کسری/معیوب/
    ضایعات پیش آمد، معلوم شود کدام بار مشکل داشته است. همچنین تاریخِ انقضا و سریال‌های
    کارتنِ همان بار را نگه می‌دارد.

    `qty` = مقدارِ **باقی‌مانده‌ی سالمِ** این بار (received_qty منهای کسری/معیوبِ ثبت‌شده).
    `received_qty` = مقدارِ اولیه‌ای که هنگامِ ورود ثبت شد. اختلافشان = مجموعِ کسری/معیوب.
    این جدول «دفترِ ردیابیِ بار» است، نه موتورِ مصرفِ بچ‌محور: فروش، بچِ خاصی را مصرف
    نمی‌کند؛ موتورِ اصلیِ موجودی همان میانگینِ موزون می‌ماند.
    """

    __tablename__ = "stock_batches"

    __table_args__ = (
        CheckConstraint(f"qc_status IN {QC_STATUSES}", name="ck_stock_batches_qc_status"),
        CheckConstraint(f"hold_status IN {HOLD_STATUSES}", name="ck_stock_batches_hold_status"),
        #: پرسشِ همیشگیِ FEFO: «بارهای این کالا در این انبار، به ترتیبِ انقضا».
        Index("ix_stock_batches_fefo", "tenant_id", "item_id", "warehouse_id", "expiry_date"),
    )

    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"), index=True)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id"))
    batch_number: Mapped[str] = mapped_column(String(80))
    expiry_date: Mapped[date_ | None] = mapped_column(Date, nullable=True, index=True)
    qty: Mapped[float] = mapped_column(Numeric(18, 3), default=0, server_default="0")
    #: مقدارِ اولیه‌ی ورودیِ این بار (پیش از کسر کسری/معیوب). با qty برابر است تا وقتی
    #: تعدیلی ثبت شود.
    received_qty: Mapped[float] = mapped_column(Numeric(18, 3), default=0, server_default="0")
    #: بهای واحدِ این بار (ریالِ صحیح) — از فاکتورِ خرید snapshot می‌شود؛ برای مبلغِ زیانِ
    #: کسری/معیوب و گزارشِ ارزشِ بار. همان «قیمتِ خرید» است.
    #: چهار رقم اعشار، هم‌راستا با `StockLedger.unit_cost` — همان عدد است و
    #: نباید در دو جا دو جور گِرد شود (مهاجرت ۰۱۳۱).
    unit_cost: Mapped[float] = mapped_column(Numeric(18, 4), default=0, server_default="0")
    #: قیمتِ مصرف‌کننده (فروشِ پیشنهادی) برای این بار — تا حاشیه‌ی سود (فروش − خرید) معلوم
    #: باشد. هنگامِ خریدِ بازار خودکار از قیمتِ لیستینگ می‌آید؛ در ورودِ دستی وارد می‌شود. ۰ = نامشخص.
    consumer_price: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    #: تاریخِ تولیدِ این بار (اختیاری) — کنارِ تاریخِ انقضا برای ردیابیِ عمرِ کالا.
    production_date: Mapped[date_ | None] = mapped_column(Date, nullable=True)
    #: منشأِ بار: purchase_invoice | manual | marketplace. با source_id به سندِ مبدأ می‌رسد.
    source_type: Mapped[str] = mapped_column(String(30), default="manual", server_default="manual")
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    received_date: Mapped[date_] = mapped_column(Date)
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    #: شماره‌ی باری که **تأمین‌کننده** روی بسته زده — با شماره‌ی داخلیِ ما یکی
    #: نیست و در فراخوانِ کارخانه همین عدد اعلام می‌شود، نه مالِ ما.
    supplier_batch_code: Mapped[str] = mapped_column(String(80), default="", server_default="")
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=True
    )
    #: کجای انبار. تهی = ثبت‌نشده، و برای انبارِ کوچک حالتِ کاملاً عادی است (§۲۸).
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouse_locations.id", ondelete="SET NULL"), nullable=True
    )
    #: بارِ مبدأ وقتی این بار با **انتقال بینِ انبار** ساخته شده.
    #:
    #: `StockBatch` به `(کالا، انبار)` بسته است، پس انتقال باید در مقصد بارِ
    #: آینه بسازد وگرنه کالا آن‌طرفِ مرز بی‌بچ ظاهر می‌شود. این ستون زنجیره را
    #: نگه می‌دارد تا «این بار از کجا آمد؟» در مقصد هم جواب داشته باشد.
    parent_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stock_batches.id"), nullable=True
    )

    #: **وضعیت: سه ستونِ عمود بر هم، نه یک ستونِ چندحالته.**
    #:
    #: فصل ۱۲ وضعیت خواسته بود ولی خودش هم گفت «نباید فقط به status تکیه شود».
    #: آن ۱۲ تا سه واقعیتِ مستقل‌اند — بار می‌تواند هم‌زمان منتظرِ QC **و**
    #: فراخوان‌شده باشد — و بقیه‌شان (`near_expiry`، `depleted`، `fully_reserved`)
    #: از عدد و تاریخ مشتق می‌شوند. ستونی که بتواند با واقعیت اختلاف پیدا کند،
    #: بالاخره پیدا می‌کند؛ پس فقط **نیتِ انسان** ذخیره می‌شود.
    #:
    #: `passed` پیش‌فرض است نه `pending`: هر بارِ موجود امروز قابلِ استفاده است و
    #: کسب‌وکارِ بدونِ QC هرگز این فیلد را نمی‌بیند.
    qc_status: Mapped[str] = mapped_column(String(20), default="passed", server_default="passed")
    hold_status: Mapped[str] = mapped_column(String(20), default="none", server_default="none")
    hold_reason: Mapped[str] = mapped_column(Text, default="", server_default="")
    held_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    held_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    #: «کارم با این بار تمام است» — حتی با ۰٫۳ مانده. مشتق‌شدنی نیست چون تصمیم
    #: است، نه نتیجه‌ی عدد.
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    serials: Mapped[list["StockBatchSerial"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan", order_by="StockBatchSerial.serial"
    )


class StockBatchSerial(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """سریالِ کارتنِ یک بار — هر کارتن یک ردیف. اپراتورِ انبار دستی اضافه می‌کند
    (یا با تولیدِ توالیِ خودکار). وضعیت: ok = سالم، defect = معیوب."""

    __tablename__ = "stock_batch_serials"

    __table_args__ = (
        UniqueConstraint("tenant_id", "batch_id", "serial", name="uq_batch_serials_batch_serial"),
    )

    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stock_batches.id", ondelete="CASCADE"), index=True
    )
    serial: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default="ok", server_default="ok")  # ok | defect
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")

    batch: Mapped["StockBatch"] = relationship(back_populates="serials")
    events: Mapped[list["SerialEvent"]] = relationship(
        back_populates="serial_row",
        cascade="all, delete-orphan",
        order_by="SerialEvent.entry_date, SerialEvent.created_at",
    )


#: رویدادهایی که یک سریال می‌تواند بگیرد.
SERIAL_EVENT_TYPES = ("receipt", "issue", "return_in", "return_out", "adjust")
SERIAL_EVENT_LABELS = {
    "receipt": "ورود",
    "issue": "خروج",
    "return_in": "برگشت به انبار",
    "return_out": "برگشت از انبار",
    "adjust": "تعدیل",
}
#: رویدادهایی که سریال را از انبار بیرون می‌برند — مبنای «الان کجاست؟».
SERIAL_OUTBOUND_EVENTS = frozenset({"issue", "return_out"})


class SerialEvent(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """یک اتفاق در زندگیِ یک سریال — ورود، خروج، برگشت.

    **دفتر است، نه موقعیت.** تا پیش از مهاجرتِ ۰۱۴۵ سریال فقط به بچِ ورودش وصل
    بود و فروش هیچ‌وقت لمسش نمی‌کرد؛ پرسشِ «SN-1 به چه کسی فروخته شد؟» جوابی
    نداشت و جوابِ سیستم تا ابد «در همان بچِ اول» می‌ماند.

    راهِ ساده‌تر یک ستونِ `current_document_id` بود — و غلط: با هر حرکت بازنویسی
    می‌شد و تاریخچه را می‌بلعید. همان دلیلی که موجودیِ کوبیتا از دفتر مشتق
    می‌شود و در یک ستون ذخیره نمی‌شود. **موقعیتِ فعلی از آخرین رویداد مشتق
    می‌شود.**
    """

    __tablename__ = "serial_events"

    __table_args__ = (
        CheckConstraint(f"event_type IN {SERIAL_EVENT_TYPES}", name="ck_serial_events_type"),
        #: **یک سریال روی یک سند بیش از یک رویداد نمی‌گیرد.** بی این، تلاشِ
        #: دوباره‌ی شبکه دو رویدادِ اقتصادی می‌ساخت و «کجاست؟» دو جواب پیدا
        #: می‌کرد. جزئی است چون رویدادِ بی‌سند (تعدیلِ دستی) می‌تواند تکرار شود.
        Index(
            "uq_serial_events_serial_source",
            "tenant_id",
            "serial_id",
            "source_type",
            "source_id",
            unique=True,
            postgresql_where=text("source_id IS NOT NULL"),
        ),
    )

    serial_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stock_batch_serials.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(20))
    #: سندی که این رویداد را ساخت — همان واژگانِ `valuation.SOURCE_LABELS`، تا
    #: ردیابی از سریال به سند همان مسیرِ کاردکس باشد، نه یک نگاشتِ دوم.
    source_type: Mapped[str] = mapped_column(String(50), default="", server_default="")
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    #: تاریخِ **مؤثرِ** سند، نه تاریخِ ثبت. سندِ پیش‌تاریخ سرِ جای زمانی‌اش
    #: می‌نشیند — همان قاعده‌ای که کاردکس دارد.
    entry_date: Mapped[date_] = mapped_column(Date)
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    serial_row: Mapped["StockBatchSerial"] = relationship(back_populates="events")
