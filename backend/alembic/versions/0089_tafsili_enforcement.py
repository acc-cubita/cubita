"""سطحِ اجبارِ تفصیلی — انتخابِ کسب‌وکار، نه تصمیمِ ما

Revision ID: 0089
Revises: 0088

یک ستونِ اختیاری روی `tenants`. NULL = پیش‌فرضِ سرویس (`hybrid`) — همان الگویی که
`account_code_widths` و `enabled_modules` دارند، و همان دلیل: هیچ ردیفی backfill
نمی‌شود، پس هیچ کسب‌وکارِ موجودی رفتارش عوض نمی‌شود.

پیش‌تر «تفصیلیِ اجباری» فقط روی سندِ دستی اعمال می‌شد و ردیف‌های ماژول‌ها (فاکتور،
انبار، تولید) بی‌صدا از آن می‌گذشتند. آن مصالحه بود نه طراحی: کاربری که پرچمِ
«تفصیلی پذیر» را روشن می‌کند دقیقاً برای همان گزارشی این کار را می‌کند که ردیفِ
بی‌تفصیلیِ فاکتور سوراخش می‌کند.

حالا خودِ کسب‌وکار انتخاب می‌کند:

* `strict`   — اجباری همه‌جا. سندِ دستی و ردیفِ ماژول‌ها هر دو بدونِ تفصیلی رد
               می‌شوند. سخت‌گیرترین حالت و تنها حالتی که سوراخ را واقعاً می‌بندد،
               به قیمتِ اینکه یک تیکِ نادرست در چارت می‌تواند ثبتِ فاکتور را
               متوقف کند.
* `hybrid`   — **پیش‌فرض.** فقط سندِ دستی اجباری است؛ ردیفِ ماژول‌ها رد می‌شود ولی
               در گزارشِ «ردیف‌های بدونِ تفصیلی» دیده می‌شود.
* `floating` — هیچ‌چیز مسدود نمی‌شود؛ فقط گزارش. سازگار با تصمیمِ «گزارش، نه گارد»
               که برای ماهیتِ حساب گرفته شده بود.

**گزارش در هر سه حالت هست.** این نکته‌ی اصلیِ طراحی است: انتخابِ کاربر تعیین می‌کند
چه چیزی *مسدود* شود، نه چه چیزی *دیده* شود. حتی در سست‌ترین حالت هم سوراخ نامرئی
نمی‌ماند.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0089"
down_revision: Union[str, None] = "0088"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("tafsili_enforcement", sa.String(length=20), nullable=True))
    op.create_check_constraint(
        "ck_tenants_tafsili_enforcement",
        "tenants",
        "tafsili_enforcement IS NULL OR tafsili_enforcement IN ('strict', 'hybrid', 'floating')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_tenants_tafsili_enforcement", "tenants", type_="check")
    op.drop_column("tenants", "tafsili_enforcement")
