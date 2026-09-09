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
    خطرناکِ بی‌قصد است و باید صریح گفته شود.

    این جمله از روزِ اول این‌جا بود و **هیچ‌چیز اعمالش نمی‌کرد**؛ گاردش حالا در
    `finalize_entries` است. `entry_ids` هم پیش‌فرضش `None` شد نه فهرستِ خالی، تا
    «انتخاب نکردم» از «انتخابم خالی بود» جدا بماند — دومی خطاست.
    """

    date_from: date | None = None
    date_to: date | None = None
    entry_ids: list[UUID] | None = None
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
    #: هر سه بُعدِ ردیفِ سند در ردیفِ تسعیر هم می‌مانند. `None` یعنی مانده‌ی این
    #: گروه واقعاً بُعدی نداشته، نه اینکه محاسبه دورش انداخته باشد.
    analytic_id: UUID | None = None
    analytic_code: str | None = None
    analytic_name: str | None = None
    cost_center_id: UUID | None = None
    cost_center_name: str | None = None
    currency_code: str
    fx_balance: Decimal
    rate: Decimal
    #: تاریخِ خودِ نرخ — اگر با `as_of` یکی نباشد یعنی نرخِ روز ثبت نشده.
    rate_date: date
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
    account_type: str
    #: بُعدهای مانده. حسابِ درآمدی با دو تفصیلی دو ردیفِ جداست — وگرنه حساب صفر
    #: می‌شود ولی دفترِ تفصیلی مانده‌دار می‌ماند، و چون درآمد و هزینه به سالِ بعد
    #: منتقل نمی‌شوند، هیچ‌وقت هم بسته نمی‌شود.
    analytic_id: UUID | None = None
    analytic_code: str | None = None
    analytic_name: str | None = None
    cost_center_id: UUID | None = None
    cost_center_name: str | None = None
    debit: Decimal
    credit: Decimal
    #: شکلِ قدیمیِ همان دو ستون، برای رابط.
    side: str
    amount: Decimal


class PnlPreviewOut(BaseModel):
    date_from: date | None
    date_to: date
    rows: list[PnlRowOut]
    total_income: Decimal
    total_expenses: Decimal
    net_profit: Decimal
    #: حسابِ مقصد از `system_role` پیدا می‌شود، نه از کد — کد مالِ مشتری است.
    destination_account_code: str
    destination_account_name: str
    total_debit: Decimal
    total_credit: Decimal
    #: باید صفر باشد؛ رابط تا صفر نشود دکمه‌ی صدور را فعال نمی‌کند.
    difference: Decimal
    temporary_in_range: int
    #: گامِ اول از قبل زده شده؟
    already_closed: bool


class PnlIssueOut(BaseModel):
    entry_id: UUID
    number: int | None
    line_count: int
    total_income: Decimal
    total_expenses: Decimal
    net_profit: Decimal


class ClosingRowOut(BaseModel):
    account_id: UUID
    account_code: str
    account_name: str
    account_type: str
    #: بُعدهای مانده. مانده‌ی یک حساب با سه تفصیلی سه ردیفِ جداست، وگرنه سالِ
    #: جدید با حسابی باز می‌شود که مانده دارد ولی دفترِ تفصیلی‌اش خالی است.
    analytic_id: UUID | None = None
    analytic_code: str | None = None
    analytic_name: str | None = None
    cost_center_id: UUID | None = None
    cost_center_name: str | None = None
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
    #: شناسه و شماره‌ی سندِ اختتامیه‌ای که افتتاحیه از رویش ساخته می‌شود — تا کاربر
    #: ببیند دقیقاً کدام سند دارد وارونه می‌شود. شناسه روی `reverses_entry_id`ِ
    #: سندِ افتتاحیه می‌نشیند و گاردِ «افتتاحیه‌ی تکراری» روی همان کار می‌کند.
    closing_entry_id: UUID
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


# ─────────────── اصلاحِ طبقه‌بندیِ مانده ───────────────


class ReclassSourceIn(BaseModel):
    """یک ترکیبِ (حساب، تفصیلی) که مانده‌اش منتقل می‌شود."""

    account_id: UUID
    analytic_id: UUID | None = None


class ReclassSourceRowOut(BaseModel):
    """ترکیبی که در این تاریخ مانده دارد — سیاهه‌ای که کاربر از آن انتخاب می‌کند."""

    account_id: UUID
    account_code: str
    account_name: str
    analytic_id: UUID | None
    analytic_code: str | None
    analytic_name: str | None
    balance: Decimal
    #: نقشِ سیستمی مسدود نمی‌کند؛ فقط هشدار می‌دهد که ثبت‌های خودکارِ آینده
    #: همچنان به همین حساب می‌آیند.
    system_role: str | None


class ReclassIn(BaseModel):
    as_of: date
    sources: list[ReclassSourceIn]
    dest_account_id: UUID
    dest_analytic_id: UUID | None = None
    description: str = ""


class ReclassItemOut(BaseModel):
    account_id: UUID
    account_code: str
    account_name: str
    analytic_id: UUID | None
    analytic_name: str | None
    balance: Decimal
    source_debit: Decimal
    source_credit: Decimal
    dest_debit: Decimal
    dest_credit: Decimal


class ReclassPreviewOut(BaseModel):
    as_of: date
    items: list[ReclassItemOut]
    dest_account_id: UUID
    dest_account_code: str
    dest_account_name: str
    dest_analytic_id: UUID | None
    dest_analytic_name: str | None
    total_debit: Decimal
    total_credit: Decimal
    #: باید صفر باشد — اصلاحِ طبقه‌بندی از هیچ، دارایی یا سود نمی‌سازد.
    difference: Decimal
    warnings: list[str] = []
