"""تسویه‌ی کارت‌خوان — سندِ انتقالِ وجه از «در راه» به بانک.

**چرا این جدول لازم شد.** تا پیش از این، تسویه یک *عملیات* بود نه یک *سند*:
اندپوینت ردیف‌های رسید را `settled_at = now()` می‌زد، یک خلاصه برمی‌گرداند و تمام.
هیچ‌جا ننشسته بود که این تسویه کِی، با کدام دامنه، برای کدام دستگاه و به کدام
حساب انجام شده. پیامدهایش:

* «این رسید با کدام تسویه رفت؟» بی‌جواب بود. تنها حلقه `settlement_txn_id` بود که
  **فقط وقتی کارمزد بزرگ‌تر از صفر باشد** پر می‌شد؛ تسویه‌ی بی‌کارمزد — که حالتِ
  رایج است — هیچ ردی نمی‌گذاشت.
* «فهرستِ تسویه‌ها» از روی `settled_at`ِ رسیدها بازسازی می‌شد. دو تسویه‌ی متفاوت
  در یک روز از یک پایانه، در آن فهرست یک ردیف می‌شدند.
* لغوِ تسویه ممکن نبود، چون چیزی برای لغو‌کردن وجود نداشت.

**شماره‌ی تسویه شماره‌ی رسید و شماره‌ی سند و شماره‌ی پایانه نیست (§۵).** هرکدام
هویتِ خودشان را دارند؛ این یکی از شمارنده‌ی بی‌شکافِ `pos_settlement` می‌آید.

**مبلغ ستون دارد، ولی منبعِ حقیقت نیست (§۱۲ §۲۰).** حقیقت همان رسیدهایی است که
`settlement_id`شان به این ردیف اشاره می‌کند؛ این سه عدد عکسِ لحظه‌ی ثبت‌اند تا
فهرست بدونِ جمع‌زدنِ دوباره خوانده شود. `verify_totals` در سرویس همین دو را
مقابلِ هم می‌گذارد، پس اگر روزی از هم جدا بیفتند دیده می‌شود.
"""
import uuid
from datetime import date as date_, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin

if TYPE_CHECKING:
    from app.models.banking import BankAccount
    from app.models.pos_terminal import PosTerminal


class PosSettlement(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """یک واریزِ شرکتِ پرداخت که ثبت شده است."""

    __tablename__ = "pos_settlements"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_pos_settlements_tenant_number"),
    )

    number: Mapped[int] = mapped_column(BigInteger)

    #: تاریخِ خودِ عملیاتِ تسویه — روزی که پول به بانک نشست.
    settlement_date: Mapped[date_] = mapped_column(Date)
    #: «تسویه تا تاریخ» (§۹) — برشِ انتخابِ رسیدها. **با بالایی یکی نیست**: مشتری
    #: ۱۴۰۴/۰۵/۱۰ کارت کشیده و بانک ۱۴۰۴/۰۵/۱۱ واریز کرده؛ هر دو باید بمانند.
    settle_through: Mapped[date_] = mapped_column(Date)
    #: کفِ اختیاریِ بازه. `NULL` یعنی «هر چه تسویه‌نشده مانده» — رفتارِ طبیعیِ برش.
    date_from: Mapped[date_ | None] = mapped_column(Date, nullable=True)

    pos_terminal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pos_terminals.id"), index=True
    )
    #: حسابی که واریز به آن نشست. عکسِ لحظه‌ی ثبت است، نه ارجاعِ زنده: اگر فردا
    #: حسابِ تسویه‌ی دستگاه عوض شود، تسویه‌های گذشته باید همان‌جا بمانند که رفتند.
    bank_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bank_accounts.id")
    )

    gross_amount: Mapped[Decimal] = mapped_column(Numeric(18, 0), default=0)
    fee_amount: Mapped[Decimal] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    net_amount: Mapped[Decimal] = mapped_column(Numeric(18, 0), default=0)

    #: سندِ «بانک بدهکار / وجوهِ در راه بستانکار» (§۲۳).
    journal_entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), index=True
    )
    #: ردیفِ بانکیِ همین واریز — چیزی که در مغایرت‌گیری مقابلِ صورت‌حسابِ بانک
    #: می‌نشیند (§۳۶). تا پیش از این برای واریزِ PSP هیچ ردیفی ساخته نمی‌شد و
    #: تنها ردیفِ سیستمی یک «منهای کارمزد» بود که با هیچ خطی از بانک نمی‌خواند.
    bank_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bank_transactions.id", ondelete="SET NULL"), nullable=True
    )

    note: Mapped[str] = mapped_column(Text, default="", server_default="")

    #: ابطال با سندِ معکوس — اصل سرِ جایش می‌ماند (§۳۳). همان الگویی که
    #: `CreditDebitNote` دارد: حذفِ فیزیکی نداریم، چون سند و ردیفِ بانکی از قبل
    #: صادر شده‌اند و پاک‌کردنشان یعنی بازنویسیِ بی‌صدای تاریخچه‌ی مالی.
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    void_reason: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    terminal: Mapped["PosTerminal"] = relationship("PosTerminal")
    bank_account: Mapped["BankAccount"] = relationship("BankAccount")
