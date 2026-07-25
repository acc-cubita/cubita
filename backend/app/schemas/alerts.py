from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class AlertItemOut(BaseModel):
    #: 'check' | 'receivable' | 'credit' | 'recurring' | 'calendar' | 'stock'
    category: str
    #: 'danger' | 'warning' | 'info'
    severity: str
    title: str
    detail: str
    alert_date: date | None = None
    amount: Decimal | None = None
    #: شناسه‌ی رکوردِ مرجع (چک، شخص، قالب، رویداد، کالا) برای پیوند در UI.
    ref_id: UUID | None = None


class AlertsOut(BaseModel):
    as_of: date
    total: int
    counts: dict[str, int]
    items: list[AlertItemOut]
