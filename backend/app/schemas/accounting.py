from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.accounting import ACCOUNT_TYPES, ENTRY_STATUSES


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
    #: بُعدِ ارزی و تفصیلیِ سایر — هر دو اختیاری. بدهکار/بستانکارِ بالا همیشه ریالی
    #: است؛ این‌ها فقط *مبنای* آن عدد را نگه می‌دارند تا تسعیر و گزارشِ تحلیلی
    #: بعداً بتوانند رویشان تکیه کنند.
    currency_code: str | None = None
    fx_amount: Decimal | None = None
    fx_rate: Decimal | None = None
    analytic_id: UUID | None = None


class JournalEntryIn(BaseModel):
    entry_date: date
    description: str = ""
    #: مرکز هزینه/پروژه‌ی سند؛ به همه‌ی ردیف‌هایش منتقل می‌شود. None = بدون مرکز.
    cost_center_id: UUID | None = None
    #: تفصیلیِ سایرِ سند — مثلِ مرکزِ هزینه به ردیف‌ها ارث می‌رسد، مگر خودِ ردیف
    #: تفصیلیِ صریح داشته باشد.
    analytic_id: UUID | None = None
    #: سندِ تازه به‌صورتِ پیش‌فرض *موقت* ثبت می‌شود تا در کارتابل بازبینی شود.
    #: `permanent` یعنی همان لحظه قطعی — برای دفترداری که بازبینی نمی‌خواهد.
    status: str = "temporary"
    #: شماره فرعی — ارجاعِ آزادِ کاربر (شماره‌ی سند در سیستمِ قبلی، شماره‌ی پرونده،
    #: کدِ دسته). عطف اینجا گرفته نمی‌شود: آن را فقط سرور می‌دهد.
    sub_number: str | None = Field(default=None, max_length=30)
    lines: list[JournalLineIn]

    @field_validator("sub_number")
    @classmethod
    def _clean_sub_number(cls, v: str | None) -> str | None:
        #: رشته‌ی خالی و فاصله‌ی تنها همان «خالی» است. بدونِ این، فیلدِ دست‌نخورده‌ی
        #: فرم به‌صورتِ "" ذخیره می‌شد و جستجو و «دارد/ندارد» را به هم می‌ریخت.
        cleaned = (v or "").strip()
        return cleaned or None

    @field_validator("status")
    @classmethod
    def _valid_status(cls, v: str) -> str:
        if v not in ENTRY_STATUSES:
            raise ValueError("وضعیتِ سند نامعتبر است")
        return v

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


class SubNumberIn(BaseModel):
    """تنها فیلدی از سند که بعد از ثبت هم قابلِ اصلاح است."""

    sub_number: str | None = Field(default=None, max_length=30)

    @field_validator("sub_number")
    @classmethod
    def _clean(cls, v: str | None) -> str | None:
        cleaned = (v or "").strip()
        return cleaned or None


class JournalLineOut(BaseModel):
    id: UUID
    account_id: UUID
    cost_center_id: UUID | None = None
    analytic_id: UUID | None = None
    debit: Decimal
    credit: Decimal
    description: str
    currency_code: str | None = None
    fx_amount: Decimal | None = None
    fx_rate: Decimal | None = None

    model_config = {"from_attributes": True}


class JournalEntryOut(BaseModel):
    id: UUID
    number: int | None
    #: شماره عطف — سرور لحظه‌ی ثبت می‌دهد و هیچ عملیاتی عوضش نمی‌کند. فقط سندهای
    #: پیش از مهاجرتِ ۰۰۸۵ که هنوز پر نشده‌اند می‌توانند NULL باشند.
    atf_number: int | None = None
    #: شماره فرعی — ارجاعِ آزادِ کاربر. NULL = خالی.
    sub_number: str | None = None
    entry_date: date
    description: str
    source_type: str
    #: موقت/دائم — «دائم» یعنی بازبینی‌شده و بیرون از دسترسِ ادغام و بازشماره‌گذاری.
    status: str = "temporary"
    finalized_at: datetime | None = None
    #: مهرِ ابطال (اگر باطل شده) و ارجاع به سندی که این سند معکوسِ آن است — برای
    #: نمایشِ وضعیت در دفتر روزنامه (سندِ باطل و سندِ برگشتیِ متناظر).
    voided_at: datetime | None = None
    reverses_entry_id: UUID | None = None
    lines: list[JournalLineOut]

    model_config = {"from_attributes": True}
