"""تسویه‌ی حسابِ طرف مقابل — کدام بدهکار با کدام بستانکار تسویه شد.

**این جدول پول جابه‌جا نمی‌کند (§۲۲ §۲۳).** فاکتور و رسید و چک، هرکدام اثرِ مالیِ
خودشان را همان لحظه‌ی ثبت زده‌اند؛ چیزی که تا امروز *هیچ‌جا* نمی‌نشست این بود که
آن دریافت بابتِ کدام فاکتور بوده. پس تسویه سندِ حسابداری نمی‌زند و نباید بزند:
سندِ دوم فقط همان ۱۰۰ بدهکار/۱۰۰ بستانکارِ خنثی را تکرار می‌کند و دفتر را شلوغ‌تر
می‌کند بی‌آنکه چیزی را درست‌تر کند.

**چرا «تخصیص» و نه یک ستون روی فاکتور.** رابطه ذاتاً چند‌به‌چند است (§۱۷): یک
فاکتور با چند رسید، و یک رسید با چند فاکتور. `receipt.invoice_id` این را
نمی‌گیرد، و `is_paid` بولی هم نه — فاکتور می‌تواند ۳۰٪ تسویه شده باشد (§۴۲).

**مبلغِ تسویه‌شده‌ی هر سند ذخیره نمی‌شود (§۴۳).** جمعِ همین تخصیص‌هاست. سه ستونِ
مستقل (مبلغ، تسویه‌شده، مانده) یعنی سه چیزی که می‌توانند از هم جدا بیفتند؛ همان
اصلی که مانده‌ی حساب‌ها هم در کوبیتا با آن مشتق می‌شود، نه ذخیره.
"""
import uuid
from datetime import date as date_, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
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

if TYPE_CHECKING:
    from app.models.accounting import Account
    from app.models.inventory import Contact

#: سمتِ قلم در تسویه. جهت از **اثرِ واقعیِ سند روی حسابِ طرف مقابل** می‌آید، نه از
#: نامِ فرم (§۸): فاکتورِ فروش دریافتنی را بدهکار می‌کند و فاکتورِ خرید پرداختنی را
#: بستانکار — پس «فاکتور» به‌خودیِ‌خود نه بدهکار است نه بستانکار.
SETTLEMENT_SIDES = ("debit", "credit")


class Settlement(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """یک عملیاتِ تسویه: چند قلمِ بدهکار در برابرِ چند قلمِ بستانکارِ همان طرف حساب."""

    __tablename__ = "settlements"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_settlements_tenant_number"),
        Index("ix_settlements_tenant_contact", "tenant_id", "contact_id"),
    )

    number: Mapped[int] = mapped_column(BigInteger)
    settlement_date: Mapped[date_] = mapped_column(Date)

    contact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("contacts.id"), index=True)
    #: **معینِ طرف مقابل (§۵).** تسویه فقط `contact_id` نیست: همان شرکت می‌تواند هم
    #: مشتری باشد هم تأمین‌کننده (§۳۰)، و طلبِ ما از او با بدهیِ ما به او دو حسابِ
    #: متفاوت‌اند. بدونِ این ستون، تهاترِ بینِ دو معین بی‌سروصدا اتفاق می‌افتاد —
    #: چیزی که §۳۱ صریحاً می‌گوید بدونِ قاعده‌ی مشخص نباید فرض شود.
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id"), index=True)

    #: زمینه‌ی ارزی (§۳۲). تخصیص همیشه به ارزِ پایه است — همان عددی که در دفتر
    #: نشسته. اقلامِ با ارزهای متفاوت در یک تسویه رد می‌شوند، چون این فصل قاعده‌ی
    #: تسویه‌ی چندارزی را تعریف نمی‌کند و ساختنش از خودمان یعنی نرخی که کسی
    #: نگفته است.
    currency_code: Mapped[str] = mapped_column(String(3), default="IRR", server_default="IRR")

    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    #: شرحِ دوم (§۳) — همان الگویی که فرمِ مرجع دارد؛ جای ارجاعِ داخلی/شماره‌ی نامه.
    description2: Mapped[str] = mapped_column(Text, default="", server_default="")

    #: جمعِ یک سمت. چون دو سمت باید برابر باشند (§۱۹)، یک عدد کافی است. منبعِ حقیقت
    #: همان ردیف‌های تخصیص است؛ این عکسِ لحظه‌ی ثبت است تا فهرست بدونِ جمع‌زدنِ
    #: دوباره خوانده شود — و `verify_totals` در سرویس این دو را مقابلِ هم می‌گذارد.
    total_amount: Mapped[float] = mapped_column(Numeric(18, 0), default=0)

    #: **برگشت، نه حذف (§۳۷ §۳۸).** تسویه مالکِ فاکتور و رسید نیست؛ برگرداندنش فقط
    #: رابطه را آزاد می‌کند. ردیف‌های تخصیص سرِ جایشان می‌مانند تا «چه چیزی آزاد شد»
    #: هم قابلِ دیدن باشد؛ مشتق‌کننده‌ی مانده، تسویه‌ی باطل را کنار می‌گذارد.
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    void_reason: Mapped[str] = mapped_column(Text, default="", server_default="")
    voided_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    contact: Mapped["Contact"] = relationship()
    account: Mapped["Account"] = relationship()
    allocations: Mapped[list["SettlementAllocation"]] = relationship(
        back_populates="settlement", cascade="all, delete-orphan", order_by="SettlementAllocation.seq"
    )

    @property
    def is_voided(self) -> bool:
        return self.voided_at is not None


class SettlementAllocation(TenantMixin, UUIDPKMixin, Base):
    """یک قلم: «از این سند، این مبلغ در این تسویه مصرف شد».

    **لنگر، سندِ منبع است نه کپی‌اش (§۱۰).** `source_type` + `source_id` به همان
    فاکتور/رسید/چکِ واقعی اشاره می‌کنند؛ مبلغ و تاریخ و شماره هر بار از خودِ سند
    خوانده می‌شوند. کپی‌کردنشان یعنی اگر فاکتور ویرایش شود، تسویه رقمِ کهنه را
    نشان دهد — دقیقاً همان چیزی که §۳۹ می‌گوید نباید بی‌صدا بماند.

    **چرا جفتِ بدهکار↔بستانکار ذخیره نمی‌شود.** وقتی دو فاکتور با دو رسید تسویه
    می‌شوند، این‌که کدام رسید به کدام فاکتور خورده در واقعیت *تعیین‌نشده* است؛ هر
    جفت‌کردنی حدسِ ماشین است. پس واحدِ ثبت همان چیزی است که کاربر واقعاً وارد کرده:
    قلم و مبلغش. «این فاکتور با چه چیزی تسویه شد؟» از همان تسویه جواب می‌گیرد —
    سمتِ مقابلِ همان سند (§۳۵ خودش هم تسویه را حلقه‌ی وصل نشان می‌دهد، نه جفت‌ها).
    """

    __tablename__ = "settlement_allocations"
    __table_args__ = (
        CheckConstraint(f"side IN {SETTLEMENT_SIDES}", name="ck_settlement_allocations_side"),
        CheckConstraint("amount > 0", name="ck_settlement_allocations_amount_positive"),
        #: یک سند دوبار در یک تسویه نمی‌آید — وگرنه «مانده‌ی قابلِ تسویه»ی همان قلم
        #: در فرم دوبار مصرف می‌شد و کنترلِ §۱۴ از دو ردیفِ جدا رد می‌شد.
        #: `tenant_id` در قید هست هرچند `settlement_id` خودش مستأجرمحور است: قاعده‌ی
        #: مخزن می‌گوید هیچ ایندکسِ یکتای سراسری روی جدولِ مستأجرمحور نباشد، و
        #: تستِ دریفت همین را می‌سنجد.
        UniqueConstraint(
            "tenant_id",
            "settlement_id",
            "source_type",
            "source_id",
            name="uq_settlement_allocations_source",
        ),
        Index("ix_settlement_allocations_source", "tenant_id", "source_type", "source_id"),
    )

    settlement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("settlements.id", ondelete="CASCADE"), index=True
    )
    #: ترتیبِ ورودِ کاربر در همان سمت. بدونش ترتیب با `id`ِ تصادفی می‌شد — همان
    #: مشکلی که ردیف‌های سندِ حسابداری با `seq` حلش کردند.
    seq: Mapped[int] = mapped_column(default=0, server_default="0")
    side: Mapped[str] = mapped_column(String(6))

    #: کلیدِ نوعِ منبع از رجیستریِ `open_items.SETTLEABLE`. رشته است نه کلیدِ خارجی،
    #: چون منبع‌ها در جدول‌های مختلفی زندگی می‌کنند — همان الگویی که
    #: `JournalEntry.source_type` دارد.
    source_type: Mapped[str] = mapped_column(String(30))
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))

    amount: Mapped[float] = mapped_column(Numeric(18, 0))

    settlement: Mapped["Settlement"] = relationship(back_populates="allocations")
