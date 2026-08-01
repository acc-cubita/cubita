from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, field_validator, model_validator

from app.models.accounting import ACCOUNT_TYPES


class AccountOut(BaseModel):
    id: UUID
    code: str
    name: str
    type: str
    is_group: bool
    is_active: bool
    parent_id: UUID | None
    #: نقشِ سیستمی (cash، inventory، …) — اگر پرشده باشد، حسابِ سیستمی است و
    #: نه قابلِ حذف است نه غیرفعال‌سازی. برای حساب‌های معمولی NULL.
    system_role: str | None = None

    model_config = {"from_attributes": True}


class AccountCreateIn(BaseModel):
    """ساختِ حسابِ تازه در چارت — زیرِ یک سرفصل یا در ریشه."""

    code: str
    name: str
    type: str
    is_group: bool = False
    parent_id: UUID | None = None

    @field_validator("code", "name")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("این فیلد نمی‌تواند خالی باشد")
        return v.strip()

    @field_validator("type")
    @classmethod
    def _valid_type(cls, v: str) -> str:
        if v not in ACCOUNT_TYPES:
            raise ValueError("نوعِ حساب نامعتبر است")
        return v


class AccountUpdateIn(BaseModel):
    """ویرایشِ حساب — فقط نام و فعال‌بودن. کد/نوع/سرفصل پس از ساخت ثابت‌اند (روی
    اسناد و گزارش‌ها نشسته‌اند)."""

    name: str | None = None
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not v.strip():
            raise ValueError("نام حساب نمی‌تواند خالی باشد")
        return v.strip()


class JournalLineIn(BaseModel):
    account_id: UUID
    debit: Decimal = Decimal(0)
    credit: Decimal = Decimal(0)
    description: str = ""


class JournalEntryIn(BaseModel):
    entry_date: date
    description: str = ""
    #: مرکز هزینه/پروژه‌ی سند؛ به همه‌ی ردیف‌هایش منتقل می‌شود. None = بدون مرکز.
    cost_center_id: UUID | None = None
    lines: list[JournalLineIn]

    @model_validator(mode="after")
    def validate_balance(self) -> "JournalEntryIn":
        if len(self.lines) < 2:
            raise ValueError("سند حسابداری باید حداقل دو ردیف داشته باشد")
        total_debit = sum(line.debit for line in self.lines)
        total_credit = sum(line.credit for line in self.lines)
        if total_debit != total_credit:
            raise ValueError(f"سند متوازن نیست: بدهکار={total_debit} بستانکار={total_credit}")
        if total_debit == 0:
            raise ValueError("مجموع سند نمی‌تواند صفر باشد")
        return self


class JournalLineOut(BaseModel):
    id: UUID
    account_id: UUID
    cost_center_id: UUID | None = None
    debit: Decimal
    credit: Decimal
    description: str

    model_config = {"from_attributes": True}


class JournalEntryOut(BaseModel):
    id: UUID
    number: int | None
    entry_date: date
    description: str
    source_type: str
    #: مهرِ ابطال (اگر باطل شده) و ارجاع به سندی که این سند معکوسِ آن است — برای
    #: نمایشِ وضعیت در دفتر روزنامه (سندِ باطل و سندِ برگشتیِ متناظر).
    voided_at: datetime | None = None
    reverses_entry_id: UUID | None = None
    lines: list[JournalLineOut]

    model_config = {"from_attributes": True}
