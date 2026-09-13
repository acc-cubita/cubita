"""عملیاتِ ماژولِ فروش: نوعِ فروش، قیمت‌گذاری، بسته، پورسانت، گمرک، اعلامیه.

این فایل چیزهایی را نگه می‌دارد که فاکتورِ فروش *دورش* می‌چرخند، نه خودِ فاکتور
(آن در `invoices.py` است).

**چرا تخفیف و عاملِ افزاینده یک جدول‌اند:** شکلشان دقیقاً یکی است — نام، درصد یا
مبلغ، دامنه (کالا/گروه/همه)، بازه‌ی تاریخ، فعال/غیرفعال — و تنها فرقشان جهتِ اثر
است. دو جدولِ آینه‌ای یعنی دو مسیرِ محاسبه که بی‌سروصدا از هم جدا می‌افتند؛ یک جدول
با `kind` یعنی هر اصلاحی یک‌بار انجام می‌شود. دو منوی عملیات روی همین یک جدول
می‌نویسند و یک فهرستِ مشترک با فیلتر دارند — همان استثنای دومِ قاعده‌ی نظیر.
"""
import uuid
from datetime import date as date_
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin

#: **اعلامیه‌ی قیمت جدولِ تازه ندارد.** `price_lists` از قبل هست (انبار پیشرفته) و
#: حتی به کالاها وصل شده؛ ساختنِ جدولِ دوم یعنی دو حقیقتِ ممکن برای «قیمتِ این کالا
#: چند است». صفحه‌ی «اعلامیه قیمت» همان جدول را مدیریت می‌کند، با یک ستونِ تازه‌ی
#: `effective_from` که مهاجرتِ ۰۰۸۶ به آن اضافه می‌کند.

#: جهتِ اثرِ یک عاملِ قیمت‌گذاری روی مبلغِ ردیف.
FACTOR_KINDS = ("discount", "markup")
#: مبنای عدد: درصدی از خالصِ ردیف، یا مبلغِ ثابت به ازای هر واحد.
FACTOR_MODES = ("percent", "amount")
#: دامنه‌ی اعمال — کدام ردیف‌ها مشمول‌اند.
FACTOR_SCOPES = ("all", "item", "group")
#: مبنای محاسبه‌ی پورسانت.
COMMISSION_BASES = ("net", "profit")
#: اعلامیه به سودِ ما (بدهکار کردنِ طرف) یا به زیانِ ما (بستانکار کردنِ طرف).
NOTE_KINDS = ("debit", "credit")
#: حالت‌های «تغییر فی»ِ گروهی روی اعلامیه‌ی قیمت (§۴۳).
#:
#: «بدونِ تغییر» واقعاً کاری می‌کند: قیمت‌ها را دست نمی‌زند ولی دوباره **رند**
#: می‌کند — تنها راهِ یکدست‌کردنِ رندِ یک اعلامیه‌ی از پیش ثبت‌شده.
BULK_PRICE_MODES = (
    "increase_percent",
    "increase_amount",
    "decrease_percent",
    "decrease_amount",
    "fixed",
    "none",
)


class SaleType(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """نوعِ فروش: نقدی، اعتباری، امانی، صادراتی…

    فقط یک برچسبِ دسته‌بندی نیست — مهلتِ پیش‌فرضِ تسویه و نرخِ مالیاتِ پیش‌فرض را
    هم نگه می‌دارد، چون همان چیزی است که کاربر با انتخابِ نوعِ فروش انتظار دارد
    خودکار پر شود.
    """

    __tablename__ = "sale_types"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_sale_types_tenant_name"),)

    name: Mapped[str] = mapped_column(String(80))
    #: مهلتِ تسویه به روز. ۰ = نقدی.
    due_days: Mapped[int] = mapped_column(default=0, server_default="0")
    #: نرخِ پیش‌فرضِ مالیات بر ارزش افزوده. NULL = از تنظیماتِ عمومی بیاید.
    default_tax_rate: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    goods_revenue_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=True
    )
    service_revenue_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=True
    )
    goods_discount_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=True
    )
    service_discount_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=True
    )
    addition_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=True
    )
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class DiscountItemGroup(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """گروهِ کالا برای قیمت‌گذاری — مجموعه‌ای نام‌دار از کالاها.

    چرا جدا از `Item.category`: دسته‌بندیِ کالا یک متنِ آزاد است و کارش سازمان‌دهیِ
    انبار است. گروهِ تخفیف عضویتِ صریح می‌خواهد (یک کالا می‌تواند در چند گروهِ تخفیف
    باشد و در هیچ‌کدام نباشد) و تغییرِ دسته‌بندیِ انبار نباید بی‌خبر قیمت را عوض کند.
    """

    __tablename__ = "discount_item_groups"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_discount_item_groups_tenant_name"),)

    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    members: Mapped[list["DiscountItemGroupMember"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )


class DiscountItemGroupMember(TenantMixin, UUIDPKMixin, Base):
    __tablename__ = "discount_item_group_members"
    __table_args__ = (
        UniqueConstraint("tenant_id", "group_id", "item_id", name="uq_discount_group_member"),
    )

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("discount_item_groups.id", ondelete="CASCADE"), index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"))

    group: Mapped["DiscountItemGroup"] = relationship(back_populates="members")


class PricingFactor(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """تخفیف یا عاملِ افزاینده — یک جدول، دو جهت (توضیحِ بالای فایل).

    اثرش *پیشنهادی* است: فرمِ فاکتور عددِ حاصل را پیشنهاد می‌دهد و کاربر می‌تواند
    عوضش کند. عمداً اجباری نیست، چون مسیرِ ثبتِ حسابداریِ فاکتور نباید به یک موتورِ
    قیمت‌گذاری گره بخورد که خطایش سند را وارونه می‌کند.
    """

    __tablename__ = "pricing_factors"
    __table_args__ = (
        CheckConstraint(f"kind IN {FACTOR_KINDS}", name="ck_pricing_factors_kind"),
        CheckConstraint(f"mode IN {FACTOR_MODES}", name="ck_pricing_factors_mode"),
        CheckConstraint(f"scope IN {FACTOR_SCOPES}", name="ck_pricing_factors_scope"),
        CheckConstraint("value >= 0", name="ck_pricing_factors_value_nonneg"),
    )

    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(10), index=True)
    mode: Mapped[str] = mapped_column(String(10), default="percent", server_default="percent")
    #: همیشه نامنفی؛ جهت را `kind` تعیین می‌کند نه علامتِ عدد. علامت‌دار بودن یعنی
    #: «تخفیفِ منفی» می‌شد ساخت که در عمل یک افزایشِ پنهان است.
    value: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    scope: Mapped[str] = mapped_column(String(10), default="all", server_default="all")
    item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), nullable=True
    )
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("discount_item_groups.id", ondelete="CASCADE"), nullable=True
    )
    #: بازه‌ی اعتبار. NULL یعنی بی‌کران از آن سمت.
    valid_from: Mapped[date_ | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date_ | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    description: Mapped[str] = mapped_column(Text, default="", server_default="")


class ProductBundle(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """بسته‌ی محصول — چند کالا که با هم و به یک قیمت فروخته می‌شوند.

    بسته کالای انبار نیست: موجودی ندارد و کاردکس نمی‌گیرد. هنگامِ فروش به ردیف‌های
    کالاهای عضوش باز می‌شود، تا انبار و بهای تمام‌شده همان مسیرِ همیشگی را بروند.
    """

    __tablename__ = "product_bundles"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_product_bundles_tenant_name"),)

    name: Mapped[str] = mapped_column(String(120))
    #: قیمتِ فروشِ کلِ بسته. NULL = جمعِ قیمتِ اعضا (بسته فقط برای سرعتِ ثبت است).
    bundle_price: Mapped[float | None] = mapped_column(Numeric(18, 0), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    description: Mapped[str] = mapped_column(Text, default="", server_default="")

    lines: Mapped[list["ProductBundleLine"]] = relationship(
        back_populates="bundle", cascade="all, delete-orphan"
    )


class ProductBundleLine(TenantMixin, UUIDPKMixin, Base):
    __tablename__ = "product_bundle_lines"
    __table_args__ = (
        UniqueConstraint("tenant_id", "bundle_id", "item_id", name="uq_product_bundle_line_item"),
        CheckConstraint("qty > 0", name="ck_product_bundle_lines_qty_positive"),
    )

    bundle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product_bundles.id", ondelete="CASCADE"), index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"))
    qty: Mapped[float] = mapped_column(Numeric(18, 3), default=1)

    bundle: Mapped["ProductBundle"] = relationship(back_populates="lines")


class CommissionRule(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """قاعده‌ی پورسانتِ یک فروشنده.

    فروشنده یک *کاربرِ* سامانه است (نقشِ `salesperson`)، نه طرف‌حساب — تصمیمِ صریحِ
    کاربر. پس خروجیِ محاسبه یک عددِ قابلِ پرداخت به کارمند است، نه بدهی به یک
    طرفِ بیرونی.
    """

    __tablename__ = "commission_rules"
    __table_args__ = (
        CheckConstraint(f"basis IN {COMMISSION_BASES}", name="ck_commission_rules_basis"),
        CheckConstraint("rate >= 0 AND rate <= 100", name="ck_commission_rules_rate_range"),
        UniqueConstraint("tenant_id", "salesperson_id", name="uq_commission_rules_tenant_person"),
    )

    salesperson_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    #: درصد. مبنایش `basis` است: خالصِ فاکتور یا سودِ ناخالص.
    rate: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    basis: Mapped[str] = mapped_column(String(10), default="net", server_default="net")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    description: Mapped[str] = mapped_column(Text, default="", server_default="")


class CommissionRun(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """یک محاسبه‌ی پورسانت روی یک بازه — نتیجه ذخیره می‌شود، نه هر بار از نو.

    چرا ذخیره: پورسانت مبنای پرداخت است. اگر هر بار دوباره محاسبه شود، ابطالِ یک
    فاکتورِ قدیمی عددی را که ماهِ پیش پرداخت شده بی‌خبر عوض می‌کند.
    """

    __tablename__ = "commission_runs"

    date_from: Mapped[date_] = mapped_column(Date)
    date_to: Mapped[date_] = mapped_column(Date)
    total_amount: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    note: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    lines: Mapped[list["CommissionRunLine"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class CommissionRunLine(TenantMixin, UUIDPKMixin, Base):
    __tablename__ = "commission_run_lines"

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("commission_runs.id", ondelete="CASCADE"), index=True
    )
    salesperson_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    invoice_count: Mapped[int] = mapped_column(default=0)
    #: مبنای محاسبه (خالص یا سود) — همان که در لحظه‌ی محاسبه استفاده شد.
    base_amount: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    rate: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    basis: Mapped[str] = mapped_column(String(10), default="net", server_default="net")
    amount: Mapped[float] = mapped_column(Numeric(18, 0), default=0)

    run: Mapped["CommissionRun"] = relationship(back_populates="lines")


class CustomsDeclaration(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """اظهارنامه‌ی گمرکی برای فروشِ صادراتی.

    به فاکتور گره می‌خورد ولی اجباری نیست: اظهارنامه گاهی پیش از صدورِ فاکتور
    باز می‌شود و بعد به آن وصل می‌شود.
    """

    __tablename__ = "customs_declarations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "declaration_no", name="uq_customs_declarations_tenant_no"),
    )

    declaration_no: Mapped[str] = mapped_column(String(40))
    declaration_date: Mapped[date_] = mapped_column(Date, default=date_.today)
    customs_office: Mapped[str] = mapped_column(String(120), default="", server_default="")
    #: کدِ تعرفه‌ی گمرکی (HS). متن است چون صفرِ ابتدایی دارد.
    hs_code: Mapped[str] = mapped_column(String(20), default="", server_default="")
    destination_country: Mapped[str] = mapped_column(String(80), default="", server_default="")
    #: ارزشِ اظهارشده به ارزِ اظهارنامه، و خودِ ارز.
    declared_value: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    currency_code: Mapped[str] = mapped_column(String(3), default="IRR", server_default="IRR")
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales_invoices.id", ondelete="SET NULL"), nullable=True, index=True
    )
    description: Mapped[str] = mapped_column(Text, default="", server_default="")


class CreditDebitNote(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """اعلامیه‌ی بدهکار/بستانکار — تعدیلِ حسابِ طرف مقابل بیرون از فاکتور.

    برخلافِ بقیه‌ی این فایل، این یکی **سند حسابداری می‌زند**: اعلامیه چیزی جز یک
    تعدیلِ واقعیِ مانده نیست و اگر در دفتر ننشیند، صورت‌حسابِ طرف مقابل با دفتر
    نمی‌خواند.

    **سربرگ سمت ندارد؛ ردیف‌ها دارند.** تا مهاجرتِ ۰۱۲۷ این سند یک طرف حساب و یک
    مبلغ بود و سمتِ دومش همیشه حسابِ فروش — یعنی تعدیلِ مانده، درآمد می‌ساخت، و
    تهاترِ «بدهیِ ما به فلانی در برابرِ طلبِ ما از او» اصلاً ممکن نبود. حالا هر
    ردیف یک جفتِ کامل است و سند فقط ظرفِ آن‌هاست.

    این سند **مانده‌ی حسابداری** را جابه‌جا می‌کند و نه چیزِ دیگری: نه پول
    (خزانه)، نه کالا (انبار)، نه مالیات — و **نه تسویه‌ی قلمِ باز**. اینکه این
    ۲۰ میلیون بابتِ کدام فاکتور بوده، دامنه‌ی `settlements` است و تخصیصِ صریح
    می‌خواهد؛ کم‌شدنِ مانده به‌خودیِ‌خود هیچ فاکتوری را تسویه‌شده نمی‌کند.
    """

    __tablename__ = "credit_debit_notes"
    __table_args__ = (
        #: `NULL` از این قید رد می‌شود — و ردیف‌های تازه دقیقاً همین‌اند.
        CheckConstraint(f"kind IN {NOTE_KINDS}", name="ck_credit_debit_notes_kind"),
        CheckConstraint("amount > 0", name="ck_credit_debit_notes_amount_positive"),
        UniqueConstraint("tenant_id", "number", name="uq_credit_debit_notes_tenant_number"),
    )

    number: Mapped[int | None] = mapped_column(nullable=True, index=True)
    note_date: Mapped[date_] = mapped_column(Date, default=date_.today)

    #: **میراثِ شکلِ تک‌سمتی — دیگر نوشته نمی‌شوند.** ردیف‌های پیش از ۰۱۲۷ سمت و
    #: طرف حسابشان را این‌جا داشتند. ستون می‌ماند تا آن ردیف‌ها خوانا بمانند؛ کدِ
    #: تازه هیچ‌وقت به این دو نگاه نمی‌کند و سمت را از ردیف‌ها می‌گیرد.
    kind: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=True, index=True
    )

    #: جمعِ ردیف‌ها — عکسِ لحظه‌ی ثبت، نه منبعِ حقیقت. همان الگوی
    #: `Settlement.total_amount`: فهرست بدونِ جمع‌زدنِ دوباره خوانده می‌شود و
    #: سرویس این دو را مقابلِ هم می‌گذارد.
    amount: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    #: معادلِ ریالیِ همان جمع — جمعِ `base_amount`ِ ردیف‌ها و دقیقاً جمعِ دفتر.
    base_amount: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")

    #: ارزِ سند و نرخش (مهاجرتِ ۰۱۳۶). مبلغِ ردیف به ارزِ سند است و دفتر به ارزِ
    #: پایه می‌نشیند: `مبلغ × نرخ`، ردیف‌به‌ردیف گرد — همان قراردادِ رسید و اعلامیه
    #: پرداخت. نرخ عکسِ لحظه‌ی ثبت است؛ عوض‌شدنِ نرخِ روز سندِ قدیمی را تکان نمی‌دهد.
    currency_code: Mapped[str] = mapped_column(String(3), default="IRR", server_default="IRR")
    exchange_rate: Mapped[float] = mapped_column(Numeric(18, 4), default=1, server_default="1")
    reason: Mapped[str] = mapped_column(Text, default="", server_default="")
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales_invoices.id", ondelete="SET NULL"), nullable=True
    )
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True, index=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    #: همان سه ستونِ `VoidableMixin`. خودِ میکسین استفاده نشد چون `voided_at` از
    #: پیش از آن روی این جدول نشسته و تعریفِ میکسین نمایه‌ای دارد که این ستون ندارد.
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    void_reason: Mapped[str] = mapped_column(Text, default="", server_default="")

    lines: Mapped[list["CreditDebitNoteLine"]] = relationship(
        back_populates="note", cascade="all, delete-orphan", order_by="CreditDebitNoteLine.seq"
    )


class CreditDebitNoteLine(TenantMixin, UUIDPKMixin, Base):
    """یک تعدیل: این حساب/طرف بدهکار، آن حساب/طرف بستانکار، به این مبلغ.

    **ردیف ذاتاً تراز است** چون یک مبلغ دارد که هر دو سمت را می‌سازد؛ پس سندِ
    چندردیفی هم بی‌آنکه کسی حسابش را نگه دارد تراز می‌ماند.

    **طرف حساب اختیاری است، حساب نه.** سمتِ مقابلِ یک تعدیل همیشه طرف حساب ندارد
    (مثلاً تخفیفِ اعطایی)، ولی همیشه یک معین دارد. و هر سمتی که طرف حساب دارد،
    تفصیلیِ همان طرف روی ردیفِ سند می‌نشیند — وگرنه کارتِ حسابِ او این تعدیل را
    نمی‌بیند، که دقیقاً همان چیزی است که این سند برایش ساخته شده.

    **نقشِ طرف حساب، معینِ پیش‌فرض را تعیین می‌کند** (مشتری ← دریافتنی،
    تأمین‌کننده ← پرداختنی) ولی قفلش نمی‌کند: کاربر می‌تواند از میانِ معین‌های
    مجازِ طرف مقابل یکی دیگر بردارد. پیش‌فرض شاهد دارد، «تنها گزینه» نه.
    """

    __tablename__ = "credit_debit_note_lines"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_credit_debit_note_lines_amount_positive"),
        CheckConstraint("base_amount > 0", name="ck_credit_debit_note_lines_base_amount_positive"),
        #: سندی که همان حساب و همان تفصیلی را در دو سمت می‌گذارد هیچ‌چیز را
        #: جابه‌جا نمی‌کند. بی‌صدا پذیرفتنش یعنی ردیفی در دفتر که معنی ندارد.
        CheckConstraint(
            "debit_account_id <> credit_account_id "
            "OR debit_contact_id IS DISTINCT FROM credit_contact_id",
            name="ck_credit_debit_note_lines_not_noop",
        ),
        UniqueConstraint("tenant_id", "note_id", "seq", name="uq_credit_debit_note_lines_seq"),
    )

    note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("credit_debit_notes.id", ondelete="CASCADE"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer, default=1)

    debit_contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=True, index=True
    )
    debit_account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id"))
    credit_contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=True, index=True
    )
    credit_account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id"))

    #: به ارزِ سند.
    amount: Mapped[float] = mapped_column(Numeric(18, 0))
    #: معادلِ ریالیِ همین ردیف — همان عددی که دو سمتِ سندِ حسابداری می‌گیرند.
    base_amount: Mapped[float] = mapped_column(Numeric(18, 0))
    description: Mapped[str] = mapped_column(Text, default="", server_default="")

    note: Mapped["CreditDebitNote"] = relationship(back_populates="lines")
