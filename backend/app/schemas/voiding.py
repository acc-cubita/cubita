from datetime import date
from uuid import UUID

from pydantic import BaseModel, field_validator


class VoidIn(BaseModel):
    """درخواست ابطال.

    `reason` اجباری است و خالی پذیرفته نمی‌شود: ابطال سند مالی چیزی است که ماه‌ها
    بعد کسی باید بتواند بفهمد چرا انجام شده — حسابرس، شریک، یا خودِ کاربر. سند
    باطلِ بی‌دلیل، یک سؤالِ بی‌جواب در دفتر است.
    """

    reason: str
    #: تاریخ سند معکوس. خالی یعنی همان تاریخ سند اصلی. اگر آن دوره بسته باشد،
    #: کاربر باید تاریخی در دوره‌ی باز بدهد و پیام خطا همین را می‌گوید.
    void_date: date | None = None

    @field_validator("reason")
    @classmethod
    def reason_is_meaningful(cls, v: str) -> str:
        if len(v.strip()) < 3:
            raise ValueError("دلیل ابطال باید نوشته شود")
        return v.strip()


class VoidOut(BaseModel):
    reversal_entry_id: UUID
    reversal_entry_number: int | None
