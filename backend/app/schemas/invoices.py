from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, model_validator


class SalesInvoiceLineIn(BaseModel):
    item_id: UUID
    qty: Decimal
    unit_price: Decimal
    #: تخفیفِ ردیف به مبلغ (نه درصد). درصد در رابط کاربری به مبلغ تبدیل می‌شود تا
    #: رقمِ ذخیره‌شده بی‌ابهام باشد و با فیلدِ تخفیفِ صورتحساب مؤدیان هم بخواند.
    discount: Decimal = Decimal(0)
    description: str = ""
    source_quotation_line_id: UUID | None = None

    @model_validator(mode="after")
    def validate_positive(self) -> "SalesInvoiceLineIn":
        if self.qty <= 0:
            raise ValueError("تعداد باید بزرگ‌تر از صفر باشد")
        if self.unit_price < 0:
            raise ValueError("قیمت واحد نمی‌تواند منفی باشد")
        if self.discount < 0:
            raise ValueError("تخفیف نمی‌تواند منفی باشد")
        # تخفیفِ بیشتر از مبلغِ ردیف یعنی خالصِ منفی؛ به‌جای گردکردنِ بی‌صدا رد می‌شود
        # تا اشتباهِ ورود اطلاعات همان‌جا دیده شود.
        if self.discount > self.qty * self.unit_price:
            raise ValueError("تخفیف نمی‌تواند از مبلغ ردیف بیشتر باشد")
        return self


#: سقفِ قدرمطلقِ گِرد کردن — رند برای «رند کردنِ خرده‌ریز» است، نه ابزارِ تعدیلِ
#: دلخواهِ درآمد. تا نزدیکِ رند به بالاترین پله‌ی رایج (۵۰٬۰۰۰) اجازه می‌دهد.
MAX_ROUNDING = Decimal(100_000)


class SalesInvoiceIn(BaseModel):
    invoice_date: date
    warehouse_id: UUID
    contact_id: UUID | None = None
    cost_center_id: UUID | None = None
    description: str = ""
    #: واسطه‌ی معامله. باید طرف‌حسابی با نقشِ «واسط» باشد؛ کارمزدش از نرخِ همان
    #: طرف‌حساب حساب و روی فاکتور قفل می‌شود. None = بی‌واسطه.
    broker_id: UUID | None = None
    #: فروشنده‌ی این فاکتور — **مبنای محاسبه‌ی پورسانت**. کاربرِ سامانه است نه
    #: طرف‌حساب. تا امروز ستونش بود ولی هیچ‌جا فرستاده نمی‌شد، پس «محاسبه پورسانت»
    #: همیشه صفر ردیف برمی‌گرداند.
    salesperson_id: UUID | None = None
    #: نوعِ فروش (نقدی، اعتباری، صادراتی…). None = تعیین‌نشده.
    sale_type_id: UUID | None = None
    lines: list[SalesInvoiceLineIn]
    #: نرخ مالیات بر ارزش افزوده به درصد (مثلاً 10). صفر = بدون مالیات/معاف.
    tax_rate: Decimal = Decimal(0)
    #: تخفیفِ کلِ فاکتور به مبلغ (درصد در رابط کاربری به مبلغ تبدیل می‌شود). هنگام ثبت
    #: به‌نسبتِ خالصِ هر ردیف تسهیم می‌شود، پس پایه‌ی مالیات و درآمد هر دو پس از آن‌اند.
    invoice_discount: Decimal = Decimal(0)
    #: تعدیلِ گِرد کردنِ مبلغِ نهایی (پس از مالیات)، علامت‌دار: منفی = رند به پایین.
    rounding: Decimal = Decimal(0)
    source_order_id: int | None = None  # فقط برای فاکتورهای وارداتی از سایت فروشگاهی پر می‌شود
    source_quotation_id: UUID | None = None
    #: ارز فاکتور (مثل USD). None/خالی = پایه (ریال). مبالغِ سطرها همیشه پایه‌اند —
    #: کلاینت پیش از ارسال با نرخ تبدیل می‌کند؛ این‌ها فقط برای نمایش ذخیره می‌شوند.
    currency_code: str | None = None
    exchange_rate: Decimal = Decimal(1)

    @model_validator(mode="after")
    def validate_lines(self) -> "SalesInvoiceIn":
        if not self.lines:
            raise ValueError("فاکتور باید حداقل یک ردیف داشته باشد")
        if not (Decimal(0) <= self.tax_rate <= Decimal(100)):
            raise ValueError("نرخ مالیات باید بین ۰ تا ۱۰۰ باشد")
        if self.invoice_discount < 0:
            raise ValueError("تخفیفِ کلِ فاکتور نمی‌تواند منفی باشد")
        if abs(self.rounding) > MAX_ROUNDING:
            raise ValueError("مبلغِ گِرد کردن خارج از حدِّ مجاز است")
        if self.currency_code and self.exchange_rate <= 0:
            raise ValueError("نرخ ارز باید بزرگ‌تر از صفر باشد")
        return self


class SalesInvoiceLineOut(BaseModel):
    id: UUID
    item_id: UUID
    qty: Decimal
    unit_price: Decimal
    discount: Decimal = Decimal(0)
    unit_cost: Decimal
    description: str
    source_quotation_line_id: UUID | None = None

    model_config = {"from_attributes": True}


class SalesInvoiceOut(BaseModel):
    id: UUID
    number: int | None
    invoice_date: date
    warehouse_id: UUID
    contact_id: UUID | None
    cost_center_id: UUID | None = None
    description: str
    total_amount: Decimal
    total_discount: Decimal = Decimal(0)
    invoice_discount: Decimal = Decimal(0)
    rounding: Decimal = Decimal(0)
    total_cost: Decimal
    tax_rate: Decimal
    tax_amount: Decimal
    currency_code: str | None = None
    exchange_rate: Decimal = Decimal(1)
    journal_entry_id: UUID | None
    source_order_id: int | None
    source_quotation_id: UUID | None = None
    #: بدون این، رابط کاربری فاکتور باطل را عیناً مثل معتبر نشان می‌دهد
    voided_at: datetime | None = None
    void_reason: str = ""
    #: فاکتورِ بسته دیگر ویرایش و ابطال نمی‌شود — رابط باید بداند تا دکمه‌ی بی‌اثر
    #: نشان ندهد. NULL = باز.
    closed_at: datetime | None = None
    salesperson_id: UUID | None = None
    sale_type_id: UUID | None = None
    broker_id: UUID | None = None
    #: کارمزدِ قفل‌شده در لحظه‌ی ثبت — نه محاسبه‌ی دوباره از نرخِ امروزِ واسطه.
    broker_commission: Decimal = Decimal(0)
    #: نامِ فروشنده و نوعِ فروش برای نمایش؛ روتر پُرشان می‌کند.
    salesperson_name: str | None = None
    sale_type_name: str | None = None
    #: نامِ واسطه برای نمایش؛ روتر پُرش می‌کند، پس در پاسخِ خام None می‌ماند.
    broker_name: str | None = None
    #: ثبت‌کننده‌ی فاکتور — چه کسی و با چه نقشی آن را زده. `created_by_id` همیشه هست؛
    #: نام/نقش را روتر پُر می‌کند (join به users/memberships)، پس برای پاسخِ خام None می‌مانند.
    created_by_id: UUID | None = None
    created_by_name: str | None = None
    created_by_role: str | None = None
    lines: list[SalesInvoiceLineOut]

    model_config = {"from_attributes": True}


class SalesSummaryOut(BaseModel):
    """خلاصه‌ی فروش، محاسبه‌شده در پایگاه‌داده (نه با دانلودِ همه‌ی فاکتورها در کلاینت).

    فقط فاکتورهای باطل‌نشده. مبالغ همه پایه (ریال)اند.
    """
    invoice_count: int
    total_net: Decimal        # جمعِ خالص (پس از تخفیف، بدون مالیات)
    total_tax: Decimal
    total_with_tax: Decimal   # خالص + مالیات = مبلغِ واقعیِ فروش
    total_cost: Decimal       # بهای تمام‌شده‌ی کالای فروش‌رفته
    gross_profit: Decimal     # خالص − بهای تمام‌شده
    margin_pct: Decimal       # حاشیه‌ی سود = سود ÷ خالص × ۱۰۰
    last_30_with_tax: Decimal # فروشِ ۳۰ روزِ اخیر (با مالیات)
    avg_invoice: Decimal      # میانگینِ هر فاکتور (با مالیات)


class PurchaseSummaryOut(BaseModel):
    """خلاصه‌ی خرید، محاسبه‌شده در پایگاه‌داده. فقط فاکتورهای باطل‌نشده.

    خرید سود ندارد (خودش بهای تمام‌شده است)، پس فقط جمع‌ها گزارش می‌شوند.
    """
    invoice_count: int
    total_net: Decimal        # جمعِ خالص (پس از تخفیف، بدون مالیات)
    total_tax: Decimal
    total_with_tax: Decimal   # خالص + مالیات = مبلغِ پرداختنی به تأمین‌کننده
    last_30_with_tax: Decimal
    avg_invoice: Decimal


class PurchaseInvoiceLineIn(BaseModel):
    item_id: UUID
    qty: Decimal
    unit_cost: Decimal
    #: تخفیفِ ردیف به مبلغ. بهای موجودی از همان اول پس از تخفیف ثبت می‌شود.
    discount: Decimal = Decimal(0)
    addition: Decimal = Decimal(0)
    duty_amount: Decimal = Decimal(0)
    description: str = ""

    @model_validator(mode="after")
    def validate_positive(self) -> "PurchaseInvoiceLineIn":
        if self.qty <= 0:
            raise ValueError("تعداد باید بزرگ‌تر از صفر باشد")
        if self.unit_cost < 0:
            raise ValueError("بهای واحد نمی‌تواند منفی باشد")
        if self.discount < 0:
            raise ValueError("تخفیف نمی‌تواند منفی باشد")
        if self.addition < 0 or self.duty_amount < 0:
            raise ValueError("اضافات و عوارض نمی‌توانند منفی باشند")
        if self.discount > self.qty * self.unit_cost:
            raise ValueError("تخفیف نمی‌تواند از مبلغ ردیف بیشتر باشد")
        return self


class PurchaseInvoiceIn(BaseModel):
    invoice_date: date
    # اختیاری و فقط برای سازگاری گردش قدیمی «خرید+ورود هم‌زمان».
    warehouse_id: UUID | None = None
    contact_id: UUID | None = None
    supplier_invoice_number: str = ""
    cost_center_id: UUID | None = None
    description: str = ""
    description2: str = ""
    lines: list[PurchaseInvoiceLineIn]
    #: نرخ مالیات بر ارزش افزوده به درصد (مثلاً 10). صفر = بدون مالیات/معاف.
    tax_rate: Decimal = Decimal(0)
    #: تخفیفِ کلِ فاکتور به مبلغ (درصد در رابط کاربری به مبلغ تبدیل می‌شود). هنگام ثبت
    #: به‌نسبتِ خالصِ هر ردیف تسهیم می‌شود، پس ارزش‌گذاریِ موجودی و پایه‌ی مالیات پس از آن‌اند.
    invoice_discount: Decimal = Decimal(0)
    invoice_addition: Decimal = Decimal(0)
    duty_amount: Decimal = Decimal(0)
    #: ارز فاکتور (مثل USD). None/خالی = پایه. مبالغِ سطرها همیشه پایه‌اند.
    currency_code: str | None = None
    exchange_rate: Decimal = Decimal(1)

    @model_validator(mode="after")
    def validate_lines(self) -> "PurchaseInvoiceIn":
        if not self.lines:
            raise ValueError("فاکتور باید حداقل یک ردیف داشته باشد")
        if not (Decimal(0) <= self.tax_rate <= Decimal(100)):
            raise ValueError("نرخ مالیات باید بین ۰ تا ۱۰۰ باشد")
        if self.invoice_discount < 0:
            raise ValueError("تخفیفِ کلِ فاکتور نمی‌تواند منفی باشد")
        if self.invoice_addition < 0 or self.duty_amount < 0:
            raise ValueError("اضافات و عوارض نمی‌توانند منفی باشند")
        if self.currency_code and self.exchange_rate <= 0:
            raise ValueError("نرخ ارز باید بزرگ‌تر از صفر باشد")
        return self


class PurchaseInvoiceLineOut(BaseModel):
    id: UUID
    item_id: UUID
    qty: Decimal
    unit_cost: Decimal
    discount: Decimal = Decimal(0)
    addition: Decimal = Decimal(0)
    duty_amount: Decimal = Decimal(0)
    tax_rate_snapshot: Decimal = Decimal(0)
    tax_amount_snapshot: Decimal = Decimal(0)
    item_code_snapshot: str = ""
    item_name_snapshot: str = ""
    unit_snapshot: str = ""
    received_qty: Decimal = Decimal(0)
    remaining_qty: Decimal = Decimal(0)
    description: str

    model_config = {"from_attributes": True}


class PurchaseInvoiceOut(BaseModel):
    id: UUID
    number: int | None
    invoice_date: date
    warehouse_id: UUID | None = None
    contact_id: UUID | None
    supplier_invoice_number: str = ""
    cost_center_id: UUID | None = None
    description: str
    description2: str = ""
    total_amount: Decimal
    total_discount: Decimal = Decimal(0)
    invoice_discount: Decimal = Decimal(0)
    total_additions: Decimal = Decimal(0)
    total_duties: Decimal = Decimal(0)
    tax_rate: Decimal
    tax_amount: Decimal
    currency_code: str | None = None
    exchange_rate: Decimal = Decimal(1)
    transaction_total_amount: Decimal = Decimal(0)
    transaction_tax_amount: Decimal = Decimal(0)
    final_amount: Decimal = Decimal(0)
    transaction_final_amount: Decimal = Decimal(0)
    received_total_qty: Decimal = Decimal(0)
    inventory_status: str = "not_received"
    settled_amount: Decimal = Decimal(0)
    remaining_amount: Decimal = Decimal(0)
    financial_status: str = "unsettled"
    related_payment_count: int = 0
    journal_entry_id: UUID | None
    voided_at: datetime | None = None
    void_reason: str = ""
    #: ثبت‌کننده‌ی فاکتور — نام/نقش را روتر پُر می‌کند (join به users/memberships).
    created_by_id: UUID | None = None
    created_by_name: str | None = None
    created_by_role: str | None = None
    lines: list[PurchaseInvoiceLineOut]

    model_config = {"from_attributes": True}


class WarehouseReceiptLineIn(BaseModel):
    purchase_invoice_line_id: UUID
    qty: Decimal
    description: str = ""

    @model_validator(mode="after")
    def validate_qty(self) -> "WarehouseReceiptLineIn":
        if self.qty <= 0:
            raise ValueError("مقدار تحویل باید بزرگ‌تر از صفر باشد")
        return self


class WarehouseReceiptIn(BaseModel):
    receipt_date: date
    warehouse_id: UUID
    description: str = ""
    lines: list[WarehouseReceiptLineIn]

    @model_validator(mode="after")
    def validate_lines(self) -> "WarehouseReceiptIn":
        if not self.lines:
            raise ValueError("رسید انبار باید حداقل یک ردیف داشته باشد")
        if len({line.purchase_invoice_line_id for line in self.lines}) != len(self.lines):
            raise ValueError("هر ردیف فاکتور در رسید فقط یک‌بار مجاز است")
        return self


class WarehouseReceiptLineOut(BaseModel):
    id: UUID
    purchase_invoice_line_id: UUID
    item_id: UUID
    qty: Decimal
    unit_cost: Decimal
    item_code_snapshot: str = ""
    item_name_snapshot: str = ""
    unit_snapshot: str = ""
    description: str = ""

    model_config = {"from_attributes": True}


class WarehouseReceiptOut(BaseModel):
    id: UUID
    number: int
    receipt_date: date
    purchase_invoice_id: UUID
    warehouse_id: UUID
    status: str
    description: str = ""
    voided_at: datetime | None = None
    void_reason: str = ""
    created_by_id: UUID
    lines: list[WarehouseReceiptLineOut]

    model_config = {"from_attributes": True}
