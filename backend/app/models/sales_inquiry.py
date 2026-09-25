"""درخواستِ خرید و مشاوره از فرمِ «تماس برای خرید»ِ سایتِ cubita.ir.

پلن‌های قیمت‌دار از سایت برداشته شدند (۱۴۰۵/۰۷/۰۳): فروشِ هر چهار محصول — وب، دسکتاپ، موبایل و
«کوبیتا سازمانی» — از راهِ گفت‌وگو با کارشناسِ فروش است. این جدول صفِ همان گفت‌وگوهاست و در
`admin.cubita.ir` مرور و پیگیری می‌شود.

**چرا جدولِ سراسری و نه مستأجرمحور:** فرستنده هنوز مشتری نیست — هیچ مستأجر و هیچ نشستی ندارد. مثلِ
`client_errors` پیش از هر زمینه‌ی مستأجری نوشته می‌شود، پس RLS فقط درجش را ناممکن می‌کرد.

نشانیِ IP نگه داشته نمی‌شود: برای مهارِ هرزنامه سقفِ نرخ کافی است و نگه‌داشتنِ IPِ کسی که فقط
فرمِ تماس پر کرده، داده‌ی شخصیِ بی‌مصرف است.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

#: محصولی که درخواست درباره‌اش است — همان گزینه‌های فرمِ سایت.
SALES_PRODUCTS = ("cloud", "desktop", "enterprise", "mobile", "unsure")
#: چرخه‌ی پیگیری در ستاد: تازه → تماس گرفته شد → فروخته شد / منتفی.
SALES_STATUSES = ("new", "contacted", "won", "lost")


class SalesInquiry(Base):
    __tablename__ = "sales_inquiries"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    name: Mapped[str] = mapped_column(String(120))
    company: Mapped[str] = mapped_column(String(200), default="")
    phone: Mapped[str] = mapped_column(String(32), default="")
    email: Mapped[str] = mapped_column(String(200), default="")
    product: Mapped[str] = mapped_column(String(16), index=True)
    #: تعدادِ کاربرِ موردِ نیاز — برای «سازمانی» تعیین‌کننده‌ی قیمت است؛ اختیاری.
    seats: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str] = mapped_column(Text, default="")

    status: Mapped[str] = mapped_column(String(16), default="new", server_default="new", index=True)
    #: یادداشتِ کارشناسِ فروش — فقط در ستاد دیده می‌شود.
    staff_note: Mapped[str] = mapped_column(Text, default="", server_default="")
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: ایمیلِ کارمندی که آخرین بار وضعیت را عوض کرد — اسنپ‌شات، نه کلیدِ خارجی.
    handled_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
