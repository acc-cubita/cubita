"""Item-specific units and observed batch ratios for INV-02."""
import uuid
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, ForeignKeyConstraint, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin


class ItemUnit(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "item_units"
    __table_args__ = (
        UniqueConstraint("tenant_id", "item_id", "unit_id", name="uq_item_units_identity"),
        ForeignKeyConstraint(["tenant_id", "item_id"], ["items.tenant_id", "items.id"], name="fk_item_unit_item", ondelete="CASCADE"),
        ForeignKeyConstraint(["tenant_id", "unit_id"], ["units_of_measure.tenant_id", "units_of_measure.id"], name="fk_item_unit_unit"),
    )
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    purchase_allowed: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    sale_allowed: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    inventory_allowed: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    production_allowed: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    decimal_allowed: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class ItemUnitConversion(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "item_unit_conversions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "item_id", "from_unit_id", "to_unit_id", name="uq_item_conversion_pair"),
        UniqueConstraint("tenant_id", "item_id", "id", name="uq_item_conversion_identity"),
        ForeignKeyConstraint(["tenant_id", "item_id", "from_unit_id"], ["item_units.tenant_id", "item_units.item_id", "item_units.unit_id"], name="fk_item_conversion_from", ondelete="CASCADE"),
        ForeignKeyConstraint(["tenant_id", "item_id", "to_unit_id"], ["item_units.tenant_id", "item_units.item_id", "item_units.unit_id"], name="fk_item_conversion_to", ondelete="CASCADE"),
        CheckConstraint("from_unit_id <> to_unit_id", name="ck_item_conversion_not_self"),
        CheckConstraint("(mode = 'fixed' AND factor > 0 AND factor IS NOT NULL) OR (mode = 'variable' AND factor IS NULL)", name="ck_item_conversion_factor"),
        CheckConstraint("version > 0", name="ck_item_conversion_version"),
        CheckConstraint("factor IS NULL OR factor::text NOT IN ('NaN', 'Infinity', '-Infinity')", name="ck_item_conversion_finite"),
    )
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    from_unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    to_unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    mode: Mapped[str] = mapped_column(String(12), default="fixed", server_default="fixed")
    factor: Mapped[Decimal | None] = mapped_column(Numeric(30, 12), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class BatchUnitConversion(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "batch_unit_conversions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "batch_id", "rule_id", name="uq_batch_conversion_rule"),
        ForeignKeyConstraint(["tenant_id", "item_id", "rule_id"], ["item_unit_conversions.tenant_id", "item_unit_conversions.item_id", "item_unit_conversions.id"], name="fk_batch_conversion_rule"),
        ForeignKeyConstraint(["tenant_id", "item_id", "batch_id"], ["stock_batches.tenant_id", "stock_batches.item_id", "stock_batches.id"], name="fk_batch_conversion_batch"),
        CheckConstraint("from_qty > 0 AND to_qty > 0", name="ck_batch_conversion_observations"),
        CheckConstraint("from_qty::text NOT IN ('NaN', 'Infinity', '-Infinity') AND to_qty::text NOT IN ('NaN', 'Infinity', '-Infinity')", name="ck_batch_conversion_finite"),
    )
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    rule_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    from_qty: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    to_qty: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    approved_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
