"""اسکیمای API عمومیِ فروشگاه (`/api/shop/*`).

**این‌ها عمداً باریک‌اند.** سطحِ عمومی روی هاستِ مستأجر (و در مرورگرِ خریدار) دیده
می‌شود، پس هیچ فیلدِ محرمانه‌ای — بهای تمام‌شده (`average_cost`)، سود، یا هر دیتای
داخلی — نباید در این مدل‌ها باشد. هر افزودنِ فیلد باید با این پرسش سنجیده شود:
«آیا اشکالی دارد که رقیب یا هر رهگذری این را ببیند؟»
"""
from pydantic import BaseModel


class ShopProductOut(BaseModel):
    """کالای قابلِ نمایش روی سایت — بدونِ هیچ عددِ داخلی/کاست."""

    id: str
    slug: str
    title: str
    category: str
    price: int
    images: list[str]
    badge: str
    description: str
    stock: int
    out_of_stock: bool


class ShopCategoryOut(BaseModel):
    id: str
    name: str
    slug: str
    parent_id: str | None = None


class ShopInfoOut(BaseModel):
    """اطلاعاتِ عمومیِ خودِ فروشگاه برای رندرِ قالب."""

    theme_id: str
    theme_config: dict
    seo_title: str
    seo_description: str
    contact_block: dict


class ShopOrderLineIn(BaseModel):
    slug: str
    qty: int


class ShopOrderIn(BaseModel):
    customer_name: str
    customer_phone: str
    customer_email: str = ""
    shipping_address: str = ""
    note: str = ""
    lines: list[ShopOrderLineIn]


class ShopOrderOut(BaseModel):
    """رسیدِ سفارشِ ثبت‌شده — قیمت‌ها سمتِ سرور محاسبه شده‌اند، نه از کلاینت."""

    id: str
    order_number: int
    tracking_code: str
    total: int
    payment_status: str
