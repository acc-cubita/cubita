"""bank statement lines (تطبیق بانکی رسمی) — imported statement rows matched against system bank transactions

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bank_statement_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("bank_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("bank_accounts.id"), nullable=False),
        sa.Column("line_date", sa.Date, nullable=False),
        sa.Column("amount", sa.Numeric(18, 0), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column(
            "matched_transaction_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("bank_transactions.id"), nullable=True
        ),
    )
    op.create_index("ix_bank_statement_lines_bank_account_id", "bank_statement_lines", ["bank_account_id"])


def downgrade() -> None:
    op.drop_index("ix_bank_statement_lines_bank_account_id", "bank_statement_lines")
    op.drop_table("bank_statement_lines")
