"""Frozen entered quantity shared by document lines; ledger.qty remains base quantity."""
import uuid
from decimal import Decimal

from sqlalchemy import Numeric
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column


class EnteredQuantityMixin:
    # Nullable during the legacy transition: unknown historical input is not invented.
    entered_qty: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    entered_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    base_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    unit_conversion_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class CommercialQuantityMixin(EnteredQuantityMixin):
    # Financial line.qty is commercial; this is its independently summable stock quantity.
    base_qty: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
