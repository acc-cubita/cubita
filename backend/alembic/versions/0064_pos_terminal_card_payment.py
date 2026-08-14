"""کارتخوان — متادیتای پرداختِ کارتی روی خزانه + جدولِ pos_terminals

Revision ID: 0064
Revises: 0063

- روی treasury_transactions شش ستونِ متادیتای کارت (paid_via/RRN/trace/کارت/پایانه/PSP)،
  همه nullable؛ ایندکسِ یکتای جزئی روی (tenant_id, reference_no) برای idempotency.
- جدولِ تازه‌ی pos_terminals: پروفایلِ دستگاهِ کارتخوانِ هر کسب‌وکار (تنانت‌محور، با RLS).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.tenancy import rls_statements

revision: str = "0064"
down_revision: Union[str, None] = "0063"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── متادیتای پرداختِ کارتی روی خزانه ──
    op.add_column("treasury_transactions", sa.Column("paid_via", sa.String(20), nullable=True))
    op.add_column("treasury_transactions", sa.Column("reference_no", sa.String(40), nullable=True))
    op.add_column("treasury_transactions", sa.Column("trace_no", sa.String(40), nullable=True))
    op.add_column("treasury_transactions", sa.Column("card_mask", sa.String(30), nullable=True))
    op.add_column("treasury_transactions", sa.Column("terminal_no", sa.String(30), nullable=True))
    op.add_column("treasury_transactions", sa.Column("psp", sa.String(30), nullable=True))
    # یکتاییِ RRN در سطحِ مستأجر (فقط ردیف‌های دارای RRN) → کلیدِ idempotency برای پرداختِ کارتی.
    op.create_index(
        "uq_treasury_tenant_reference",
        "treasury_transactions",
        ["tenant_id", "reference_no"],
        unique=True,
        postgresql_where=sa.text("reference_no IS NOT NULL"),
    )

    # ── جدولِ ترمینال‌های کارتخوان (تنانت‌محور) ──
    op.create_table(
        "pos_terminals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("label", sa.String(120), nullable=False, server_default=""),
        sa.Column("psp", sa.String(30), nullable=False, server_default=""),
        sa.Column("transport", sa.String(20), nullable=False, server_default="simulator"),
        sa.Column("host", sa.String(120), nullable=False, server_default=""),
        sa.Column("port", sa.Integer, nullable=False, server_default="0"),
        sa.Column("com_port", sa.String(20), nullable=False, server_default=""),
        sa.Column("bank_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("bank_accounts.id"), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default="false"),
        sa.CheckConstraint(
            "transport IN ('simulator', 'network', 'serial', 'sdk')",
            name="ck_pos_terminals_transport",
        ),
    )
    op.create_index("ix_pos_terminals_tenant_id", "pos_terminals", ["tenant_id"])

    # طرف‌حسابِ سیستمیِ «فروشِ کارتیِ گذری» با این پرچم از فهرستِ مشتریان پنهان می‌ماند.
    op.add_column(
        "contacts",
        sa.Column("is_system", sa.Boolean, nullable=False, server_default="false"),
    )

    conn = op.get_bind()
    for stmt in rls_statements(("pos_terminals",)):
        conn.execute(sa.text(stmt))


def downgrade() -> None:
    op.drop_column("contacts", "is_system")
    op.drop_table("pos_terminals")
    op.drop_index("uq_treasury_tenant_reference", table_name="treasury_transactions")
    op.drop_column("treasury_transactions", "psp")
    op.drop_column("treasury_transactions", "terminal_no")
    op.drop_column("treasury_transactions", "card_mask")
    op.drop_column("treasury_transactions", "trace_no")
    op.drop_column("treasury_transactions", "reference_no")
    op.drop_column("treasury_transactions", "paid_via")
