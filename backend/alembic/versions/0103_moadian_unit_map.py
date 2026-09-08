"""نگاشتِ واحدِ سنجش برای سامانه‌ی مؤدیان

Revision ID: 0103
Revises: 0102

## باگی که این می‌بندد

`build_invoice_packet` کدِ واحدِ اندازه‌گیری را **ثابت** می‌فرستاد:

    "mu": "164",  # واحد اندازه‌گیری (عدد)

یعنی هر ردیفِ هر صورتحساب — چه کیلوگرم، چه متر، چه لیتر، چه کارتن — به‌عنوان
«عدد» به سازمانِ امور مالیاتی اظهار می‌شد. فروشِ ۵۰ کیلوگرم می‌شد ۵۰ عدد.

این «قابلیتِ نداشته» نبود؛ **دادهٔ نادرست بود که ارسال می‌شد.**

## چرا جدول و نه ستون روی کالا

واحد در کوبیتا موجودیت نیست — متنِ آزادِ `Item.unit` است. اگر کد را روی خودِ کالا
می‌گذاشتیم، صد کالای «کیلوگرم» باید صد بار جدا تنظیم می‌شدند و اولین اشتباهِ
تایپی یک کدِ متفاوت به سامانه می‌فرستاد. نگاشتِ `(نوشتارِ واحد → کد)` یک بار
تعریف می‌شود و همه‌ی کالاهای همان واحد از آن استفاده می‌کنند.

## هیچ داده‌ای seed نمی‌شود

قاعده‌ی پروژه: **هرگز داخلِ مهاجرت روی جدولِ RLS ردیف ننویس** — یا صفر ردیف
می‌نشیند یا روی مستأجرِ اشتباه. به‌جایش «عدد → ۱۶۴» به‌صورتِ `BUILTIN_UNIT_CODES`
در کد است، پس رفتارِ امروز برای «عدد» بدونِ هیچ داده‌ای دست‌نخورده می‌ماند و
بقیه‌ی کدها را کاربر از روی جدولِ رسمی وارد می‌کند.

## RLS

جدولِ تازه در این پروژه یعنی RLSِ تازه. بدونِ سیاست، نگاشتِ یک کسب‌وکار برای
بقیه هم دیده می‌شود — و این جدول به بسته‌ای که با نامِ همان کسب‌وکار امضا و ارسال
می‌شود وصل است.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.tenancy import policy_name

revision: str = "0103"
down_revision: Union[str, None] = "0102"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "moadian_unit_maps"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("code", sa.String(10), nullable=False),
        sa.Column("created_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("tenant_id", "unit", name="uq_moadian_unit_maps_tenant_unit"),
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


def downgrade() -> None:
    op.drop_table(TABLE)
