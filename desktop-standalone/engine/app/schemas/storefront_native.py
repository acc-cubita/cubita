"""اسکیمای مدیریتِ فروشگاهِ بومی (`/api/storefront/*`) — سطحِ احرازشده‌ی داخلِ برنامه.

جدا از `schemas/shop.py` (سطحِ عمومیِ خریدار) و `schemas/storefront.py` (اتصالِ بیرونیِ
ipnetcity). این‌جا مالکِ کسب‌وکار فروشگاهش را می‌سازد/منتشر می‌کند.

`publishable_key` این‌جا **برمی‌گردد** (چون قرار است در سایتِ استاتیک بیک شود و رازِ
پنهان نیست)، ولی `merchant_id`ِ درگاه هرگز برنمی‌گردد (فقط `has_merchant` — الگوی مؤدیان).
"""
from datetime import datetime

from pydantic import BaseModel, Field


class StorefrontSettingsIn(BaseModel):
    theme_id: str = "general"
    theme_config: dict = Field(default_factory=dict)
    seo_title: str = ""
    seo_description: str = ""
    contact_block: dict = Field(default_factory=dict)
    allowed_origin: str = ""


class StorefrontSettingsOut(BaseModel):
    #: شناسه‌ی عمومیِ فروشگاه (= slugِ مستأجر) که در سایت بیک می‌شود.
    slug: str
    theme_id: str
    theme_config: dict
    seo_title: str
    seo_description: str
    contact_block: dict
    allowed_origin: str
    #: کلیدِ publishable — عمداً برمی‌گردد (در سایت بیک می‌شود؛ رازِ پنهان نیست).
    publishable_key: str
    status: str
    last_built_at: datetime | None = None


class ItemListingIn(BaseModel):
    is_listed: bool = True
    images: list[str] = Field(default_factory=list)
    long_description: str = ""
    slug: str = ""
    sort: int = 0
    badge: str = ""


class ItemListingOut(BaseModel):
    item_id: str
    name: str
    sku: str
    sales_price: int
    is_listed: bool
    images: list[str]
    long_description: str
    slug: str
    sort: int
    badge: str


class GatewayIn(BaseModel):
    #: خالی هنگام به‌روزرسانی یعنی «مرچنتِ فعلی حفظ شود» (تا با ارسالِ فرم پاک نشود).
    merchant_id: str = ""
    is_active: bool = False


class GatewayOut(BaseModel):
    provider: str
    #: مرچنت راز است؛ فقط اینکه ست شده یا نه.
    has_merchant: bool
    is_active: bool


class OrderLineOut(BaseModel):
    item_id: str
    item_name: str
    qty: float
    unit_price: int
    line_total: int


class OrderOut(BaseModel):
    id: str
    order_number: int
    tracking_code: str
    customer_name: str
    customer_phone: str
    customer_email: str
    shipping_address: str
    note: str
    subtotal: int
    total: int
    payment_status: str
    fulfillment_status: str
    sales_invoice_id: str | None
    created_at: datetime
    lines: list[OrderLineOut]


class FulfillmentIn(BaseModel):
    fulfillment_status: str
