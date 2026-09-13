"""اعلامیه‌ی بدهکار/بستانکار — معادلِ ریالی، و «چه کسی و چرا» باطلش کرد.

Revision ID: 0142
Revises: 0141

دو شکافِ فصلِ «اعلامیه بدهکار و بستانکار» (نوبتِ دوم) ستون می‌خواهند:

* **`base_amount`** روی ردیف و سربرگ. تا امروز نرخِ ارز ذخیره می‌شد ولی سند با خودِ
  مبلغِ ارزی می‌خورد: اعلامیه‌ی ۱۰۰ دلاری در دفتر ۱۰۰ ریال می‌نشست. از این پس
  مبلغِ ردیف به ارزِ سند است و معادلِ ریالیِ **همان ردیف** کنارش ذخیره می‌شود —
  ردیف‌به‌ردیف گرد می‌شود، پس جمعِ دفتر دقیقاً جمعِ همین ستون است.
* **`voided_by_id`** و **`void_reason`** روی سربرگ — همان دو ستونی که
  `VoidableMixin`ِ بقیه‌ی اسناد دارد. تا امروز دلیلِ ابطال فقط در شرحِ سندِ معکوس
  می‌ماند و «چه کسی» هیچ‌جا.

**backfill:** `base_amount = amount` برای ردیف‌ها و سربرگ‌های موجود. این حدس نیست،
همان چیزی است که واقعاً در دفتر نشسته: کدِ قبلی مبلغ را بدونِ ضرب در نرخ به سند
می‌فرستاد، پس ستونِ تازه با دفترِ موجود می‌خواند — حتی برای اعلامیه‌ای که از راهِ
API با ارزِ غیرِ ریال ثبت شده باشد. زیرِ `rls_disabled`، وگرنه `UPDATE` بی‌صدا صفر
ردیف می‌دید.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.migration_utils import rls_disabled

revision: str = "0142"
down_revision: Union[str, None] = "0141"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NOTES = "credit_debit_notes"
LINES = "credit_debit_note_lines"


def upgrade() -> None:
    op.add_column(NOTES, sa.Column("base_amount", sa.Numeric(18, 0), server_default="0", nullable=False))
    op.add_column(
        NOTES, sa.Column("voided_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True)
    )
    op.add_column(NOTES, sa.Column("void_reason", sa.Text(), server_default="", nullable=False))
    op.add_column(LINES, sa.Column("base_amount", sa.Numeric(18, 0), nullable=True))

    conn = op.get_bind()
    with rls_disabled(conn, [NOTES, LINES]):
        conn.execute(sa.text(f"UPDATE {LINES} SET base_amount = amount"))
        conn.execute(sa.text(f"UPDATE {NOTES} SET base_amount = amount"))

    op.alter_column(LINES, "base_amount", existing_type=sa.Numeric(18, 0), nullable=False)
    op.create_check_constraint(
        "ck_credit_debit_note_lines_base_amount_positive", LINES, "base_amount > 0"
    )


def downgrade() -> None:
    #: بااتلاف برای اعلامیه‌های ارزی: معادلِ ریالی می‌رود و `amount` تنها عدد می‌ماند،
    #: در حالی که سندِ حسابداری‌شان به ریال خورده. دلیل و کاربرِ ابطال هم می‌روند.
    op.drop_constraint("ck_credit_debit_note_lines_base_amount_positive", LINES, type_="check")
    op.drop_column(LINES, "base_amount")
    op.drop_column(NOTES, "void_reason")
    op.drop_column(NOTES, "voided_by_id")
    op.drop_column(NOTES, "base_amount")
