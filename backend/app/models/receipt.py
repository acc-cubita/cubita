"""رسید دریافت — سربرگی که تا امروز نداشتیم.

`TreasuryTransaction` هرچه دارد در سطحِ **ابزار** است (`cashbox_id`،
`bank_account_id`، `pos_terminal_id`، `reference_no`، `settled_at`) و هرچه ندارد
در سطحِ **سند** (شماره، نوعِ دریافت، ارز، طرفِ مقابل به‌عنوانِ صاحبِ سند). یعنی
آن جدول از اول «یک جزء» بوده، نه یک رسید — و همین بود که یک رسید را به یک ابزار
محدود می‌کرد.

پس رسید بالای اجزا ساخته شد، نه زیرِ آن‌ها:

    Receipt
      ├── TreasuryTransaction(method=cash,  cashbox_id=…)          نقد
      ├── TreasuryTransaction(method=bank,  bank_account_id=…)     حواله
      ├── TreasuryTransaction(method=bank,  paid_via=pos_terminal) کارت‌خوان
      └── Check(type=receivable, status=in_hand)                   چک

سه چیز این شکل را تعیین کرد:

۱. **هیچ مصرف‌کننده‌ای نمی‌شکند.** ستون‌های سطحِ‌ابزارِ خزانه در نُه جای دیگر
   مستقیم خوانده می‌شوند (تسویه‌ی کارت‌خوان، گاردهای «در حالِ استفاده»، موجودیِ
   دستگاه). اگر جزء را زیرِ خزانه می‌بردیم، هر کدام که جا می‌ماند یک عددِ غلطِ
   بی‌صدا می‌شد.

۲. **چک باید `Check` بماند.** چرخه‌ی عمرِ مستقل دارد و `contact_balance` جداگانه
   می‌شماردش؛ اگر جزءِ خزانه می‌شد، دوبار حساب می‌شد.

۳. **`receipt_id IS NULL` یک حقیقت است، نه شکاف.** یعنی «پیش از این مهاجرت» یا
   «اثرِ جانبیِ سندِ دیگر» (قسط، بازارگاه، فروشِ کارتیِ گذری) — آن‌ها سندِ خودشان
   را دارند و رسیدِ جدا برایشان ساختن یعنی سندِ دوم برای یک رویداد.

**ارز از موتورِ خودِ کوبیتا می‌آید** (§۹)، نه موتورِ دومِ رسید: مبالغِ اجزا به
ارزِ سندند و `base_currency_amount` معادلِ پایه‌شان است — همان که سند می‌خورد.

**قرینه‌ی `payments` است و عمداً.** دو سندِ خواهر با دو توانِ متفاوت، کاربر را
مجبور می‌کند یادش بماند کدام‌یک تخفیف دارد. تنها استثنا کارمزد است که فقط سمتِ
پرداخت معنا دارد.
"""
import uuid
from datetime import date as date_
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin, VoidableMixin
from app.models.tenant import TenantMixin

if TYPE_CHECKING:
    from app.models.inventory import Contact

#: §۲ — نوعِ دریافت فقط یک برچسب نیست: تعیین می‌کند حسابِ طرفِ مقابل کدام است.
#: نگاشتش در `app/services/receipts.py::COUNTERPARTY_ROLE` است، نه اینجا، چون
#: انتخابِ حساب کارِ سرویس است نه مدل.
RECEIPT_TYPES = ("customer", "supplier", "intermediary", "other", "petty_holder")


class Receipt(TenantMixin, VoidableMixin, UUIDPKMixin, TimestampMixin, Base):
    """سربرگِ رسید دریافت — یک رویدادِ دریافت با یک یا چند ابزار و **یک** سند."""

    __tablename__ = "receipts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_receipts_tenant_number"),
        CheckConstraint(f"receipt_type IN {RECEIPT_TYPES}", name="ck_receipts_type"),
        CheckConstraint("receipt_amount > 0", name="ck_receipts_amount_positive"),
        CheckConstraint("discount_amount >= 0", name="ck_receipts_nonnegative"),
        CheckConstraint("exchange_rate > 0", name="ck_receipts_exchange_rate_positive"),
    )

    #: شماره‌ی عملیاتیِ خودِ رسید — نه شماره‌ی سند، نه شماره‌ی چک (§۴).
    #: از `next_document_number` می‌آید: بی‌شکاف و درونِ همان تراکنش.
    number: Mapped[int] = mapped_column(Numeric(18, 0))
    receipt_type: Mapped[str] = mapped_column(String(20), default="customer")
    contact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("contacts.id"))
    receipt_date: Mapped[date_] = mapped_column(Date, default=date_.today)

    #: حساب‌ها از نقشِ سیستمی resolve می‌شوند، ولی شناسه‌ی واقعیِ استفاده‌شده روی
    #: سند می‌ماند — سالِ بعد که چارت عوض شده، باید معلوم باشد کجا خورد.
    counterparty_account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id"))
    discount_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=True
    )

    currency_code: Mapped[str] = mapped_column(String(3), default="IRR", server_default="IRR")
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=1)

    #: **چهار مفهومِ مستقل** (§۲۲). ادغامشان در یک عدد یعنی از دست دادنِ تفاوتِ
    #: «پول رسید» و «بدهی بسته شد» — و تخفیف دقیقاً همان‌جایی است که این دو
    #: از هم جدا می‌شوند: پولی وارد صندوق نشده، ولی مطالبه کم شده است (§۲۳).
    #:
    #: `receipt_amount` به ارزِ سند است؛ `base_currency_amount` همان مقدار به
    #: ارزِ پایه — و **سند همیشه از این یکی می‌خورد**.
    receipt_amount: Mapped[Decimal] = mapped_column(Numeric(18, 0))
    base_currency_amount: Mapped[Decimal] = mapped_column(Numeric(18, 0))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(18, 0), default=0)
    settlement_total: Mapped[Decimal] = mapped_column(Numeric(18, 0))

    description: Mapped[str] = mapped_column(Text, default="")
    description2: Mapped[str] = mapped_column(String(200), default="")
    #: §۲۹ — فقط ذخیره می‌شود. فصل صریح می‌گوید تا گردش‌کارِ «استقرار» معلوم نشده،
    #: اثرِ مالی یا قاعده‌ای برایش حدس نزنید.
    establishment: Mapped[str] = mapped_column(String(120), default="", server_default="")

    #: **یک رسید، یک سند** (§۳۰ §۳۱). اجزا همین شناسه را به اشتراک می‌گذارند.
    journal_entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), index=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    contact: Mapped["Contact"] = relationship()


class ReceiptRelatedDocument(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """پیوندِ قابلِ ردگیری بینِ رسید و سندِ کسب‌وکار (§۲۰).

    **این موتورِ تسویه نیست و نباید با آن اشتباه شود.** فصل صریح است: «منطق دقیق
    Allocation را بهتر است با قسمت تسویه حساب طرف مقابل نهایی کنیم». پس این‌جا
    فقط رابطه ثبت می‌شود و یک گاردِ ساده که جمعِ تخصیص از جمعِ تسویه بیشتر نشود.
    گزارشِ سنی و مانده‌ی طرف‌حساب همچنان در سطحِ **شخص** حساب می‌شوند، نه از
    این جدول — عوض‌کردنش تصمیمِ فصلِ تسویه است.

    قرینه‌ی `payment_related_documents` است، با `sales_invoice` به‌جای
    `purchase_invoice`.
    """

    __tablename__ = "receipt_related_documents"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "receipt_id", "document_type", "document_id", name="uq_receipt_related_document"
        ),
        CheckConstraint("allocated_amount >= 0", name="ck_receipt_related_allocated_nonnegative"),
    )

    receipt_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("receipts.id"), index=True)
    document_type: Mapped[str] = mapped_column(String(40))
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    allocated_amount: Mapped[Decimal] = mapped_column(Numeric(18, 0), default=0)
