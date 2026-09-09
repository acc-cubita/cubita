import uuid
from datetime import date as date_, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
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

    `system_qty` و `unit_cost` هنگام ایجادِ جلسه عکس‌برداری می‌شوند (نه هنگام ثبت) تا
    مغایرت همان چیزی باشد که شمارنده در آن لحظه دید. `counted_qty` با همان مقدارِ
    سیستمی مقداردهی می‌شود تا کاربر فقط کالاهای دارای اختلاف را دست بزند.
    """

    __tablename__ = "stock_count_lines"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stock_count_sessions.id", ondelete="CASCADE"), index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"))
    system_qty: Mapped[float] = mapped_column(Numeric(18, 3), default=0, server_default="0")
    counted_qty: Mapped[float] = mapped_column(Numeric(18, 3), default=0, server_default="0")
    unit_cost: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")

    session: Mapped["StockCountSession"] = relationship("StockCountSession", back_populates="lines")
    item: Mapped["object"] = relationship("Item")
