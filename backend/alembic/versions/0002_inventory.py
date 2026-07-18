"""inventory: warehouses, contacts, items, stock ledger, sales/purchase invoices

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "warehouses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_warehouses_code", "warehouses", ["code"])

    op.create_table(
        "contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("type", sa.String(20), nullable=False, server_default="customer"),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("email", sa.String(150), nullable=True),
        sa.Column("address", sa.Text, nullable=False, server_default=""),
        sa.Column("tax_id", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.CheckConstraint("type IN ('customer','supplier','both')", name="ck_contacts_type"),
    )

    op.create_table(
        "items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("sku", sa.String(50), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("category", sa.String(100), nullable=False, server_default=""),
        sa.Column("unit", sa.String(20), nullable=False, server_default="عدد"),
        sa.Column("is_service", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("sales_price", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("average_cost", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("storefront_product_id", sa.Integer, nullable=True),
        sa.UniqueConstraint("sku"),
    )
    op.create_index("ix_items_sku", "items", ["sku"])

    op.create_table(
        "stock_ledger",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("qty", sa.Numeric(18, 3), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 0), nullable=False),
        sa.Column("entry_date", sa.Date, nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_stock_ledger_item_id", "stock_ledger", ["item_id"])
    op.create_index("ix_stock_ledger_warehouse_id", "stock_ledger", ["warehouse_id"])

    op.execute("CREATE SEQUENCE sales_invoice_number_seq START 1")
    op.execute("CREATE SEQUENCE purchase_invoice_number_seq START 1")

    op.create_table(
        "sales_invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("number", sa.Integer, nullable=True),
        sa.Column("invoice_date", sa.Date, nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contacts.id"), nullable=True),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("total_amount", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("total_cost", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("journal_entries.id"), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.UniqueConstraint("number"),
    )
    op.create_index("ix_sales_invoices_number", "sales_invoices", ["number"])

    op.create_table(
        "sales_invoice_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sales_invoices.id"), nullable=False),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("qty", sa.Numeric(18, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 0), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 0), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
    )

    op.create_table(
        "purchase_invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("number", sa.Integer, nullable=True),
        sa.Column("invoice_date", sa.Date, nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contacts.id"), nullable=True),
        sa.Column("warehouse_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("total_amount", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("journal_entries.id"), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.UniqueConstraint("number"),
    )
    op.create_index("ix_purchase_invoices_number", "purchase_invoices", ["number"])

    op.create_table(
        "purchase_invoice_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("purchase_invoices.id"), nullable=False),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("items.id"), nullable=False),
        sa.Column("qty", sa.Numeric(18, 3), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 0), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_table("purchase_invoice_lines")
    op.drop_table("purchase_invoices")
    op.drop_table("sales_invoice_lines")
    op.drop_table("sales_invoices")
    op.execute("DROP SEQUENCE purchase_invoice_number_seq")
    op.execute("DROP SEQUENCE sales_invoice_number_seq")
    op.drop_table("stock_ledger")
    op.drop_table("items")
    op.drop_table("contacts")
    op.drop_table("warehouses")
