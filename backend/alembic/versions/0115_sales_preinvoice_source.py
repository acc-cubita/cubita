"""پیش‌فاکتورِ نسخه‌پذیر با منبعِ ردیفی و چرخه‌ی خاتمه."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0115"
down_revision: Union[str, None] = "0114"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("sales_quotations", "warehouse_id", existing_type=UUID(), nullable=True)
    op.add_column("sales_quotations", sa.Column("customer_snapshot", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column("sales_quotations", sa.Column("customer_name2", sa.String(200), server_default="", nullable=False))
    op.add_column("sales_quotations", sa.Column("delivery_location", sa.Text(), server_default="", nullable=False))
    op.add_column("sales_quotations", sa.Column("sale_type_id", UUID(), nullable=True))
    op.add_column("sales_quotations", sa.Column("currency_code", sa.String(3), nullable=True))
    op.add_column("sales_quotations", sa.Column("exchange_rate", sa.Numeric(18, 4), server_default="1", nullable=False))
    op.add_column("sales_quotations", sa.Column("terminated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("sales_quotations", sa.Column("terminated_by_id", UUID(), nullable=True))
    op.create_foreign_key("fk_sales_quotations_sale_type", "sales_quotations", "sale_types", ["sale_type_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_sales_quotations_terminated_by", "sales_quotations", "users", ["terminated_by_id"], ["id"])

    for table in ("sales_quotation_lines",):
        op.add_column(table, sa.Column("item_code_snapshot", sa.String(50), server_default="", nullable=False))
        op.add_column(table, sa.Column("item_name_snapshot", sa.String(300), server_default="", nullable=False))
        op.add_column(table, sa.Column("unit_snapshot", sa.String(20), server_default="", nullable=False))

    op.add_column("sales_invoices", sa.Column("source_quotation_id", UUID(), nullable=True))
    op.create_foreign_key("fk_sales_invoices_source_quotation", "sales_invoices", "sales_quotations", ["source_quotation_id"], ["id"])
    op.create_index("ix_sales_invoices_source_quotation_id", "sales_invoices", ["source_quotation_id"])
    op.add_column("sales_invoice_lines", sa.Column("source_quotation_line_id", UUID(), nullable=True))
    op.create_foreign_key("fk_sales_invoice_lines_source_quotation_line", "sales_invoice_lines", "sales_quotation_lines", ["source_quotation_line_id"], ["id"])
    op.create_index("ix_sales_invoice_lines_source_quotation_line_id", "sales_invoice_lines", ["source_quotation_line_id"])


def downgrade() -> None:
    op.drop_index("ix_sales_invoice_lines_source_quotation_line_id", table_name="sales_invoice_lines")
    op.drop_constraint("fk_sales_invoice_lines_source_quotation_line", "sales_invoice_lines", type_="foreignkey")
    op.drop_column("sales_invoice_lines", "source_quotation_line_id")
    op.drop_index("ix_sales_invoices_source_quotation_id", table_name="sales_invoices")
    op.drop_constraint("fk_sales_invoices_source_quotation", "sales_invoices", type_="foreignkey")
    op.drop_column("sales_invoices", "source_quotation_id")
    for column in ("unit_snapshot", "item_name_snapshot", "item_code_snapshot"):
        op.drop_column("sales_quotation_lines", column)
    op.drop_constraint("fk_sales_quotations_terminated_by", "sales_quotations", type_="foreignkey")
    op.drop_constraint("fk_sales_quotations_sale_type", "sales_quotations", type_="foreignkey")
    for column in ("terminated_by_id", "terminated_at", "exchange_rate", "currency_code", "sale_type_id", "delivery_location", "customer_name2", "customer_snapshot"):
        op.drop_column("sales_quotations", column)
    op.alter_column("sales_quotations", "warehouse_id", existing_type=UUID(), nullable=False)
