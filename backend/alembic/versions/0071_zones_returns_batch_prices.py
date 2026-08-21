"""زونِ مشتری + مرجوعیِ بازار + تاریخ/قیمتِ مصرف‌کننده روی بچ و لیستینگ

Revision ID: 0071
Revises: 0070

- زون (مورد ۱): جدولِ سراسریِ `marketplace_zones` + `marketplace_connections.zone_id`.
- مرجوعی (مورد ۲): `marketplace_settings` (return_policy/return_window_days/next_return_number)
  + جدول‌های سراسریِ `marketplace_returns` و `marketplace_return_lines`.
- بچ/کاتالوگ (مورد ۳): `stock_batches` (consumer_price/production_date) و
  `marketplace_listings.consumer_price`.

همه‌ی جدول‌های بازار سراسری‌اند (بدونِ RLS)؛ در GLOBAL_TABLES ثبت شده‌اند.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0071"
down_revision: Union[str, None] = "0070"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── مورد ۳: بچ + لیستینگ ──
    op.add_column("stock_batches", sa.Column("consumer_price", sa.Numeric(18, 0), server_default="0", nullable=False))
    op.add_column("stock_batches", sa.Column("production_date", sa.Date(), nullable=True))
    op.add_column("marketplace_listings", sa.Column("consumer_price", sa.Numeric(18, 0), server_default="0", nullable=False))

    # ── مورد ۲: سیاستِ مرجوعی روی تنظیماتِ پخش‌کننده ──
    op.add_column("marketplace_settings", sa.Column("return_policy", sa.Text(), server_default="", nullable=False))
    op.add_column("marketplace_settings", sa.Column("return_window_days", sa.Integer(), server_default="0", nullable=False))
    op.add_column("marketplace_settings", sa.Column("next_return_number", sa.Integer(), server_default="1", nullable=False))

    # ── مورد ۱: زون ──
    op.create_table(
        "marketplace_zones",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("distributor_tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("notes", sa.Text(), server_default="", nullable=False),
        sa.UniqueConstraint("distributor_tenant_id", "name", name="uq_mp_zone_distributor_name"),
    )
    op.create_index("ix_marketplace_zones_distributor_tenant_id", "marketplace_zones", ["distributor_tenant_id"])

    op.add_column("marketplace_connections", sa.Column("zone_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_mp_connections_zone_id", "marketplace_connections", "marketplace_zones",
        ["zone_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_marketplace_connections_zone_id", "marketplace_connections", ["zone_id"])

    # ── مورد ۲: مرجوعی ──
    op.create_table(
        "marketplace_returns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("marketplace_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("distributor_tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("retailer_tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("return_number", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.String(20), server_default="requested", nullable=False),
        sa.Column("reason", sa.Text(), server_default="", nullable=False),
        sa.Column("response_note", sa.Text(), server_default="", nullable=False),
        sa.Column("total", sa.Numeric(18, 0), server_default="0", nullable=False),
        sa.Column("distributor_sales_return_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sales_returns.id", ondelete="SET NULL"), nullable=True),
        sa.Column("retailer_purchase_return_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("purchase_returns.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_marketplace_returns_order_id", "marketplace_returns", ["order_id"])
    op.create_index("ix_marketplace_returns_distributor_tenant_id", "marketplace_returns", ["distributor_tenant_id"])
    op.create_index("ix_marketplace_returns_retailer_tenant_id", "marketplace_returns", ["retailer_tenant_id"])

    op.create_table(
        "marketplace_return_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("return_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("marketplace_returns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_line_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("marketplace_order_lines.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(300), server_default="", nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 0), server_default="0", nullable=False),
        sa.Column("qty", sa.Numeric(18, 3), server_default="0", nullable=False),
        sa.Column("line_total", sa.Numeric(18, 0), server_default="0", nullable=False),
    )
    op.create_index("ix_marketplace_return_lines_return_id", "marketplace_return_lines", ["return_id"])
    op.create_index("ix_marketplace_return_lines_order_line_id", "marketplace_return_lines", ["order_line_id"])


def downgrade() -> None:
    op.drop_table("marketplace_return_lines")
    op.drop_table("marketplace_returns")
    op.drop_index("ix_marketplace_connections_zone_id", table_name="marketplace_connections")
    op.drop_constraint("fk_mp_connections_zone_id", "marketplace_connections", type_="foreignkey")
    op.drop_column("marketplace_connections", "zone_id")
    op.drop_index("ix_marketplace_zones_distributor_tenant_id", table_name="marketplace_zones")
    op.drop_table("marketplace_zones")
    op.drop_column("marketplace_settings", "next_return_number")
    op.drop_column("marketplace_settings", "return_window_days")
    op.drop_column("marketplace_settings", "return_policy")
    op.drop_column("marketplace_listings", "consumer_price")
    op.drop_column("stock_batches", "production_date")
    op.drop_column("stock_batches", "consumer_price")
