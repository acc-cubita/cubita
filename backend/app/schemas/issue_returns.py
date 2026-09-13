from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, model_validator

from app.models.issue_returns import ISSUE_RETURN_TYPES


class IssueReturnLineIn(BaseModel):
    """ردیفِ برگشت — «مبنا» یا ردیفِ فاکتور برگشتی است یا ردیفِ خود خروج، نه هر دو."""

    sales_return_line_id: UUID | None = None
    warehouse_issue_line_id: UUID | None = None
    qty: Decimal
    #: خالی یعنی واحدِ اصلی؛ تبدیل فقط در `units.to_primary`.
    unit_id: UUID | None = None
    description: str = ""

    @model_validator(mode="after")
    def validate_line(self) -> "IssueReturnLineIn":
        if self.qty <= 0:
            raise ValueError("مقدارِ برگشت باید بزرگ‌تر از صفر باشد")
        if (self.sales_return_line_id is None) == (self.warehouse_issue_line_id is None):
            raise ValueError("هر ردیفِ برگشت دقیقاً یک مبنا دارد: ردیفِ فاکتور برگشتی یا ردیفِ خروج")
        return self


class IssueReturnIn(BaseModel):
    return_date: date
    return_type: str = "sale"
    warehouse_id: UUID
    deliverer_id: UUID | None = None
    description: str = ""
    lines: list[IssueReturnLineIn]

    @model_validator(mode="after")
    def validate_return(self) -> "IssueReturnIn":
        if self.return_type == "transfer":
            raise ValueError("انتقال بین انبار برگشت ندارد؛ انتقالِ برعکس را از مسیرِ انتقال ثبت کنید")
        if self.return_type not in ISSUE_RETURN_TYPES:
            raise ValueError("نوعِ برگشت نامعتبر است")
        if not self.lines:
            raise ValueError("برگشت خروج انبار باید حداقل یک ردیف داشته باشد")
        if self.return_type == "sale":
            #: مبنای فاکتور برگشتی مشتری را خودش می‌شناسد (و مشتریِ نقدی اصلاً طرف‌حساب
            #: ندارد)؛ فقط خروجِ فروشِ بی‌فاکتور تحویل‌دهنده‌ی صریح می‌خواهد.
            if self.deliverer_id is None and any(line.warehouse_issue_line_id for line in self.lines):
                raise ValueError("برای برگشتِ خروجِ فروش، تحویل‌دهنده را مشخص کنید")
        elif any(line.sales_return_line_id for line in self.lines):
            raise ValueError("فاکتور برگشتی فقط مبنای برگشتِ «فروش» است")
        return self


class IssueReturnLineOut(BaseModel):
    id: UUID
    seq: int = 0
    warehouse_issue_line_id: UUID
    sales_return_line_id: UUID | None = None
    item_id: UUID
    qty: Decimal
    unit_cost: Decimal
    amount: Decimal = Decimal(0)
    account_id: UUID | None = None
    account_code: str = ""
    account_name: str = ""
    cost_center_id: UUID | None = None
    secondary_qty: Decimal | None = None
    secondary_unit_snapshot: str = ""
    item_code_snapshot: str = ""
    item_name_snapshot: str = ""
    unit_snapshot: str = ""
    description: str = ""
    #: شماره‌ی خروج و فاکتور برگشتیِ مبدأ — برای ناوبری در جزئیات.
    issue_id: UUID | None = None
    issue_number: int | None = None
    sales_return_id: UUID | None = None
    sales_return_number: int | None = None

    model_config = {"from_attributes": True}


class IssueReturnOut(BaseModel):
    id: UUID
    number: int
    return_date: date
    return_type: str
    origin: str
    warehouse_id: UUID
    deliverer_id: UUID | None = None
    sales_return_id: UUID | None = None
    description: str = ""
    journal_entry_id: UUID | None = None
    voided_at: datetime | None = None
    void_reason: str = ""
    created_by_id: UUID
    total_qty: Decimal = Decimal(0)
    total_cost: Decimal = Decimal(0)
    lines: list[IssueReturnLineOut]

    model_config = {"from_attributes": True}


class IssueReturnRowOut(BaseModel):
    """ردیفِ فهرستِ برگشت‌ها — Projection از همان سند، با ستون‌هایی که فصل نام می‌برد."""

    id: UUID
    number: int
    return_date: date
    return_type: str
    type_label: str
    origin: str
    warehouse_id: UUID
    warehouse_code: str = ""
    warehouse_name: str = ""
    deliverer_id: UUID | None = None
    deliverer_name: str = ""
    sales_return_numbers: list[int] = []
    issue_numbers: list[int] = []
    journal_entry_id: UUID | None = None
    journal_entry_number: int | None = None
    journal_entry_date: date | None = None
    created_by_name: str = ""
    line_count: int = 0
    total_qty: Decimal = Decimal(0)
    total_cost: Decimal = Decimal(0)
    description: str = ""
    voided_at: datetime | None = None
    void_reason: str = ""


class IssueReturnBasisDocOut(BaseModel):
    """یک سندِ قابلِ انتخاب در پنجره‌ی «مبنا»."""

    kind: str  # sales_return | issue
    id: UUID
    number: int | None = None
    doc_date: date
    party_id: UUID | None = None
    party_name: str = ""
    warehouse_id: UUID | None = None
    warehouse_name: str = ""
    remaining_qty: Decimal


class IssueReturnBasisLineOut(BaseModel):
    """ردیفِ پنجره‌ی «مبنا» — مقدار، برگشت‌خورده و **باقیمانده‌ی مشتق**."""

    kind: str
    basis_line_id: UUID
    item_id: UUID
    item_code: str = ""
    item_name: str = ""
    unit: str = ""
    qty: Decimal
    returned: Decimal
    remaining: Decimal
    unit_cost: Decimal
    amount: Decimal
    source_warehouse_id: UUID | None = None


class IssueReturnBasisOut(BaseModel):
    kind: str
    id: UUID
    number: int | None = None
    doc_date: date
    party_id: UUID | None = None
    party_name: str = ""
    warehouse_id: UUID | None = None
    lines: list[IssueReturnBasisLineOut]
