from datetime import date, datetime
from decimal import Decimal
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
    #: شناسه‌ی پیش‌فرضِ کالا/خدمتِ مالیاتی (sstid، ۱۳رقمی) برای ردیف‌هایی که کدِ خودشان را ندارند.
    default_stuff_id: str = ""
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
    default_stuff_id: str
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
    #: شماره و خریدارِ فاکتورِ مربوط — برای اینکه تاریخچه بگوید «کدام فاکتور».
    invoice_number: int | None = None
    buyer_name: str = ""
    tax_id: str
    serial: int
    invoice_date: date
    status: str
    reference_number: str
    error_message: str
    sent_at: datetime | None

    model_config = {"from_attributes": True}


class MoadianReadinessCheck(BaseModel):
    """یک شرطِ ارسال — همان شرطی که مسیرِ ارسال واقعاً می‌سنجد، نه یک توصیه."""

    key: str
    ok: bool
    title: str
    detail: str


class MoadianReadinessOut(BaseModel):
    ready: bool
    checks: list[MoadianReadinessCheck]
    #: `sandbox` یا `production` — محیطِ مؤثرِ فعلی.
    environment: str
    pending_count: int
    blocked_count: int


class MoadianPendingInvoiceOut(BaseModel):
    """یک ردیفِ صفِ ارسال. `blocked_reason` خالی یعنی همین حالا قابلِ ارسال است."""

    id: UUID
    number: int | None
    invoice_date: date
    buyer_name: str
    buyer_is_legal: bool
    net_amount: Decimal
    tax_amount: Decimal
    payable: Decimal
    blocked_reason: str


class MoadianBatchIn(BaseModel):
    invoice_ids: list[UUID] = []


class MoadianBatchResultOut(BaseModel):
    invoice_id: UUID
    ok: bool
    #: وضعیتِ ثبت‌شده، یا `skipped` وقتی اصلاً ارسال نشد (قاعده جلویش را گرفت).
    status: str
    tax_id: str
    reference_number: str
    error_message: str


class MoadianUnitMapIn(BaseModel):
    """نگاشتِ واحدِ سنجش به کدِ رسمیِ سامانه.

    کدها **حدس زده نمی‌شوند**: جدولِ رسمی ده‌ها ردیف دارد و کدِ اشتباه به سازمانِ
    امور مالیاتی از نفرستادن بدتر است. تنها استثنا «عدد → ۱۶۴» است که در کد
    به‌عنوان پایه هست، چون تا امروز همان برای *هر* ردیفی ارسال می‌شد.
    """

    unit: str
    code: str


class MoadianUnitMapOut(BaseModel):
    id: UUID
    unit: str
    code: str

    model_config = {"from_attributes": True}
