"""پروفایلِ حسابداریِ نوعِ فروش: حسابِ برگشت، و هویتِ کامل.

Revision ID: 0146
Revises: 0145

**پروب.** یک نوعِ فروش با حسابِ کالا (۴۱۹۱) و حسابِ خدمت (۴۱۹۲) ساختم و یک
فاکتورِ مخلوط (کالا ۱٬۰۰۰ + خدمت ۵۰۰) زدم:

    ۱۱۰۴ بدهکار ۱٬۵۰۰ · ۴۱۹۱ بستانکار ۱٬۰۰۰ · ۴۱۹۲ بستانکار ۵۰۰

**موتور از قبل درست کار می‌کرد.** پنج اسلاتِ حساب روی `sale_types` هست و
`issue_sales_invoice_journal` کالا و خدمت را تفکیک می‌کند. چیزی که نبود، دَرِ
ورودی بود: تایپِ `SaleType` در رابط این پنج فیلد را نداشت و `updateSaleType`
هیچ مصرف‌کننده‌ای نداشت — پس هر پنج ستون در هر کسب‌وکاری تا ابد `NULL` می‌ماندند.

**و پروبِ دوم بدتر بود:** `PATCH` با همان بدنه‌ای که رابطِ امروز می‌سازد ۲۰۰
برمی‌گرداند و **هر پنج حساب را `NULL` می‌کرد** — چون مسیر «همه‌ی فیلدها را
بنویس» بود. همان شکلِ باگِ `clear()`ِ لیستِ قیمت، فقط هنوز خفته.

## این مهاجرت چه اضافه می‌کند

    goods_return_account_id   ← حسابِ برگشتِ فروشِ کالا
    service_return_account_id ← حسابِ برگشتِ فروشِ خدمات
    code                      ← کدِ مِستر (یکتا در هر کسب‌وکار)
    title2                    ← عنوانِ دوم — همان الگوی `sales_return_reasons`

برگشت از فروش تا امروز **همه‌چیز** را به یک حسابِ سراسری می‌برد: کالا و خدمت
یکی، و برای هر نوعِ فروش یکی. حالا اگر تنظیم شده باشد تفکیک می‌شود، و اگر نه
همان حسابِ سراسری می‌ماند — یعنی رفتارِ دیروز پیش‌فرض است.

**بدونِ backfill.** `code` روی ردیف‌های موجود `NULL` می‌ماند و یعنی «کد ندارد»،
نه یک کدِ ساختگی. ایندکسِ یکتا جزئی است (`WHERE code IS NOT NULL`) تا چند
ردیفِ بی‌کد کنارِ هم زندگی کنند.

**FK زیرِ RLS.** دو ستونِ حساب کلیدِ خارجی‌اند و اعتبارسنجیِ FK یک پرس‌وجوی
واقعی است که RLS رویش اعمال می‌شود — روی PG 14 با
`invalid input syntax for type uuid: ""` می‌ترکد. `app/migration_utils.py`.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.migration_utils import rls_disabled

revision: str = "0146"
down_revision: Union[str, None] = "0145"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "sale_types"
RETURN_ACCOUNTS = ("goods_return_account_id", "service_return_account_id")


def upgrade() -> None:
    op.add_column(TABLE, sa.Column("code", sa.String(20), nullable=True))
    op.add_column(
        TABLE, sa.Column("title2", sa.String(80), nullable=False, server_default="")
    )
    #: اعتبارسنجیِ کلیدِ خارجی مشمولِ RLS است و روی PG 14 می‌ترکد —
    #: `app/migration_utils.py`. جدولِ `accounts` هم باید باز شود چون
    #: پرس‌وجوی اعتبارسنجی هر دو طرف را می‌خوانَد.
    with rls_disabled(op.get_bind(), (TABLE, "accounts")):
        for name in RETURN_ACCOUNTS:
            op.add_column(
                TABLE,
                sa.Column(
                    name,
                    UUID(as_uuid=True),
                    sa.ForeignKey("accounts.id"),
                    nullable=True,
                ),
            )
    #: جزئی، وگرنه ردیف‌های بی‌کدِ موجود همدیگر را مسدود می‌کردند.
    op.create_index(
        "uq_sale_types_tenant_code",
        TABLE,
        ["tenant_id", "code"],
        unique=True,
        postgresql_where=sa.text("code IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_sale_types_tenant_code", table_name=TABLE)
    for name in reversed(RETURN_ACCOUNTS):
        op.drop_column(TABLE, name)
    op.drop_column(TABLE, "title2")
    op.drop_column(TABLE, "code")
