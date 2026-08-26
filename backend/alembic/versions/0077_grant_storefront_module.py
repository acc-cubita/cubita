"""«اتصال فروشگاه» ماژولِ محدود شد — گرنت برای کسانی که از قبل استفاده می‌کنند

Revision ID: 0077
Revises: 0076

از این نسخه، `integration` در `RESTRICTED_MODULES` است: پیش‌فرض خاموش، و سوپرادمین
برای هر اکانت بازش می‌کند. بدونِ این مهاجرت، همان تغییر یعنی کسب‌وکارهایی که *همین
حالا* فروشگاه‌شان وصل است، با یک ارتقا منو و APIشان را از دست می‌دهند.

پس هرکس نشانه‌ی واقعیِ استفاده دارد، گرنت را می‌گیرد. «واقعی» یعنی کاری کرده که
فقط از سرِ راه‌اندازیِ جدی برمی‌آید:
  • `storefront_settings` با آدرسِ سایت یا اتصالِ فعال (اتصال به سایتِ بیرونی)
  • `storefronts` منتشرشده، یا با دامنه‌ی تنظیم‌شده، یا سایتی که واقعاً build شده
  • کالایی که روی فروشگاه لیست شده، یا سفارشی که از فروشگاه آمده

`publishable_key` عمداً نشانه *نیست*: با اولین بازکردنِ صفحه خودکار ساخته می‌شود، پس
یک نگاهِ گذرا هم اکانت را برای همیشه گرنت می‌کرد. بقیه دست‌نخورده می‌مانند (خاموش). برگشت‌پذیر نیست به‌معنای دقیق: در downgrade گرنتِ
`integration` برداشته می‌شود، چون در آن نسخه ماژول اصلاً محدود نیست و گرنت بی‌معناست.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.migration_utils import rls_disabled

revision: str = "0077"
down_revision: Union[str, None] = "0076"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: جدول‌های مستأجرمحوری که برای دیدنِ ردیفِ همه‌ی مستأجرها باید از RLS رد شویم.
TENANT_TABLES = ("storefront_settings", "storefronts", "item_storefront", "storefront_orders")

IN_USE = sa.text(
    """
    SELECT tenant_id FROM storefront_settings
     WHERE coalesce(base_url, '') <> '' OR is_active
    UNION
    SELECT tenant_id FROM storefronts
     WHERE coalesce(status, 'draft') <> 'draft'
        OR coalesce(allowed_origin, '') <> ''
        OR last_built_at IS NOT NULL
    UNION
    SELECT tenant_id FROM item_storefront
    UNION
    SELECT tenant_id FROM storefront_orders
    """
)


def upgrade() -> None:
    conn = op.get_bind()
    with rls_disabled(conn, TENANT_TABLES):
        tenant_ids = [row[0] for row in conn.execute(IN_USE)]

    for tenant_id in tenant_ids:
        # jsonb_set نه: ستون یک آرایه‌ی ساده است و افزودنِ بی‌تکرار با ||/distinct
        # خواناتر است. جداگانه به‌ازای هر مستأجر تا ترتیبِ کلیدها مرتب بماند.
        conn.execute(
            sa.text(
                """
                UPDATE tenants
                   SET granted_modules = (
                         SELECT coalesce(jsonb_agg(DISTINCT k ORDER BY k), '[]'::jsonb)
                           FROM jsonb_array_elements_text(
                                  coalesce(granted_modules, '[]'::jsonb) || '["integration"]'::jsonb
                                ) AS k
                       )
                 WHERE id = :tid
                """
            ),
            {"tid": tenant_id},
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE tenants
               SET granted_modules = (
                     SELECT coalesce(jsonb_agg(k ORDER BY k), '[]'::jsonb)
                       FROM jsonb_array_elements_text(coalesce(granted_modules, '[]'::jsonb)) AS k
                      WHERE k <> 'integration'
                   )
             WHERE granted_modules @> '["integration"]'::jsonb
            """
        )
    )
