import uuid
from datetime import date as date_

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin

#: بُعدهایی که یک مرکز می‌تواند نمایندگی کند. یک فهرستِ درهم از پروژه و شعبه و
#: دپارتمان عملاً غیرقابل‌گزارش است؛ نوع همان چیزی است که فهرست را قابلِ فیلتر می‌کند.
COST_CENTER_KINDS = ("project", "branch", "department", "product", "contract", "other")
COST_CENTER_KIND_LABELS = {
    "project": "پروژه",
    "branch": "شعبه",
    "department": "واحد سازمانی",
    "product": "خط محصول",
    "contract": "قرارداد",
    "other": "سایر",
}


class CostCenter(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """مرکز هزینه یا پروژه — یک بُعد برای برچسب‌زدنِ اسناد و سنجشِ سود به تفکیک.

    یک سند (فاکتور فروش/خرید یا سند دستی) می‌تواند به یک مرکز نسبت داده شود؛ آن‌گاه
    همه‌ی ردیف‌های سندش این برچسب را به ارث می‌برند (`journal_lines.cost_center_id`)
    و گزارشِ سودِ مرکز از تراکنش‌های واقعی درمی‌آید، نه از تخصیصِ دستی و جداگانه.

    برچسب روی خودِ ردیفِ سند نگه داشته می‌شود (نه فقط روی فاکتور) تا سندهای دستی و
    فاکتورها یک‌جور گزارش شوند و منبعِ گزارش یک ستونِ واحد باشد.

    **درختی است.** `parent_id` خالی یعنی ریشه. سند همیشه به یک مرکزِ *مشخص* برچسب
    می‌خورد — هرگز به مرکزِ مادر — و عددِ مادر از جمعِ زیرشاخه‌هایش در گزارش درمی‌آید.
    اگر برچسب‌زدن به مادر هم مجاز بود، جمعِ زیرشاخه‌ها و رقمِ خودِ مادر دو عددِ
    متناقض می‌شدند و معلوم نبود کدام «سودِ شعبه» است.
    """

    __tablename__ = "cost_centers"
    __table_args__ = (
        CheckConstraint(f"kind IN {COST_CENTER_KINDS}", name="ck_cost_centers_kind"),
        Index("ix_cost_centers_tenant_parent", "tenant_id", "parent_id"),
    )

    #: کدِ اختیاریِ کوتاه برای مرتب‌سازی/ارجاع؛ یکتا نیست چون برچسبِ کاربر است.
    code: Mapped[str] = mapped_column(String(30), default="", server_default="")
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20), default="project", server_default="project")
    #: مرکزِ مادر؛ NULL یعنی ریشه. RESTRICT در دیتابیس و گاردِ صریح در سرویس.
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cost_centers.id", ondelete="RESTRICT"), nullable=True
    )
    #: سرپرست/مسئولِ مرکز — متنِ آزاد، چون همیشه کاربرِ سیستم نیست (پیمانکار، مدیرِ پروژه).
    manager: Mapped[str] = mapped_column(String(200), default="", server_default="")
    #: بازه‌ی پروژه. تنها برای گزارش و هشدار است، نه قفلِ ثبتِ سند: سندِ خارج از بازه
    #: در واقعیت پیش می‌آید (فاکتورِ دیرکرد) و مسدودکردنش کاربر را به برچسب‌نزدن وامی‌دارد.
    start_date: Mapped[date_ | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date_ | None] = mapped_column(Date, nullable=True)
    #: مرکزِ بسته‌شده دیگر در فرم‌ها پیشنهاد نمی‌شود ولی سوابقش در گزارش می‌ماند.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
