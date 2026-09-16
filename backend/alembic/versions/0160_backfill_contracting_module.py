"""بک‌فیلِ ماژولِ «پیمانکاری» برای مستأجرهای شخصی‌سازی‌شده.

`contracting` در `OPTIONAL_MODULES` هست، ولی مستأجری که پیش از وجودِ این ماژول
پنلش را شخصی‌سازی کرده (یعنی `tenants.enabled_modules` دیگر `NULL` نیست و یک
آرایه‌ی مشخص است) هرگز عضوِ تازه‌ی این لیست را نمی‌بیند — دقیقاً همان شکافی که
مهاجرتِ `0073` برای `manufacturing` با گرنتِ خودکار بست، ولی این‌بار برای یک
ماژولِ **غیرمحدود** که فقط باید در `enabled_modules` باشد، نه `granted_modules`.

بدونِ این بک‌فیل، حسابی که صنفش را انتخاب کرده (یا از پیش‌فرض خارج شده) پیمانکاری
را در منو نمی‌بیند، هرچند بک‌اندش کاملاً فعال است — اولین علامتش همین بود:
acc.cubita@gmail.com هم پیمانکاری را نداشت.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0160"
down_revision: Union[str, None] = "0159"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    #: tenants جدولِ مستأجرمحور نیست (خودش مرزِ مستأجر است)، پس RLS ندارد —
    #: rls_disabled این‌جا لازم نیست.
    conn.execute(
        sa.text(
            """
            UPDATE tenants
            SET enabled_modules = enabled_modules || '["contracting"]'::jsonb
            WHERE enabled_modules IS NOT NULL
              AND NOT (enabled_modules @> '["contracting"]'::jsonb)
            """
        )
    )


def downgrade() -> None:
    #: برگرداندنِ امن ناممکن است — نمی‌شود فهمید کدام مستأجر پیش از این مهاجرت
    #: خودش «پیمانکاری» را در enabled_modules داشته و کدام از همین بک‌فیل گرفته.
    #: حذفِ کورکورانه دسترسیِ مستأجرهایی را که واقعاً باید داشته باشند می‌شکند.
    pass
