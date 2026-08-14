"""دفتر ردِ حسابرسی، فقط‌افزودنی در سطح پایگاه‌داده

Revision ID: 0021
Revises: 0020

**چرا trigger و نه REVOKE:** اپ با همان نقشی وصل می‌شود که مالک جدول‌هاست، و مالک
می‌تواند هر GRANT ی را به خودش برگرداند. trigger تنها چیزی است که در برابر خودِ
مالک هم می‌ایستد — و برداشتنش یک DDL صریح است که در تاریخچه‌ی مهاجرت می‌ماند، نه
یک اشتباه بی‌صدا.

**دریچه‌ی پاک‌سازی:** حذف مستأجر باید ممکن بماند (offboarding مشتری). ولی اگر
حذف را باز بگذاریم، همان مسیر برای پاک کردن ردِ یک ابطال هم کار می‌کند. پس حذف
فقط وقتی مجاز است که `app.audit_purge` صریحاً روشن شده باشد — چیزی که هیچ مسیر
عادی‌ای ست نمی‌کند و در کد قابل grep است. UPDATE هیچ دریچه‌ای ندارد: هیچ دلیل
مشروعی برای عوض کردن یک رکورد حسابرسی وجود ندارد.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.audit import GUARD_FN, GUARD_TRIGGER, append_only_statements
from app.tenancy import policy_name

revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "audit_log"


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
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        # کاربر ممکن است پاک شود ولی رکورد باید بماند — پس SET NULL و نه CASCADE.
        # نام کاربر جداگانه کپی شده، پس هویتش با پاک شدن حساب گم نمی‌شود.
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("actor_email", sa.String(255), nullable=False, server_default=""),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("changes", postgresql.JSONB(), nullable=True),
        sa.Column("request_id", sa.String(64), nullable=True),
    )
    op.create_index(f"ix_{TABLE}_tenant_id", TABLE, ["tenant_id"])
    op.create_index(f"ix_{TABLE}_at", TABLE, ["at"])
    op.create_index(f"ix_{TABLE}_action", TABLE, ["action"])
    op.create_index(f"ix_{TABLE}_entity_type", TABLE, ["entity_type"])
    op.create_index(f"ix_{TABLE}_entity_id", TABLE, ["entity_id"])

    conn = op.get_bind()

    # جدول مستأجرمحور است، پس مثل بقیه زیر RLS می‌رود.
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

    # همان DDL ای که تست‌ها هم استفاده می‌کنند. اگر اینجا کپی می‌شد، دیر یا زود
    # نسخه‌ی مهاجرت و نسخه‌ی تست از هم جدا می‌افتادند و تست چیزی را می‌سنجید که
    # روی production نیست.
    for stmt in append_only_statements(TABLE):
        conn.execute(sa.text(stmt))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(f"DROP TRIGGER IF EXISTS {GUARD_TRIGGER} ON {TABLE}"))
    conn.execute(sa.text(f"DROP FUNCTION IF EXISTS {GUARD_FN}()"))
    op.drop_table(TABLE)
