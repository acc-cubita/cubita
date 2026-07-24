import re
from datetime import date
from uuid import UUID

from pydantic import BaseModel, field_validator

from app.models.calendar import EVENT_CATEGORIES

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")  # HH:MM در بازه‌ی 00:00 تا 23:59


class CalendarEventIn(BaseModel):
    title: str
    description: str = ""
    event_date: date
    start_time: str | None = None
    end_time: str | None = None
    category: str = "reminder"
    is_done: bool = False

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("عنوان رویداد الزامی است")
        return v.strip()

    @field_validator("category")
    @classmethod
    def category_valid(cls, v: str) -> str:
        if v not in EVENT_CATEGORIES:
            raise ValueError("دسته‌بندی نامعتبر است")
        return v

    @field_validator("start_time", "end_time")
    @classmethod
    def time_format(cls, v: str | None) -> str | None:
        # رشته‌ی خالی هم مثل نبودِ ساعت است (تمام‌روز)، نه یک مقدار نامعتبر.
        if v is None or v == "":
            return None
        if not _TIME_RE.match(v):
            raise ValueError("ساعت باید به‌صورت HH:MM باشد")
        return v


class CalendarEventDone(BaseModel):
    is_done: bool


class CalendarEventOut(BaseModel):
    id: UUID
    title: str
    description: str
    event_date: date
    start_time: str | None
    end_time: str | None
    category: str
    is_done: bool
    created_by_id: UUID

    model_config = {"from_attributes": True}
