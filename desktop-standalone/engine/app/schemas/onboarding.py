"""اسکیمای راه‌اندازی: ورودِ گروهیِ کالا/اشخاص و مانده‌های اول دوره (سند افتتاحیه)."""
from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, field_validator


# ── ورودِ گروهی ────────────────────────────────────────
class ItemImportRow(BaseModel):
    sku: str
    name: str
    category: str = ""
    unit: str = "عدد"
    is_service: bool = False
    sales_price: Decimal = Decimal(0)
    barcode: str | None = None


class ContactImportRow(BaseModel):
    name: str
    type: str = "customer"
    phone: str | None = None
    email: str | None = None
    address: str = ""
    entity_type: str = "real"
    national_id: str | None = None
    economic_code: str | None = None
    postal_code: str | None = None


class ImportItemsIn(BaseModel):
    rows: list[ItemImportRow]


class ImportContactsIn(BaseModel):
    rows: list[ContactImportRow]


class ImportError(BaseModel):
    row: int  # شماره‌ی ردیف در فایل (۱-پایه، بدونِ سرستون)
    message: str


class ImportResult(BaseModel):
    created: int
    skipped: int  # تکراری (رد شد)
    errors: list[ImportError]


# ── مانده‌های اول دوره / سند افتتاحیه ──────────────────
class OpeningAccountLine(BaseModel):
    account_id: UUID
    debit: Decimal = Decimal(0)
    credit: Decimal = Decimal(0)
    description: str = ""

    @field_validator("debit", "credit")
    @classmethod
    def _non_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("مبلغ نمی‌تواند منفی باشد")
        return v


class OpeningStockLine(BaseModel):
    item_id: UUID
    warehouse_id: UUID
    qty: Decimal
    unit_cost: Decimal

    @field_validator("qty", "unit_cost")
    @classmethod
    def _non_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("مقدار/بها نمی‌تواند منفی باشد")
        return v


class OpeningBalancesIn(BaseModel):
    entry_date: date
    lines: list[OpeningAccountLine] = []
    stock: list[OpeningStockLine] = []
    #: حسابی که اختلافِ تراز به آن بسته می‌شود (معمولاً «سرمایه»). اگر داده نشود،
    #: سند باید خودش متوازن باشد وگرنه رد می‌شود.
    balancing_account_id: UUID | None = None


class OpeningStatusOut(BaseModel):
    exists: bool
    entry_id: UUID | None = None
    entry_number: int | None = None
    entry_date: date | None = None
