"""اسکیمای سالِ مالی."""
from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class FiscalYearIn(BaseModel):
    title: str = Field(min_length=1, max_length=60)
    start_date: date
    end_date: date
    notes: str = ""
    #: پس از ساخت، همین سال «جاری» شود.
    activate: bool = True


class FiscalYearUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=60)
    start_date: date | None = None
    end_date: date | None = None
    notes: str | None = None


class FiscalYearOut(BaseModel):
    id: UUID
    title: str
    start_date: date
    end_date: date
    status: str
    is_active: bool
    notes: str
    opening_entry_id: UUID | None
    closing_entry_id: UUID | None
    closed_at: datetime | None
    #: شمارِ اسنادِ حسابداریِ داخلِ بازه — پایه‌ی تصمیمِ «قابلِ حذف/ویرایش هست یا نه».
    entry_count: int = 0

    model_config = {"from_attributes": True}


class FiscalYearSuggestion(BaseModel):
    """پیشنهادِ بازه‌ی سالِ مالیِ بعدی بر پایه‌ی تقویمِ شمسی."""

    jalali_year: int
    title: str
    start_date: date
    end_date: date
    days: int
    #: سالِ کبیسه‌ی شمسی (اسفندِ ۳۰روزه).
    is_leap: bool
