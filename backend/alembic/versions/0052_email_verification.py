"""تأیید ایمیل هنگام ثبت‌نام (verify-before-create)

Revision ID: 0052
Revises: 0051

- جدولِ `email_verification_codes` — کدِ تأییدِ ایمیل *پیش از* ساختِ حساب. کلیدش خودِ
  ایمیل است نه user_id (هنوز کاربری نیست)، پس در `auth_tokens` نمی‌گنجید. سراسری و
  بدونِ RLS (مثلِ auth_tokens؛ پیش از احراز هویت و بی‌زمینه‌ی مستأجر اجرا می‌شود).
- `users.email_verified_at` — لحظه‌ی تأییدِ ایمیل؛ NULL یعنی تأییدنشده (حساب‌های قدیمی/دستی).
  ثبت‌نامِ خودسرویسِ تازه همیشه پرش می‌کند چون کد قبل از ساختِ حساب تأیید می‌شود.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0052"
down_revision: Union[str, None] = "0051"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "email_verification_codes",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index(op.f("ix_email_verification_codes_email"), "email_verification_codes", ["email"])
    op.create_index(op.f("ix_email_verification_codes_code_hash"), "email_verification_codes", ["code_hash"])

    op.add_column(
        "users",
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "email_verified_at")
    op.drop_index(op.f("ix_email_verification_codes_code_hash"), table_name="email_verification_codes")
    op.drop_index(op.f("ix_email_verification_codes_email"), table_name="email_verification_codes")
    op.drop_table("email_verification_codes")
