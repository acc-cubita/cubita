"""banking: bank accounts, checks, bank transactions, petty cash

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bank_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("bank_name", sa.String(100), nullable=False, server_default=""),
        sa.Column("account_number", sa.String(50), nullable=False, server_default=""),
        sa.Column("iban", sa.String(34), nullable=False, server_default=""),
        sa.Column("gl_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
    )

    op.create_table(
        "checks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("number", sa.String(50), nullable=False),
        sa.Column("bank_name", sa.String(100), nullable=False, server_default=""),
        sa.Column("amount", sa.Numeric(18, 0), nullable=False),
        sa.Column("issue_date", sa.Date, nullable=False),
        sa.Column("due_date", sa.Date, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contacts.id"), nullable=True),
        sa.Column("bank_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("bank_accounts.id"), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.CheckConstraint("type IN ('receivable','payable')", name="ck_checks_type"),
        sa.CheckConstraint(
            "status IN ('in_hand','deposited','cleared','bounced','endorsed','issued')", name="ck_checks_status"
        ),
    )

    op.create_table(
        "bank_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("bank_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("bank_accounts.id"), nullable=False),
        sa.Column("transaction_date", sa.Date, nullable=False),
        sa.Column("amount", sa.Numeric(18, 0), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("is_reconciled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("source_type", sa.String(50), nullable=False, server_default="manual"),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("journal_entries.id"), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
    )

    op.create_table(
        "petty_cash_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("transaction_date", sa.Date, nullable=False),
        sa.Column("amount", sa.Numeric(18, 0), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("counter_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("journal_entries.id"), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.CheckConstraint("type IN ('charge','expense')", name="ck_petty_cash_type"),
    )


def downgrade() -> None:
    op.drop_table("petty_cash_transactions")
    op.drop_table("bank_transactions")
    op.drop_table("checks")
    op.drop_table("bank_accounts")
