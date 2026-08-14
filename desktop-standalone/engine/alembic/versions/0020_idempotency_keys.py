"""کلید یکتاسازی درخواست: جلوگیری از ثبت دوباره‌ی سند مالی

Revision ID: 0020
Revises: 0019

قید یکتای (tenant_id, key) فقط برای جلوگیری از تکرار نیست — همان چیزی است که
درخواست‌های هم‌زمان را سریالیزه می‌کند. توضیح کامل در services/idempotency.py
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.migration_utils import rls_disabled
from app.tenancy import policy_name

revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "idempotency_keys"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(200), nullable=False),
        sa.Column("operation", sa.String(80), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "key", name="uq_idempotency_tenant_key"),
    )
    op.create_index(f"ix_{TABLE}_tenant_id", TABLE, ["tenant_id"])
    op.create_index(f"ix_{TABLE}_key", TABLE, ["key"])

    # جدول مستأجرمحور است، پس مثل بقیه زیر RLS می‌رود. بدون این، تست
    # introspection قرمز می‌شود — که دقیقاً کاری است که باید بکند.
    conn = op.get_bind()
    conn.execute(sa.text(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"DROP POLICY IF EXISTS {policy_name(TABLE)} ON {TABLE}"))
    conn.execute(
        sa.text(
            f"CREATE POLICY {policy_name(TABLE)} ON {TABLE} "
            "USING (tenant_id = current_setting('app.tenant_id', true)::uuid) "
            "WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)"
        )
    )


def downgrade() -> None:
    op.drop_table(TABLE)
