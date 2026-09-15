import uuid
from datetime import date as date_
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin, VoidableMixin
from app.models.tenant import TenantMixin

if TYPE_CHECKING:
    from app.models.analytic import AnalyticAccount
    from app.models.inventory import Contact

CHECK_TYPES = ("receivable", "payable")
#: چرخه‌ی عمرِ چک. **سه «برگشت» عمداً سه وضعیتِ جدا هستند** و یکی‌کردنشان گزارشِ
#: چک را غیرقابلِ‌اعتماد می‌کند:
#:
#: * `bounced`  — بانک نتوانست وصول کند (واخواست).
#: * `returned` — ما خودمان برگ را پس دادیم (مثلاً معامله فسخ شد).
#: * `endorsed → in_hand` — چکی که خرج کرده بودیم به ما برگشت.
#:
#: `cashed` تازه است: چکِ دریافتنی می‌تواند به‌جای واگذاری به بانک، مستقیم نقد شود
#: و پولش به صندوق برود. تا پیش از این چنین راهی نبود و کاربر مجبور بود آن را
#: «وصول» ثبت کند — که پول را به بانکی می‌برد که هرگز چیزی نگرفته بود.
CHECK_STATUSES = (
    "in_hand",
    "deposited",
    "cleared",
    "bounced",
    "endorsed",
    "issued",
    "returned",
    "cashed",
)
#: **سه نوع، و سومی تا امروز نبود.**
#:
#: `return_balance` = استردادِ ماندهٔ تنخواه. بدونِ آن، تنخواه‌داری که می‌رفت پولِ
#: دستش را فقط با یک «هزینه»ی جعلی می‌توانست برگرداند — و دفتر آن را هزینه
#: می‌دید، نه بازگشتِ وجه.
PETTY_CASH_TYPES = ("charge", "expense", "return_balance")


class BankAccount(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """حسابِ بانکیِ عملیاتی — **نه** حسابی در چارتِ حسابداری.

    مستنداتِ `Cashbox` این کلاس را الگوی خودش معرفی می‌کند، ولی تا مهاجرتِ ۰۱۰۶
    یک چیز را نداشت که همان الگو رویش سوار است: `analytic_id`. بدونِ آن هر
    حسابِ بانکی روی همان معینِ «بانک» می‌نشست و **مانده‌ی تک‌تکشان اصلاً
    مشتق‌شدنی نبود** — نه اینکه سخت باشد؛ در دفتر اطلاعاتی که بگوید کدام ریال
    مالِ کدام بانک است وجود نداشت.

    امروز جفتِ `(gl_account_id, analytic_id)` هویتِ حسابداریِ حساب است: سمتِ
    نوشتن همان جفت را روی ردیفِ سند می‌گذارد و سمتِ خواندن با همان جفت مانده را
    درمی‌آورد. هیچ ستونِ `balance`ای وجود ندارد و نباید ساخته شود.
    """

    __tablename__ = "bank_accounts"

    name: Mapped[str] = mapped_column(String(200))
    #: عنوانِ دومِ تفصیلی — همان نقشی که `name2` در بقیه‌ی موجودیت‌ها دارد.
    name2: Mapped[str] = mapped_column(String(200), default="", server_default="")
    bank_name: Mapped[str] = mapped_column(String(100), default="")
    #: شعبه. عمداً متن است نه کلیدِ خارجی به جدولِ مرجعِ شعب — ر.ک. OPEN_DECISIONS.
    branch_name: Mapped[str] = mapped_column(String(100), default="", server_default="")
    account_number: Mapped[str] = mapped_column(String(50), default="")
    #: جاری، پس‌انداز، قرض‌الحسنه… متنِ آزاد است و هیچ رفتاری به مقدارش گره نمی‌خورد.
    account_type: Mapped[str] = mapped_column(String(50), default="", server_default="")
    #: سه شناسه‌ی بانکیِ **جدا** (§۷): شماره حساب، شماره کارت، شبا. هیچ‌کدام جای
    #: دیگری به کار نمی‌رود، و هیچ‌کدام هویتِ داخلیِ رکورد نیست — آن `id` است (§۴).
    card_number: Mapped[str] = mapped_column(String(30), default="", server_default="")
    iban: Mapped[str] = mapped_column(String(34), default="")

    #: **بُعدی که مانده را مشتق‌شدنی می‌کند.** NULL یعنی «حسابِ تفکیک‌نشده» — همان
    #: توده‌ای که پیش از مهاجرتِ ۰۱۰۶ روی معینِ بانک نشسته بود. فقط *یک* حساب
    #: می‌تواند NULL باشد، وگرنه دو حساب یک مانده می‌خوانند.
    analytic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analytic_accounts.id", ondelete="SET NULL"), nullable=True
    )
    # حساب دفتر کل متناظر (پیش‌فرض «۱۱۰۲ بانک»)؛ امکان تفکیک حساب معین جداگانه در آینده باقی می‌ماند
    gl_account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id"))

    #: یک حساب، یک ارز (§۱۱). حسابِ دلاری از ریالی جدا مدیریت می‌شود.
    currency_code: Mapped[str] = mapped_column(String(3), default="IRR", server_default="IRR")
    #: **داده‌ی کسب‌وکار، نه `created_at`** (§۱۵): حساب می‌تواند ۱۴۰۰ باز شده باشد
    #: و ۱۴۰۴ وارد کوبیتا شود.
    opening_date: Mapped[date_ | None] = mapped_column(Date, nullable=True)

    #: صاحبِ حساب ≠ نامِ شرکت (§۱۷) — می‌تواند شعبه یا یک عنوانِ حقوقیِ دیگر باشد.
    holder_name: Mapped[str] = mapped_column(String(200), default="", server_default="")
    holder_name2: Mapped[str] = mapped_column(String(200), default="", server_default="")

    #: مبلغی که بانک بلوکه کرده. **ذخیره می‌شود ولی هرگز به دفتر نمی‌خورد** (§۱۸):
    #: بلوکه‌شدن رویدادِ حسابداری نیست، پس نه سند می‌زند نه مانده را عوض می‌کند.
    #: «قابل استفاده» از این و مانده *مشتق* می‌شود و ذخیره نمی‌شود.
    blocked_amount: Mapped[float] = mapped_column(
        Numeric(18, 0), default=0, server_default="0"
    )

    #: فرمتِ چاپِ چکِ همین بانک (§۱۶) — فعلاً فقط نگهداری می‌شود؛ موتورِ چاپ جداست.
    cheque_print_format: Mapped[str] = mapped_column(String(50), default="", server_default="")

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    analytic: Mapped["AnalyticAccount | None"] = relationship(lazy="joined")


class Check(TenantMixin, VoidableMixin, UUIDPKMixin, TimestampMixin, Base):
    """چک دریافتنی/پرداختنی. چرخه‌ی وضعیت در app/services/banking.py مدیریت و سند حسابداری متناظر می‌سازد."""

    __tablename__ = "checks"
    __table_args__ = (
        CheckConstraint(f"type IN {CHECK_TYPES}", name="ck_checks_type"),
        CheckConstraint(f"status IN {CHECK_STATUSES}", name="ck_checks_status"),
        #: یک برگِ فیزیکی فقط یک بار خرج می‌شود. شرطِ جزئی لازم است چون چکِ
        #: دریافتنی دسته ندارد و شماره‌اش را طرفِ مقابل تعیین کرده — یکتاییِ بینِ
        #: آن‌ها نه ممکن است نه درست.
        #:
        #: این قید «برگِ باطل‌شده آزاد نمی‌شود» را هم می‌سازد: ردیفِ چک می‌ماند،
        #: پس شماره‌اش برای همیشه گرفته است.
        Index(
            "uq_checks_tenant_book_number",
            "tenant_id",
            "checkbook_id",
            "number",
            unique=True,
            postgresql_where=text("checkbook_id IS NOT NULL"),
        ),
        #: کد صیادی در سطحِ **کشور** یکتاست — یک برگ، یک کد. پس دو چکِ یک
        #: کسب‌وکار با یک کد یعنی خطای ورودِ داده، نه یک حالتِ ممکن.
        #: شرطِ جزئی لازم است چون کد اختیاری است و چک‌های موجود همه رشته‌ی خالی
        #: می‌گیرند؛ بدونِ شرط، دومین چک بلافاصله قید را می‌شکست.
        Index(
            "uq_checks_tenant_sayad",
            "tenant_id",
            "sayad_id",
            unique=True,
            postgresql_where=text("sayad_id <> ''"),
        ),
    )

    type: Mapped[str] = mapped_column(String(20))
    number: Mapped[str] = mapped_column(String(50))
    #: شماره‌ی پشتِ برگ. روی چکِ صیادی چاپ شده و در بانک با همین پیگیری می‌شود؛
    #: با `number` یکی نیست و هویتِ رکورد هم نیست.
    back_number: Mapped[str] = mapped_column(String(50), default="", server_default="")
    #: شناسه‌ی صیادی (۱۶ رقم). از ۱۴۰۰ روی هر برگِ بانکی هست و در استعلام و
    #: مغایرت‌گیری همین است که یکتاست — نه شماره‌ی چک، که بینِ بانک‌ها تکرار می‌شود.
    sayad_id: Mapped[str] = mapped_column(String(20), default="", server_default="")
    bank_name: Mapped[str] = mapped_column(String(100), default="")
    amount: Mapped[float] = mapped_column(Numeric(18, 0))
    issue_date: Mapped[date_] = mapped_column(Date)
    due_date: Mapped[date_] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(Text, default="")

    #: شرحِ دوم — قرینه‌ی `name2` روی بقیه‌ی موجودیت‌ها.
    description2: Mapped[str] = mapped_column(String(200), default="", server_default="")

    # ── هویتِ برگ (§۱۰ §۱۱) ──
    #: `sayad_id` و `back_number` بالا تعریف شده‌اند — مهاجرتِ ۰۱۱۰ (چرخه‌ی عمرِ
    #: چک) زودتر ساختشان و روی تولید نشسته‌اند. این‌جا بقیه‌ی مشخصاتِ برگ است.
    branch_name: Mapped[str] = mapped_column(String(100), default="", server_default="")
    branch_code: Mapped[str] = mapped_column(String(20), default="", server_default="")
    #: شماره‌حسابِ **صادرکننده**، نه ما. برای چکِ دریافتنی تنها ردِ حسابِ مبدأ است.
    account_number: Mapped[str] = mapped_column(String(40), default="", server_default="")
    #: صاحبِ چک — همیشه طرف‌حسابِ ما نیست. چکِ شخصِ ثالث دقیقاً همین حالت است.
    owner_name: Mapped[str] = mapped_column(String(120), default="", server_default="")

    contact_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=True)
    bank_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bank_accounts.id"), nullable=True
    )
    #: برگِ کدام دسته‌چک است. NULL برای چکِ دریافتنی (دسته‌ی ما نیست) و چک‌های قدیمی.
    checkbook_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("checkbooks.id", ondelete="SET NULL"), nullable=True
    )
    #: صندوقی که چک در آن نقد شد. فقط برای وضعیتِ `cashed` معنا دارد و برای بقیه
    #: `NULL` می‌ماند — قرینه‌ی `bank_account_id` که مقصدِ واگذاری/وصول است.
    cashbox_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cashboxes.id"), nullable=True
    )

    #: **از کدام رسید آمد** (§۳۸). `NULL` = چکی که مستقیم از «عملیات بانکی چک
    #: دریافتنی» ثبت شده، یا پیش از مهاجرتِ ۰۱۰۹ بوده.
    receipt_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("receipts.id"), nullable=True, index=True
    )
    #: چکِ پرداختنیِ صادرشده در این اعلامیه. چک دریافتنیِ خرج‌شده از جدول رخداد
    #: `payment_cheque_transfers` به اعلامیه وصل می‌شود و این ستون روی آن نمی‌نشیند.
    payment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id"), nullable=True, index=True
    )

    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    contact: Mapped["Contact | None"] = relationship("Contact")
    bank_account: Mapped["BankAccount | None"] = relationship("BankAccount")

    @property
    def contact_name(self) -> str | None:
        """نامِ طرف‌حساب برای نمایش در فهرستِ چک‌ها (خروجیِ CheckOut از همین می‌خواند)."""
        return self.contact.name if self.contact else None


class BankTransaction(TenantMixin, UUIDPKMixin, Base):
    """واریز(+)/برداشت(-) در یک حساب بانکی؛ برای تطبیق بانکی، is_reconciled بعداً علامت زده می‌شود."""

    __tablename__ = "bank_transactions"

    bank_account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("bank_accounts.id"))
    transaction_date: Mapped[date_] = mapped_column(Date, default=date_.today)
    amount: Mapped[float] = mapped_column(Numeric(18, 0))  # مثبت = واریز، منفی = برداشت
    description: Mapped[str] = mapped_column(Text, default="")
    description2: Mapped[str] = mapped_column(String(200), default="", server_default="")
    reference_no: Mapped[str] = mapped_column(String(50), default="", server_default="")
    #: برای برداشتِ اعلامیه، اصل و کارمزد جدا می‌مانند؛ `amount` اثرِ واقعی و
    #: علامت‌دار بانک است. روی ردیف‌های قدیمی هر دو صفرند.
    principal_amount: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    bank_fee_amount: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    is_reconciled: Mapped[bool] = mapped_column(Boolean, default=False)

    source_type: Mapped[str] = mapped_column(String(50), default="manual")  # manual | check_clear
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    #: برداشتِ بانکیِ یک اعلامیه، برای پیمایش دوطرفه و جلوگیری از حذفِ بی‌رد.
    payment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id"), nullable=True, index=True
    )

    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True, index=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))


class BankStatementLine(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """یک ردیف واردشده از صورت‌حساب رسمی بانک؛ برای تطبیق با BankTransaction ثبت‌شده در سیستم."""

    __tablename__ = "bank_statement_lines"
    __table_args__ = (
        #: **جزئی، و همین جزئی‌بودن نکته‌اش است.** همه‌ی صورت‌حساب‌ها شماره‌ی مرجع
        #: نمی‌دهند؛ قیدِ کامل، ردیف‌های بی‌مرجع را با `NULL`های تکراری مسدود
        #: می‌کرد. (همان الگوی `uq_sale_types_tenant_code`.)
        Index(
            "uq_bank_statement_lines_external_ref",
            "tenant_id",
            "bank_account_id",
            "external_ref",
            unique=True,
            postgresql_where=text("external_ref IS NOT NULL"),
        ),
    )

    bank_account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("bank_accounts.id"))
    #: شناسه‌ی خودِ بانک برای این تراکنش — شماره‌ی پیگیری/مرجع. تهی‌پذیر، چون
    #: فایل‌های صورت‌حساب همیشه ندارندش. وقتی باشد، **تنها** تکیه‌گاهِ مطمئنِ
    #: «این ردیف را قبلاً وارد کرده‌ایم» است.
    external_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    line_date: Mapped[date_] = mapped_column(Date)
    amount: Mapped[float] = mapped_column(Numeric(18, 0))  # مثبت = واریز، منفی = برداشت (مطابق صورت‌حساب بانک)
    description: Mapped[str] = mapped_column(Text, default="")

    # وقتی با یک BankTransaction سیستم تطبیق داده شود، اینجا و is_reconciled آن تراکنش هر دو ست می‌شوند
    matched_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bank_transactions.id"), nullable=True
    )


class PettyCashFund(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """یک صندوقِ تنخواه — **موجودیتی جدا از تنخواه‌دارش**.

    تا امروز صندوقی وجود نداشت: `PettyCashTransaction` یک جدولِ تخت بود و
    docstringش می‌گفت «یک صندوق تنخواه واحد». پیامدش این بود که تنخواه‌دار جایی
    ثبت نمی‌شد و عوض‌شدنش هیچ ردی نداشت.

    **چرا تنخواه‌دار طرف حساب است نه کاربر:** تنخواه‌دار لزوماً حسابِ ورود به
    نرم‌افزار ندارد؛ ممکن است فقط کارمندی باشد که پول دستش است. و چون نقشِ
    کارمند هم روی همان طرف حساب می‌نشیند، این پیوند هویتِ دومی نمی‌سازد.

    **عوض‌کردنِ تنخواه‌دار هویتِ صندوق را عوض نمی‌کند** — همان صندوق می‌ماند و
    تاریخچه‌ی تراکنش‌هایش دست‌نخورده. این دقیقاً چیزی است که مدلِ قبلی نمی‌توانست.
    """

    __tablename__ = "petty_cash_funds"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_petty_cash_funds_tenant_name"),
    )

    name: Mapped[str] = mapped_column(String(120))
    custodian_contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=True
    )
    location: Mapped[str] = mapped_column(String(160), default="", server_default="")
    #: ۰ = بی‌سقف. **هشدار است نه گارد** — همان «گزارش، نه گارد»ی که لیستِ سیاه
    #: هم دارد: بستنِ ثبت یعنی کاربر سقف را بالا می‌برد و نشانه از بین می‌رود.
    spending_limit: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")


class PettyCashTransaction(TenantMixin, UUIDPKMixin, Base):
    """یک رویدادِ تنخواه: شارژ، هزینه‌کرد، یا استردادِ مانده."""

    __tablename__ = "petty_cash_transactions"
    __table_args__ = (CheckConstraint(f"type IN {PETTY_CASH_TYPES}", name="ck_petty_cash_type"),)

    type: Mapped[str] = mapped_column(String(20))
    #: تهی‌پذیر برای ردیف‌های پیش از مهاجرتِ ۰۱۵۱ که backfill نشده‌اند. اجباری‌کردنش
    #: یعنی یک backfillِ ناقص کلِ مهاجرت را می‌انداخت.
    fund_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("petty_cash_funds.id"), nullable=True, index=True
    )
    #: شماره‌ی مدرکِ پشتوانه (فاکتور، رسید). خالی یعنی مدرکی ثبت نشده — که خودش
    #: گزارش‌شدنی است، برخلافِ امروز که اصلاً جایی برای ثبتش نبود.
    evidence_ref: Mapped[str] = mapped_column(String(120), default="", server_default="")
    transaction_date: Mapped[date_] = mapped_column(Date, default=date_.today)
    amount: Mapped[float] = mapped_column(Numeric(18, 0))
    description: Mapped[str] = mapped_column(Text, default="")

    # برای شارژ: از کجا تأمین شد (صندوق/بانک). برای هزینه: بابت کدام حساب هزینه.
    counter_account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id"))

    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True, index=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))


class Checkbook(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """یک دسته‌چکِ بانکی — بازه‌ی شماره‌ی برگ‌ها و اینکه چند برگ خرج شده.

    **چرا مدلِ جدا و نه فقط یک فیلد روی چک:** بدونِ دسته، نه معلوم است چند برگ مانده،
    نه می‌شود جلوی شماره‌ی تکراری را گرفت، و نه هنگامِ صدورِ چکِ تازه شماره‌ی بعدی
    پیشنهاد می‌شود. سه چیزی که کاربر هر بار دستی حساب می‌کرد.

    شماره‌ی برگ **رشته** است نه عدد: بانک‌ها صفرِ ابتدایی می‌گذارند («۰۰۰۱۲۳») و
    تبدیل به عدد آن را می‌خورد.
    """

    __tablename__ = "checkbooks"
    __table_args__ = (
        UniqueConstraint("tenant_id", "bank_account_id", "serial", name="uq_checkbooks_tenant_serial"),
    )

    bank_account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("bank_accounts.id"))
    #: شناسه‌ی دسته روی جلد (سریِ صیاد یا شماره‌ی داخلیِ بانک).
    serial: Mapped[str] = mapped_column(String(40), default="")
    first_number: Mapped[str] = mapped_column(String(30))
    last_number: Mapped[str] = mapped_column(String(30))
    leaf_count: Mapped[int] = mapped_column(Integer, default=0)
    issue_date: Mapped[date_ | None] = mapped_column(Date, nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    #: بسته‌شده = دیگر برگِ تازه از آن صادر نمی‌شود (تمام شد یا باطل شد).
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    #: قالبِ چاپِ این دسته. **خالی یعنی از حسابِ بانکی ارث ببر** — دسته‌های یک حساب
    #: معمولاً یک قالب دارند و تکرارِ آن روی هر دسته فقط راهی برای ناهماهنگ‌شدن است.
    #: موتورِ چاپِ چک هنوز وجود ندارد؛ این فقط ترتیبِ خواندن را تثبیت می‌کند.
    cheque_print_format: Mapped[str] = mapped_column(String(50), default="", server_default="")

    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    bank_account: Mapped["BankAccount"] = relationship()
