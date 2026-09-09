import uuid
from datetime import date as date_
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin

if TYPE_CHECKING:
    from app.models.accounting import Account
    from app.models.analytic import AnalyticAccount


class Cashbox(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """صندوق — جایی که پولِ نقدِ کسب‌وکار واقعاً نگه داشته می‌شود.

    **صندوق حسابِ حسابداری نیست.** پیش از این بود: تنها تعریفِ «صندوق» در بک‌اند یک
    `if method == "cash": return get_account(cc.CASH)` بود، یعنی صندوق *همان* حسابِ
    معین بود و بیش از یکی نمی‌شد داشت. «صندوق دفتر مرکزی» و «صندوق شعبه» کنارِ هم
    ممکن نبودند.

    الگویش تازه نیست: `BankAccount` و `PosTerminal` هر دو موجودیتِ عملیاتی‌اند که با
    یک کلید به حسابداری وصل می‌شوند. صندوق تنها چیزی بود که این الگو را نگرفت.

    **مانده این‌جا ذخیره نمی‌شود.** مانده‌ی صندوق از دفتر مشتق می‌شود — مانده‌ی
    `(gl_account, analytic)`. دلیلش در `services/cashboxes.py` نوشته شده.
    """

    __tablename__ = "cashboxes"

    #: نامی که کاربر در عملیاتِ مالی می‌بیند — نه کد، نه شناسه.
    name: Mapped[str] = mapped_column(String(200))
    #: عنوانِ دوم/جایگزین. کاربردش را بیش از این فرض نمی‌کنیم.
    name2: Mapped[str] = mapped_column(String(200), default="", server_default="")

    #: بُعدِ حسابداریِ این صندوق. **کلیدِ تفکیک است**: مانده‌ی هر صندوق مانده‌ی
    #: همین تفصیلی روی حسابِ صندوق است.
    #:
    #: `NULL` معنای دقیقی دارد و تصادفی نیست — صندوقِ پیش‌فرض، یعنی «نقدی که به
    #: صندوقِ مشخصی نسبت داده نشده». همه‌ی ردیف‌های امروزِ دفتر همین‌اند، پس داده‌ی
    #: مستقر بدونِ هیچ backfill درست می‌ماند.
    analytic_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analytic_accounts.id", ondelete="SET NULL"), nullable=True
    )

    #: حسابِ معینِ متناظر. `NULL` یعنی همان حسابِ نقشِ `cash`. مثلِ `BankAccount`
    #: امکانِ معینِ جداگانه باز می‌ماند، ولی حالتِ عادی یک معین و چند تفصیلی است.
    gl_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=True
    )

    #: یک صندوق، یک ارز. صندوقِ چندارزی عمداً ساخته نشده — اگر روزی لازم شد باید
    #: تصمیمِ آگاهانه باشد، نه چیزی که از این‌جا نتیجه گرفته شود.
    currency_code: Mapped[str] = mapped_column(String(3), default="IRR", server_default="IRR")

    #: تاریخِ افتتاح — **داده‌ی کسب‌وکار**، نه `created_at`. کاربر می‌تواند امروز
    #: صندوقی را تعریف کند که از سه سال پیش باز بوده.
    opening_date: Mapped[date_ | None] = mapped_column(Date, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    analytic: Mapped["AnalyticAccount | None"] = relationship(lazy="joined")
    gl_account: Mapped["Account | None"] = relationship(lazy="joined")
