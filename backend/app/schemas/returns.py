from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, field_validator, model_validator


class SalesReturnLineIn(BaseModel):
    """یک قلمِ برگشتی.

    `sales_invoice_line_id` اختیاری است و **عمداً**: `marketplace` و اپِ موبایل
    کالا-محور می‌فرستند و شکلِ درخواستشان نباید بشکند. سرویس هر ورودیِ
    کالا-محور را خودش روی ردیف‌های همان کالا پخش می‌کند (قدیمی‌ترین اول)، پس
    ردیفِ ذخیره‌شده در هر حال هویتِ مبدأ دارد.
    """

    item_id: UUID | None = None
    sales_invoice_line_id: UUID | None = None
    qty: Decimal
    return_reason_id: UUID | None = None
    description: str = ""

    @model_validator(mode="after")
    def validate_positive(self) -> "SalesReturnLineIn":
        if self.qty <= 0:
            raise ValueError("تعداد باید بزرگ‌تر از صفر باشد")
        if self.item_id is None and self.sales_invoice_line_id is None:
            raise ValueError("هر ردیفِ برگشت باید کالا یا ردیفِ فاکتورِ مبدأ داشته باشد")
        return self


class SalesReturnIn(BaseModel):
    return_date: date
    sales_invoice_id: UUID
    description: str = ""
    lines: list[SalesReturnLineIn]

    @model_validator(mode="after")
    def validate_lines(self) -> "SalesReturnIn":
        if not self.lines:
            raise ValueError("برگشت از فروش باید حداقل یک ردیف داشته باشد")
        return self


class SalesReturnLineOut(BaseModel):
    id: UUID
    item_id: UUID
    sales_invoice_line_id: UUID | None = None
    qty: Decimal
    unit_price: Decimal
    unit_cost: Decimal
    return_reason_id: UUID | None = None
    description: str

    model_config = {"from_attributes": True}


class SalesReturnOut(BaseModel):
    id: UUID
    number: int | None
    return_date: date
    sales_invoice_id: UUID
    description: str
    total_amount: Decimal
    total_cost: Decimal
    tax_rate: Decimal
    journal_entry_id: UUID | None
    voided_at: datetime | None = None
    void_reason: str = ""

    #: مشتق در `returns.attach_return_state` — هیچ‌کدام ستونِ ذخیره‌شده نیستند (§۹۲).
    final_amount: Decimal = Decimal(0)
    settled_amount: Decimal = Decimal(0)
    remaining_amount: Decimal = Decimal(0)
    accounting_status: str = "unposted"
    financial_status: str = "unsettled"
    #: **برگشتِ تجاری ≠ برگشتِ فیزیکی.** `inline` = خودِ این سند موجودی را برگردانده
    #: (برگشت‌های پیش از مهاجرتِ ۰۱۳۴ و فاکتورهای بی‌خروجِ قدیمی)؛ `issue_return` =
    #: کالا با «برگشت خروج انبار» برمی‌گردد و وضعیتش مشتق است.
    stock_mode: str = "inline"
    physical_status: str = "inline"  # inline | none | not_returned | partially_returned | fully_returned
    physical_qty: Decimal = Decimal(0)
    physical_returned_qty: Decimal = Decimal(0)
    physical_remaining_qty: Decimal = Decimal(0)
    lines: list[SalesReturnLineOut]

    model_config = {"from_attributes": True}


class ReturnableLineOut(BaseModel):
    """یک **ردیفِ** «قابلِ برگشت» از یک فاکتور.

    هویتِ ردیفِ مبدأ حمل می‌شود تا فرم بتواند بگوید «از کدام ردیف، با کدام
    قیمت» — فاکتوری که یک کالا را دو بار با دو قیمت فروخته، اینجا دو سطر دارد.
    """

    sales_invoice_line_id: UUID | None = None
    purchase_invoice_line_id: UUID | None = None
    invoice_number: int | None = None
    item_id: UUID
    item_name: str
    unit: str
    sold: Decimal
    already_returned: Decimal
    remaining: Decimal
    unit_price: Decimal


class PurchaseReturnLineIn(BaseModel):
    """قرینه‌ی `SalesReturnLineIn` — همان قاعده‌ی اختیاری‌بودنِ ردیفِ مبدأ."""

    item_id: UUID | None = None
    purchase_invoice_line_id: UUID | None = None
    #: **لنگرِ فیزیکی (مبنا).** وقتی یک کالا چند بار با بهای متفاوت وارد شده،
    #: باید معلوم باشد کدام ورود برگشت می‌خورد.
    warehouse_receipt_line_id: UUID | None = None
    qty: Decimal
    #: «فیِ مرجوعی توافقی». `None` یعنی «همان ارزشِ دفتری» — پس گردشِ عادی
    #: هیچ عددی وارد نمی‌کند و هیچ اختلافی نمی‌سازد.
    agreed_unit_value: Decimal | None = None
    description: str = ""

    @model_validator(mode="after")
    def validate_positive(self) -> "PurchaseReturnLineIn":
        if self.qty <= 0:
            raise ValueError("تعداد باید بزرگ‌تر از صفر باشد")
        if (
            self.item_id is None
            and self.purchase_invoice_line_id is None
            and self.warehouse_receipt_line_id is None
        ):
            raise ValueError("هر ردیفِ برگشت باید کالا یا ردیفِ مبدأ داشته باشد")
        if self.agreed_unit_value is not None and self.agreed_unit_value < 0:
            raise ValueError("مبلغ مرجوعی توافقی نمی‌تواند منفی باشد")
        return self


class PurchaseReturnIn(BaseModel):
    """برگشت کالا — با لنگر روی فاکتورِ خرید یا روی رسیدِ انبار.

    `purchase_invoice_id` دیگر اجباری نیست: رسیدِ **مستقیم** فاکتوری ندارد.
    """

    return_date: date
    purchase_invoice_id: UUID | None = None
    warehouse_receipt_id: UUID | None = None
    #: «تحویل‌گیرنده» — کسی که کالای خارج‌شده را می‌گیرد. خالی یعنی همان طرفِ
    #: سندِ مبدأ.
    receiver_id: UUID | None = None
    #: چهار نوع؛ «موجودی اول دوره» عمداً نیست.
    return_type: str = "purchase_domestic"
    currency_code: str | None = None
    exchange_rate: Decimal = Decimal(1)
    description: str = ""
    lines: list[PurchaseReturnLineIn]

    @field_validator("return_type")
    @classmethod
    def _known_type(cls, v: str) -> str:
        from app.models.returns import RETURN_TYPES

        if v not in RETURN_TYPES:
            raise ValueError("نوعِ برگشت نامعتبر است")
        return v

    @model_validator(mode="after")
    def validate_lines(self) -> "PurchaseReturnIn":
        if not self.lines:
            raise ValueError("برگشت از خرید باید حداقل یک ردیف داشته باشد")
        if self.purchase_invoice_id is None and self.warehouse_receipt_id is None:
            raise ValueError("برگشت باید به فاکتور خرید یا رسید انبار گره بخورد")
        anchored = [l for l in self.lines if l.warehouse_receipt_line_id is not None]
        if anchored and len({l.warehouse_receipt_line_id for l in anchored}) != len(anchored):
            raise ValueError("هر ردیف رسید در یک برگشت فقط یک‌بار مجاز است")
        return self


class PurchaseReturnLineOut(BaseModel):
    id: UUID
    seq: int = 0
    item_id: UUID
    purchase_invoice_line_id: UUID | None = None
    warehouse_receipt_line_id: UUID | None = None
    qty: Decimal
    #: «فی» و «فی تمام‌شده» هر دو — یکی نیستند.
    unit_cost: Decimal
    freight_share: Decimal = Decimal(0)
    landed_amount: Decimal = Decimal(0)
    #: مبالغ مرجوعی توافقی، مستقل و قابلِ تفکیک.
    agreed_unit_value: Decimal = Decimal(0)
    agreed_amount: Decimal = Decimal(0)
    tax_rate_snapshot: Decimal = Decimal(0)
    tax_amount_snapshot: Decimal = Decimal(0)
    description: str

    model_config = {"from_attributes": True}


class PurchaseReturnOut(BaseModel):
    id: UUID
    number: int | None
    return_date: date
    purchase_invoice_id: UUID | None = None
    warehouse_receipt_id: UUID | None = None
    warehouse_id: UUID | None = None
    receiver_id: UUID | None = None
    return_type: str = "purchase_domestic"
    currency_code: str | None = None
    exchange_rate: Decimal = Decimal(1)
    description: str
    total_amount: Decimal
    #: **«خالص» و «خالص توافقی» — دو ستونِ جدا در فهرستِ مرجع، و عمداً جدا.**
    base_amount: Decimal = Decimal(0)
    agreed_total: Decimal = Decimal(0)
    tax_rate: Decimal
    journal_entry_id: UUID | None
    voided_at: datetime | None = None
    void_reason: str = ""

    #: مشتق در `returns.attach_return_state` — هیچ‌کدام ستونِ ذخیره‌شده نیستند (§۹۲).
    final_amount: Decimal = Decimal(0)
    settled_amount: Decimal = Decimal(0)
    remaining_amount: Decimal = Decimal(0)
    accounting_status: str = "unposted"
    financial_status: str = "unsettled"
    lines: list[PurchaseReturnLineOut]

    model_config = {"from_attributes": True}


class SalesReturnReasonIn(BaseModel):
    """علتِ برگشتِ کالا (§۲۴ §۲۵) — عنوان، عنوانِ دوم، فعال/غیرفعال."""

    title: str
    title2: str = ""
    is_active: bool = True

    @model_validator(mode="after")
    def validate_title(self) -> "SalesReturnReasonIn":
        if not self.title.strip():
            raise ValueError("عنوانِ علتِ برگشت نمی‌تواند خالی باشد")
        return self


class SalesReturnReasonOut(BaseModel):
    id: UUID
    title: str
    title2: str
    is_active: bool

    model_config = {"from_attributes": True}


class VoidIn(BaseModel):
    """دلیلِ ابطال و — در صورتِ بسته‌بودنِ دوره — تاریخِ سندِ معکوس."""

    reason: str = ""
    void_date: date | None = None


class ReceiptReturnableLineOut(BaseModel):
    """یک ردیفِ پنجره‌ی «مبنا» — چه چیزی از این رسید هنوز قابلِ برگشت است.

    ستون‌هایی که فصل نام می‌برد: تاریخ، باقیمانده، کد کالا، عنوان، مقدار.
    `return_status` **مشتق** است، نه یک بولینِ مستقل.
    """

    warehouse_receipt_line_id: UUID
    purchase_invoice_line_id: UUID | None = None
    receipt_number: int
    receipt_date: date
    item_id: UUID
    item_code: str = ""
    item_name: str = ""
    unit: str = ""
    received: Decimal
    already_returned: Decimal
    remaining: Decimal
    unit_cost: Decimal
    landed_unit_cost: Decimal
    return_status: str
