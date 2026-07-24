import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin


class CostCenter(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """مرکز هزینه یا پروژه — یک بُعد برای برچسب‌زدنِ اسناد و سنجشِ سود به تفکیک.

    یک سند (فاکتور فروش/خرید یا سند دستی) می‌تواند به یک مرکز نسبت داده شود؛ آن‌گاه
    همه‌ی ردیف‌های سندش این برچسب را به ارث می‌برند (`journal_lines.cost_center_id`)
    و گزارشِ سودِ مرکز از تراکنش‌های واقعی درمی‌آید، نه از تخصیصِ دستی و جداگانه.

    برچسب روی خودِ ردیفِ سند نگه داشته می‌شود (نه فقط روی فاکتور) تا سندهای دستی و
    فاکتورها یک‌جور گزارش شوند و منبعِ گزارش یک ستونِ واحد باشد.
    """

    __tablename__ = "cost_centers"

    #: کدِ اختیاریِ کوتاه برای مرتب‌سازی/ارجاع؛ یکتا نیست چون برچسبِ کاربر است.
    code: Mapped[str] = mapped_column(String(30), default="", server_default="")
    name: Mapped[str] = mapped_column(String(200))
    #: مرکزِ بسته‌شده دیگر در فرم‌ها پیشنهاد نمی‌شود ولی سوابقش در گزارش می‌ماند.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
