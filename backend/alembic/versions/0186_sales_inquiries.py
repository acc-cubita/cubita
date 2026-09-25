"""درخواست‌های خرید و مشاوره از سایت — `sales_inquiries`

Revision ID: 0186
Revises: 0185

پلن‌های قیمت‌دار از cubita.ir برداشته شدند و فروش از راهِ فرمِ «تماس برای خرید» است. جدول سراسری
است و RLS ندارد (فرستنده هنوز مشتری نیست — توضیح در `app/models/sales_inquiry.py`). بدونِ مهاجرتِ داده.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0186"
down_revision: Union[str, None] = "0185"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sales_inquiries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("company", sa.String(length=200), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("email", sa.String(length=200), nullable=False),
        sa.Column("product", sa.String(length=16), nullable=False),
        sa.Column("seats", sa.Integer(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="new", nullable=False),
        sa.Column("staff_note", sa.Text(), server_default="", nullable=False),
        sa.Column("handled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("handled_by", sa.String(length=200), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sales_inquiries_created_at", "sales_inquiries", ["created_at"])
    op.create_index("ix_sales_inquiries_product", "sales_inquiries", ["product"])
    op.create_index("ix_sales_inquiries_status", "sales_inquiries", ["status"])


def downgrade() -> None:
    op.drop_index("ix_sales_inquiries_status", table_name="sales_inquiries")
    op.drop_index("ix_sales_inquiries_product", table_name="sales_inquiries")
    op.drop_index("ix_sales_inquiries_created_at", table_name="sales_inquiries")
    op.drop_table("sales_inquiries")
