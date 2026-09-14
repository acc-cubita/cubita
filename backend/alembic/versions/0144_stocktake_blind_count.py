"""انبارگردانی: شمارشِ کور، و عکسِ سیستمی در لحظه‌ی شمارش.

Revision ID: 0144
Revises: 0143

**باگی که این مهاجرت زیرساختش را می‌سازد.** `system_qty` هنگام **باز کردنِ جلسه**
عکس‌برداری می‌شد، ولی شمارش ساعت‌ها بعد انجام می‌شود. یعنی مبنای مقایسه وضعیتی
بود که شمارنده هرگز ندید. پروب:

    موجودی ۱۰۰ → جلسه باز شد (عکس = ۱۰۰)
    ۱۰ عدد فروخته شد → موجودیِ واقعی ۹۰
    شمارنده می‌شمارد ۹۰   (درست؛ ده تا واقعاً رفته)
    ثبت → اختلاف = ۹۰ − ۱۰۰ = −۱۰
    موجودیِ نهایی = ۸۰      ← باید ۹۰ می‌بود

فروشِ ده‌تایی **دو بار** از موجودی کم شد و سندی هم برای کسری‌ای که وجود نداشت
خورد. مدل این را می‌دانست و نوشته بود «بازه‌ی شمارش را کوتاه نگه دارید» — ولی یک
فروش دو ثانیه طول می‌کشد و انبارگردانی ساعت‌ها.

اصلاح در سرویس است: عکسِ سیستمیِ هر ردیف **در لحظه‌ای که شمارشش وارد می‌شود** از
دفتر بازخوانده می‌شود، یعنی همان چیزی که سیستم *در همان لحظه* باور داشت.
`counted_at` این‌جا ستونِ لنگر است.

## سه ستون

* **`counted_qty` تهی‌پذیر می‌شود.** تا امروز با `system_qty` از پیش پر می‌شد —
  یعنی شمارنده نه‌تنها عددِ سیستم را می‌دید، فرم از قبل نوشته بودش. حالا
  `NULL` = «هنوز شمرده نشده» و از اختلاف‌گیری **کنار گذاشته می‌شود**؛ صفرِ صریح
  = «شمردم، هیچ نبود» و کسریِ واقعی می‌سازد.

  این تفاوت یک فاجعه را می‌بندد: اگر «شمرده‌نشده» صفر تفسیر شود، جلسه‌ای که
  نیمه‌کاره ثبت شود کلِ موجودیِ صدها کالای دست‌نخورده را از انبار بیرون می‌ریزد.

  **ردیف‌های موجود دست نمی‌خورند** — عددشان می‌ماند، پس جلسه‌های بازِ امروز
  دقیقاً مثل دیروز رفتار می‌کنند.
* **`counted_at`** — کِی این شمارش وارد شد. مبنای «عکس در لحظه‌ی شمارش» و پاسخِ
  «چه‌قدر از این جلسه واقعاً شمرده شده؟».
* **`counted_by_id`** — چه کسی واردش کرد. فصل صریح است که شمارنده، سرپرست و
  واردکننده‌ی داده ممکن است سه نفر باشند؛ این ستون فقط سومی را ادعا می‌کند.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.migration_utils import rls_disabled

revision: str = "0144"
down_revision: Union[str, None] = "0143"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

LINES = "stock_count_lines"
SESSIONS = "stock_count_sessions"


def upgrade() -> None:
    #: **شماره‌ی سند.** برگه‌ی شمارشِ کاغذی باید به جلسه‌اش وصل باشد؛ بی شماره،
    #: تگی که از انبار برمی‌گردد به هیچ‌چیز نمی‌خورد. سریِ خودش است — سندِ
    #: کسری/اضافی سندِ دیگری است و شماره‌ی دیگری دارد.
    op.add_column(SESSIONS, sa.Column("number", sa.Integer(), nullable=True))
    conn = op.get_bind()
    #: `document_counters` هم در فهرست است و نبودش مهاجرت را می‌انداخت: آن جدول
    #: هم `FORCE RLS` دارد، پس `INSERT`ِ بی‌زمینه با «new row violates row-level
    #: security policy» رد می‌شود — نه بی‌صدا، ولی همان خانواده‌ی تله.
    with rls_disabled(conn, (SESSIONS, "document_counters")):
        #: backfill به ترتیبِ ساخت، مستأجربه‌مستأجر — پس شماره‌ها با تاریخچه
        #: می‌خوانند و بینِ دو کسب‌وکار قاطی نمی‌شوند.
        conn.execute(
            sa.text(
                f"UPDATE {SESSIONS} s SET number = r.rn FROM ("
                f"  SELECT id, row_number() OVER (PARTITION BY tenant_id ORDER BY created_at, id) AS rn"
                f"  FROM {SESSIONS}"
                f") r WHERE r.id = s.id"
            )
        )
        #: شمارنده‌ی سند هم باید از جایی ادامه دهد که backfill رسانده، وگرنه
        #: اولین جلسه‌ی بعد از استقرار شماره‌ی تکراری می‌گیرد.
        conn.execute(
            sa.text(
                "INSERT INTO document_counters (id, tenant_id, doc_type, last_number) "
                "SELECT gen_random_uuid(), tenant_id, 'stock_count', max(number) "
                f"FROM {SESSIONS} GROUP BY tenant_id "
                "ON CONFLICT (tenant_id, doc_type) DO UPDATE "
                "SET last_number = GREATEST(document_counters.last_number, EXCLUDED.last_number)"
            )
        )
    op.alter_column(SESSIONS, "number", existing_type=sa.Integer(), nullable=False)
    op.create_unique_constraint(
        "uq_stock_count_sessions_tenant_number", SESSIONS, ["tenant_id", "number"]
    )

    #: تهی‌پذیر، بی backfill: هر ردیفِ موجود عددش را نگه می‌دارد و رفتارِ دیروز
    #: برای جلسه‌های باز عوض نمی‌شود. `NULL` فقط برای ردیف‌های تازه معنا پیدا
    #: می‌کند. `server_default` هم برداشته می‌شود، وگرنه ردیفِ تازه باز صفر می‌گرفت.
    op.alter_column(LINES, "counted_qty", existing_type=sa.Numeric(18, 3), nullable=True)
    op.alter_column(LINES, "counted_qty", existing_type=sa.Numeric(18, 3), server_default=None)

    op.add_column(LINES, sa.Column("counted_at", sa.DateTime(timezone=True), nullable=True))

    #: اعتبارسنجیِ کلیدِ خارجی مشمولِ RLS است و روی PG 14 با
    #: `invalid input syntax for type uuid: ""` می‌ترکد — `app/migration_utils.py`.
    with rls_disabled(op.get_bind(), (LINES, "users")):
        op.add_column(
            LINES,
            sa.Column(
                "counted_by_id",
                UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )


def downgrade() -> None:
    """پُرافت: «شمرده نشده» به صفر فرو می‌ریزد.

    و صفر در مدلِ قدیمی یعنی «کسریِ کاملِ این کالا». پس پیش از برگرداندن،
    ردیف‌های نشمرده به عددِ سیستمی برمی‌گردند — همان پیش‌فرضِ قدیمی، که بی‌اختلاف
    است و چیزی را از انبار بیرون نمی‌ریزد.
    """
    conn = op.get_bind()
    with rls_disabled(conn, (LINES,)):
        conn.execute(
            sa.text(f"UPDATE {LINES} SET counted_qty = system_qty WHERE counted_qty IS NULL")
        )
    op.drop_constraint("uq_stock_count_sessions_tenant_number", SESSIONS, type_="unique")
    op.drop_column(SESSIONS, "number")
    op.drop_column(LINES, "counted_by_id")
    op.drop_column(LINES, "counted_at")
    op.alter_column(LINES, "counted_qty", existing_type=sa.Numeric(18, 3), server_default="0")
    op.alter_column(LINES, "counted_qty", existing_type=sa.Numeric(18, 3), nullable=False)
