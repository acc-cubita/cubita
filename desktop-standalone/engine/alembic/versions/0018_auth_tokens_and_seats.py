"""توکن‌های یک‌بارمصرف، سقف کاربران، و مهر تغییر رمز

Revision ID: 0018
Revises: 0017

سه تغییر که با هم یک قابلیت می‌سازند: مدیریت کاربران کسب‌وکار و بازیابی رمز.

`auth_tokens` عمداً RLS ندارد و در GLOBAL_TABLES است: بازیابی رمز و پذیرش دعوت هر
دو *قبل از* احراز هویت اجرا می‌شوند، پس در لحظه‌ی مصرف هیچ زمینه‌ی مستأجری وجود
ندارد و سیاست، هر لینک معتبری را هم «نامعتبر» نشان می‌داد.

`tenants.max_users` عمداً nullable است و NULL یعنی نامحدود — یعنی مستأجرهای موجود
هیچ سقف تازه‌ای نمی‌گیرند. این تصمیم آگاهانه است: اعمال سقف روی مشتری‌ای که از قبل
کار می‌کرده باید تصمیم جداگانه‌ای باشد، نه اثر جانبیِ یک مهاجرت.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "auth_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("purpose", sa.String(length=30), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    # یکتا روی hash: دو ردیف با یک توکن نباید ممکن باشد، و جست‌وجو در هر مصرف از
    # همین ایندکس می‌آید.
    op.create_index("ix_auth_tokens_token_hash", "auth_tokens", ["token_hash"], unique=True)
    op.create_index("ix_auth_tokens_user_id", "auth_tokens", ["user_id"])
    op.create_index("ix_auth_tokens_tenant_id", "auth_tokens", ["tenant_id"])
    op.create_index("ix_auth_tokens_purpose", "auth_tokens", ["purpose"])

    op.add_column("tenants", sa.Column("max_users", sa.Integer(), nullable=True))

    # نسل توکن از صفر شروع می‌شود و توکن‌های قدیمی که این ادعا را ندارند هم صفر
    # خوانده می‌شوند، پس استقرار هیچ نشست بازی را نمی‌کشد. محافظت از همان لحظه
    # برقرار است: اولین تغییر رمز نسل را به ۱ می‌برد و توکن‌های قبلی باطل می‌شوند.
    op.add_column(
        "users", sa.Column("token_version", sa.Integer(), nullable=False, server_default="0")
    )


def downgrade() -> None:
    op.drop_column("users", "token_version")
    op.drop_column("tenants", "max_users")
    op.drop_index("ix_auth_tokens_purpose", table_name="auth_tokens")
    op.drop_index("ix_auth_tokens_tenant_id", table_name="auth_tokens")
    op.drop_index("ix_auth_tokens_user_id", table_name="auth_tokens")
    op.drop_index("ix_auth_tokens_token_hash", table_name="auth_tokens")
    op.drop_table("auth_tokens")
