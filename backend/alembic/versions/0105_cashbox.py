"""صندوق به‌عنوان موجودیت — نه یک صافی روی تراکنش‌ها

Revision ID: 0105
Revises: 0104

## چه چیزی نبود

`grep -rn "cashbox" backend/app/` تا پیش از این **صفر نتیجه** می‌داد. تنها تعریفِ
«صندوق» در کلِ بک‌اند این بود:

    if data.method == "cash":
        return get_account(db, cc.CASH)

یعنی صندوق *همان* حسابِ معین بود. سه پیامد داشت: بیش از یک صندوق ممکن نبود،
صندوق و حسابِ حسابداری یکی گرفته شده بودند، و هیچ‌کدام از مشخصاتِ صندوق (عنوان
دوم، تفصیلی، ارز، تاریخِ افتتاح، فعال/غیرفعال) جایی برای نشستن نداشت.

`BankAccount` و `PosTerminal` از قبل موجودیتِ عملیاتیِ درست‌اند و با یک کلید به
حسابداری وصل می‌شوند. صندوق تنها چیزی بود که این الگو را نگرفت.

## چرا مانده ستون ندارد

عمدی است. مانده‌ی صندوق از **دفتر** مشتق می‌شود — مانده‌ی `(gl_account, analytic)`.
ستونِ مانده یعنی منبعِ دومِ حقیقت که می‌تواند با تراز نخواند؛ همان چیزی که تحلیل
(§۱۳) و خودِ پروژه منعش می‌کنند. موجودیِ اولیه هم جدول ندارد: موجودیِ اولِ سالِ N
همان مانده‌ی مشتق در ابتدای آن سال است.

## چرا هیچ ردیفی نوشته نمی‌شود

قاعده‌ی پروژه: **هرگز داخلِ مهاجرت روی جدولِ RLS ردیف ننویس** — یا صفر ردیف
می‌نشیند یا روی مستأجرِ اشتباه.

و لازم هم نیست. صندوقِ پیش‌فرض `analytic_id = NULL` دارد و مانده‌اش ردیف‌های
بی‌تفصیلیِ حسابِ صندوق است — یعنی دقیقاً همان چیزی که داده‌ی امروز هست. پس
`cashbox_id` روی تراکنش‌های موجود `NULL` می‌ماند و هیچ ردیفِ مستقری دست نمی‌خورد.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.tenancy import policy_name

revision: str = "0105"
down_revision: Union[str, None] = "0104"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "cashboxes"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("name2", sa.String(200), server_default="", nullable=False),
        sa.Column(
            "analytic_id",
            UUID(as_uuid=True),
            sa.ForeignKey("analytic_accounts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("gl_account_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=True),
        sa.Column("currency_code", sa.String(3), server_default="IRR", nullable=False),
        sa.Column("opening_date", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    conn = op.get_bind()
    conn.execute(sa.text(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"DROP POLICY IF EXISTS {policy_name(TABLE)} ON {TABLE}"))
    conn.execute(
        sa.text(
            f"CREATE POLICY {policy_name(TABLE)} ON {TABLE} "
            "USING (tenant_id = current_setting('app.tenant_id', true)::uuid) "
            "WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)"
        )
    )

    # nullable عمدی: تراکنش‌های موجود به صندوقِ پیش‌فرض تعلق دارند و NULL همان را
    # می‌گوید، بدونِ آن‌که یک ردیف هم به‌روز شود.
    op.add_column(
        "treasury_transactions",
        sa.Column("cashbox_id", UUID(as_uuid=True), sa.ForeignKey("cashboxes.id"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("treasury_transactions", "cashbox_id")
    op.drop_table(TABLE)
