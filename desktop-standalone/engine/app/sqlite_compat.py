"""سازگاریِ SQLite برای نسخه‌ی محلیِ دسکتاپ.

بک‌اند برای Postgres نوشته شده و در چند مدل از نوعِ `JSONB` استفاده می‌کند. روی SQLite
(که نسخه‌ی محلی رویش اجرا می‌شود) کامپایلرِ نوعِ SQLite `JSONB` را نمی‌شناسد. اینجا یک
کامپایلرِ سفارشی ثبت می‌کنیم تا `JSONB` روی SQLite به‌صورتِ `JSON` رندر شود (ذخیره‌ی متنی؛
سریال‌سازیِ dict↔JSON از نوعِ پایه‌ی `JSON` می‌آید). `UUID` در سطحِ DDL نیازی به شیم ندارد —
SQLAlchemy آن را روی SQLite به‌صورتِ `CHAR(32)` رندر می‌کند.

فقط با import شدن (در `database.py` وقتی dialect برابر sqlite است) اثر می‌کند.
"""
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(element, compiler, **kw):  # noqa: ANN001, ANN201
    return "JSON"


def uuid_param(value):  # noqa: ANN001, ANN201
    """UUID را برای بایندِ *SQLِ خام* به همان شکلی که ORM ذخیره می‌کند سریال می‌کند.

    گیرِ ظریف: ORM ستون‌های `postgresql.UUID` را روی SQLite به‌صورتِ ۳۲ کاراکترِ hex
    **بدونِ خط‌تیره** ذخیره می‌کند (مثلِ `32f905628fb3…`)، در حالی که `str(UUID)` شکلِ
    ۳۶ کاراکتریِ **خط‌تیره‌دار** می‌دهد (`32f90562-8fb3-…`). پس هر SQLِ خامی که
    `str(uuid)` را بایند کند روی SQLite هیچ‌وقت match نمی‌شود (روی Postgres هر دو شکل
    نرمال می‌شوند، برای همین آنجا کار می‌کرد). نرمال‌سازی به ۳۲‌hex هم با شکلِ ذخیره‌ی
    SQLite می‌خواند و هم موردِ قبولِ ورودیِ uuidِ Postgres است، پس قابل‌حمل است.

    ورودی می‌تواند UUID یا str باشد؛ None بی‌تغییر رد می‌شود. هر جا در سرویس‌ها SQLِ خام
    با بایندِ UUID نوشتید، مقدار را از این تابع رد کنید.
    """
    if value is None:
        return None
    return str(value).replace("-", "")
