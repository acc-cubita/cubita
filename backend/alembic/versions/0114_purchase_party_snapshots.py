"""قفل‌کردن هویت طرفین فاکتور خرید برای چاپ تاریخی."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0114"
down_revision: Union[str, None] = "0113"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # داده‌های قدیمی عمداً خالی می‌مانند و چاپ برای آن‌ها از Master فعلی fallback
    # می‌گیرد؛ backfill بدون دانستن هویت تاریخی، گذشته‌ای ساختگی تولید می‌کرد.
    op.add_column(
        "purchase_invoices",
        sa.Column("supplier_snapshot", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
    )
    op.add_column(
        "purchase_invoices",
        sa.Column("buyer_snapshot", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("purchase_invoices", "buyer_snapshot")
    op.drop_column("purchase_invoices", "supplier_snapshot")
