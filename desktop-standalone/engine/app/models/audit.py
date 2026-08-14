"""دفتر ردِ حسابرسی — چه کسی، چه چیزی را، کِی عوض کرد.

**چرا این برای نرم‌افزار حسابداری اختیاری نیست:** دفتر باید بتواند نشان دهد یک عدد
از کجا آمد و چه کسی مسئولش بود. بدون این، «فاکتور باطل شد» یک واقعیت بی‌صاحب است؛
با این، یک رویداد با نام و زمان و دلیل. جایی که تقلب پنهان می‌شود دقیقاً همین‌جاست:
ابطال و اصلاحِ بی‌ردّ.

**چرا `actor_email` کپی می‌شود و از users خوانده نمی‌شود:** رد حسابرسی نباید به
داده‌ی متغیر وابسته باشد. اگر کاربر بعداً ایمیلش را عوض کند یا حسابش پاک شود، رکورد
باید همچنان بگوید آن روز چه کسی بود. JOIN به جدول زنده یعنی گذشته با حال تغییر
می‌کند — که دقیقاً همان چیزی است که رد حسابرسی برای جلوگیری از آن وجود دارد.

**چرا TimestampMixin ندارد:** `updated_at` روی جدولی که هرگز به‌روز نمی‌شود یک
دروغ است. فقط `at` هست، و همان لحظه‌ی وقوع است.

**فقط‌افزودنی بودن در پایگاه‌داده اعمال می‌شود، نه با قرارداد.** یک trigger هر
UPDATE و DELETE را رد می‌کند. قرارداد کدی کافی نیست: کسی که بخواهد ردش را پاک کند
دقیقاً همان کسی است که قرارداد را رعایت نمی‌کند. توضیح دریچه‌ی پاک‌سازی در مهاجرت
۰۰۲۱.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import UUIDPKMixin
from app.models.tenant import TenantMixin


class AuditLog(TenantMixin, UUIDPKMixin, Base):
    __tablename__ = "audit_log"

    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    #: کاربر ممکن است بعداً پاک شود؛ رکورد باید بماند، پس بدون CASCADE و nullable.
    #: خالی یعنی کار سیستمی بود (اسکریپت، مهاجرت، seed) — و آن هم اطلاعات است.
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor_email: Mapped[str] = mapped_column(String(255), default="")

    #: create | update | void | delete — «void» عمداً از «update» جدا شده، چون
    #: مهم‌ترین رویدادی است که کسی ممکن است دنبالش بگردد.
    action: Mapped[str] = mapped_column(String(20), index=True)

    entity_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)

    #: توضیح خوانا به فارسی — تا کسی که دنبال یک رویداد می‌گردد مجبور نباشد JSON بخواند.
    summary: Mapped[str] = mapped_column(Text, default="")

    #: {"field": {"from": ..., "to": ...}} برای تغییرها. برای ساخت و حذف خالی است.
    changes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    #: پل به لاگ ساختاریافته: با این شناسه می‌شود همان درخواست را در journalctl پیدا کرد.
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
