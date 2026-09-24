"""مجوزِ «کوبیتا سازمانی» — جدولِ تک‌ردیفیِ `enterprise_license`

Revision ID: 0184
Revises: 0183

M2 از ENTERPRISE_PLAN.md. جدول در هر دو نسخه ساخته می‌شود (یک اسکیما، دو محصول) ولی
در ابر خالی می‌ماند. سراسری است و RLS ندارد — مالِ نصب است، نه یک کسب‌وکار؛ توضیح در
`app/models/enterprise_license.py`. بدونِ مهاجرتِ داده.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0184"
down_revision: Union[str, None] = "0183"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "enterprise_license",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("install_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("installed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("token", sa.Text(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.CheckConstraint("id = 1", name="ck_enterprise_license_singleton"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("enterprise_license")
