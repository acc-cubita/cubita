"""بازارِ عمده‌فروشیِ درون‌پلتفرمی — جدول‌های سراسری (بدونِ RLS)

Revision ID: 0059
Revises: 0058

هفت جدولِ لایه‌ی بازار. عمداً میان‌مستأجری‌اند (پخش‌کننده منتشر می‌کند، فروشگاهِ مستأجرِ
دیگری می‌بیند/سفارش می‌دهد)، پس مثلِ `tenants`/`subscriptions` **RLS ندارند**؛ جداسازی در
کدِ روتر انجام می‌شود. FKها به `tenants`/`items`/فاکتورها می‌پرند (بررسیِ FK از RLS عبور می‌کند).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0059"
down_revision: Union[str, None] = "0058"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID(as_uuid=True)


def _fk(target: str, ondelete: str):
    return sa.ForeignKey(target, ondelete=ondelete)


def upgrade() -> None:
    # ── marketplace_settings ─────────────────────────────────────────────
    op.create_table(
        "marketplace_settings",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("distributor_tenant_id", UUID, _fk("tenants.id", "CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("display_name", sa.String(200), nullable=False, server_default=""),
        sa.Column("settlement_mode", sa.String(20), nullable=False, server_default="credit"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("next_order_number", sa.Integer, nullable=False, server_default="1"),
        sa.UniqueConstraint("distributor_tenant_id", name="uq_mp_settings_distributor"),
    )
    op.create_index("ix_mp_settings_distributor", "marketplace_settings", ["distributor_tenant_id"])

    # ── marketplace_listings ─────────────────────────────────────────────
    op.create_table(
        "marketplace_listings",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("distributor_tenant_id", UUID, _fk("tenants.id", "CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("kind", sa.String(10), nullable=False, server_default="single"),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("code", sa.String(60), nullable=False, server_default=""),
        sa.Column("unit", sa.String(20), nullable=False, server_default="عدد"),
        sa.Column("wholesale_price", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("currency_code", sa.String(10), nullable=False, server_default=""),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("images", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("category", sa.String(100), nullable=False, server_default=""),
        sa.Column("is_published", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("distributor_item_id", UUID, _fk("items.id", "CASCADE"), nullable=True),
    )
    op.create_index("ix_mp_listings_distributor", "marketplace_listings", ["distributor_tenant_id"])
    op.create_index("ix_mp_listings_item", "marketplace_listings", ["distributor_item_id"])

    # ── marketplace_listing_components ───────────────────────────────────
    op.create_table(
        "marketplace_listing_components",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("listing_id", UUID, _fk("marketplace_listings.id", "CASCADE"), nullable=False),
        sa.Column("distributor_item_id", UUID, _fk("items.id", "CASCADE"), nullable=False),
        sa.Column("item_name", sa.String(300), nullable=False, server_default=""),
        sa.Column("qty", sa.Numeric(18, 3), nullable=False, server_default="1"),
    )
    op.create_index("ix_mp_components_listing", "marketplace_listing_components", ["listing_id"])
    op.create_index("ix_mp_components_item", "marketplace_listing_components", ["distributor_item_id"])

    # ── marketplace_connections ──────────────────────────────────────────
    op.create_table(
        "marketplace_connections",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("distributor_tenant_id", UUID, _fk("tenants.id", "CASCADE"), nullable=False),
        sa.Column("retailer_tenant_id", UUID, _fk("tenants.id", "CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("requested_by", sa.String(20), nullable=False, server_default="retailer"),
        sa.UniqueConstraint("distributor_tenant_id", "retailer_tenant_id", name="uq_mp_connection_pair"),
    )
    op.create_index("ix_mp_conn_distributor", "marketplace_connections", ["distributor_tenant_id"])
    op.create_index("ix_mp_conn_retailer", "marketplace_connections", ["retailer_tenant_id"])

    # ── marketplace_orders ───────────────────────────────────────────────
    op.create_table(
        "marketplace_orders",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("distributor_tenant_id", UUID, _fk("tenants.id", "CASCADE"), nullable=False),
        sa.Column("retailer_tenant_id", UUID, _fk("tenants.id", "CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("order_number", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="placed"),
        sa.Column("settlement_mode", sa.String(20), nullable=False, server_default="credit"),
        sa.Column("payment_status", sa.String(20), nullable=False, server_default="unpaid"),
        sa.Column("note", sa.Text, nullable=False, server_default=""),
        sa.Column("subtotal", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("distributor_sales_invoice_id", UUID, _fk("sales_invoices.id", "SET NULL"), nullable=True),
        sa.Column("retailer_purchase_invoice_id", UUID, _fk("purchase_invoices.id", "SET NULL"), nullable=True),
    )
    op.create_index("ix_mp_orders_distributor", "marketplace_orders", ["distributor_tenant_id"])
    op.create_index("ix_mp_orders_retailer", "marketplace_orders", ["retailer_tenant_id"])

    # ── marketplace_order_lines ──────────────────────────────────────────
    op.create_table(
        "marketplace_order_lines",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("order_id", UUID, _fk("marketplace_orders.id", "CASCADE"), nullable=False),
        sa.Column("listing_id", UUID, _fk("marketplace_listings.id", "SET NULL"), nullable=True),
        sa.Column("title", sa.String(300), nullable=False, server_default=""),
        sa.Column("unit_price", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("qty", sa.Numeric(18, 3), nullable=False, server_default="1"),
        sa.Column("line_total", sa.Numeric(18, 0), nullable=False, server_default="0"),
    )
    op.create_index("ix_mp_order_lines_order", "marketplace_order_lines", ["order_id"])

    # ── marketplace_item_links ───────────────────────────────────────────
    op.create_table(
        "marketplace_item_links",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("retailer_tenant_id", UUID, _fk("tenants.id", "CASCADE"), nullable=False),
        sa.Column("distributor_tenant_id", UUID, _fk("tenants.id", "CASCADE"), nullable=False),
        sa.Column("distributor_item_id", UUID, _fk("items.id", "CASCADE"), nullable=False),
        sa.Column("retailer_item_id", UUID, _fk("items.id", "CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("retailer_tenant_id", "distributor_item_id", name="uq_mp_item_link"),
    )
    op.create_index("ix_mp_item_links_retailer", "marketplace_item_links", ["retailer_tenant_id"])
    op.create_index("ix_mp_item_links_dist_item", "marketplace_item_links", ["distributor_item_id"])


def downgrade() -> None:
    op.drop_table("marketplace_item_links")
    op.drop_table("marketplace_order_lines")
    op.drop_table("marketplace_orders")
    op.drop_table("marketplace_connections")
    op.drop_table("marketplace_listing_components")
    op.drop_table("marketplace_listings")
    op.drop_table("marketplace_settings")
