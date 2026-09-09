from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator


class CashboxIn(BaseModel):
    name: str
    name2: str = ""
    #: بُعدِ حسابداریِ صندوق — کلیدِ تفکیکِ مانده‌ها.
    analytic_id: UUID | None = None
    #: معینِ جداگانه، اگر کسی بخواهد. خالی = حسابِ نقشِ «صندوق».
    gl_account_id: UUID | None = None
    currency_code: str = "IRR"
    opening_date: date | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def validate_fields(self) -> "CashboxIn":
        if not self.name.strip():
            raise ValueError("عنوان صندوق لازم است")
        return self


class CashboxUpdateIn(BaseModel):
    name: str | None = None
    name2: str | None = None
    analytic_id: UUID | None = None
    gl_account_id: UUID | None = None
    currency_code: str | None = None
    opening_date: date | None = None
    is_active: bool | None = None


class CashboxOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    name2: str
    analytic_id: UUID | None
    analytic_code: str | None
    analytic_name: str | None
    gl_account_id: UUID | None
    currency_code: str
    opening_date: date | None
    is_active: bool
    #: هر دو **مشتق** از دفترند و در جدول ذخیره نمی‌شوند. جدا نگه داشته می‌شوند
    #: چون یکی ابتدای دوره است و دیگری نتیجه‌ی هرچه بعدش افتاده.
    opening_balance: Decimal
    balance: Decimal
