import uuid
from datetime import date as date_

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin, VoidableMixin
from app.models.tenant import TenantMixin


class StockTransfer(TenantMixin, VoidableMixin, UUIDPKMixin, TimestampMixin, Base):
    """حواله‌ی بین‌انباری: خروج از مبدأ و ورود به مقصد در **یک** سند.

    **اتمی، نه دو سندِ جدا (§۲۹).** اگر خروج و ورود دو سند بودند، خطایی بینِ آن‌ها
    کالا را «گم» می‌کرد: از مبدأ کم شده و به مقصد نرسیده. این‌جا هر دو حرکت در
    یک تراکنش نوشته می‌شوند و ابطال هم هر دو را با هم برمی‌گرداند.

    **سندِ حسابداری فقط وقتی دو انبار دو معینِ متفاوت دارند.** جمعِ موجودیِ شرکت
    عوض نمی‌شود (§۲۸)، پس انتقال میانِ دو انبارِ هم‌حساب هیچ سندی نمی‌زند. ولی از
    وقتی هر انبار می‌تواند معینِ موجودیِ خودش را داشته باشد، نزدنِ سند یعنی مانده‌ی
    آن دو معین با ارزشِ کالای هر انبار برای همیشه نخواند.
    """

    __tablename__ = "stock_transfers"
    __table_args__ = (
        CheckConstraint("from_warehouse_id <> to_warehouse_id", name="ck_stock_transfers_diff_warehouse"),
        UniqueConstraint("tenant_id", "number", name="uq_stock_transfers_tenant_number"),
    )

    number: Mapped[int | None] = mapped_column(nullable=True, index=True)
    transfer_date: Mapped[date_] = mapped_column(Date, default=date_.today)
    from_warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id"))
    to_warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id"))
    description: Mapped[str] = mapped_column(Text, default="")
    #: فقط وقتی دو انبار به دو معینِ موجودیِ متفاوت نگاشت شده‌اند (مهاجرتِ ۰۱۳۳).
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True, index=True
    )

    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    lines: Mapped[list["StockTransferLine"]] = relationship(
        back_populates="transfer", cascade="all, delete-orphan", order_by="StockTransferLine.id"
    )


class StockTransferLine(TenantMixin, UUIDPKMixin, Base):
    __tablename__ = "stock_transfer_lines"

    transfer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stock_transfers.id"))
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"))
    qty: Mapped[float] = mapped_column(Numeric(18, 3))

    transfer: Mapped["StockTransfer"] = relationship(back_populates="lines")
    item: Mapped["Item"] = relationship()
