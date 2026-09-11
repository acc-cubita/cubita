"""رویدادِ چک می‌گفت چه شد، ولی نه کجا ثبت شد

Revision ID: 0115
Revises: 0114

## چه چیزی نبود

مهاجرتِ ۰۱۱۰ تاریخچه‌ی چک را ساخت و `check_events` هر گذر را با عملیات، بانک،
صندوق، طرف‌حساب و **سندِ حسابداری** نگه می‌دارد. یک چیز جا ماند: **سندِ
عملیاتی**.

یعنی تایم‌لاین می‌گفت «دریافت، ۱۴۰۴/۰۱/۰۱» ولی نمی‌گفت این دریافت در کدام
*رسید* ثبت شده. سؤالِ «این چک با کدام رسید آمد؟ با کدام اعلامیه خرج شد؟» — که
کارِ روزمره‌ی خزانه‌دار و اولین سؤالِ هر حسابرسی است — هیچ جوابی نداشت، و
drill-down از تایم‌لاین به سندِ اصلی اصلاً ممکن نبود.

`operation_no` هست، ولی شماره‌ی **عملیاتِ چک** است. رسید و اعلامیه عملیاتِ چک
نیستند؛ سندِ دیگری‌اند با شمارنده‌ی دیگر.

## چه چیزی اینجا اضافه می‌شود

`check_events.source_type` و `source_id` — سندی که گذر در آن ثبت شده. کلیدِ
خارجی نیست چون منبع‌ها در جدول‌های مختلفی زندگی می‌کنند؛ همان الگویی که
`journal_entries.source_type` دارد.

## چه چیزی backfill می‌شود — و چه چیزی نه

**فقط آنچه از یک کلیدِ خارجیِ واقعی مشتق می‌شود، نه آنچه حدس زده می‌شود.**

* رویدادِ `receive` روی چکی که `receipt_id` دارد → منبعش همان رسید است. این
  استنتاج نیست: `checks.receipt_id` یعنی این برگ در همان رسید وارد شده، و
  رویدادِ دریافتش همان‌جا ثبت شده.
* رویدادِ `issue` روی چکی که `payment_id` دارد → همان، سمتِ پرداخت.
* رویدادِ `endorse` روی چکی که `payment_id` دارد → چک با آن اعلامیه خرج شده.

بقیه دست‌نخورده `NULL` می‌مانند:

* چکی که مستقیم ثبت شده منبعِ بیرونی **ندارد** — `NULL` همان حقیقت است.
* واگذاری، وصول، واخواست و نقدکردن منبعشان خودِ عملیاتِ چک است و `operation_no`
  از قبل شناسه‌اش را دارد.
* و هیچ رویدادی با حدس پر نمی‌شود. اگر چکی هم `receipt_id` دارد هم چند بار
  خرج و برگشت خورده، فقط اولین حلقه‌ی قابلِ اثبات وصل می‌شود — همان قاعده‌ای که
  ۰۱۱۰ هم با آن تاریخچه را backfill نکرد.

## چرا UPDATE روی جدولِ فقط‌افزودنی ممکن است

`check_events` تریگرِ `BEFORE UPDATE OR DELETE` دارد. `app.audit_purge` همان
دریچه‌ی فراری است که برای برون‌سپاریِ مستأجر و بازیابیِ پشتیبان ساخته شد، و
این‌جا هم به همان دلیل باز می‌شود: **مهاجرتِ اسکیما تاریخچه را بازنویسی
نمی‌کند، فقط ستونی را پر می‌کند که هنوز وجود نداشت.** هیچ وضعیت، تاریخ یا
کاربری دست نمی‌خورد.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.migration_utils import rls_disabled

revision: str = "0115"
down_revision: Union[str, None] = "0114"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "check_events"


def upgrade() -> None:
    conn = op.get_bind()

    op.add_column(TABLE, sa.Column("source_type", sa.String(30), nullable=True))
    op.add_column(TABLE, sa.Column("source_id", UUID(as_uuid=True), nullable=True))
    #: ناوبریِ برعکس (§۱۵): از رسید/اعلامیه به چک‌هایش.
    op.create_index("ix_check_events_source", TABLE, ["tenant_id", "source_type", "source_id"])

    with rls_disabled(conn, [TABLE, "checks"]):
        #: تریگرِ فقط‌افزودنی باید برای همین یک نوشتن کنار برود. بدونش `UPDATE`
        #: خطا می‌دهد و مهاجرت می‌شکند — و «بی‌صدا صفر ردیف» هم نمی‌شود، چون
        #: تریگر صریح raise می‌کند.
        conn.execute(sa.text("SET LOCAL app.audit_purge = 'on'"))
        for operation, column, source in (
            ("receive", "receipt_id", "receipt"),
            ("issue", "payment_id", "payment"),
            ("endorse", "payment_id", "payment"),
        ):
            conn.execute(
                sa.text(
                    f"""
                    UPDATE {TABLE} e
                       SET source_type = :source, source_id = c.{column}
                      FROM checks c
                     WHERE c.id = e.check_id
                       AND e.operation = :operation
                       AND c.{column} IS NOT NULL
                       AND e.source_id IS NULL
                    """
                ),
                {"source": source, "operation": operation},
            )


def downgrade() -> None:
    op.drop_index("ix_check_events_source", table_name=TABLE)
    op.drop_column(TABLE, "source_id")
    op.drop_column(TABLE, "source_type")
