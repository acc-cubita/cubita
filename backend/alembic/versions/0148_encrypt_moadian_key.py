"""کلیدِ امضای مؤدیان خام در دیتابیس می‌نشست.

Revision ID: 0148
Revises: 0147

**بررسی.** `moadian_settings.private_key_pem` یک ستونِ `Text` بود، بدونِ
رمزگذاری. سه دفاع داشت و هر سه واقعی‌اند:

* از API برنمی‌گشت — اسکیمای خروجی فقط `has_private_key` می‌دهد
* در لاگ نمی‌آمد
* RLS بینِ کسب‌وکارها جدایش می‌کرد

ولی هیچ‌کدام **یک نسخه‌ی پشتیبان** را پوشش نمی‌دادند. یک `pg_dump` یعنی کلیدِ
امضای همه‌ی کسب‌وکارها در دستِ کسی که آن فایل را دارد — یعنی توانِ فرستادنِ
صورتحسابِ رسمی به سازمان امور مالیاتی به نامِ آن‌ها.

## این مهاجرت چه می‌کند

هر کلیدِ موجود را با `SECRETS_KEY`ِ محیط رمز می‌کند و به شکلِ `enc:v1:<token>`
برمی‌گرداند. **هیچ ستونی اضافه یا حذف نمی‌شود** — فقط محتوای همان ستون عوض
می‌شود. `app/secrets_at_rest.py` منطقِ باز و بسته‌کردن را دارد و مقدارِ
بی‌پیشوند را دست‌نخورده برمی‌گرداند، پس کدِ جدید روی داده‌ی مهاجرت‌نشده هم
نمی‌شکند.

## چرا این‌جا سخت‌گیر است ولی بوت نه

نبودِ `SECRETS_KEY` در زمانِ **بوت** فقط هشدار می‌دهد: شکستنِ بوت یعنی اولین
استقرارِ بعد از این مهاجرت کلِ سامانه را پایین بیاورد، و رفتارِ بی‌کلید همان
رفتارِ دیروز است — بد، ولی نه بدتر.

این‌جا فرق می‌کند. اگر کلیدی برای رمزکردن هست و `SECRETS_KEY` نیست، مهاجرت
**می‌شکند** — چون رد شدنش یعنی راز خام بماند در حالی که سرپرست فکر کند رمز شده.
سکوت این‌جا از شکست بدتر است.

## اگر `SECRETS_KEY` گم شود

کلیدهای امضا **برنمی‌گردند**. غیرقابل‌جبران نیست — هر کسب‌وکار کلیدش را دوباره
از کارپوشه می‌گیرد و آپلود می‌کند — ولی تا آن لحظه صورتحسابی ارسال نمی‌شود.
`downgrade` هم همین را برمی‌گرداند: با همان کلید باز می‌کند و خام می‌نویسد، و
اگر کلید نباشد **می‌شکند** به‌جای اینکه متنِ رمزشده را به‌عنوان کلیدِ معتبر جا
بزند.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.migration_utils import rls_disabled
from app.secrets_at_rest import PREFIX, SecretUnreadable, decrypt, encrypt, is_configured

revision: str = "0148"
down_revision: Union[str, None] = "0147"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "moadian_settings"

_MISSING_KEY = (
    "{n} کسب‌وکار کلیدِ امضای سامانه‌ی مؤدیان دارند ولی SECRETS_KEY تنظیم نیست. "
    "بدونِ آن این مهاجرت رازها را خام رها می‌کند در حالی که وانمود می‌شود رمز شده‌اند. "
    'یک کلید بسازید (python -c "import secrets; print(secrets.token_urlsafe(48))")، '
    "در محیطِ سرور بگذارید، و دوباره اجرا کنید. **آن کلید را کنارِ نسخه‌ی پشتیبانِ "
    "دیتابیس نگه ندارید.**"
)


def _rows(conn, only_prefixed: bool):
    op_ = "LIKE" if only_prefixed else "NOT LIKE"
    return conn.execute(
        sa.text(
            f"SELECT id, private_key_pem FROM {TABLE} "
            f"WHERE private_key_pem IS NOT NULL AND btrim(private_key_pem) <> '' "
            f"AND private_key_pem {op_} :p"
        ),
        {"p": PREFIX + "%"},
    ).fetchall()


def _rewrite(conn, rows, transform) -> int:
    for row_id, value in rows:
        conn.execute(
            sa.text(f"UPDATE {TABLE} SET private_key_pem = :v WHERE id = :i"),
            {"v": transform(value), "i": row_id},
        )
    return len(rows)


def upgrade() -> None:
    conn = op.get_bind()
    #: جدول `FORCE RLS` دارد و `app.tenant_id` در مهاجرت تنظیم نیست — بی این،
    #: `SELECT` صفر ردیف می‌دید و مهاجرت **بی‌صدا هیچ‌کاری نمی‌کرد**، که بدترین
    #: حالتِ ممکن است: راز خام می‌ماند و گزارش می‌گوید موفق بود.
    with rls_disabled(conn, (TABLE,)):
        pending = _rows(conn, only_prefixed=False)
        if pending and not is_configured():
            raise RuntimeError(_MISSING_KEY.format(n=len(pending)))
        count = _rewrite(conn, pending, encrypt)
    print(f"0148: {count} کلیدِ امضا رمزگذاری شد")


def downgrade() -> None:
    conn = op.get_bind()
    with rls_disabled(conn, (TABLE,)):
        encrypted = _rows(conn, only_prefixed=True)
        if encrypted and not is_configured():
            raise RuntimeError(
                f"{len(encrypted)} کلیدِ رمزشده هست و SECRETS_KEY تنظیم نیست؛ "
                "بازگرداندنشان ممکن نیست. بدونِ این گارد، متنِ رمزشده به‌عنوان "
                "کلیدِ معتبر جا می‌افتاد و امضا بی‌صدا خراب می‌شد."
            )
        try:
            count = _rewrite(conn, encrypted, decrypt)
        except SecretUnreadable as exc:
            raise RuntimeError(f"بازگرداندنِ کلیدها شکست خورد: {exc}") from exc
    print(f"0148: {count} کلیدِ امضا به متنِ خام برگشت")
