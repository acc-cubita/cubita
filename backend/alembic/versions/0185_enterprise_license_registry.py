"""دفترِ مجوزهای «کوبیتا سازمانی» در ابر — `enterprise_licenses` و `enterprise_license_events`

Revision ID: 0185
Revises: 0184

M3 از ENTERPRISE_PLAN.md: پنلِ ستاد و فعال‌سازیِ آنلاین. هر دو جدول سراسری‌اند و RLS
ندارند — دفترِ کنترل‌پنل‌اند، نه دفترِ یک مشتری (توضیح در
`app/models/enterprise_license_registry.py`). بدونِ مهاجرتِ داده.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0185"
down_revision: Union[str, None] = "0184"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "enterprise_licenses",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lic_id", sa.String(length=16), nullable=False),
        sa.Column("org_name", sa.String(length=200), nullable=False),
        sa.Column("contact", sa.String(length=200), nullable=True),
        sa.Column("seats", sa.Integer(), nullable=True),
        sa.Column("mods", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("feat", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("grace_days", sa.Integer(), server_default="14", nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("code_hint", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="active", nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("install_id", sa.String(length=64), nullable=True),
        sa.Column("fp", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("bound_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("issue_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by_email", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lic_id"),
        sa.UniqueConstraint("code_hash"),
    )
    op.create_table(
        "enterprise_license_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("license_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("actor", sa.String(length=255), nullable=False),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["license_id"], ["enterprise_licenses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_enterprise_license_events_license_id"), "enterprise_license_events", ["license_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_enterprise_license_events_license_id"), table_name="enterprise_license_events")
    op.drop_table("enterprise_license_events")
    op.drop_table("enterprise_licenses")
