from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class MoadianSettingsIn(BaseModel):
    memory_id: str = ""
    economic_code: str = ""
    national_id: str = ""
    #: خالی بگذارید تا کلیدِ ذخیره‌شده دست‌نخورده بماند؛ مقدارِ تازه جایگزینش می‌شود.
    private_key_pem: str | None = None
    #: گواهیِ امضا (PEM)؛ خالی = دست‌نخورده. برای هدرِ `x5c` لازم است.
    certificate_pem: str | None = None
    is_sandbox: bool = True
    is_active: bool = False
    base_url_override: str = ""


class MoadianSettingsOut(BaseModel):
    """خروجیِ تنظیمات — **بدون کلید خصوصی**.

    کلید عمداً در هیچ پاسخی برنمی‌گردد: یک‌بار وارد می‌شود و از آن به بعد فقط
    وجود/نبودش گزارش می‌شود. برگرداندنش یعنی هر کسی که به رابط کاربری دسترسی دارد
    می‌تواند کلیدِ امضای مالیاتیِ کسب‌وکار را بردارد.
    """

    memory_id: str
    economic_code: str
    national_id: str
    has_private_key: bool
    has_certificate: bool
    is_sandbox: bool
    is_active: bool
    base_url_override: str
    last_serial: int
    effective_base_url: str


class MoadianConnectionTestOut(BaseModel):
    """نتیجه‌ی «تستِ اتصال» — بدونِ ارسالِ صورتحساب، فقط احراز هویت با سامانه."""

    ok: bool
    environment: str
    status_code: int | None
    message: str
    server_key_id: str | None


class MoadianSubmissionOut(BaseModel):
    id: UUID
    sales_invoice_id: UUID
    tax_id: str
    serial: int
    invoice_date: date
    status: str
    reference_number: str
    error_message: str
    sent_at: datetime | None

    model_config = {"from_attributes": True}
