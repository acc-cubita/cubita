"""هویتِ ستادِ پلتفرم و دفترِ ردِ کارهای ستاد

Revision ID: 0180
Revises: 0179

مدیریتِ پلتفرم از اپِ مشتری به `admin.cubita.ir` کوچ می‌کند. تا امروز
«سوپرادمین» فقط یک ایمیل در متغیرِ محیطی بود و — مهم‌تر — هیچ‌کس بدونِ **عضویتِ
فعال در یک کسب‌وکار** اصلاً توکن نمی‌گرفت. این مهاجرت آن گره را باز می‌کند.

دو کار:

۱. `platform_admins` (از مهاجرتِ ۰۰۱۵ وجود داشت و هیچ‌جا استفاده نشده بود) نقش و
   مجوز می‌گیرد. اعتبارنامه عمداً اینجا نمی‌آید و روی `users` می‌ماند — یک مسیرِ
   هش، یک سازوکارِ ابطال (`token_version`).
۲. `staff_audit_log` ساخته می‌شود. تا امروز حذفِ برگشت‌ناپذیرِ یک مشتری، تعلیق و
   تغییرِ رمزِ مالک **صفر رد** می‌گذاشتند: `audit_log` مستأجرمحور است و هیچ مدلِ
   پلتفرمی‌ای در `audited_models()` نیست.

**سیدِ ضدِقفل:** برای هر ایمیلِ `SUPER_ADMIN_EMAILS` یک ردیفِ `owner` و برای هر
`PLATFORM_ADMIN_EMAILS` یک ردیفِ `finance` ساخته می‌شود. بدونِ این، لحظه‌ی بعد از
استقرار هیچ‌کس نمی‌توانست وارد اپِ ستاد شود — و راهِ برگشتی هم نبود.

هر دو جدول در `GLOBAL_TABLES`اند و RLS ندارند، پس این سید به `rls_disabled` نیاز
ندارد (برخلافِ سیدِ نقشِ حسابرس در ۰۱۷۸ که روی `roles`ِ RLS‌دار می‌نشست).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.audit import append_only_statements
from app.config import get_settings

revision: str = "0180"
down_revision: Union[str, None] = "0179"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "staff_audit_log"
GUARD_TRIGGER = f"{TABLE}_no_update_delete"


def _emails(raw: str) -> list[str]:
    return [e.strip().lower() for e in (raw or "").split(",") if e.strip()]


def upgrade() -> None:
    op.add_column(
        "platform_admins",
        sa.Column("role", sa.String(length=20), nullable=False, server_default="support"),
    )
    op.add_column("platform_admins", sa.Column("permissions", postgresql.JSONB, nullable=True))
    op.add_column(
        "platform_admins", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "platform_admins", sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "platform_admins",
        sa.Column(
            "created_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    op.create_table(
        TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        # کاربر ممکن است پاک شود ولی ردِ کارهایش باید بماند.
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("actor_email", sa.String(length=255), nullable=False),
        sa.Column("actor_role", sa.String(length=20), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("target_type", sa.String(length=40), nullable=True),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("target_label", sa.String(length=200), nullable=True),
        # **عمداً بدونِ ForeignKey به tenants.** کلیدِ خارجی ردِ حذفِ مشتری را همراهِ
        # خودِ مشتری cascade می‌کرد، و آن مهم‌ترین ردیفِ این جدول است.
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("details", postgresql.JSONB, nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("via", sa.String(length=10), nullable=False, server_default="staff"),
    )
    op.create_index(f"ix_{TABLE}_at", TABLE, ["at"])
    op.create_index(f"ix_{TABLE}_action", TABLE, ["action"])
    op.create_index(f"ix_{TABLE}_tenant_id", TABLE, ["tenant_id"])

    conn = op.get_bind()
    # همان DDLای که تست‌ها هم استفاده می‌کنند — کپی‌کردنش یعنی دیر یا زود نسخه‌ی
    # تست و نسخه‌ی production از هم جدا می‌افتند.
    for stmt in append_only_statements(TABLE):
        conn.execute(sa.text(stmt))

    settings = get_settings()
    seeds = [(e, "owner") for e in _emails(settings.super_admin_emails)]
    seeds += [
        (e, "finance")
        for e in _emails(settings.platform_admin_emails)
        if e not in {s[0] for s in seeds}
    ]
    for email, role in seeds:
        conn.execute(
            sa.text(
                "INSERT INTO platform_admins (id, user_id, is_active, role, created_at, updated_at) "
                "SELECT gen_random_uuid(), u.id, true, :role, now(), now() FROM users u "
                "WHERE lower(u.email) = :email "
                "ON CONFLICT (user_id) DO UPDATE SET role = EXCLUDED.role, is_active = true"
            ),
            {"role": role, "email": email},
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(f"DROP TRIGGER IF EXISTS {GUARD_TRIGGER} ON {TABLE}"))
    # تابعِ گارد مشترک است (audit_log و check_events هم از آن استفاده می‌کنند)، پس
    # اینجا حذف نمی‌شود — فقط تریگرِ همین جدول.
    op.drop_index(f"ix_{TABLE}_tenant_id", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_action", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_at", table_name=TABLE)
    op.drop_table(TABLE)

    op.drop_column("platform_admins", "created_by_id")
    op.drop_column("platform_admins", "disabled_at")
    op.drop_column("platform_admins", "last_login_at")
    op.drop_column("platform_admins", "permissions")
    op.drop_column("platform_admins", "role")
