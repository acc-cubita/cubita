import uuid

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin


class AnalyticAccount(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """تفصیلیِ سایر — بُعدِ تحلیلیِ آزادِ ردیفِ سند.

    سه بُعد روی ردیفِ سند می‌نشیند و هرکدام جای خودش را دارد: **حساب** می‌گوید چه
    نوع رویدادی بود، **مرکز هزینه** می‌گوید برای کدام پروژه/شعبه، و این یکی برای
    هر چیزِ دیگری که کسب‌وکار می‌خواهد رویش گزارش بگیرد و در آن دو نمی‌گنجد —
    خودرو، قرارداد، دستگاه، پرونده. عمداً بی‌ساختار است: کد و نام و یک دسته‌ی آزاد.

    نه درخت دارد نه نوع، چون بُعدِ *سایر* است؛ لحظه‌ای که چیزی ساختار بگیرد، جایش
    مرکز هزینه است نه اینجا.
    """

    __tablename__ = "analytic_accounts"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_analytic_accounts_tenant_code"),)

    code: Mapped[str] = mapped_column(String(20), index=True)
    name: Mapped[str] = mapped_column(String(200))
    #: دسته‌ی آزاد برای گروه‌بندیِ فهرست («خودرو»، «قرارداد»، …). خالی = بی‌دسته.
    group_name: Mapped[str] = mapped_column(String(100), default="", server_default="")
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    #: غیرفعال از فهرستِ ثبتِ سند پنهان می‌شود ولی ردیف‌های گذشته‌اش می‌مانند.
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
