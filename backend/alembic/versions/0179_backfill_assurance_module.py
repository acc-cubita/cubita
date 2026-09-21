"""بک‌فیلِ ماژولِ «حسابرسی» برای مستأجرهای شخصی‌سازی‌شده

Revision ID: 0179
Revises: 0178

`assurance` در `OPTIONAL_MODULES` هست، ولی مستأجری که پیش از وجودِ این ماژول
پنلش را شخصی‌سازی کرده — یعنی `tenants.enabled_modules` دیگر `NULL` نیست —
عضوِ تازه‌ی این فهرست را **هرگز** نمی‌بیند. همان شکافی که مهاجرتِ ۰۱۶۰ برای
پیمانکاری بست، و همان‌جا هم اولین نشانه‌اش این بود که خودِ حسابِ مالک ماژول را
نداشت.

فقط ماژولِ *درخواست* بک‌فیل می‌شود. `assurance_work` اصلاً در هیچ ستونی ذخیره
نمی‌شود (ماژولِ مشتق است) و از خودِ قرارداد می‌آید.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0179"
down_revision: Union[str, None] = "0178"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    #: `tenants` خودش مرزِ مستأجر است و RLS ندارد، پس `rls_disabled` لازم نیست.
    conn.execute(
        sa.text(
            """
            UPDATE tenants
            SET enabled_modules = enabled_modules || '["assurance"]'::jsonb
            WHERE enabled_modules IS NOT NULL
              AND NOT (enabled_modules @> '["assurance"]'::jsonb)
            """
        )
    )


def downgrade() -> None:
    #: برگرداندنِ امن ناممکن است — نمی‌شود فهمید کدام مستأجر خودش «حسابرسی» را
    #: روشن کرده بوده و کدام از این بک‌فیل گرفته.
    pass
