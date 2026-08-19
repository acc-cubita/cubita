"""توکنِ دستگاهِ Push (FCM) — جدولِ سراسریِ device_tokens

Revision ID: 0068
Revises: 0067

ثبتِ توکنِ FCMِ اپ موبایل برای اعلانِ Push. **سراسری/بدونِ RLS** — دستگاه به کاربر
(سراسری) تعلق دارد؛ نامش در GLOBAL_TABLES است، پس rls_statements صدا زده نمی‌شود.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0068"
down_revision: Union[str, None] = "0067"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "device_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("fcm_token", sa.String(255), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("platform", sa.String(20), server_default="android", nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_device_tokens_fcm_token", "device_tokens", ["fcm_token"], unique=True)
    op.create_index("ix_device_tokens_user_id", "device_tokens", ["user_id"])
    op.create_index("ix_device_tokens_tenant_id", "device_tokens", ["tenant_id"])
    # عمداً بدونِ rls_statements — این جدول سراسری است (در GLOBAL_TABLES).


def downgrade() -> None:
    op.drop_index("ix_device_tokens_tenant_id", table_name="device_tokens")
    op.drop_index("ix_device_tokens_user_id", table_name="device_tokens")
    op.drop_index("ix_device_tokens_fcm_token", table_name="device_tokens")
    op.drop_table("device_tokens")
