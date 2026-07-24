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
