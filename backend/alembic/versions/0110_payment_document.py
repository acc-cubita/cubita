"""اعلامیه‌ی پرداخت چندابزاری روی خزانه، بانک و چرخه‌ی چک موجود."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.tenancy import policy_name

revision: str = "0110"
down_revision: Union[str, None] = "0109"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enable_rls(table: str) -> None:
    conn = op.get_bind()
    conn.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"DROP POLICY IF EXISTS {policy_name(table)} ON {table}"))
    conn.execute(sa.text(
        f"CREATE POLICY {policy_name(table)} ON {table} "
        "USING (tenant_id = current_setting('app.tenant_id', true)::uuid) "
        "WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)"
    ))


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("number", sa.Numeric(18, 0), nullable=False),
        sa.Column("payment_type", sa.String(20), server_default="supplier", nullable=False),
        sa.Column("contact_id", UUID(as_uuid=True), sa.ForeignKey("contacts.id"), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("counterparty_account_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("bank_fee_account_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=True),
        sa.Column("discount_account_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=True),
        sa.Column("currency_code", sa.String(3), server_default="IRR", nullable=False),
        sa.Column("exchange_rate", sa.Numeric(18, 4), server_default="1", nullable=False),
        sa.Column("payment_amount", sa.Numeric(18, 0), nullable=False),
        sa.Column("base_currency_amount", sa.Numeric(18, 0), nullable=False),
        sa.Column("discount_amount", sa.Numeric(18, 0), server_default="0", nullable=False),
        sa.Column("settlement_total", sa.Numeric(18, 0), nullable=False),
        sa.Column("bank_fee_amount", sa.Numeric(18, 0), server_default="0", nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("description2", sa.String(200), server_default="", nullable=False),
        sa.Column("establishment", sa.String(120), server_default="", nullable=False),
        sa.Column("journal_entry_id", UUID(as_uuid=True), sa.ForeignKey("journal_entries.id"), nullable=False, index=True),
        sa.Column("created_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column("void_reason", sa.Text(), server_default="", nullable=False),
        sa.Column("voided_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("tenant_id", "number", name="uq_payments_tenant_number"),
        sa.CheckConstraint("payment_amount > 0", name="ck_payments_amount_positive"),
        sa.CheckConstraint("discount_amount >= 0 AND bank_fee_amount >= 0", name="ck_payments_nonnegative"),
        sa.CheckConstraint("exchange_rate > 0", name="ck_payments_exchange_rate_positive"),
    )
    _enable_rls("payments")

    op.create_table(
        "payment_cheque_transfers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("payment_id", UUID(as_uuid=True), sa.ForeignKey("payments.id"), nullable=False, index=True),
        sa.Column("check_id", UUID(as_uuid=True), sa.ForeignKey("checks.id"), nullable=False, index=True),
        sa.Column("previous_status", sa.String(20), server_default="in_hand", nullable=False),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("tenant_id", "payment_id", "check_id", name="uq_payment_cheque_transfer"),
    )
    _enable_rls("payment_cheque_transfers")

    op.create_table(
        "payment_related_documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("payment_id", UUID(as_uuid=True), sa.ForeignKey("payments.id"), nullable=False, index=True),
        sa.Column("document_type", sa.String(40), nullable=False),
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("allocated_amount", sa.Numeric(18, 0), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("tenant_id", "payment_id", "document_type", "document_id", name="uq_payment_related_document"),
        sa.CheckConstraint("allocated_amount >= 0", name="ck_payment_related_allocated_nonnegative"),
    )
    _enable_rls("payment_related_documents")

    op.add_column("treasury_transactions", sa.Column("payment_id", UUID(as_uuid=True), sa.ForeignKey("payments.id"), nullable=True))
    op.create_index("ix_treasury_transactions_payment_id", "treasury_transactions", ["payment_id"])
    op.add_column("checks", sa.Column("payment_id", UUID(as_uuid=True), sa.ForeignKey("payments.id"), nullable=True))
    op.create_index("ix_checks_payment_id", "checks", ["payment_id"])
    op.add_column("bank_transactions", sa.Column("payment_id", UUID(as_uuid=True), sa.ForeignKey("payments.id"), nullable=True))
    op.create_index("ix_bank_transactions_payment_id", "bank_transactions", ["payment_id"])
    op.add_column("bank_transactions", sa.Column("description2", sa.String(200), server_default="", nullable=False))
    op.add_column("bank_transactions", sa.Column("reference_no", sa.String(50), server_default="", nullable=False))
    op.add_column("bank_transactions", sa.Column("principal_amount", sa.Numeric(18, 0), server_default="0", nullable=False))
    op.add_column("bank_transactions", sa.Column("bank_fee_amount", sa.Numeric(18, 0), server_default="0", nullable=False))


def downgrade() -> None:
    for name in ("bank_fee_amount", "principal_amount", "reference_no", "description2"):
        op.drop_column("bank_transactions", name)
    op.drop_index("ix_bank_transactions_payment_id", table_name="bank_transactions")
    op.drop_column("bank_transactions", "payment_id")
    op.drop_index("ix_checks_payment_id", table_name="checks")
    op.drop_column("checks", "payment_id")
    op.drop_index("ix_treasury_transactions_payment_id", table_name="treasury_transactions")
    op.drop_column("treasury_transactions", "payment_id")
    op.drop_table("payment_related_documents")
    op.drop_table("payment_cheque_transfers")
    op.drop_table("payments")
