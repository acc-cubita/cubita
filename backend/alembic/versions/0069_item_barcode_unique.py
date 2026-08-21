"""یکتاییِ بارکدِ کالا در سطحِ مستأجر — ایندکسِ جزئیِ uq_items_tenant_barcode

Revision ID: 0069
Revises: 0068

تا امروز بارکد فقط ایندکسِ ساده داشت، پس دو کالا می‌توانستند بارکدِ یکسان بگیرند و
اسکن مبهم می‌شد («آخرین کالای ذخیره‌شده» را می‌آورد). این مهاجرت بارکد را در سطحِ
مستأجر یکتا می‌کند (فقط ردیف‌های دارای بارکد؛ چند کالای بی‌بارکد مجاز می‌مانند).

**پاک‌سازیِ داده‌ی موجود پیش از ایجادِ ایندکس:** اگر همین حالا بارکدِ تکراری وجود
داشته باشد، ایجادِ ایندکسِ یکتا شکست می‌خورد. پس ابتدا در هر گروهِ (tenant_id,
barcode)ِ تکراری، بارکد را فقط روی **جدیدترین** کالا (بیشترین created_at، سپس id)
نگه می‌داریم و بقیه را NULL می‌کنیم. هیچ کالایی حذف/ادغام نمی‌شود؛ فقط بارکدِ
بازنده‌ها خالی می‌شود تا کاربر دوباره تخصیص دهد.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.migration_utils import rls_disabled

revision: str = "0069"
down_revision: Union[str, None] = "0068"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ۱) خالی‌کردنِ بارکدِ تکراری‌ها (نگه‌داشتن روی جدیدترین کالای هر گروه)
    #
    # items تحتِ FORCE RLS است و این migration بدونِ زمینه‌ی مستأجر اجرا می‌شود، پس یک
    # UPDATEِ خام هیچ ردیفی را نمی‌بیند (۰ ردیف) — de-dup بی‌اثر می‌شد و بعد CREATE UNIQUE
    # INDEX (که DDL است و همه‌ی ردیف‌ها را می‌بیند) روی بارکدهای تکراریِ واقعی شکست می‌خورد.
    # پس مثلِ 0039/0043/0072 موقتاً RLS را برمی‌داریم تا پاک‌سازی همه‌ی مستأجرها را بگیرد.
    conn = op.get_bind()
    with rls_disabled(conn, ["items"]):
        conn.execute(
            sa.text(
                """
                WITH ranked AS (
                    SELECT id,
                           ROW_NUMBER() OVER (
                               PARTITION BY tenant_id, barcode
                               ORDER BY created_at DESC, id DESC
                           ) AS rn
                    FROM items
                    WHERE barcode IS NOT NULL
                )
                UPDATE items
                SET barcode = NULL
                FROM ranked
                WHERE items.id = ranked.id AND ranked.rn > 1
                """
            )
        )
    # ۲) ایندکسِ یکتای جزئی
    op.create_index(
        "uq_items_tenant_barcode",
        "items",
        ["tenant_id", "barcode"],
        unique=True,
        postgresql_where=sa.text("barcode IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_items_tenant_barcode", table_name="items")
