from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class MoadianSettingsIn(BaseModel):
    memory_id: str = ""
    economic_code: str = ""
    national_id: str = ""
    #: خالی بگذارید تا کلیدِ ذخیره‌شده دست‌نخورده بماند؛ مقدارِ تازه جایگزینش می‌شود.
    private_key_pem: str | None = None
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
    is_sandbox: bool
    is_active: bool
    base_url_override: str
    last_serial: int
    effective_base_url: str


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
