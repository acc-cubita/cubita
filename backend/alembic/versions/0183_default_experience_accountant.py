"""پیش‌فرضِ حالتِ تجربه به «حسابدار» تغییر می‌کند

Revision ID: 0183
Revises: 0182

`0182` پیش‌فرض را `simple` گذاشت و دلیلش را هم نوشت: «پیش‌فرض باید رفتارِ امروز
را نگه دارد». آن استدلال در روزِ خودش درست بود — حالتِ حسابدار هنوز وجود نداشت
و هیچ کاربری ندیده بودش. حالا دیده شده و تصمیمِ محصول عوض شده: حسابدار پیش‌فرض
می‌شود. این مهاجرت آن تصمیم را اجرا می‌کند، نه اینکه اشتباهی را رفع کند.

**چرا ردیف‌های موجود هم جابه‌جا می‌شوند.** آن ۱۰ ردیفِ `simple` **انتخابِ کاربر
نیستند** — `server_default`ِ خودِ `0182` نوشته‌شان. ستون جایی ثبت نمی‌کند که
مقدار از انتخابِ آدم آمده یا از پیش‌فرضِ مهاجرت، پس «فقط آن‌هایی که انتخاب
نکرده‌اند» با این اسکیما اصلاً قابلِ بیان نیست. تنها انتخاب‌های واقعیِ موجود
`accountant`اند و این `UPDATE` دقیقاً به آن‌ها دست نمی‌زند.

اگر روزی کسی واقعاً «ساده» را انتخاب کرده باشد و بخواهیم حفظش کنیم، راهش ستونِ
«انتخاب شد یا نه» است نه حدس‌زدن از روی مقدار. امروز چنین ستونی نداریم و
افزودنش برای ۱۲ ردیفِ یک‌روزه بی‌مورد است.

**بی RLS و بی `rls_disabled`.** `users` در `GLOBAL_TABLES` است و
`pg_class.relrowsecurity` رویش `false` — روی تولید هم سنجیده شد. پس `UPDATE`
همه‌ی ردیف‌ها را می‌بیند. (این را فقط جدول‌های مستأجری لازم دارند.)

**قیدِ `ck_users_experience_mode` دست نمی‌خورد**: هر دو مقدار از قبل مجازند.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0183"
down_revision: Union[str, None] = "0182"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "experience_mode",
        existing_type=sa.String(length=20),
        existing_nullable=False,
        server_default="accountant",
    )
    op.execute("UPDATE users SET experience_mode = 'accountant' WHERE experience_mode = 'simple'")


def downgrade() -> None:
    #: فقط پیش‌فرض برمی‌گردد، **نه داده**. بازگرداندنِ داده یعنی حدس‌زدنِ اینکه
    #: کدام ردیف را این مهاجرت جابه‌جا کرده و کدام را خودِ کاربر — و ستون این را
    #: نمی‌داند. یک `UPDATE`ِ معکوس، انتخابِ آگاهانه‌ی هر کسی را که پس از این
    #: مهاجرت «حسابدار» زده هم پاک می‌کرد. برگشتِ ناقصِ صادق بهتر از برگشتِ
    #: کاملِ دروغ است.
    op.alter_column(
        "users",
        "experience_mode",
        existing_type=sa.String(length=20),
        existing_nullable=False,
        server_default="simple",
    )
