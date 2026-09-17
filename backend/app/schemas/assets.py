from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, model_validator


class FixedAssetIn(BaseModel):
    name: str
    category: str = ""
    acquired_date: date
    cost: Decimal
    salvage_value: Decimal = Decimal(0)
    useful_life_months: int
    notes: str = ""
    #: حسابِ تأمینِ مالیِ خرید (صندوق/بانک/پرداختنی). اگر داده شود، سندِ خرید خودکار
    #: زده می‌شود: بدهکارِ داراییِ ثابت، بستانکارِ همین حساب. اگر None باشد سندی زده
    #: نمی‌شود — برای دارایی‌هایی که از قبل در دفاتر هستند یا آورده‌ی مالک‌اند.
    funding_account_id: UUID | None = None

    @model_validator(mode="after")
    def validate(self) -> "FixedAssetIn":
        if not self.name.strip():
            raise ValueError("نام دارایی الزامی است")
        if self.cost < 0 or self.salvage_value < 0:
            raise ValueError("مبالغ نمی‌توانند منفی باشند")
        if self.salvage_value > self.cost:
            raise ValueError("ارزش اسقاط نمی‌تواند از بهای تمام‌شده بیشتر باشد")
        if self.useful_life_months <= 0:
            raise ValueError("عمر مفید باید بزرگ‌تر از صفر (ماه) باشد")
        return self


class FixedAssetOut(BaseModel):
    id: UUID
    name: str
    category: str
    acquired_date: date
    cost: Decimal
    salvage_value: Decimal
    useful_life_months: int
    method: str
    accumulated_depreciation: Decimal
    is_disposed: bool
    disposed_date: date | None
    notes: str
    #: وضعیتِ استقرارِ امروز — آینه‌ی آخرین ردیفِ تاریخچه‌ی تحویل/جابه‌جایی.
    custodian_id: UUID | None = None
    custodian_name: str = ""
    location: str = ""
    cost_center_id: UUID | None = None
    cost_center_name: str = ""
    #: محاسبه‌شده در سرویس — ارزش دفتری = cost − accumulated_depreciation
    book_value: Decimal
    #: استهلاکِ ماهانه‌ی خط مستقیم = (cost − salvage) / life
    monthly_depreciation: Decimal
    fully_depreciated: bool

    model_config = {"from_attributes": True}


class DepreciationRunIn(BaseModel):
    """اجرای استهلاک برای یک دوره (معمولاً یک ماه)."""

    period_date: date


class DepreciationRunOut(BaseModel):
    period_date: date
    asset_count: int  # چند دارایی مستهلک شد
    total_amount: Decimal
    journal_entry_id: UUID | None
    journal_entry_number: int | None


class DepreciationEntryOut(BaseModel):
    id: UUID
    asset_id: UUID
    asset_name: str
    period_date: date
    amount: Decimal
    journal_entry_id: UUID | None

    model_config = {"from_attributes": True}


# ── تحویل/استقرار و جابه‌جایی ───────────────────────────
class AssetAssignmentIn(BaseModel):
    """مقصدِ تحویل یا جابه‌جایی. مبدأ از وضعیتِ فعلیِ دارایی خوانده می‌شود، نه از کاربر."""

    assignment_date: date
    to_custodian_id: UUID | None = None
    to_location: str = ""
    to_cost_center_id: UUID | None = None
    notes: str = ""

    @model_validator(mode="after")
    def validate(self) -> "AssetAssignmentIn":
        #: بدونِ این، «جابه‌جایی» می‌تواند یک ردیفِ خالی بسازد که هیچ‌چیز را عوض
        #: نمی‌کند و فقط تاریخچه را شلوغ می‌کند.
        if self.to_custodian_id is None and not self.to_location.strip() and self.to_cost_center_id is None:
            raise ValueError("حداقل یکی از تحویل‌گیرنده، محلِ استقرار یا مرکزِ هزینه را مشخص کنید")
        return self


class AssetDisposalIn(BaseModel):
    """خروجِ دارایی — فروش، اسقاط یا اهدا."""

    disposal_date: date
    disposal_type: str = "sale"
    proceeds: Decimal = Decimal(0)
    #: حسابِ دریافتِ وجه. اگر مبلغ صفر نباشد الزامی است — سرویس هم دوباره می‌سنجد.
    settlement_account_id: UUID | None = None
    buyer_id: UUID | None = None
    notes: str = ""

    @model_validator(mode="after")
    def validate(self) -> "AssetDisposalIn":
        if self.disposal_type not in ("sale", "scrap", "donation"):
            raise ValueError("نوعِ خروج نامعتبر است")
        if self.proceeds < 0:
            raise ValueError("مبلغِ دریافتی نمی‌تواند منفی باشد")
        #: اسقاط و اهدا به تعریف بی‌عوض‌اند. اگر مبلغی دریافت شده، آن واگذاری
        #: «فروش» است — وگرنه سودِ فروش زیرِ عنوانِ اسقاط گم می‌شود.
        if self.disposal_type != "sale" and self.proceeds > 0:
            raise ValueError("اسقاط و اهدا مبلغِ دریافتی ندارند؛ برای واگذاری با عوض «فروش» را انتخاب کنید")
        if self.proceeds > 0 and self.settlement_account_id is None:
            raise ValueError("حسابِ دریافتِ وجه را برای مبلغِ فروش مشخص کنید")
        return self


class AssetDisposalOut(BaseModel):
    id: UUID
    asset_id: UUID
    asset_name: str = ""
    asset_category: str = ""
    disposal_type: str
    disposal_date: date
    proceeds: Decimal
    settlement_account_id: UUID | None
    settlement_account_name: str = ""
    buyer_id: UUID | None
    buyer_name: str = ""
    cost_at_disposal: Decimal
    accumulated_at_disposal: Decimal
    book_value: Decimal
    gain_loss: Decimal
    journal_entry_id: UUID | None
    journal_entry_number: int | None = None
    notes: str

    model_config = {"from_attributes": True}


class AssetAssignmentOut(BaseModel):
    id: UUID
    asset_id: UUID
    asset_name: str = ""
    kind: str
    assignment_date: date
    to_custodian_id: UUID | None
    to_custodian_name: str = ""
    to_location: str
    to_cost_center_id: UUID | None
    to_cost_center_name: str = ""
    from_custodian_id: UUID | None
    from_custodian_name: str = ""
    from_location: str
    from_cost_center_id: UUID | None
    from_cost_center_name: str = ""
    notes: str

    model_config = {"from_attributes": True}
