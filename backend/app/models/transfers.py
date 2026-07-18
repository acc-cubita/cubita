import uuid
from datetime import date as date_

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin


class StockTransfer(UUIDPKMixin, TimestampMixin, Base):
    """حواله بین‌انباری: انتقال کالا از یک انبار به انبار دیگر. بدون سند حسابداری چون فقط جابه‌جایی موجودی است، نه تغییر ارزش."""

    __tablename__ = "stock_transfers"
    __table_args__ = (
        CheckConstraint("from_warehouse_id <> to_warehouse_id", name="ck_stock_transfers_diff_warehouse"),
    )

    number: Mapped[int | None] = mapped_column(nullable=True, unique=True, index=True)
    transfer_date: Mapped[date_] = mapped_column(Date, default=date_.today)
    from_warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id"))
    to_warehouse_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouses.id"))
    description: Mapped[str] = mapped_column(Text, default="")

    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    lines: Mapped[list["StockTransferLine"]] = relationship(
        back_populates="transfer", cascade="all, delete-orphan", order_by="StockTransferLine.id"
    )


class StockTransferLine(UUIDPKMixin, Base):
    __tablename__ = "stock_transfer_lines"

    transfer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stock_transfers.id"))
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"))
    qty: Mapped[float] = mapped_column(Numeric(18, 3))

    transfer: Mapped["StockTransfer"] = relationship(back_populates="lines")
    item: Mapped["Item"] = relationship()
