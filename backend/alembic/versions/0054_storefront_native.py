"""فروشگاهِ بومیِ کوبیتا — جدول‌های پایه

Revision ID: 0054
Revises: 0053

فروشگاه یک سطحِ بومیِ خودِ برنامه می‌شود (نه sync با سایتِ بیرونی): کاتالوگ = همان
`items`، سفارشِ سایت مستقیماً فاکتورِ فروش می‌شود. این مهاجرت ۷ جدولِ مستأجرمحور می‌سازد
و روی همه RLS فعال می‌کند. جزئیات: STOREFRONT_PLAN.md.

مدلِ اتصالِ بیرونیِ فعلی (`storefront_settings`, مهاجرت 0036) دست‌نخورده می‌ماند —
ipnetcity روی آن زنده است.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.tenancy import rls_statements

revision: str = "0054"
down_revision: Union[str, None] = "0053"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TENANT_TABLES = (
    "storefronts",
    "item_storefront",
    "storefront_categories",
    "storefront_customers",
    "storefront_orders",
    "storefront_order_lines",
    "payment_gateways",
)


def _common(*cols):
    """ستون‌های مشترکِ هر جدولِ مستأجرمحور (id/tenant_id/created_at/updated_at) + بقیه."""
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        *cols,
    ]


def upgrade() -> None:
    op.create_table(
        "storefronts",
        *_common(
            sa.Column("theme_id", sa.String(50), nullable=False, server_default="general"),
            sa.Column("theme_config", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("seo_title", sa.String(200), nullable=False, server_default=""),
            sa.Column("seo_description", sa.Text, nullable=False, server_default=""),
            sa.Column("contact_block", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("publishable_key", sa.String(64), nullable=False, server_default=""),
            sa.Column("allowed_origin", sa.String(300), nullable=False, server_default=""),
            sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
            sa.Column("last_built_at", sa.DateTime(timezone=True), nullable=True),
        ),
        sa.UniqueConstraint("tenant_id", name="uq_storefronts_tenant"),
    )
    op.create_index("ix_storefronts_tenant_id", "storefronts", ["tenant_id"])
    op.create_index("ix_storefronts_publishable_key", "storefronts", ["publishable_key"])

    op.create_table(
        "item_storefront",
        *_common(
            sa.Column("item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("items.id", ondelete="CASCADE"), nullable=False),
            sa.Column("is_listed", sa.Boolean, nullable=False, server_default="true"),
            sa.Column("images", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("long_description", sa.Text, nullable=False, server_default=""),
            sa.Column("slug", sa.String(200), nullable=False, server_default=""),
            sa.Column("sort", sa.Integer, nullable=False, server_default="0"),
            sa.Column("badge", sa.String(30), nullable=False, server_default=""),
        ),
        sa.UniqueConstraint("tenant_id", "item_id", name="uq_item_storefront_item"),
    )
    op.create_index("ix_item_storefront_tenant_id", "item_storefront", ["tenant_id"])
    op.create_index("ix_item_storefront_item_id", "item_storefront", ["item_id"])
    op.create_index("ix_item_storefront_slug", "item_storefront", ["slug"])

    op.create_table(
        "storefront_categories",
        *_common(
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("slug", sa.String(120), nullable=False),
            sa.Column("sort", sa.Integer, nullable=False, server_default="0"),
            sa.Column("parent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("storefront_categories.id"), nullable=True),
        ),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_storefront_categories_slug"),
    )
    op.create_index("ix_storefront_categories_tenant_id", "storefront_categories", ["tenant_id"])
    op.create_index("ix_storefront_categories_slug", "storefront_categories", ["slug"])

    op.create_table(
        "storefront_customers",
        *_common(
            sa.Column("name", sa.String(150), nullable=False, server_default=""),
            sa.Column("phone", sa.String(20), nullable=False),
            sa.Column("email", sa.String(150), nullable=False, server_default=""),
            sa.Column("address", sa.Text, nullable=False, server_default=""),
            sa.Column("contact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contacts.id"), nullable=True),
        ),
        sa.UniqueConstraint("tenant_id", "phone", name="uq_storefront_customers_phone"),
    )
    op.create_index("ix_storefront_customers_tenant_id", "storefront_customers", ["tenant_id"])
    op.create_index("ix_storefront_customers_phone", "storefront_customers", ["phone"])

    op.create_table(
        "storefront_orders",
        *_common(
            sa.Column("order_number", sa.Integer, nullable=False, server_default="0"),
            sa.Column("tracking_code", sa.String(40), nullable=False, server_default=""),
            sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("storefront_customers.id"), nullable=True),
            sa.Column("customer_name", sa.String(150), nullable=False, server_default=""),
            sa.Column("customer_phone", sa.String(20), nullable=False, server_default=""),
            sa.Column("customer_email", sa.String(150), nullable=False, server_default=""),
            sa.Column("shipping_address", sa.Text, nullable=False, server_default=""),
            sa.Column("note", sa.Text, nullable=False, server_default=""),
            sa.Column("subtotal", sa.Numeric(18, 0), nullable=False, server_default="0"),
            sa.Column("discount", sa.Numeric(18, 0), nullable=False, server_default="0"),
            sa.Column("shipping_fee", sa.Numeric(18, 0), nullable=False, server_default="0"),
            sa.Column("tax", sa.Numeric(18, 0), nullable=False, server_default="0"),
            sa.Column("total", sa.Numeric(18, 0), nullable=False, server_default="0"),
            sa.Column("payment_status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("payment_provider", sa.String(20), nullable=False, server_default=""),
            sa.Column("payment_ref", sa.String(100), nullable=False, server_default=""),
            sa.Column("payment_authority", sa.String(100), nullable=False, server_default=""),
            sa.Column("fulfillment_status", sa.String(20), nullable=False, server_default="new"),
            sa.Column("sales_invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sales_invoices.id"), nullable=True),
        ),
        sa.CheckConstraint(
            "payment_status IN ('pending', 'paid', 'failed', 'cancelled')",
            name="ck_storefront_orders_payment",
        ),
        sa.CheckConstraint(
            "fulfillment_status IN ('new', 'confirmed', 'shipped', 'done', 'cancelled')",
            name="ck_storefront_orders_fulfillment",
        ),
    )
    op.create_index("ix_storefront_orders_tenant_id", "storefront_orders", ["tenant_id"])
    op.create_index("ix_storefront_orders_tracking_code", "storefront_orders", ["tracking_code"])
    op.create_index("ix_storefront_orders_payment_authority", "storefront_orders", ["payment_authority"])

    op.create_table(
        "storefront_order_lines",
        *_common(
            sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("storefront_orders.id", ondelete="CASCADE"), nullable=False),
            sa.Column("item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("items.id"), nullable=False),
            sa.Column("item_name", sa.String(300), nullable=False, server_default=""),
            sa.Column("qty", sa.Numeric(18, 3), nullable=False, server_default="0"),
            sa.Column("unit_price", sa.Numeric(18, 0), nullable=False, server_default="0"),
            sa.Column("line_total", sa.Numeric(18, 0), nullable=False, server_default="0"),
        ),
    )
    op.create_index("ix_storefront_order_lines_tenant_id", "storefront_order_lines", ["tenant_id"])
    op.create_index("ix_storefront_order_lines_order_id", "storefront_order_lines", ["order_id"])
    op.create_index("ix_storefront_order_lines_item_id", "storefront_order_lines", ["item_id"])

    op.create_table(
        "payment_gateways",
        *_common(
            sa.Column("provider", sa.String(20), nullable=False),
            sa.Column("merchant_id", sa.Text, nullable=False, server_default=""),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default="false"),
            sa.Column("sort", sa.Integer, nullable=False, server_default="0"),
            sa.Column("config", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        ),
        sa.UniqueConstraint("tenant_id", "provider", name="uq_payment_gateways_provider"),
        sa.CheckConstraint(
            "provider IN ('zarinpal', 'zibal', 'idpay')", name="ck_payment_gateways_provider"
        ),
    )
    op.create_index("ix_payment_gateways_tenant_id", "payment_gateways", ["tenant_id"])

    conn = op.get_bind()
    for stmt in rls_statements(_TENANT_TABLES):
        conn.execute(sa.text(stmt))


def downgrade() -> None:
    for table in reversed(_TENANT_TABLES):
        op.drop_table(table)
