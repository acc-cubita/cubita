"""گفتگوی زیرِ هر سفارشِ بازار — order_id روی پیام‌ها + last_read روی سفارش

Revision ID: 0066
Revises: 0065

- روی `marketplace_messages`: `connection_id` قابلِ‌تهی می‌شود و ستونِ تازه‌ی `order_id`
  (FK→marketplace_orders, CASCADE) افزوده می‌شود؛ هر پیام دقیقاً به یکی از این دو رشته
  تعلق دارد (CheckConstraint: num_nonnulls=1). ایندکسِ (order_id, created_at).
- روی `marketplace_orders`: دو ستونِ `distributor_last_read_at`/`retailer_last_read_at`
  برای شمارشِ خوانده‌نشده‌ی رشته‌ی گفتگوی همان سفارش.

هر دو جدول سراسری‌اند (بدونِ RLS) — جداسازی در روتر با تطبیقِ tenant با دو سمتِ سفارش.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0066"
down_revision: Union[str, None] = "0065"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # پیام‌ها: connection_id تهی‌پذیر + order_id تازه.
    op.alter_column("marketplace_messages", "connection_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
    op.add_column(
        "marketplace_messages",
        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("marketplace_orders.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("ix_mp_messages_order_created", "marketplace_messages", ["order_id", "created_at"])
    op.create_check_constraint(
        "ck_mp_messages_one_thread",
        "marketplace_messages",
        "num_nonnulls(connection_id, order_id) = 1",
    )

    # سفارش‌ها: last_read هر سمت برای رشته‌ی گفتگوی همان سفارش.
    op.add_column("marketplace_orders", sa.Column("distributor_last_read_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("marketplace_orders", sa.Column("retailer_last_read_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("marketplace_orders", "retailer_last_read_at")
    op.drop_column("marketplace_orders", "distributor_last_read_at")
    op.drop_constraint("ck_mp_messages_one_thread", "marketplace_messages", type_="check")
    op.drop_index("ix_mp_messages_order_created", table_name="marketplace_messages")
    op.drop_column("marketplace_messages", "order_id")
    op.alter_column("marketplace_messages", "connection_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)
