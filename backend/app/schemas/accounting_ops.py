"""شِماهای عملیاتِ حسابداری — ورودی/خروجیِ هجده عملیاتِ ماژول.

هر عملیاتِ سندساز دو شِمای خروجی دارد: یکی برای **پیش‌نمایش** و یکی برای **نتیجه**.
جدا نگه‌داشتنشان عمدی است — پیش‌نمایش باید ردیف‌به‌ردیف نشان دهد چه سندی زده خواهد
شد، و نتیجه فقط باید بگوید چه شد. یکی‌کردنشان یعنی یکی از دو طرف فیلدهای بی‌معنا
حمل کند.
"""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.accounting import ACCOUNT_TYPES


# ───────────────────────────── نمای کلی ─────────────────────────────


class AccountingOverviewOut(BaseModel):
    temporary_count: int
    permanent_count: int
    voided_count: int
    account_count: int
    group_count: int
    last_number: int | None
    oldest_temporary_date: date | None
    last_close_date: date | None


# ───────────────────────── سند و کارتابل ────────────────────────────


class EntrySummaryOut(BaseModel):
    id: UUID
    number: int | None
    #: عطف و فرعی در کارتابل هم دیده می‌شوند: کسی که سند را بازبینی می‌کند همان
    #: کسی است که با این دو دنبالش می‌گردد.
    atf_number: int | None = None
    sub_number: str | None = None
    entry_date: date
    description: str
    source_type: str
    status: str
    voided_at: datetime | None
    total: Decimal
    line_count: int
    accounts: list[str]


class CartableGroupOut(BaseModel):
    source_type: str
    count: int
    total: Decimal


class CartableOut(BaseModel):
    total_count: int
    groups: list[CartableGroupOut]
    entries: list[EntrySummaryOut]


class FinalizeIn(BaseModel):
    """دستِ‌کم یکی از فیلترها لازم است — «همه‌ی اسنادِ موقتِ تاریخ» یک درخواستِ
    خطرناکِ بی‌قصد است و باید صریح گفته شود."""

    date_from: date | None = None
    date_to: date | None = None
    entry_ids: list[UUID] = Field(default_factory=list)
    source_type: str | None = None


class FinalizeOut(BaseModel):
    count: int
    first_date: date
    last_date: date


# ───────────────────── بازشماره‌گذاری و ادغام ────────────────────────


class RenumberIn(BaseModel):
    date_from: date | None = None
    date_to: date | None = None
    #: انتخابِ دستی. اگر داده شود **جای** بازه می‌نشیند نه کنارش — دو فیلترِ
    #: هم‌زمان یعنی کاربر باید حدس بزند کدام برنده است.
    entry_ids: list[UUID] | None = None
    start_number: int = 1

    @field_validator("start_number")
    @classmethod
    def _positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("شماره‌ی شروع باید دستِ‌کم ۱ باشد")
        return v


class RenumberRowOut(BaseModel):
    id: UUID
    entry_date: date
    description: str
    #: عطف در پیش‌نمایش می‌آید تا کاربر با چشمِ خودش ببیند بازشماره‌گذاری به آن
    #: دست نمی‌زند — همان تضمینی که کلِ دلیلِ وجودِ این ستون است.
    atf_number: int | None = None
    old_number: int | None
    new_number: int
    changed: bool
    status: str
    source_type: str
    accounts: list[str]


class RenumberPreviewOut(BaseModel):
    count: int
    changed_count: int
    #: اسنادِ دائمِ بازه که دست نمی‌خورند — تا روشن باشد چرا نقشه کوچک‌تر از بازه است.
    skipped_permanent: int
    rows: list[RenumberRowOut]
    truncated: bool


class RenumberResultOut(BaseModel):
    count: int
    changed_count: int
    first_number: int
    last_number: int


class MergeIn(BaseModel):
    entry_ids: list[UUID]
    description: str = ""


class MergeOut(BaseModel):
    entry_id: UUID
    number: int | None
    line_count: int
    merged_numbers: list[int | None]


# ──────────────────────────── تسعیر ارز ──────────────────────────────


class FxRowOut(BaseModel):
    account_id: UUID
    account_code: str
    account_name: str
    currency_code: str
    fx_balance: Decimal
    rate: Decimal
    book_value: Decimal
    market_value: Decimal
    difference: Decimal


class FxPreviewOut(BaseModel):
    as_of: date
    items: list[FxRowOut]
    total_difference: Decimal
    #: ارزهایی که تا این تاریخ هیچ نرخی ندارند — بدونشان نمی‌شود تسعیر کرد.
    missing_rates: list[str]


class IssueIn(BaseModel):
    """ورودیِ مشترکِ همه‌ی عملیاتِ «صدور سند» با یک تاریخ."""

    as_of: date
    description: str = ""


class IssueOut(BaseModel):
    entry_id: UUID
    number: int | None
    line_count: int


class FxIssueOut(IssueOut):
    net_difference: Decimal


class BalancedIssueOut(IssueOut):
    total: Decimal


# ─────────────────── سود و زیان / اختتامیه / افتتاحیه ────────────────


class PnlRowOut(BaseModel):
    account_id: UUID
    account_code: str
    account_name: str
    side: str
    amount: Decimal


class PnlPreviewOut(BaseModel):
    date_from: date | None
    date_to: date
    rows: list[PnlRowOut]
    total_income: Decimal
    total_expenses: Decimal
    net_profit: Decimal
    temporary_in_range: int


class ClosingRowOut(BaseModel):
    account_id: UUID
    account_code: str
    account_name: str
    account_type: str
    debit: Decimal
    credit: Decimal
    balance: Decimal


class ClosingPreviewOut(BaseModel):
    as_of: date
    rows: list[ClosingRowOut]
    total: Decimal
    open_pnl_total: Decimal
    temporary_count: int


class OpeningPreviewOut(BaseModel):
    as_of: date
    source_date: date
    rows: list[ClosingRowOut]
    #: شماره‌ی سندِ اختتامیه‌ای که افتتاحیه از رویش ساخته می‌شود — تا کاربر ببیند
    #: دقیقاً کدام سند دارد وارونه می‌شود.
    closing_entry_number: int | None
    total: Decimal


class OpeningIssueIn(BaseModel):
    as_of: date
    #: تاریخِ اختتامیه‌ی سالِ قبل — مانده‌ها از همان لحظه برداشته می‌شوند.
    source_date: date
    description: str = ""


# ────────────────────────── ترازها و دفاتر ──────────────────────────


class BalanceRowOut(BaseModel):
    account_id: UUID
    account_code: str
    account_name: str
    account_type: str
    parent_id: UUID | None
    opening_debit: Decimal
    opening_credit: Decimal
    period_debit: Decimal
    period_credit: Decimal
    closing_debit: Decimal
    closing_credit: Decimal
    balance: Decimal


class LegalBookRowOut(BaseModel):
    entry_id: UUID
    entry_number: int | None
    entry_date: date
    status: str
    voided: bool
    account_code: str
    account_name: str
    description: str
    debit: Decimal
    credit: Decimal


class LegalBookOut(BaseModel):
    date_from: date
    date_to: date
    rows: list[LegalBookRowOut]
    total_debit: Decimal
    total_credit: Decimal


# ─────────────────────── اصلاحِ طبقه‌بندیِ حساب ───────────────────────


class ReclassifyItemIn(BaseModel):
    account_id: UUID
    parent_id: UUID | None = None
    type: str | None = None

    @field_validator("type")
    @classmethod
    def _valid_type(cls, v: str | None) -> str | None:
        if v is not None and v not in ACCOUNT_TYPES:
            raise ValueError("نوعِ حساب نامعتبر است")
        return v


class ReclassifyIn(BaseModel):
    items: list[ReclassifyItemIn]


class ReclassifiedOut(BaseModel):
    account_id: UUID
    account_code: str
    account_name: str
    old_parent_id: UUID | None
    new_parent_id: UUID | None
    old_type: str
    new_type: str


class ReclassifyOut(BaseModel):
    count: int
    changed: list[ReclassifiedOut]


# ────────────────────────── تفصیلیِ سایر ────────────────────────────


class AnalyticOut(BaseModel):
    id: UUID
    code: str
    name: str
    group_name: str
    description: str
    is_active: bool
    #: چند ردیفِ سند به این تفصیلی اشاره می‌کند — گاردِ حذف و سرنخِ استفاده.
    line_count: int


class AnalyticIn(BaseModel):
    code: str
    name: str
    group_name: str = ""
    description: str = ""

    @field_validator("code", "name")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("این فیلد نمی‌تواند خالی باشد")
        return v.strip()


class AnalyticUpdateIn(BaseModel):
    code: str | None = None
    name: str | None = None
    group_name: str | None = None
    description: str | None = None
    is_active: bool | None = None

    @field_validator("code", "name")
    @classmethod
    def _not_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("این فیلد نمی‌تواند خالی باشد")
        return v.strip() if v is not None else v
