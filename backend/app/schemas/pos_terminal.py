from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, model_validator

from app.models.pos_terminal import POS_TRANSPORTS


class PosTerminalIn(BaseModel):
    label: str = ""
    name2: str = ""
    #: شماره‌ی پایانه — اختیاری، ولی یکتا اگر پر شود. هویتِ رکورد نیست (§۴).
    terminal_no: str = ""
    currency_code: str = "IRR"
    psp: str = ""
    transport: str = "simulator"
    host: str = ""
    port: int = 0
    com_port: str = ""
    bank_account_id: UUID | None = None
    #: تفصیلیِ دستگاه روی حسابِ «وجوهِ در راهِ کارت‌خوان» — همان نقشی که در صندوق
    #: و حسابِ بانکی دارد. بدونِ آن، وجوهِ در راهِ همه‌ی دستگاه‌ها یک عدد می‌شود.
    analytic_id: UUID | None = None
    is_active: bool = True
    is_default: bool = False

    @model_validator(mode="after")
    def validate_fields(self) -> "PosTerminalIn":
        if self.transport not in POS_TRANSPORTS:
            raise ValueError(f"روشِ اتصال باید یکی از {POS_TRANSPORTS} باشد")
        if self.transport == "network" and not (self.host or "").strip():
            raise ValueError("برای اتصالِ تحت‌شبکه، آدرسِ host الزامی است")
        if not (0 <= self.port <= 65535):
            raise ValueError("شماره‌ی پورت نامعتبر است")
        return self


class PosTerminalOut(BaseModel):
    id: UUID
    label: str
    name2: str = ""
    terminal_no: str = ""
    currency_code: str = "IRR"
    #: نام و عنوانِ دومِ حسابِ تسویه، برای فهرست (§۲۲) — بدونِ کوئریِ جدا.
    bank_account_name: str | None = None
    bank_account_name2: str | None = None
    #: **مشتق** — جمعِ رسیدهای کارتیِ تسویه‌نشده. ستون نیست.
    unsettled_balance: Decimal = Decimal(0)
    psp: str
    transport: str
    host: str
    port: int
    com_port: str
    bank_account_id: UUID | None
    analytic_id: UUID | None = None
    analytic_code: str | None = None
    analytic_name: str | None = None
    is_active: bool
    is_default: bool

    model_config = {"from_attributes": True}


class PosTerminalUpdateIn(BaseModel):
    """ویرایشِ جزئی — فقط فیلدهای ارسال‌شده تغییر می‌کنند.

    وجودِ این کلاس یک اشکالِ واقعی را می‌بندد: پیش از این PATCH همان
    `PosTerminalIn` را می‌گرفت و `model_dump()`ِ کامل را می‌نشاند، پس هر فیلدی که
    کلاینت نمی‌فرستاد پیش‌فرضش نوشته می‌شد — و `is_active` پیش‌فرضش `True` است.
    نتیجه: ویرایشِ نامِ یک دستگاهِ غیرفعال، بی‌صدا فعالش می‌کرد.
    """

    label: str | None = None
    name2: str | None = None
    terminal_no: str | None = None
    currency_code: str | None = None
    psp: str | None = None
    transport: str | None = None
    host: str | None = None
    port: int | None = None
    com_port: str | None = None
    bank_account_id: UUID | None = None
    analytic_id: UUID | None = None
    is_active: bool | None = None
    is_default: bool | None = None
