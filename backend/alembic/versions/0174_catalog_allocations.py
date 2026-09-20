"""تخصیصِ بارِ ورودی به کاتالوگِ بازار

Revision ID: 0174
Revises: 0173

## چه چیزی اضافه می‌شود

جدولِ مستأجرمحورِ `marketplace_catalog_allocations`: «از این بار، این‌قدر در
کاتالوگ عرضه می‌شود».

## چرا لازم شد (§۶)

بارِ ۱۰۰۰تایی در انبار لزوماً یعنی ۱۰۰۰ تا برای فروشِ عمده نیست. مدیرِ پخش
ممکن است بخواهد فقط ۴۰۰ تایش را در کاتالوگ بگذارد و بقیه را برای مشتریِ
قدیمی، شعبه‌ی دیگر یا سفارشِ خاص نگه دارد. تا امروز چنین مرزی وجود نداشت:
هرچه در انبار بود، در کاتالوگ قابلِ سفارش بود.

## چرا در دفترِ **پخش‌کننده** و نه کنارِ بقیه‌ی جدول‌های بازار

جدول‌های `marketplace_*` سراسری‌اند و RLS ندارند، چون داده‌شان ذاتاً
میان‌مستأجری است (کاتالوگی که مستأجرِ دیگری می‌بیند). ولی این جدول **موجودی**
است، نه کاتالوگ: می‌گوید از انبارِ *من* چه‌قدر عرضه می‌شود. موجودی هرگز سراسری
نبوده و نباید بشود.

پس جدول مستأجرمحور است و `listing_id` **بی کلیدِ خارجی** نگه داشته می‌شود —
همان کاری که `MarketplaceOrder.distributor_sales_invoice_id` از سمتِ مقابل
می‌کند. FKِ مستأجری→سراسری معنا ندارد.

## چرا مقدارِ «رزروشده» و «باقی‌مانده» ستون ندارند

§۶ سه عدد خواسته (`allocated`، `reserved`، `remaining`) ولی فقط اولی **تصمیم**
است؛ دو تای دیگر از دفترِ رزرو و وضعیتِ بار مشتق می‌شوند. ستون‌کردنشان یعنی سه
عدد که باید همیشه با هم بخوانند و روزی نمی‌خوانند — همان چیزی که کلِ این
مجموعه مهاجرت برای رفعش نوشته شد.

## چرا `rls_disabled` لازم نیست

جدول تازه است و هیچ ردیفی ندارد؛ اسکنِ اعتبارسنجیِ کلیدِ خارجی روی جدولِ خالی
اصلاً اجرا نمی‌شود.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.tenancy import policy_name

revision: str = "0174"
down_revision: Union[str, None] = "0173"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enable_rls(table: str) -> None:
    conn = op.get_bind()
    conn.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"DROP POLICY IF EXISTS {policy_name(table)} ON {table}"))
    conn.execute(sa.text(
        f"CREATE POLICY {policy_name(table)} ON {table} "
        "USING (tenant_id = current_setting('app.tenant_id', true)::uuid) "
        "WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)"
    ))


def upgrade() -> None:
    op.create_table(
        "marketplace_catalog_allocations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        #: بی FK و عمداً: به جدولِ **سراسریِ** لیستینگ اشاره می‌کند.
        sa.Column("listing_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column(
            "batch_id",
            UUID(as_uuid=True),
            sa.ForeignKey("stock_batches.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("qty", sa.Numeric(18, 3), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("notes", sa.Text(), server_default="", nullable=False),
        sa.Column("created_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("qty > 0", name="ck_mp_catalog_alloc_qty"),
        #: یک بار در یک لیستینگ فقط یک تخصیص دارد — دو ردیف یعنی دو جواب برای
        #: «چه‌قدر از این بار عرضه شده».
        sa.UniqueConstraint("tenant_id", "listing_id", "batch_id", name="uq_mp_catalog_alloc"),
    )
    _enable_rls("marketplace_catalog_allocations")


def downgrade() -> None:
    op.drop_table("marketplace_catalog_allocations")
