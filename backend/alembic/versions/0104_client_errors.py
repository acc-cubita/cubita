"""گزارشِ کرشِ کلاینت‌ها

Revision ID: 0104
Revises: 0103

اپِ موبایل روی کافه‌بازار زنده بود و هیچ راهی نداشتیم بفهمیم دستِ کاربرِ واقعی
می‌شکند یا نه. این جدول مقصدِ گزارش‌هایی است که خودِ اپ می‌فرستد.

**چرا سراسری و بدونِ RLS:** کرش ممکن است پیش از ورود بیفتد — موقعِ راه‌اندازی، در
صفحه‌ی ورود، یا وقتی رفرش‌توکن باطل شده. آن لحظه هیچ زمینه‌ی مستأجری وجود ندارد.
با RLS دقیقاً همان گزارش‌هایی که بیشترین ارزش را دارند هرگز نوشته نمی‌شدند. جدول
در `GLOBAL_TABLES` ثبت شده تا `test_migration_drift` هم آن را استثنای عمدی بداند،
نه جدولی که یادمان رفته محافظت کنیم.

**چرا `client_id` یکتاست:** دستگاه صفِ گزارش‌ها را تا وقتی پاسخِ موفق نگیرد نگه
می‌دارد و دوباره می‌فرستد — که رفتارِ درستی است. بدونِ قیدِ یکتا، یک قطعیِ شبکه
یعنی چند رکوردِ تکراری از یک کرش.

**چرا ۰۱۰۴ و نه ۰۱۰۰:** این مهاجرت اولش ۰۱۰۰ بود و همزمان روی شاخه‌ی دیگری
هم ۰۱۰۰ ساخته شد. Alembic دو شناسه‌ی یکسان را **خطا نمی‌گیرد** — فقط
`UserWarning: Revision 0100 is present more than once` می‌دهد، یکی را بی‌صدا
دور می‌ریزد و دو head می‌سازد. یعنی این جدول هرگز ساخته نمی‌شد و اندپوینتِ
گزارشِ کرش روی سرور خطا می‌داد، بی‌آنکه استقرار چیزی بگوید. پیش از ساختِ
مهاجرت `alembic heads` را ببین (قاعده‌ی «مهاجرتِ همزمان» در CLAUDE.md).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0104"
down_revision: Union[str, None] = "0103"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "client_errors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("client_id", sa.String(64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("fatal", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("stack", sa.Text(), nullable=True),
        sa.Column("screen", sa.String(100), nullable=True),
        sa.Column("app_version", sa.String(30), nullable=True),
        sa.Column("platform", sa.String(20), nullable=True),
        sa.Column("os_version", sa.String(30), nullable=True),
        sa.Column("device", sa.String(100), nullable=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("uq_client_errors_client_id", "client_errors", ["client_id"], unique=True)
    op.create_index("ix_client_errors_fatal", "client_errors", ["fatal"])
    op.create_index("ix_client_errors_screen", "client_errors", ["screen"])
    op.create_index("ix_client_errors_app_version", "client_errors", ["app_version"])
    # پرس‌وجوی همیشگی «تازه‌ترین‌ها اول» است؛ بدونِ این، هر بار کلِ جدول اسکن می‌شود.
    op.create_index("ix_client_errors_received_at", "client_errors", [sa.text("received_at DESC")])


def downgrade() -> None:
    op.drop_index("ix_client_errors_received_at", table_name="client_errors")
    op.drop_index("ix_client_errors_app_version", table_name="client_errors")
    op.drop_index("ix_client_errors_screen", table_name="client_errors")
    op.drop_index("ix_client_errors_fatal", table_name="client_errors")
    op.drop_index("uq_client_errors_client_id", table_name="client_errors")
    op.drop_table("client_errors")
