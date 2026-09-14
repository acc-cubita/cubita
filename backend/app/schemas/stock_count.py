from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, field_validator


class StockCountCreateIn(BaseModel):
    warehouse_id: UUID
    count_date: date
    notes: str = ""
    #: دامنه‌ی شمارش. خالی = هر کالایی که در همین انبار سابقه‌ی حرکت دارد —
    #: نه کلِ کاتالوگ. پرکردنش یعنی شمارشِ چرخه‌ای روی چند قلمِ مشخص.
    item_ids: list[UUID] = []


class CountLineUpdateIn(BaseModel):
    line_id: UUID
    #: `None` = «شمارش را پس بگیر» → ردیف به حالتِ نشمرده برمی‌گردد. صفرِ صریح
    #: یعنی «شمردم، هیچ نبود» و کسریِ واقعی می‌سازد. این دو یکی نیستند.
    counted_qty: Decimal | None

    @field_validator("counted_qty")
    @classmethod
    def _non_negative(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and v < 0:
            raise ValueError("شمارش نمی‌تواند منفی باشد")
        return v


class SetCountsIn(BaseModel):
    lines: list[CountLineUpdateIn]


class StockCountLineOut(BaseModel):
    id: UUID
    item_id: UUID
    item_name: str
    item_sku: str
    unit: str
    system_qty: Decimal
    #: `None` = هنوز شمرده نشده. رابط باید این را از «صفر شمردم» جدا نشان دهد.
    counted_qty: Decimal | None
    unit_cost: Decimal
    counted_at: datetime | None = None
    variance: Decimal | None
    variance_value: Decimal | None


class StockCountSessionOut(BaseModel):
    id: UUID
    number: int
    warehouse_id: UUID
    warehouse_name: str
    count_date: date
    status: str
    notes: str
    journal_entry_id: UUID | None
    posted_at: datetime | None
    created_at: datetime | None
    line_count: int
    counted_line_count: int
    variance_line_count: int
    total_variance_value: Decimal
    lines: list[StockCountLineOut]


class StockCountSummaryOut(BaseModel):
    id: UUID
    number: int
    warehouse_id: UUID
    warehouse_name: str
    count_date: date
    status: str
    notes: str
    posted_at: datetime | None
    created_at: datetime | None
    line_count: int
    counted_line_count: int


class CountDriftOut(BaseModel):
    """کالایی که **پس از** ثبتِ شمارشش حرکت کرده.

    گزارش است، نه گارد: اختلافش همچنان درست حساب می‌شود، ولی کاربر باید بداند
    بینِ شمارش و ثبت انبار بی‌کار ننشسته.
    """

    item_id: UUID
    item_name: str
    system_qty_at_count: Decimal
    system_qty_now: Decimal
    counted_at: datetime | None
