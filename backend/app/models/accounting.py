import uuid
from datetime import date as date_
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin, VoidableMixin
from app.models.tenant import TenantMixin

ACCOUNT_TYPES = ("asset", "liability", "equity", "income", "expense")

#: ماهیتِ حساب — سمتی که مانده‌ی حساب طبیعتاً باید در آن باشد. «صندوق» بستانکار
#: شدن یعنی جایی اشتباه ثبت شده. `any` = حسابی که هر دو سمت برایش طبیعی است
#: (حسابِ واسط، تسویه، طرفِ‌حسابی که هم می‌خرد هم می‌فروشد).
ACCOUNT_NATURES = ("debit", "credit", "any")
ACCOUNT_NATURE_LABELS = {"debit": "بدهکار", "credit": "بستانکار", "any": "مهم نیست"}

#: نوع‌هایی که در **ترازنامه** می‌نشینند؛ بقیه (درآمد و هزینه) در **سود و زیان**.
#: عمداً ستون نیست: صددرصد از `type` مشتق می‌شود و ذخیره‌کردنش یعنی دو منبعِ حقیقت
#: که می‌توانند با هم نخوانند — حسابی با `type='asset'` و صورتِ «سود و زیان».
BALANCE_SHEET_TYPES = ("asset", "liability", "equity")
STATEMENT_TYPE_LABELS = {"balance_sheet": "ترازنامه‌ای", "income_statement": "سود و زیانی"}

#: ماهیتِ ضمنیِ هر نوعِ حساب. `nature=NULL` یعنی «همین را حساب کن» — پس هیچ حسابِ
#: موجودی با این مهاجرت معنایش عوض نمی‌شود و کسی مجبور نیست چارتش را دوباره پر کند.
NATURE_BY_TYPE = {
    "asset": "debit",
    "expense": "debit",
    "liability": "credit",
    "equity": "credit",
    "income": "credit",
}


#: وضعیتِ سند. «موقت» یعنی ثبت شده ولی هنوز بازبینی/تأیید نشده؛ «دائم» یعنی
#: قطعی‌شده. هر دو در دفتر و گزارش‌ها دیده می‌شوند — تفاوت در قابلِ‌بازبینی‌بودن
#: است، نه در اثرِ مالی.
ENTRY_STATUSES = ("temporary", "permanent")
ENTRY_STATUS_LABELS = {"temporary": "موقت", "permanent": "دائم"}


class Account(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """یک گره در چارت حساب‌ها. is_group=True یعنی سرفصل (فقط برای دسته‌بندی)، نه ثبت سند مستقیم روی آن."""

    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint(f"type IN {ACCOUNT_TYPES}", name="ck_accounts_type"),
        UniqueConstraint("tenant_id", "code", name="uq_accounts_tenant_code"),
        # هر نقش در هر کسب‌وکار فقط یک حساب دارد. بدون این قید، دو حساب با نقش
        # «صندوق» ممکن بود وجود داشته باشد و ثبت خودکار بی‌قاعده یکی را برمی‌داشت.
        UniqueConstraint("tenant_id", "system_role", name="uq_accounts_tenant_system_role"),
        CheckConstraint(f"nature IS NULL OR nature IN {ACCOUNT_NATURES}", name="ck_accounts_nature"),
        # «تسعیر پذیر» بدونِ «ارزی» بی‌معناست؛ در فرم هم تا ارزی تیک نخورد خاکستری است.
        CheckConstraint("NOT fx_revaluable OR is_fx", name="ck_accounts_fx_revaluable"),
    )

    code: Mapped[str] = mapped_column(String(20), index=True)
    #: نقش معنایی برای ثبت خودکار (cash، inventory، cogs و…). برای حساب‌های معمولی
    #: و سرفصل‌ها NULL است — قید یکتا روی NULL اعمال نمی‌شود، پس تعدادشان آزاد است.
    system_role: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    #: عنوانِ دوم (معمولاً انگلیسی) برای گزارشِ دوزبانه و صورت‌های مالیِ ارزی.
    #: خالی = ندارد؛ هیچ‌جا اجباری نیست و روی نمایشِ فارسی اثر ندارد.
    name2: Mapped[str] = mapped_column(String(200), default="", server_default="")
    type: Mapped[str] = mapped_column(String(20))
    #: ماهیتِ *صریح*. NULL یعنی از `type` مشتق شود (`NATURE_BY_TYPE`) — الگوی
    #: همیشگیِ این مخزن برای «پیش‌فرضِ سرویس». فقط گزارش می‌دهد؛ هیچ ثبتی را
    #: نمی‌شکند، چون خلافِ ماهیت شدن گاهی واقعاً درست است (اضافه‌برداشتِ بانکی).
    nature: Mapped[str | None] = mapped_column(String(10), nullable=True)
    is_group: Mapped[bool] = mapped_column(default=False)
    #: حسابِ غیرفعال از فهرست‌های ثبتِ سند پنهان می‌شود ولی تاریخچه‌اش می‌ماند —
    #: راهی برای بایگانیِ حساب‌هایی که دیگر استفاده نمی‌شوند ولی سند دارند و پاک
    #: نمی‌شوند. پیش‌فرض فعال؛ حساب‌های موجود بی‌تغییر می‌مانند.
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")

    # ── ویژگی‌های حساب ────────────────────────────────────────────────────────
    # شش پرچمی که فرمِ ویرایشِ حساب نشان می‌دهد. هیچ‌کدام تنهایی مانعِ ثبت نیستند؛
    # هرکدام یک رفتارِ مشخص را باز یا محدود می‌کند و پیش‌فرضشان طوری است که چارتِ
    # موجود بی‌تغییر بماند.

    #: کنترلِ ماهیت طی دوره — «این حساب را رصد کن». جدا از خودِ `nature` است: آن
    #: می‌گوید ماهیت *چیست*، این می‌گوید *پیگیری‌اش کن*. گزارشِ خلافِ ماهیت با
    #: پارامترِ `controlled_only` می‌تواند فقط همین‌ها را نشان دهد.
    nature_control: Mapped[bool] = mapped_column(default=False, server_default="false")

    #: حسابِ ارزی — مبنای نمایشِ فیلدهای ارز روی ردیفِ سند.
    is_fx: Mapped[bool] = mapped_column(default=False, server_default="false")
    #: تسعیرپذیر. فقط روی حسابِ ارزی معنا دارد (قیدِ `ck_accounts_fx_revaluable`).
    #: **انصراف است، نه انتخاب**: سندِ تسعیر همه‌ی حساب‌های دارای ردیفِ ارزی را
    #: می‌بیند، مگر حسابی صریحاً `is_fx` باشد و این خاموش — یعنی «ارزی هست ولی
    #: تسعیرش نکن». اگر انتخاب بود، پیش‌فرضِ false صفحه‌ی تسعیر را خالی می‌کرد.
    fx_revaluable: Mapped[bool] = mapped_column(default=False, server_default="false")

    #: تفصیلی‌پذیر — ردیفِ سندِ این حساب **باید** تفصیلی (`analytic_id`) داشته باشد.
    #:
    #: این همان «تفصیلیِ شناور»ِ حسابداریِ ایران است: بُعدی متغیر و پرتعداد (۵۰۰
    #: مشتری) که در فهرستِ جدا نگه داشته می‌شود و لحظه‌ی ثبتِ سند به حساب می‌چسبد.
    #: **با زیرشاخه‌ی درختی اشتباه نشود** — آن یکی بخشی از کدینگِ چهارسطحی است
    #: (بانک ملی زیرِ بانک)، کم‌تعداد و ثابت، و قیدِ خودش را دارد: والد نباید سندِ
    #: مستقیم خورده باشد. این پرچم هیچ کاری به ساختِ زیرحساب ندارد.
    #:
    #: قفلش یک‌طرفه است: روشن‌کردن همیشه آزاد، خاموش‌کردن فقط تا وقتی هیچ ردیفی از
    #: این حساب تفصیلی نگرفته باشد.
    accepts_tafsili: Mapped[bool] = mapped_column(default=False, server_default="false")

    #: پیگیری — «شماره پیگیری» و «تاریخ پیگیری» را روی ردیفِ سندِ این حساب باز
    #: می‌کند. ردیفِ حسابی که این پرچم را ندارد پیگیری نمی‌پذیرد.
    has_tracking: Mapped[bool] = mapped_column(default=False, server_default="false")

    #: نمایش در گزارشاتِ مدیریتی. پیش‌فرض *روشن* تا هیچ حسابی بی‌صدا از گزارش
    #: نیفتد؛ خاموش‌کردنش کارِ آگاهانه‌ی کاربر است (حساب‌های واسط و انتظامی).
    in_management_reports: Mapped[bool] = mapped_column(default=True, server_default="true")

    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=True
    )

    parent: Mapped["Account | None"] = relationship(remote_side="Account.id", back_populates="children")
    children: Mapped[list["Account"]] = relationship(back_populates="parent")

    @property
    def effective_nature(self) -> str:
        """ماهیتی که گزارش با آن می‌سنجد: مقدارِ صریح، وگرنه مشتق از نوعِ حساب."""
        return self.nature or NATURE_BY_TYPE.get(self.type, "any")

    @property
    def statement_type(self) -> str:
        """صورتِ مالیِ این حساب — ترازنامه‌ای یا سود و زیانی.

        مشتق است نه ذخیره‌شده. اگر روزی حساب‌های *انتظامی* اضافه شوند، آن‌وقت این
        اشتقاق می‌شکند و تازه آن‌جا ستونِ صریح موجه می‌شود — نه پیش از آن.
        """
        return "balance_sheet" if self.type in BALANCE_SHEET_TYPES else "income_statement"


class JournalEntry(TenantMixin, VoidableMixin, UUIDPKMixin, TimestampMixin, Base):
    """سند حسابداری: واحد اتمی هر رویداد مالی. دفتر روزنامه/کل/تراز همه از JournalLine مشتق می‌شوند."""

    __tablename__ = "journal_entries"

    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_journal_entries_tenant_number"),
        UniqueConstraint("tenant_id", "atf_number", name="uq_journal_entries_tenant_atf"),
        CheckConstraint(f"status IN {ENTRY_STATUSES}", name="ck_journal_entries_status"),
    )

    number: Mapped[int | None] = mapped_column(nullable=True, index=True)  # شماره رسمی، فقط سرور اختصاص می‌دهد

    #: **شماره عطف** — هویتِ ثابتِ سند. سرور لحظه‌ی ثبت و به‌ترتیبِ ورود می‌دهدش و
    #: هیچ عملیاتی عوضش نمی‌کند؛ «شماره‌گذاری مجدد» فقط `number` را جابه‌جا می‌کند.
    #:
    #: چرا دو شماره: شماره‌ی سند باید با *تاریخ* بخواند (دفترداری آخرِ ماه مرتبش
    #: می‌کند)، ولی ارجاعِ بیرونی — چاپِ سند، پیوستِ پرونده، نامه‌ی حسابرس — به
    #: شماره‌ای نیاز دارد که هرگز تکان نخورد. یک ستون نمی‌تواند هر دو باشد.
    #:
    #: nullable چون سندهای پیش از مهاجرتِ ۰۰۸۵ در همان مهاجرت پر می‌شوند و ستون
    #: نمی‌تواند وسطِ backfill غیرِ NULL باشد؛ از این به بعد هر سند عطف دارد.
    atf_number: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)

    #: **شماره فرعی** — ارجاعِ آزادِ کاربر: شماره‌ی سند در سیستمِ قبلی، شماره‌ی
    #: پرونده، کدِ دسته. عمداً متن است نه عدد (کاربر «ب-۱۴۰۴/۷» هم می‌نویسد)، عمداً
    #: یکتا نیست (چند سندِ یک دسته یک شماره‌ی فرعی می‌گیرند — همان کاری که باهاش
    #: می‌کنند)، و عمداً اختیاری. NULL = خالی.
    sub_number: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    entry_date: Mapped[date_] = mapped_column(Date, default=date_.today)
    description: Mapped[str] = mapped_column(Text, default="")

    # منشأ سند: مثلاً "sales_invoice" / "manual" / "payroll" برای ردیابی این‌که کدام ماژول این سند را خودکار ساخته
    source_type: Mapped[str] = mapped_column(String(50), default="manual")
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    #: سندِ تازه موقت متولد می‌شود و با «تبدیل اسناد موقت به دائم» یا با بستنِ دوره
    #: قطعی می‌شود. سندِ دائم دیگر ادغام/بازشماره‌گذاری نمی‌شود — فقط ابطال با معکوس.
    status: Mapped[str] = mapped_column(String(12), default="temporary", server_default="temporary")
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finalized_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    #: اگر این سند، معکوسِ سند دیگری باشد. رابطه یک‌طرفه و صریح است تا در دفتر
    #: روزنامه بتوان جفتِ «اصلی و معکوس» را نشان داد؛ جمعشان همیشه صفر است.
    reverses_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True, index=True
    )

    lines: Mapped[list["JournalLine"]] = relationship(
        back_populates="entry", cascade="all, delete-orphan", order_by="JournalLine.id"
    )


class JournalLine(TenantMixin, UUIDPKMixin, Base):
    __tablename__ = "journal_lines"
    __table_args__ = (
        CheckConstraint("debit >= 0 AND credit >= 0", name="ck_journal_lines_nonnegative"),
        CheckConstraint("NOT (debit > 0 AND credit > 0)", name="ck_journal_lines_one_sided"),
    )

    entry_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("journal_entries.id"))
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id"))
    #: مرکز هزینه/پروژه؛ از سطحِ سند به ردیف به ارث می‌رسد. NULL = بدون مرکز.
    cost_center_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cost_centers.id"), nullable=True, index=True
    )

    #: تفصیلیِ سایر — بُعدِ تحلیلیِ آزاد. NULL = بدونِ تفصیلی.
    analytic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analytic_accounts.id", ondelete="SET NULL"), nullable=True
    )

    debit: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    credit: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    description: Mapped[str] = mapped_column(Text, default="")

    #: ردیفِ ارزی: مبلغِ اصلی به ارزِ خارجی و نرخِ لحظه‌ی ثبت. بدهکار/بستانکارِ بالا
    #: همیشه ریالی‌اند؛ این سه فقط *مبنای* آن عدد را نگه می‌دارند تا «تسعیر ارز»
    #: بتواند بعداً بفهمد مانده‌ی ریالی معادلِ چند واحدِ ارز بوده. NULL = ردیفِ ریالی.
    currency_code: Mapped[str | None] = mapped_column(String(3), nullable=True)
    fx_amount: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    fx_rate: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)

    #: پیگیری — ارجاعِ آزادِ همین ردیف: شماره‌ی حواله، شماره‌ی نامه، کدِ پرونده.
    #: فقط برای حسابی که `has_tracking` دارد پذیرفته می‌شود. روی *ردیف* است نه سند،
    #: چون یک سند می‌تواند چند ردیف با پیگیری‌های متفاوت داشته باشد.
    #: این جایگزینِ جدولِ `checks` نیست: چک موجودیتی با سررسید و وضعیت و گردش است،
    #: پیگیری فقط یک ارجاعِ متنی که هیچ گردشی ندارد.
    tracking_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tracking_date: Mapped[date_ | None] = mapped_column(Date, nullable=True)

    entry: Mapped["JournalEntry"] = relationship(back_populates="lines")
    account: Mapped["Account"] = relationship()
