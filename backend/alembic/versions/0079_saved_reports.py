"""گزارش‌ساز: تعریفِ گزارش‌های ساخته‌شده‌ی کاربر

Revision ID: 0079
Revises: 0078

جدولِ `saved_reports` با RLS. فقط *تعریفِ* گزارش ذخیره می‌شود نه نتیجه‌اش — نتیجه
هر بار زنده اجرا می‌شود، وگرنه گزارشی می‌ماند که با گذشتِ زمان دروغ می‌گوید.

`config` از نوعِ JSONB است چون شکلِ تعریف (ستون‌ها، فیلترها، مرتب‌سازی) با هر ستونِ
تازه‌ای در منابعِ داده عوض می‌شود؛ مهاجرت‌به‌ازای‌هر‌تغییرِ‌رابط هزینه‌ای است که این
قابلیت نمی‌ارزد.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.tenancy import policy_name

revision: str = "0079"
down_revision: Union[str, None] = "0078"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "saved_reports"


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
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("is_pinned", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column(
            "created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
    )

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
