"""گفتگوی بازار — جدولِ marketplace_messages + دو ستونِ last_read روی اتصال

Revision ID: 0065
Revises: 0064

- جدولِ تازه‌ی marketplace_messages: رشته‌ی گفتگوی دائم به‌ازای هر اتصالِ بازار
  (فروشگاه↔پخش‌کننده). **سراسری/بدونِ RLS** مثلِ بقیه‌ی جدول‌های بازار — جداسازی در
  کدِ روتر است، پس اینجا rls_statements صدا زده نمی‌شود.
- روی marketplace_connections دو ستونِ nullableِ last_read (برای شمارشِ پیامِ خوانده‌نشده‌ی هر سمت).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0065"
down_revision: Union[str, None] = "0064"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "marketplace_connections",
        sa.Column("distributor_last_read_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "marketplace_connections",
        sa.Column("retailer_last_read_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "marketplace_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "connection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("marketplace_connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sender_tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sender_role", sa.String(20), nullable=False),
        sa.Column("sender_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("body", sa.Text, nullable=False),
        sa.CheckConstraint(
            "sender_role IN ('distributor', 'retailer')",
            name="ck_mp_messages_sender_role",
        ),
    )
    op.create_index("ix_mp_messages_sender_tenant_id", "marketplace_messages", ["sender_tenant_id"])
    op.create_index(
        "ix_mp_messages_connection_created", "marketplace_messages", ["connection_id", "created_at"]
    )
    # عمداً بدونِ rls_statements — این جدول در GLOBAL_TABLES است (میان‌مستأجری).


def downgrade() -> None:
    op.drop_index("ix_mp_messages_connection_created", table_name="marketplace_messages")
    op.drop_index("ix_mp_messages_sender_tenant_id", table_name="marketplace_messages")
    op.drop_table("marketplace_messages")
    op.drop_column("marketplace_connections", "retailer_last_read_at")
    op.drop_column("marketplace_connections", "distributor_last_read_at")
