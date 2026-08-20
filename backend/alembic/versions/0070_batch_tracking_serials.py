"""جداسازیِ بارِ ورودی (بچ) + سریالِ کارتن + ردیابیِ کسری/معیوب

Revision ID: 0070
Revises: 0069

- `stock_batches` از یک «دفترِ انقضا» به «دفترِ بارِ ورودی» ارتقا می‌یابد: ستون‌های
  `received_qty` (مقدارِ اولیه)، `unit_cost` (بهای بار)، و `source_type`/`source_id`
  (منشأ: خرید/دستی/بازار). `received_qty` برای ردیف‌های موجود = `qty` بک‌فیل می‌شود.
- جدولِ تازه‌ی `stock_batch_serials` (مستأجرمحور + RLS): سریالِ کارتنِ هر بار.
- `stock_adjustments.batch_id` (تهی‌پذیر): تعدیلِ کسری/معیوب/ضایعات را به بارِ مشخص گره می‌زند.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.tenancy import rls_statements

revision: str = "0070"
down_revision: Union[str, None] = "0069"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── ارتقای stock_batches ──
    op.add_column("stock_batches", sa.Column("received_qty", sa.Numeric(18, 3), server_default="0", nullable=False))
    op.add_column("stock_batches", sa.Column("unit_cost", sa.Numeric(18, 0), server_default="0", nullable=False))
    op.add_column("stock_batches", sa.Column("source_type", sa.String(30), server_default="manual", nullable=False))
    op.add_column("stock_batches", sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True))
    # بک‌فیل: مقدارِ اولیه‌ی ردیف‌های موجود = مقدارِ فعلی
    op.execute("UPDATE stock_batches SET received_qty = qty")

    # ── stock_adjustments.batch_id ──
    op.add_column("stock_adjustments", sa.Column("batch_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_stock_adjustments_batch_id",
        "stock_adjustments",
        "stock_batches",
        ["batch_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_stock_adjustments_batch_id", "stock_adjustments", ["batch_id"])

    # ── جدولِ سریالِ کارتن ──
    op.create_table(
        "stock_batch_serials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "batch_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stock_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("serial", sa.String(120), nullable=False),
        sa.Column("status", sa.String(20), server_default="ok", nullable=False),
        sa.Column("notes", sa.Text, server_default="", nullable=False),
        sa.UniqueConstraint("tenant_id", "batch_id", "serial", name="uq_batch_serials_batch_serial"),
    )
    op.create_index("ix_stock_batch_serials_tenant_id", "stock_batch_serials", ["tenant_id"])
    op.create_index("ix_stock_batch_serials_batch_id", "stock_batch_serials", ["batch_id"])

    conn = op.get_bind()
    for stmt in rls_statements(("stock_batch_serials",)):
        conn.execute(sa.text(stmt))


def downgrade() -> None:
    op.drop_table("stock_batch_serials")
    op.drop_index("ix_stock_adjustments_batch_id", table_name="stock_adjustments")
    op.drop_constraint("fk_stock_adjustments_batch_id", "stock_adjustments", type_="foreignkey")
    op.drop_column("stock_adjustments", "batch_id")
    op.drop_column("stock_batches", "source_id")
    op.drop_column("stock_batches", "source_type")
    op.drop_column("stock_batches", "unit_cost")
    op.drop_column("stock_batches", "received_qty")
