"""شخصی‌سازیِ پنل: صنف + ماژول‌های روشن/مجاز روی tenants

Revision ID: 0073
Revises: 0072

- `industry`: صنفِ کسب‌وکار (قالبِ پیش‌فرضِ ماژول‌ها).
- `enabled_modules`: ترجیحِ نمایشِ مالک (JSONB list). NULL = شخصی‌سازی‌نشده → همه‌ی
  ماژول‌های مجاز دیده می‌شوند (حساب‌های موجود بی‌تغییر).
- `granted_modules`: «حقِ دسترسی»ِ ماژول‌های محدود که سوپرادمین می‌دهد (مثلِ تولید).

Backfill (سازگاریِ عقب‌رو): «تولید» از این پس ماژولِ محدود است. حساب‌هایی که واقعاً از
آن استفاده کرده‌اند (BOM یا سفارشِ تولید دارند) نباید دسترسی‌شان قطع شود → همان‌ها
گرنتِ `manufacturing` می‌گیرند. بقیه (که استفاده نمی‌کردند) ماژولِ بلااستفاده را از
منو از دست می‌دهند، که همان تمیزکاریِ موردِنظر است.

نکته‌ی RLS: `tenants` سراسری و بی‌RLS است، ولی زیرپرس‌وجو از `boms`/`production_orders`
(تحتِ FORCE RLS) است؛ مثلِ 0072 موقتاً RLSشان غیرفعال می‌شود تا همه‌ی مستأجرها دیده شوند.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.migration_utils import rls_disabled

revision: str = "0073"
down_revision: Union[str, None] = "0072"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("industry", sa.String(30), server_default="general", nullable=False),
    )
    op.add_column("tenants", sa.Column("enabled_modules", postgresql.JSONB(), nullable=True))
    op.add_column(
        "tenants",
        sa.Column("granted_modules", postgresql.JSONB(), server_default="[]", nullable=False),
    )

    conn = op.get_bind()
    with rls_disabled(conn, ["boms", "production_orders"]):
        conn.execute(
            sa.text(
                """
                UPDATE tenants SET granted_modules = '["manufacturing"]'::jsonb
                WHERE id IN (
                    SELECT tenant_id FROM boms
                    UNION
                    SELECT tenant_id FROM production_orders
                )
                """
            )
        )


def downgrade() -> None:
    op.drop_column("tenants", "granted_modules")
    op.drop_column("tenants", "enabled_modules")
    op.drop_column("tenants", "industry")
