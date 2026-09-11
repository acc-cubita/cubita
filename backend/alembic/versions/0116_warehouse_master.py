"""انبار سه ستون داشت: کد، نام، فعال

Revision ID: 0116
Revises: 0115

## چه چیزی نبود

`Warehouse` از روزِ اول درست طراحی شده بود — **هیچ ستونِ موجودی ندارد** و مانده
همیشه از `stock_ledger` مشتق می‌شود. آن اصلِ اصلیِ این فصل از قبل رعایت شده و
اینجا دست نمی‌خورد.

ولی جز آن سه ستون چیزی نداشت:

* **عنوانِ دوم** نبود، با آن‌که طرف‌حساب و حسابِ بانکی و صندوق همه دارند.
* **مسئول، تلفن و آدرس** نبود. انبارِ شعبه یا انبارِ برون‌سپاری‌شده اطلاعاتِ
  تماسِ خودش را دارد و جایی برای نشستن نداشت.
* **معینِ انبار نبود.** همه‌ی انبارها — مرکزی، مواد اولیه، ضایعات — به *یک*
  حسابِ موجودیِ کالا می‌نشستند، چون `cc.INVENTORY` سراسری است. شرکتی که
  می‌خواهد موجودیِ ضایعات را جدا از موجودیِ مواد اولیه ببیند، راهی نداشت.

## معینِ انبار — چرا اختیاری

`NULL` یعنی «همان حسابِ پیش‌فرضِ نقشِ `inventory`» — یعنی **دقیقاً رفتارِ
امروز**. پس این مهاجرت هیچ مستأجری را تکان نمی‌دهد؛ فقط کسی که صریحاً نگاشت
بگذارد رفتارِ تازه می‌گیرد. §۱۳ هم همین را می‌گوید: این فیلد در فرم هم‌ردیفِ
کد و عنوان اجباری نیست.

و §۱۲: تعریفِ انبار **حسابِ تازه نمی‌سازد**. فقط به حسابِ موجودِ چارت اشاره
می‌کند.

قیدِ یکتایی روی `gl_account_id` گذاشته **نمی‌شود**: §۱۴ صریحاً باز می‌گذارد که
چند انبار به یک حساب اشاره کنند (سیاستِ تجمیعی) یا هرکدام به حسابِ خودش.

## هیچ داده‌ای نوشته نمی‌شود

ستون‌ها با `server_default=''` می‌آیند و `gl_account_id` خالی می‌ماند. هیچ
`UPDATE`ی لازم نیست چون خالی‌بودن همان حقیقت است: کسی تا امروز این اطلاعات را
وارد نکرده بود.

**و هیچ سندِ حسابداری‌ای هم اینجا زده نمی‌شود** (§۳۲): تعریف و تنظیمِ انبار
رویدادِ مالی نیست.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0116"
down_revision: Union[str, None] = "0115"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "warehouses"

TEXT_COLUMNS = (
    ("name2", sa.String(200)),
    ("responsible", sa.String(200)),
    ("phone", sa.String(30)),
    ("address", sa.Text()),
    ("address2", sa.Text()),
)


def upgrade() -> None:
    for name, type_ in TEXT_COLUMNS:
        op.add_column(TABLE, sa.Column(name, type_, server_default="", nullable=False))

    op.add_column(
        TABLE,
        sa.Column(
            "gl_account_id",
            UUID(as_uuid=True),
            sa.ForeignKey("accounts.id"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(TABLE, "gl_account_id")
    for name, _ in reversed(TEXT_COLUMNS):
        op.drop_column(TABLE, name)
