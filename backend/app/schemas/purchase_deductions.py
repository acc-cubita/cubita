"""شکلِ ورودی/خروجیِ «انواعِ کسورِ خرید خدمات»."""
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.purchase_deductions import DEDUCTION_BASES, DEDUCTION_NATURES


class PurchaseDeductionTypeIn(BaseModel):
    code: str = Field(default="", max_length=30)
    name: str = Field(min_length=1, max_length=100)
    nature: str
    basis: str = "net_before_tax"
    rate: Decimal = Field(default=Decimal(0), ge=0, le=100)
    #: خالی = حسابِ پیش‌فرضِ همین ماهیت («مالیات تکلیفی پرداختنی» یا «حق بیمه
    #: پرداختنی اشخاص ثالث»)، که با اولین استفاده ساخته می‌شود.
    account_id: UUID | None = None
    is_active: bool = True
    description: str = ""

    @field_validator("name", "code")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()

    @field_validator("nature")
    @classmethod
    def _known_nature(cls, value: str) -> str:
        if value not in DEDUCTION_NATURES:
            raise ValueError("ماهیتِ کسر باید «مالیات تکلیفی» یا «بیمه» باشد")
        return value

    @field_validator("basis")
    @classmethod
    def _known_basis(cls, value: str) -> str:
        if value not in DEDUCTION_BASES:
            raise ValueError("مبنای محاسبه‌ی کسر نامعتبر است")
        return value


class PurchaseDeductionTypeOut(BaseModel):
    id: UUID
    code: str
    name: str
    nature: str
    nature_label: str
    basis: str
    basis_label: str
    rate: Decimal
    account_id: UUID | None
    account_code: str = ""
    account_name: str = ""
    #: حساب انتخاب نشده و پیش‌فرضِ ماهیت می‌خورد.
    account_is_default: bool = True
    is_active: bool
    description: str
    #: در فاکتوری خورده — پس حذف نمی‌شود و ماهیتش هم عوض نمی‌شود.
    in_use: bool = False
