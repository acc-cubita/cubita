"""«کوبیتا سازمانی» رایگان — `enterprise_licenses.tier` و `enterprise_free_codes`

Revision ID: 0192
Revises: 0191

ثبت‌نامِ رایگان: مشتری با شماره‌ی همراه (کدِ پیامکی) مجوزِ دائمیِ رایگان با سقفِ کاربر می‌گیرد
(`app/services/enterprise_free.py`). مجوزهای موجود همه فروخته‌شده‌اند، پس پیش‌فرضِ ستون
`paid` است و هیچ مهاجرتِ داده‌ای لازم نیست. هر دو جدول سراسری‌اند و RLS ندارند (توضیح در
`app/models/enterprise_license_registry.py`).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0192"
down_revision: Union[str, None] = "0191"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "enterprise_licenses",
        sa.Column("tier", sa.String(length=16), server_default="paid", nullable=False),
    )
    op.create_index(op.f("ix_enterprise_licenses_tier"), "enterprise_licenses", ["tier"])
    op.create_table(
        "enterprise_free_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_enterprise_free_codes_phone"), "enterprise_free_codes", ["phone"])


def downgrade() -> None:
    op.drop_index(op.f("ix_enterprise_free_codes_phone"), table_name="enterprise_free_codes")
    op.drop_table("enterprise_free_codes")
    op.drop_index(op.f("ix_enterprise_licenses_tier"), table_name="enterprise_licenses")
    op.drop_column("enterprise_licenses", "tier")
