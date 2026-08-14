"""initial schema: roles, users, chart of accounts, journal entries/lines

Revision ID: 0001
Revises:
Create Date: 2026-07-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("key", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("permissions", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.UniqueConstraint("key"),
    )
    op.create_index("ix_roles_key", "roles", ["key"])

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(150), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("hashed_password", sa.String(200), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("roles.id"), nullable=False),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("is_group", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=True),
        sa.UniqueConstraint("code"),
        sa.CheckConstraint(
            "type IN ('asset','liability','equity','income','expense')", name="ck_accounts_type"
        ),
    )
    op.create_index("ix_accounts_code", "accounts", ["code"])

    op.execute("CREATE SEQUENCE journal_entry_number_seq START 1")

    op.create_table(
        "journal_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("number", sa.Integer, nullable=True),
        sa.Column("entry_date", sa.Date, nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("source_type", sa.String(50), nullable=False, server_default="manual"),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.UniqueConstraint("number"),
    )
    op.create_index("ix_journal_entries_number", "journal_entries", ["number"])

    op.create_table(
        "journal_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("journal_entries.id"), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("debit", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("credit", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.CheckConstraint("debit >= 0 AND credit >= 0", name="ck_journal_lines_nonnegative"),
        sa.CheckConstraint("NOT (debit > 0 AND credit > 0)", name="ck_journal_lines_one_sided"),
    )


def downgrade() -> None:
    op.drop_table("journal_lines")
    op.drop_table("journal_entries")
    op.execute("DROP SEQUENCE journal_entry_number_seq")
    op.drop_table("accounts")
    op.drop_table("users")
    op.drop_table("roles")
