"""شکلِ ورودی/خروجیِ تسویه‌ی حسابِ طرف مقابل.

**`side` در ورودی هست ولی حرفِ آخر را نمی‌زند.** سرور سمتِ واقعیِ هر سند را از
اثرش روی معینِ انتخاب‌شده می‌سنجد و اگر با این فیلد نخواند، رد می‌کند (§۸). ماندنش
در ورودی عمدی است: یعنی کلاینت *اعلام* می‌کند قلم را در کدام ستون گذاشته، و سرور
می‌تواند بگوید «نه، این آن نیست» — به‌جای اینکه بی‌صدا جابه‌جایش کند.
"""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class SettlementItemIn(BaseModel):
    source_type: str
    source_id: UUID
    side: str
    #: مبلغی که از این قلم در **همین** تسویه مصرف می‌شود (§۱۴) — نه مبلغِ سند.
    amount: Decimal


class SettlementIn(BaseModel):
    settlement_date: date
    contact_id: UUID
    #: معینِ طرف مقابل (§۵). دریافتنی و پرداختنیِ یک شرکت دو حسابِ جدا هستند و
    #: تهاترشان قاعده‌ی صریح می‌خواهد (§۳۱).
    account_id: UUID
    description: str = ""
    description2: str = ""
    items: list[SettlementItemIn] = Field(default_factory=list)


class SettlementVoidIn(BaseModel):
    reason: str = ""


class OpenItemOut(BaseModel):
    """یک قلمِ قابلِ تسویه — همان چیزی که پنجره‌ی «افزودنِ قلم» نشان می‌دهد (§۹)."""

    source_type: str
    source_id: UUID
    label: str
    #: شماره‌ی خودِ سند، اگر داشته باشد. رسیدِ دریافت ندارد و با شماره‌ی سندِ
    #: حسابداری‌اش شناخته می‌شود.
    number: int | None = None
    entry_number: int | None = None
    document_date: date
    side: str
    document_amount: Decimal
    settled_amount: Decimal
    remaining_amount: Decimal
    status: str
    status_label: str = ""
    currency_code: str | None = None
    #: مبلغ به ارزِ سند، وقتی ردیفِ دفتر ارزی باشد. `document_amount` همیشه ریالی
    #: است، چون دفتر ریالی است.
    fx_amount: Decimal | None = None


class SettlementAllocationOut(BaseModel):
    side: str
    source_type: str
    source_id: UUID
    label: str
    amount: Decimal
    number: int | None = None
    entry_number: int | None = None
    document_date: date | None = None
    document_amount: Decimal | None = None
    settled_amount: Decimal | None = None
    remaining_amount: Decimal | None = None
    status: str | None = None
    source_missing: bool = False


class SettlementOut(BaseModel):
    id: UUID
    number: int
    settlement_date: date
    contact_id: UUID
    contact_name: str = ""
    account_id: UUID
    account_name: str = ""
    currency_code: str = "IRR"
    description: str = ""
    description2: str = ""
    total_amount: Decimal
    item_count: int = 0
    voided_at: datetime | None = None
    void_reason: str = ""
    created_at: datetime | None = None


class SettlementDetailOut(SettlementOut):
    allocations: list[SettlementAllocationOut] = Field(default_factory=list)


class AllocationHistoryCounterOut(BaseModel):
    source_type: str
    source_id: UUID
    label: str
    amount: Decimal


class AllocationHistoryOut(BaseModel):
    """تاریخچه‌ی تخصیصِ یک سند (§۳۶) — کِی، چقدر، و با چه چیزی."""

    settlement_id: UUID
    number: int
    settlement_date: date
    side: str
    amount: Decimal
    description: str = ""
    voided: bool = False
    counter_items: list[AllocationHistoryCounterOut] = Field(default_factory=list)


class CounterpartyAccountOut(BaseModel):
    id: UUID
    code: str
    name: str


class OpenItemSummaryOut(BaseModel):
    """صورتِ اقلامِ بازِ یک طرف حساب (§۴۵).

    `net` جمعِ جبریِ اقلام است و باید دقیقاً با ماندهٔ همان معین در دفتر بخواند —
    چون هر دو از یک ردیف‌های دفتر مشتق می‌شوند (§۲۶ §۴۴).
    """

    account_id: UUID
    account_name: str = ""
    #: ماندهٔ خامِ کلِ معین در دفتر. با `net` یکی نیست وقتی گردشی هست که سندِ
    #: قابلِ تسویه ندارد.
    account_ledger_net: Decimal = Decimal(0)
    #: همان اختلاف — گردشِ بی‌سند. صفر یعنی هر ریالِ این معین سندِ قابلِ تسویه دارد.
    unattributed: Decimal = Decimal(0)
    contact_id: UUID | None = None
    contact_name: str = ""
    debit_total: Decimal
    credit_total: Decimal
    net: Decimal
    open_debit: Decimal
    open_credit: Decimal
    items: list[OpenItemOut] = Field(default_factory=list)
