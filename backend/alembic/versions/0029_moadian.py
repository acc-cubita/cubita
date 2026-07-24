"""ماژول سامانه مؤدیان (صورتحساب الکترونیکی)

Revision ID: 0029
Revises: 0028

دو جدول: `moadian_settings` (اعتبارنامه‌ی هر مستأجر — شاملِ کلید خصوصی) و
`moadian_submissions` (ردِ هر تلاشِ ارسال با شناسه مالیاتی، درخواست و پاسخ).

هر دو زیر RLS می‌روند — به‌ویژه `moadian_settings` که کلید خصوصیِ امضای مالیاتی را
نگه می‌دارد و نشت‌ِ بین‌مستأجری آنجا یعنی امکانِ امضا به نامِ کسب‌وکارِ دیگر.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.tenancy import policy_name

revision: str = "0029"
down_revision: Union[str, None] = "0028"
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
        "moadian_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("memory_id", sa.String(6), nullable=False, server_default=""),
        sa.Column("economic_code", sa.String(20), nullable=False, server_default=""),
        sa.Column("national_id", sa.String(20), nullable=False, server_default=""),
        sa.Column("private_key_pem", sa.Text, nullable=False, server_default=""),
        sa.Column("is_sandbox", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("base_url_override", sa.String(300), nullable=False, server_default=""),
        sa.Column("last_serial", sa.Integer, nullable=False, server_default="0"),
        sa.UniqueConstraint("tenant_id", name="uq_moadian_settings_tenant"),
    )
    op.create_index("ix_moadian_settings_tenant_id", "moadian_settings", ["tenant_id"])

    op.create_table(
        "moadian_submissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("sales_invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sales_invoices.id"), nullable=False),
        sa.Column("tax_id", sa.String(22), nullable=False),
        sa.Column("serial", sa.Integer, nullable=False),
        sa.Column("invoice_date", sa.Date, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("reference_number", sa.String(100), nullable=False, server_default=""),
        sa.Column("error_message", sa.Text, nullable=False, server_default=""),
        sa.Column("request_payload", postgresql.JSONB, nullable=True),
        sa.Column("response_payload", postgresql.JSONB, nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'sent', 'confirmed', 'rejected', 'failed')",
            name="ck_moadian_submissions_status",
        ),
        sa.UniqueConstraint("tenant_id", "tax_id", name="uq_moadian_submissions_tax_id"),
    )
    op.create_index("ix_moadian_submissions_tenant_id", "moadian_submissions", ["tenant_id"])
    op.create_index("ix_moadian_submissions_sales_invoice_id", "moadian_submissions", ["sales_invoice_id"])
    op.create_index("ix_moadian_submissions_tax_id", "moadian_submissions", ["tax_id"])
    op.create_index("ix_moadian_submissions_status", "moadian_submissions", ["status"])

    conn = op.get_bind()
    _enable_rls(conn, "moadian_settings")
    _enable_rls(conn, "moadian_submissions")


def downgrade() -> None:
    op.drop_table("moadian_submissions")
    op.drop_table("moadian_settings")
