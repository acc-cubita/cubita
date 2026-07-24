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


class SalesInvoiceIn(BaseModel):
    invoice_date: date
    warehouse_id: UUID
    contact_id: UUID | None = None
    cost_center_id: UUID | None = None
    description: str = ""
    lines: list[SalesInvoiceLineIn]
    #: نرخ مالیات بر ارزش افزوده به درصد (مثلاً 10). صفر = بدون مالیات/معاف.
    tax_rate: Decimal = Decimal(0)
    source_order_id: int | None = None  # فقط برای فاکتورهای وارداتی از سایت فروشگاهی پر می‌شود

    @model_validator(mode="after")
    def validate_lines(self) -> "SalesInvoiceIn":
        if not self.lines:
            raise ValueError("فاکتور باید حداقل یک ردیف داشته باشد")
        if not (Decimal(0) <= self.tax_rate <= Decimal(100)):
            raise ValueError("نرخ مالیات باید بین ۰ تا ۱۰۰ باشد")
        return self


class SalesInvoiceLineOut(BaseModel):
    id: UUID
    item_id: UUID
    qty: Decimal
    unit_price: Decimal
    discount: Decimal = Decimal(0)
    unit_cost: Decimal
    description: str

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
    total_cost: Decimal
    tax_rate: Decimal
    tax_amount: Decimal
    journal_entry_id: UUID | None
    source_order_id: int | None
    #: بدون این، رابط کاربری فاکتور باطل را عیناً مثل معتبر نشان می‌دهد
    voided_at: datetime | None = None
    void_reason: str = ""
    lines: list[SalesInvoiceLineOut]

    model_config = {"from_attributes": True}


class PurchaseInvoiceLineIn(BaseModel):
    item_id: UUID
    qty: Decimal
    unit_cost: Decimal
    #: تخفیفِ ردیف به مبلغ. بهای موجودی از همان اول پس از تخفیف ثبت می‌شود.
    discount: Decimal = Decimal(0)
    description: str = ""

    @model_validator(mode="after")
    def validate_positive(self) -> "PurchaseInvoiceLineIn":
        if self.qty <= 0:
            raise ValueError("تعداد باید بزرگ‌تر از صفر باشد")
        if self.unit_cost < 0:
            raise ValueError("بهای واحد نمی‌تواند منفی باشد")
        if self.discount < 0:
            raise ValueError("تخفیف نمی‌تواند منفی باشد")
        if self.discount > self.qty * self.unit_cost:
            raise ValueError("تخفیف نمی‌تواند از مبلغ ردیف بیشتر باشد")
        return self


class PurchaseInvoiceIn(BaseModel):
    invoice_date: date
    warehouse_id: UUID
    contact_id: UUID | None = None
    cost_center_id: UUID | None = None
    description: str = ""
    lines: list[PurchaseInvoiceLineIn]
    #: نرخ مالیات بر ارزش افزوده به درصد (مثلاً 10). صفر = بدون مالیات/معاف.
    tax_rate: Decimal = Decimal(0)

    @model_validator(mode="after")
    def validate_lines(self) -> "PurchaseInvoiceIn":
        if not self.lines:
            raise ValueError("فاکتور باید حداقل یک ردیف داشته باشد")
        if not (Decimal(0) <= self.tax_rate <= Decimal(100)):
            raise ValueError("نرخ مالیات باید بین ۰ تا ۱۰۰ باشد")
        return self


class PurchaseInvoiceLineOut(BaseModel):
    id: UUID
    item_id: UUID
    qty: Decimal
    unit_cost: Decimal
    discount: Decimal = Decimal(0)
    description: str

    model_config = {"from_attributes": True}


class PurchaseInvoiceOut(BaseModel):
    id: UUID
    number: int | None
    invoice_date: date
    warehouse_id: UUID
    contact_id: UUID | None
    cost_center_id: UUID | None = None
    description: str
    total_amount: Decimal
    total_discount: Decimal = Decimal(0)
    tax_rate: Decimal
    tax_amount: Decimal
    journal_entry_id: UUID | None
    voided_at: datetime | None = None
    void_reason: str = ""
    lines: list[PurchaseInvoiceLineOut]

    model_config = {"from_attributes": True}
