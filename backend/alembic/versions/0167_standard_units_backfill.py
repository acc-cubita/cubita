"""فهرستِ واحدهای شمارش از ۱۹ به ۳۹۳ رسید — و کسب‌وکارهای موجود هم باید بگیرندش

Revision ID: 0167
Revises: 0164

## چه چیزی کم بود

مهاجرتِ ۰۱۱۸ واحدها را **از خودِ داده** ساخت: «هر نوشتاری که امروز روی کالاهای
یک کسب‌وکار هست یک واحد می‌شود». تصمیمِ درستی بود — هیچ کالایی واحدش عوض نشد و
هیچ نگاشتِ مؤدیانی نشکست. ولی نتیجه‌اش این شد که کسب‌وکارِ واقعی فقط **سه** واحد
داشت: همان سه‌تایی که تصادفاً روی کالاهایش نوشته شده بود.

فهرستِ استاندارد هم فقط به کسب‌وکارِ **بی‌کالا** داده می‌شد (`AND NOT EXISTS
(SELECT 1 FROM items ...)`)، پس کسی که یک کالا داشت هیچ‌وقت آن ۱۹تا را هم ندید.

## چه می‌شود

`STANDARD_UNITS` در `seed.py` به ۳۹۳ واحد رسید، و این مهاجرت همان را به **هر**
کسب‌وکاری می‌دهد که نداردش — بی‌شرطِ داشتنِ کالا.

`NOT EXISTS` یعنی واحدهای موجودِ هر کسب‌وکار دست نمی‌خورند: نه تکراری ساخته
می‌شود و نه چیزی بازنویسی. `uq_units_of_measure_tenant_name` هم پشتِ همین است.

## چرا `rls_disabled`

`units_of_measure` و `tenants` هر دو FORCE RLS دارند و سیاستشان
`current_setting('app.tenant_id')` را می‌خواند — که وسطِ مهاجرت وجود ندارد.
بدونِ این گارد، `INSERT ... SELECT FROM tenants` **صفر ردیف** می‌بیند و مهاجرت
با موفقیت تمام می‌شود بی‌آنکه چیزی نوشته باشد. این دقیقاً همان تله‌ای است که
یک بار سرِ ۰۱۶۴ افتاد.

## برگشت

فقط واحدهایی که **هیچ کالایی رویشان ننشسته** برداشته می‌شوند، و فقط آن‌هایی که
در فهرستِ استاندارد بودند. واحدی که کاربر خودش ساخته یا کالایی به آن وصل است
می‌ماند — برگشتِ یک مهاجرتِ داده‌ای نباید دادهٔ کاربر را ببرد.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.migration_utils import rls_disabled
from app.seed import STANDARD_UNITS

revision: str = "0167"
down_revision: Union[str, None] = "0164"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "units_of_measure"

#: SQL بیرونِ تابع است تا تست **همین** را اجرا کند، نه رونوشتش. اگر این عوض شود
#: و خراب شود، تست می‌شکند — الگوی `0158`.
_BACKFILL = f"""
    INSERT INTO {TABLE} (id, tenant_id, name, name2, is_active)
    SELECT gen_random_uuid(), t.id, u.name, '', true
      FROM tenants t
     CROSS JOIN unnest(CAST(:names AS text[])) AS u(name)
     WHERE NOT EXISTS (
           SELECT 1 FROM {TABLE} x WHERE x.tenant_id = t.id AND x.name = u.name
     )
"""


def upgrade() -> None:
    conn = op.get_bind()
    with rls_disabled(conn, [TABLE, "tenants", "items"]):
        conn.execute(sa.text(_BACKFILL), {"names": list(STANDARD_UNITS)})


def downgrade() -> None:
    conn = op.get_bind()
    with rls_disabled(conn, [TABLE, "items"]):
        conn.execute(
            sa.text(
                f"""
                DELETE FROM {TABLE} u
                 WHERE u.name = ANY(CAST(:names AS text[]))
                   AND NOT EXISTS (
                       SELECT 1 FROM items i
                        WHERE i.primary_unit_id = u.id OR i.secondary_unit_id = u.id
                   )
                """
            ),
            {"names": list(STANDARD_UNITS)},
        )
