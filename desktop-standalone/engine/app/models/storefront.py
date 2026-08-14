from sqlalchemy import Boolean, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin


class StorefrontSettings(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """اتصالِ هر کسب‌وکار به سایتِ فروشگاهیِ خودش — یک ردیف برای هر مستأجر.

    **رمزِ ادمین راز است.** اینجا ذخیره می‌شود چون sync سمتِ سرور به سایت لاگین می‌کند،
    ولی هرگز در پاسخِ API برنمی‌گردد (اسکیمای خروجی فقط `has_password` را می‌دهد).
    جداسازیِ بین مستأجرها با همان RLSِ بقیه‌ی جدول‌هاست.
    """

    __tablename__ = "storefront_settings"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_storefront_settings_tenant"),)

    #: آدرسِ پایه‌ی API سایتِ فروشگاهی (مثل https://example.ir).
    base_url: Mapped[str] = mapped_column(String(300), default="", server_default="")
    #: ایمیلِ ادمینِ سایت که sync با آن لاگین می‌کند.
    admin_email: Mapped[str] = mapped_column(String(150), default="", server_default="")
    #: رمزِ ادمینِ سایت — راز؛ هرگز در پاسخ API برنمی‌گردد.
    admin_password: Mapped[str] = mapped_column(Text, default="", server_default="")
    #: سفارش‌های با id کوچک‌تر/مساویِ این مقدار وارد نمی‌شوند (cutover راه‌اندازی).
    cutover_order_id: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    #: تا فعال نشده، هیچ sync‌ای انجام نمی‌شود.
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
