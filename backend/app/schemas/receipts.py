"""شِمای رسید دریافت.

**چهار لیستِ تایپ‌دار، نه یک لیستِ چندریختی با `kind`.** §۶ همین شکل را می‌کشد،
و دلیلِ فنی‌اش این است که هر ابزار اعتبارسنجیِ *خودش* را دارد: کارت‌خوان کد
پیگیری می‌خواهد، چک تاریخ سررسید، حواله شماره‌ی حواله. یک لیستِ یکسان یعنی
همه‌ی فیلدها اختیاری شوند و اعتبارسنجی به سرویس منتقل شود — یعنی جایی که خطایش
دیرتر پیدا می‌شود.
"""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, model_validator

from app.models.receipt import RECEIPT_TYPES


class _AmountLine(BaseModel):
    amount: Decimal
    description: str = ""

    @model_validator(mode="after")
    def validate_amount(self) -> "_AmountLine":
        if self.amount <= 0:
            raise ValueError("مبلغ هر جزء باید بزرگ‌تر از صفر باشد")
        return self


class ReceiptCashIn(_AmountLine):
    """وجه نقد (§۷). `cashbox_id` خالی = صندوقِ پیش‌فرض، مثلِ بقیه‌ی مسیرها."""

    cashbox_id: UUID | None = None


class ReceiptTransferIn(_AmountLine):
    """حواله‌ی بانکی (§۱۴ §۱۵) — به یک `BankAccount` واقعی، نه متنِ آزاد."""

    bank_account_id: UUID
    #: شماره‌ی حواله، همان‌طور که بانک داده. جدا از شماره‌ی رسید و شماره‌ی سند.
    #:
    #: **تاریخِ جدا برای حواله ذخیره نمی‌شود.** رسید یک رویداد است و یک تاریخ
    #: دارد؛ سند هم روی همان می‌نشیند. تاریخِ دومی که هیچ گزارشی با آن نمی‌خواند
    #: (مانده از دفتر می‌آید، گزارشِ سنی از تاریخِ تراکنش) عددی است که فقط
    #: می‌تواند گمراه کند. اگر پول دیروز رسیده، خودِ رسید را دیروز بزنید.
    reference_no: str = ""
    description2: str = ""


class ReceiptCardIn(_AmountLine):
    """رسیدِ کارت‌خوان (§۱۶ §۱۷).

    **کد پیگیری اجباری است.** §۱۷ می‌گوید این فیلد برای پیدا کردنِ تراکنش و
    تطبیق با تسویه است، نه یک توضیحِ آزاد؛ و یکتاییِ سطحِ‌مستأجرش از قبل
    idempotencyِ رسیدِ کارتی را می‌سازد.
    """

    pos_terminal_id: UUID
    reference_no: str
    trace_no: str = ""
    card_mask: str = ""

    @model_validator(mode="after")
    def validate_card(self) -> "ReceiptCardIn":
        self.reference_no = self.reference_no.strip()
        if not self.reference_no:
            raise ValueError("کد پیگیریِ کارت‌خوان لازم است")
        return self


class ReceiptChequeIn(_AmountLine):
    """چکِ دریافتی (§۱۰ §۱۱ §۱۲).

    این‌جا فقط ورودی است؛ خودِ چک یک `Check` واقعی با چرخه‌ی عمرِ مستقل می‌شود
    (§۱۳) — نه یک JSON داخلِ رسید.
    """

    number: str
    due_date: date
    issue_date: date | None = None
    bank_name: str = ""
    sayad_id: str = ""
    back_number: str = ""
    branch_name: str = ""
    branch_code: str = ""
    account_number: str = ""
    owner_name: str = ""
    description2: str = ""

    @model_validator(mode="after")
    def validate_cheque(self) -> "ReceiptChequeIn":
        self.number = self.number.strip()
        if not self.number:
            raise ValueError("شماره‌ی چک لازم است")
        self.sayad_id = self.sayad_id.strip()
        if self.sayad_id and not self.sayad_id.isdigit():
            raise ValueError("کد صیادی فقط رقم است")
        if self.sayad_id and len(self.sayad_id) != 16:
            raise ValueError("کد صیادی ۱۶ رقم است")
        return self


class ReceiptRelatedDocumentIn(BaseModel):
    """§۲۰ — «بابتِ کدام سند». تخصیصِ نهایی کارِ موتورِ تسویه است، نه این‌جا."""

    document_type: str = "sales_invoice"
    document_id: UUID
    allocated_amount: Decimal = Decimal(0)

    @model_validator(mode="after")
    def validate_related(self) -> "ReceiptRelatedDocumentIn":
        if self.allocated_amount < 0:
            raise ValueError("مبلغ تخصیص نمی‌تواند منفی باشد")
        return self


class ReceiptIn(BaseModel):
    receipt_type: str = "customer"
    contact_id: UUID
    receipt_date: date
    #: مبالغِ اجزا به **همین** ارزند؛ سند از معادلِ پایه‌شان می‌خورد (§۹).
    currency_code: str = "IRR"
    exchange_rate: Decimal = Decimal(1)
    #: §۲۳ — تخفیفِ تسویه پول نیست. بدهی را می‌بندد بی‌آنکه چیزی وارد صندوق شود،
    #: پس حسابش را کاربر می‌دهد؛ کوبیتا نقشِ سیستمیِ «تخفیف» ندارد و ساختنِ یکی
    #: یعنی حدس‌زدنِ چیزی که چارتِ هر کسب‌وکار جورِ خودش می‌چیند.
    discount_amount: Decimal = Decimal(0)
    discount_account_id: UUID | None = None
    description: str = ""
    description2: str = ""
    #: §۲۹ — فقط ذخیره می‌شود؛ هیچ قاعده‌ای رویش سوار نیست.
    establishment: str = ""

    cash: list[ReceiptCashIn] = []
    transfers: list[ReceiptTransferIn] = []
    cards: list[ReceiptCardIn] = []
    cheques: list[ReceiptChequeIn] = []
    related_documents: list[ReceiptRelatedDocumentIn] = []

    @model_validator(mode="after")
    def validate_receipt(self) -> "ReceiptIn":
        if self.receipt_type not in RECEIPT_TYPES:
            raise ValueError("نوع رسید معتبر نیست")
        if not (self.cash or self.transfers or self.cards or self.cheques):
            raise ValueError("رسید باید دستِ‌کم یک جزء داشته باشد")
        if self.exchange_rate <= 0:
            raise ValueError("نرخ ارز باید بزرگ‌تر از صفر باشد")
        if self.discount_amount < 0:
            raise ValueError("تخفیف نمی‌تواند منفی باشد")
        if self.discount_amount and self.discount_account_id is None:
            raise ValueError("برای ثبت تخفیف باید حساب تخفیف را انتخاب کنید")
        return self


class ReceiptComponentOut(BaseModel):
    """یک جزء، هر چهار نوع با یک شکل — چون فهرست و چاپ همه را کنارِ هم می‌خواهند."""

    kind: str  # cash | transfer | card | cheque
    label: str
    amount: Decimal
    description: str = ""
    #: شناسه‌ی موجودیتِ واقعی: تراکنشِ خزانه یا چک. §۳۸ از همین به چک می‌رسد.
    source_id: UUID | None = None
    reference_no: str = ""
    due_date: date | None = None
    status: str = ""


class ReceiptOut(BaseModel):
    id: UUID
    number: int
    receipt_type: str
    receipt_type_label: str
    contact_id: UUID
    contact_name: str
    receipt_date: date
    counterparty_account_id: UUID
    discount_account_id: UUID | None = None
    currency_code: str
    exchange_rate: Decimal
    receipt_amount: Decimal
    base_currency_amount: Decimal
    discount_amount: Decimal
    settlement_total: Decimal
    description: str
    description2: str
    establishment: str = ""
    journal_entry_id: UUID
    #: §۳۵ — «وجه نقد، چک، حواله». **مشتق**، نه متنی که کاربر تایپ کند.
    items_summary: str
    components: list[ReceiptComponentOut] = []
    related_documents: list[dict] = []
    voided_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    created_by_name: str = ""
    updated_by_name: str = ""


class ReceiptVoidIn(BaseModel):
    reason: str = ""
    void_date: date | None = None


class RasComponentIn(BaseModel):
    """یک قلم برای راس‌گیری — مبلغ و تاریخِ مؤثرش. بی‌ارتباط با ذخیره‌سازی."""

    amount: Decimal
    due_date: date


class RasIn(BaseModel):
    """§۲۷ — کدام اجزا در محاسبه بیایند، و چک‌های هم‌تاریخِ مبنا چه شوند."""

    base_date: date
    rows: list[RasComponentIn] = []
    include_same_day: bool = True

    @model_validator(mode="after")
    def validate_ras(self) -> "RasIn":
        if not self.rows:
            raise ValueError("برای راس‌گیری دستِ‌کم یک قلم لازم است")
        return self


class RasOut(BaseModel):
    #: تاریخِ متوسطِ وزنی — همان «راس».
    ras_date: date
    #: فاصله‌ی وزنی از تاریخِ مبنا، به روز.
    average_days: Decimal
    total_amount: Decimal
    counted_rows: int
    skipped_rows: int
