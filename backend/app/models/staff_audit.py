"""ردِ کارهای ستاد — «چه کسی، کی، روی کدام مشتری، چه کرد».

این جدول **سراسری** است و نه `TenantMixin`، به دو دلیلِ جداگانه که هرکدام به‌تنهایی
کافی‌اند:

۱. نشستِ ستاد عمداً هیچ `app.tenant_id`ی روی تراکنش ندارد. جدولِ RLS‌دار سیاستِ
   `WITH CHECK` دارد، پس درج **رد می‌شد** — یعنی دقیقاً همان کنش‌هایی که باید ثبت
   شوند، ثبت‌ناشدنی می‌بودند.
۲. مهم‌ترین ردیف‌ها یا اصلاً مستأجر ندارند (`login`) یا مستأجرشان در شرفِ نابودی
   است (`account_delete`).

جدولِ موجودِ `audit_log` جایگزین نبود: آن مستأجرمحور است و `audited_models()` هیچ
مدلِ پلتفرمی‌ای ندارد — به همین دلیل امروز حذفِ برگشت‌ناپذیرِ یک مشتری **صفر رد**
می‌گذارد.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import UUIDPKMixin


class StaffAuditLog(UUIDPKMixin, Base):
    __tablename__ = "staff_audit_log"

    #: مهرِ خودکارِ مستأجر (`_stamp_tenant_on_new_rows`) روی این مدل اجرا نشود.
    #: ستونِ `tenant_id` اینجا «هدفِ کار» است نه «مالکِ ردیف»، و ردیفی که هدفش یک
    #: مستأجرِ مشخص نیست (ورود، ساختِ کاربرِ ستاد) باید NULL بماند.
    __tenant_stamp__ = False

    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    #: SET NULL تا حذفِ کاربر ردِ کارهایش را نبرد.
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    #: ایمیل و نقش **در همان لحظه** اسنپ‌شات می‌شوند. ردی که برای خواندنش به
    #: join نیاز داشته باشد، بعد از حذفِ کاربر بی‌معنا می‌شود.
    actor_email: Mapped[str] = mapped_column(String(255), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(20), nullable=False)

    action: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    target_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    #: نامِ هدف در همان لحظه — تنها چیزی که بعد از حذفِ مستأجر باقی می‌ماند.
    target_label: Mapped[str | None] = mapped_column(String(200), nullable=True)

    #: **عمداً بدونِ ForeignKey.** کلیدِ خارجی، ردِ حذفِ مشتری را همراهِ خودِ مشتری
    #: cascade می‌کرد — و آن مهم‌ترین ردیفِ این جدول است. `purge_tenant` با
    #: `DELETE FROM tenants` کار می‌کند، پس بدونِ FK ردیف دست‌نخورده می‌ماند:
    #: حذفِ مشتری، ردِ حذفِ مشتری را پاک نمی‌کند.
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)

    summary: Mapped[str] = mapped_column(Text, nullable=False)
    #: جزئیاتِ ساختاریافته. **هرگز مقدارِ رمز** — فقط واقعه و هدف، همان قاعده‌ی
    #: `SECRET_FIELDS` در `app/audit.py`.
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    #: `staff` = توکنِ ستادی؛ `legacy` = پلِ سازگاریِ کوچ (`legacy_admin_allowlist`).
    #: وجودِ `legacy` در ردها یعنی کوچ هنوز تمام نشده.
    via: Mapped[str] = mapped_column(String(10), nullable=False, default="staff")
