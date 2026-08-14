from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, field_validator


class CurrencyIn(BaseModel):
    code: str
    name: str
    symbol: str = ""

    @field_validator("code")
    @classmethod
    def _upper_code(cls, v: str) -> str:
        v = v.strip().upper()
        if not (2 <= len(v) <= 3):
            raise ValueError("کد ارز باید ۲ یا ۳ حرف باشد (مثل USD)")
        return v


class CurrencyOut(BaseModel):
    id: UUID
    code: str
    name: str
    symbol: str

    model_config = {"from_attributes": True}


class ExchangeRateIn(BaseModel):
    currency_code: str
    rate_date: date
    rate: Decimal

    @field_validator("currency_code")
    @classmethod
    def _upper_code(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("rate")
    @classmethod
    def _positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("نرخ باید بزرگ‌تر از صفر باشد")
        return v


class ExchangeRateOut(BaseModel):
    id: UUID
    currency_code: str
    rate_date: date
    rate: Decimal

    model_config = {"from_attributes": True}


class LatestRateOut(BaseModel):
    currency_code: str
    rate: Decimal | None
    rate_date: date | None
