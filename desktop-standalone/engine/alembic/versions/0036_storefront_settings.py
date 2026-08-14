"""تنظیماتِ اتصال به فروشگاه — پرمستأجر

Revision ID: 0036
Revises: 0035

تا امروز آدرس/ایمیل/رمزِ سایتِ فروشگاهی در `.env`ِ سراسری بود، یعنی همه‌ی مستأجرها به
یک فروشگاه (ipnetcity.ir) وصل می‌شدند — که در یک SaaS چندمستأجری غلط است. این جدول
تنظیمات را به سطحِ هر کسب‌وکار می‌برد تا هر کاربر فروشگاهِ خودش را وصل کند.

`admin_password` راز است: پشتِ RLS ذخیره می‌شود و هرگز در پاسخ API برنمی‌گردد (اسکیمای
خروجی فقط `has_password` را می‌دهد) — همان الگوی کلید خصوصیِ مؤدیان.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.tenancy import policy_name

revision: str = "0036"
down_revision: Union[str, None] = "0035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enable_rls(conn, table: str) -> None:
    conn.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"DROP POLICY IF EXISTS {policy_name(table)} ON {table}"))
    conn.execute(
        sa.text(
            f"CREATE POLICY {policy_name(table)} ON {table} "
            "USING (tenant_id = current_setting('app.tenant_id', true)::uuid) "
            "WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)"
        )
    )


def upgrade() -> None:
    op.create_table(
        "storefront_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("base_url", sa.String(300), nullable=False, server_default=""),
        sa.Column("admin_email", sa.String(150), nullable=False, server_default=""),
        sa.Column("admin_password", sa.Text, nullable=False, server_default=""),
        sa.Column("cutover_order_id", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="false"),
        sa.UniqueConstraint("tenant_id", name="uq_storefront_settings_tenant"),
    )
    op.create_index("ix_storefront_settings_tenant_id", "storefront_settings", ["tenant_id"])

    conn = op.get_bind()
    _enable_rls(conn, "storefront_settings")


def downgrade() -> None:
    op.drop_table("storefront_settings")
