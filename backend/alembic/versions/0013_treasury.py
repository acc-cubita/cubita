"""treasury: receipts/payments against contacts (دریافت و پرداخت)

Revision ID: 0013
Revises: 0012
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "treasury_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("transaction_date", sa.Date, nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contacts.id"), nullable=False),
        sa.Column("amount", sa.Numeric(18, 0), nullable=False),
        sa.Column("method", sa.String(10), nullable=False, server_default="cash"),
        sa.Column("bank_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("bank_accounts.id"), nullable=True),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("journal_entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("journal_entries.id"), nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.CheckConstraint("type IN ('receipt', 'payment')", name="ck_treasury_transactions_type"),
        sa.CheckConstraint("method IN ('cash', 'bank')", name="ck_treasury_transactions_method"),
        sa.CheckConstraint("amount > 0", name="ck_treasury_transactions_amount_positive"),
    )


def downgrade() -> None:
    op.drop_table("treasury_transactions")
