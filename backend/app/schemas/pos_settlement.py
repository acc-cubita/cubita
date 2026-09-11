"""شکلِ ورودی/خروجیِ تسویه‌ی کارت‌خوان.

**`settlement_date` و `settle_through` عمداً دو فیلدند (§۸ §۹)** و هیچ‌کدام از
دیگری مشتق نمی‌شود:

* `settle_through` برشِ انتخابِ رسیدهاست — «هرچه تا این تاریخ کشیده شده».
* `settlement_date` روزی است که پول واقعاً به بانک نشست، و سند با همین تاریخ
  می‌خورد.

مشتری ۱۴۰۴/۰۵/۱۰ کارت کشیده و بانک ۱۴۰۴/۰۵/۱۱ واریز کرده؛ یکی‌کردنشان یعنی یکی
از این دو حقیقت گم شود.
"""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, model_validator


class PosSettlementIn(BaseModel):
    #: دستگاه **الزامی است**. حسابِ مقصد و تفصیلیِ وجوهِ در راه هر دو از خودش
    #: می‌آیند؛ بدونش تسویه نمی‌داند پول را از کجا به کجا می‌برد.
    pos_terminal_id: UUID
    settlement_date: date
    settle_through: date
    #: کفِ اختیاریِ بازه. خالی یعنی «هر چه تسویه‌نشده مانده» — رفتارِ طبیعیِ برش.
    date_from: date | None = None
    fee_amount: Decimal = Decimal(0)
    note: str = ""

    @model_validator(mode="after")
    def validate_range(self) -> "PosSettlementIn":
        if self.date_from is not None and self.date_from > self.settle_through:
            raise ValueError("«از تاریخ» بعد از «تسویه تا تاریخ» است")
        return self


class PosPendingGroupOut(BaseModel):
    """یک روزِ تسویه‌نشده‌ی یک پایانه — نمای کلیِ «کجا پولِ نرسیده هست»."""

    terminal_no: str
    #: دستگاهِ واقعی، اگر رسیدها به آن وصل باشند. برای رسیدهای پیش از مهاجرتِ
    #: ۰۱۰۷ خالی است و فقط `terminal_no` را دارند.
    pos_terminal_id: UUID | None = None
    terminal_label: str | None = None
    transaction_date: date
    count: int
    gross_amount: Decimal


class PosSettlementReceiptOut(BaseModel):
    """یک رسیدِ منبع (§۱۰) — چیزی که مبلغِ تسویه از آن ساخته شده."""

    id: UUID
    transaction_date: date
    contact_id: UUID
    contact_name: str = ""
    #: «طرفِ مقابلِ دوم» — همان `name2`ِ طرف‌حساب، نه مفهومی تازه.
    contact_name2: str = ""
    amount: Decimal
    reference_no: str | None = None
    trace_no: str | None = None
    card_mask: str | None = None
    description: str = ""


class PosSettlementPreviewOut(BaseModel):
    """آنچه با این برش تسویه خواهد شد — پیش از ثبت."""

    pos_terminal_id: UUID
    terminal_no: str = ""
    terminal_label: str = ""
    bank_account_id: UUID | None = None
    bank_account_name: str = ""
    bank_account_name2: str = ""
    gross_amount: Decimal
    receipt_count: int
    receipts: list[PosSettlementReceiptOut]


class PosSettlementOut(BaseModel):
    """ردیفِ فهرست (§۲۸) و پاسخِ ثبت."""

    id: UUID
    number: int
    settlement_date: date
    settle_through: date
    date_from: date | None = None
    pos_terminal_id: UUID
    terminal_no: str = ""
    terminal_label: str = ""
    bank_account_id: UUID
    bank_account_name: str = ""
    bank_account_name2: str = ""
    gross_amount: Decimal
    fee_amount: Decimal
    net_amount: Decimal
    receipt_count: int
    #: مقصدهای drill-down (§۲۹) — تسویه نباید بن‌بست باشد.
    journal_entry_id: UUID
    bank_transaction_id: UUID | None = None
    voided_at: datetime | None = None
    void_reason: str = ""
    note: str = ""


class PosSettlementDetailOut(PosSettlementOut):
    receipts: list[PosSettlementReceiptOut]


class PosSettlementVoidIn(BaseModel):
    #: دلیل الزامی است — ابطالِ بی‌دلیل برای کسی که ماه بعد دفتر را می‌خواند
    #: از خودِ اشتباه بدتر است.
    reason: str
