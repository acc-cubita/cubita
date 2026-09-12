from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, model_validator


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
    qty: Decimal
    description: str = ""

    @model_validator(mode="after")
    def validate_positive(self) -> "PurchaseReturnLineIn":
        if self.qty <= 0:
            raise ValueError("تعداد باید بزرگ‌تر از صفر باشد")
        if self.item_id is None and self.purchase_invoice_line_id is None:
            raise ValueError("هر ردیفِ برگشت باید کالا یا ردیفِ فاکتورِ مبدأ داشته باشد")
        return self


class PurchaseReturnIn(BaseModel):
    return_date: date
    purchase_invoice_id: UUID
    description: str = ""
    lines: list[PurchaseReturnLineIn]

    @model_validator(mode="after")
    def validate_lines(self) -> "PurchaseReturnIn":
        if not self.lines:
            raise ValueError("برگشت از خرید باید حداقل یک ردیف داشته باشد")
        return self


class PurchaseReturnLineOut(BaseModel):
    id: UUID
    item_id: UUID
    purchase_invoice_line_id: UUID | None = None
    qty: Decimal
    unit_cost: Decimal
    description: str

    model_config = {"from_attributes": True}


class PurchaseReturnOut(BaseModel):
    id: UUID
    number: int | None
    return_date: date
    purchase_invoice_id: UUID
    description: str
    total_amount: Decimal
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
