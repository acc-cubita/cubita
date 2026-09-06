"""دو ستونِ کسور روی فیشِ حقوقی — تا فیش دوباره جمع بزند

Revision ID: 0096
Revises: 0095

## ایرادی که این مهاجرت می‌بندد

مهاجرتِ ۰۰۹۵ کسرِ اقساطِ وام را به موتورِ فیش اضافه کرد و `net_pay` را کم می‌کرد،
ولی **هیچ ستونی نگه نمی‌داشت که چقدر کم شده**. نتیجه: فیشِ چاپی دیگر جمع نمی‌زد —
`ناخالص − بیمه − مالیات` با `خالص` فرق داشت و کارمند هیچ توضیحی برای اختلاف نداشت.

و ایرادِ دومِ قدیمی‌تر: ردیف‌های *کسوراتِ* قرارداد (تبِ «سایر مبالغ») از روزِ اول
بی‌صدا نادیده گرفته می‌شدند — `payroll_contracts` صراحتاً هر عاملی که `benefit`
نبود را رد می‌کرد. کاربر بیمه‌ی تکمیلی را وارد می‌کرد و هیچ‌جا کسر نمی‌شد.

دو ستونِ جدا، نه یکی، چون دو منشأ دارند و کارمند حق دارد بداند کدام است: قسطِ وام
از ماژولِ وام می‌آید و خودکار است؛ «سایر کسورات» از ردیف‌های قراردادِ خودش.

پس از این، این تساوی همیشه برقرار است و یک تست نگهش می‌دارد:

    خالص = ناخالص − بیمه‌ی سهمِ کارمند − مالیات − قسطِ وام − سایر کسورات

## چرا `server_default="0"` و نه backfill

فیش‌های قدیمی کسری نداشتند، پس صفر مقدارِ درستشان است — نه حدس. و `payslips` جدولِ
RLSدار است: `UPDATE`ِ داخلِ مهاجرت یا صفر ردیف می‌گیرد یا به مستأجرِ اشتباه می‌رود.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0096"
down_revision: Union[str, None] = "0095"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "payslips",
        sa.Column("loan_deduction", sa.Numeric(18, 0), nullable=False, server_default="0"),
    )
    op.add_column(
        "payslips",
        sa.Column("other_deductions", sa.Numeric(18, 0), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        "ck_payslips_deductions",
        "payslips",
        "loan_deduction >= 0 AND other_deductions >= 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_payslips_deductions", "payslips", type_="check")
    op.drop_column("payslips", "other_deductions")
    op.drop_column("payslips", "loan_deduction")
