"""واسطه و کارمزدش روی فاکتور فروش

Revision ID: 0097
Revises: 0096

## چه چیزی را می‌بندد

نقشِ «واسط» روی طرف‌حساب از قبل بود (`contacts.is_broker` و `contacts.commission_rate`)،
ولی هیچ فاکتوری نمی‌گفت واسطه‌اش که بود. یعنی نرخِ کارمزد ذخیره می‌شد و هرگز به
معامله‌ای نمی‌چسبید — تنظیمی که هیچ اثری نداشت.

## چرا کارمزد ذخیره می‌شود و در لحظه‌ی خواندن حساب نمی‌شود

قاعده‌ی پروژه «مشتق بهتر از ذخیره» است، و این استثنای آگاهانه‌ی همان است.
`contacts.commission_rate` نرخِ **امروزِ** واسطه است و فردا عوض می‌شود؛ کارمزدِ این
فروش اما در لحظه‌ی فروش قطعی شده و بدهیِ ثبت‌شده است. اگر مشتق بماند، تغییرِ نرخ
گذشته را بازنویسی می‌کند و صورت‌حسابِ تسویه‌شده‌ی ماهِ پیش عددِ دیگری نشان می‌دهد.

دقیقاً همان دلیلی که `tax_rate` و `tax_amount` هر دو روی فاکتور می‌نشینند به‌جای
اینکه از تنظیماتِ مالیات خوانده شوند.

## چرا `ON DELETE SET NULL`

حذفِ طرف‌حساب نباید فاکتورِ ثبت‌شده را از بین ببرد یا حذف را قفل کند. فاکتور
می‌ماند و فقط واسطه‌اش نامعلوم می‌شود — و `broker_commission` سرِ جایش می‌ماند،
چون آن مبلغ واقعاً پرداختنی بوده و پاک‌کردنش دفتر را عوض می‌کند.

## چرا backfill نیست

فاکتورهای قدیمی واسطه نداشتند؛ `NULL` و صفر مقدارِ درستشان است نه حدس. ضمناً
`sales_invoices` جدولِ RLSدار است و `UPDATE`ِ داخلِ مهاجرت یا صفر ردیف می‌گیرد یا
به مستأجرِ اشتباه می‌رود.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0097"
down_revision: Union[str, None] = "0096"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sales_invoices",
        sa.Column("broker_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_sales_invoices_broker_id",
        "sales_invoices",
        "contacts",
        ["broker_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_sales_invoices_broker_id", "sales_invoices", ["broker_id"])
    op.add_column(
        "sales_invoices",
        sa.Column("broker_commission", sa.Numeric(18, 0), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        "ck_sales_invoices_broker_commission",
        "sales_invoices",
        "broker_commission >= 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_sales_invoices_broker_commission", "sales_invoices", type_="check")
    op.drop_column("sales_invoices", "broker_commission")
    op.drop_index("ix_sales_invoices_broker_id", table_name="sales_invoices")
    op.drop_constraint("fk_sales_invoices_broker_id", "sales_invoices", type_="foreignkey")
    op.drop_column("sales_invoices", "broker_id")
