"""اشتراک: پلن سالانه فروخته می‌شد و سال دوم رایگان بود

Revision ID: 0022
Revises: 0021

**جدول سراسری است و RLS نمی‌گیرد** — داده‌ی صفحه‌ی کنترل پلتفرم است، نه دفتر
مشتری. همان تفکیک control-plane از data-plane.

**مستأجرهای موجود دوره می‌گیرند، نه انقضا.** اگر جدول خالی می‌ماند، کدی که
«اشتراک ندارد» را باز تفسیر می‌کند درست کار می‌کرد ولی وضعیت واقعی هیچ‌جا نوشته
نبود. یک ردیف صریح برای هرکدام یعنی صفحه‌ی مدیریت از روز اول حقیقت را نشان
می‌دهد. یک سال داده می‌شود چون این مستأجرها پیش از وجود صورتحساب ساخته شده‌اند و
جریمه کردنشان به‌خاطر کاری که ما دیر انجام دادیم منطقی نیست.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "subscriptions"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("plans.id"), nullable=True),
        sa.Column("purchase_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("purchases.id"), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("source", sa.String(30), nullable=False, server_default="manual"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(f"ix_{TABLE}_tenant_id", TABLE, ["tenant_id"])
    op.create_index(f"ix_{TABLE}_expires_at", TABLE, ["expires_at"])

    # هر مستأجر موجود یک سال از همین حالا می‌گیرد.
    op.execute(
        """
        INSERT INTO subscriptions (id, tenant_id, starts_at, expires_at, note, source, created_at, updated_at)
        SELECT gen_random_uuid(), t.id, now(), now() + interval '365 days',
               'انتقال از پیش از وجود صورتحساب', 'manual', now(), now()
          FROM tenants t
        """
    )


def downgrade() -> None:
    op.drop_table(TABLE)
