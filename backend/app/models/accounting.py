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
    )

    code: Mapped[str] = mapped_column(String(20), index=True)
    #: نقش معنایی برای ثبت خودکار (cash، inventory، cogs و…). برای حساب‌های معمولی
    #: و سرفصل‌ها NULL است — قید یکتا روی NULL اعمال نمی‌شود، پس تعدادشان آزاد است.
    system_role: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(20))
    is_group: Mapped[bool] = mapped_column(default=False)
    #: حسابِ غیرفعال از فهرست‌های ثبتِ سند پنهان می‌شود ولی تاریخچه‌اش می‌ماند —
    #: راهی برای بایگانیِ حساب‌هایی که دیگر استفاده نمی‌شوند ولی سند دارند و پاک
    #: نمی‌شوند. پیش‌فرض فعال؛ حساب‌های موجود بی‌تغییر می‌مانند.
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=True
    )

    parent: Mapped["Account | None"] = relationship(remote_side="Account.id", back_populates="children")
    children: Mapped[list["Account"]] = relationship(back_populates="parent")


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

    entry: Mapped["JournalEntry"] = relationship(back_populates="lines")
    account: Mapped["Account"] = relationship()
