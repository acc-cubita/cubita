import uuid
from datetime import date as date_, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin

#: چرخه‌ی وضعیت: باز → (ثبت‌شده | لغوشده). فقط جلسه‌ی «باز» قابل شمارش/ویرایش است.
STOCK_COUNT_STATUSES = ("open", "posted", "cancelled")


class StockCountSession(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """سرِ یک جلسه‌ی انبارگردانی برای یک انبار.

    هنگام ایجاد، از موجودیِ سیستمیِ همه‌ی کالاهای غیرخدماتی در آن انبار عکس‌برداری
    می‌شود (یک ردیف به‌ازای هر کالا). کاربر شمارشِ فیزیکی را وارد می‌کند و در پایان
    «ثبت» می‌کند: مغایرت‌ها به `stock_ledger` می‌روند و یک سندِ دوطرفه‌ی تجمیعی
    (موجودی ↔ مغایرت انبار) صادر می‌شود. عکس‌برداری هنگام ایجاد یعنی حرکت‌های بعدیِ
    انبار در همان بازه در این جلسه بازتاب نمی‌یابند — پس بازه‌ی شمارش را کوتاه نگه دارید.
    """

    __tablename__ = "stock_count_sessions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_stock_count_sessions_tenant_number"),
    )

    #: سریِ شماره‌ی خودش. سندِ کسری/اضافی سندِ دیگری است و شماره‌ی دیگری دارد —
    #: بی این، برگه‌ی شمارشِ کاغذی به هیچ جلسه‌ای وصل نمی‌شود.
    number: Mapped[int] = mapped_column(nullable=False, index=True)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id"))
    count_date: Mapped[date_] = mapped_column(Date, default=date_.today)
    status: Mapped[str] = mapped_column(String(20), default="open", server_default="open")
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True, index=True
    )
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    warehouse: Mapped["object"] = relationship("Warehouse")
    lines: Mapped[list["StockCountLine"]] = relationship(
        "StockCountLine", back_populates="session", cascade="all, delete-orphan"
    )


class StockCountLine(TenantMixin, UUIDPKMixin, Base):
    """یک کالا در یک جلسه‌ی انبارگردانی.

    **`system_qty` عکسِ لحظه‌ی *شمارش* است، نه لحظه‌ی بازکردنِ جلسه.** تا پیش از
    مهاجرتِ ۰۱۴۴ سرِ ایجادِ جلسه گرفته می‌شد و شمارش ساعت‌ها بعد انجام می‌شد؛ هر
    حرکتی که بینشان می‌افتاد **دو بار** شمرده می‌شد — یک‌بار خودش، یک‌بار داخلِ
    اختلاف. حالا `set_counts` همان لحظه از دفتر بازش می‌خواند، پس مبنای مقایسه
    همان چیزی است که سیستم *وقتی شمارنده عدد را داد* باور داشت.

    **`counted_qty` تهی‌پذیر است و این عمدی‌ترین بخشِ این مدل است:**

    * `NULL` → هنوز شمرده نشده. از اختلاف‌گیری **کنار گذاشته می‌شود**.
    * `0` → شمرده شد و هیچ نبود. کسریِ کامل، و واقعی.

    یکی‌گرفتنِ این دو یعنی جلسه‌ای که نیمه‌کاره ثبت شود موجودیِ صدها کالای
    دست‌نخورده را از انبار بیرون بریزد. و پیش‌فرضِ قدیمی (`counted_qty =
    system_qty`) خطای متقابل را داشت: شمارنده عددِ سیستم را از پیش نوشته
    می‌دید — نقضِ صریحِ «شمارشِ کور».
    """

    __tablename__ = "stock_count_lines"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stock_count_sessions.id", ondelete="CASCADE"), index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"))
    system_qty: Mapped[float] = mapped_column(Numeric(18, 3), default=0, server_default="0")
    counted_qty: Mapped[float | None] = mapped_column(Numeric(18, 3), nullable=True)
    unit_cost: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    #: کِی این شمارش وارد شد — لنگرِ «عکس در لحظه‌ی شمارش» و پاسخِ «چه‌قدرش را
    #: واقعاً شمردیم؟». `NULL` یعنی هنوز هیچ.
    counted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: چه کسی واردش کرد. شمارنده، سرپرست و واردکننده‌ی داده می‌توانند سه نفر
    #: باشند؛ این ستون فقط سومی را ادعا می‌کند.
    counted_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    session: Mapped["StockCountSession"] = relationship("StockCountSession", back_populates="lines")
    item: Mapped["object"] = relationship("Item")
