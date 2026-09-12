"""فیشِ حقوقی عددش درست بود، ولی نمی‌گفت از چه ساخته شده

Revision ID: 0128
Revises: 0127

`Payslip` همه‌ی مبالغش را در لحظه‌ی صدور snapshot می‌گیرد — و این درست است: حقوقِ
تیر با جدولِ مالیاتِ مرداد بازمحاسبه نمی‌شود. ولی snapshot در سطحِ **جمع** گرفته
می‌شد:

* `allowances_total` یک عدد است. عاملی که `housing` یا `food` نباشد اول در
  `other_allowance`ِ قرارداد جمع می‌شود و بعد در `allowances_total`ِ فیش.
* `other_deductions` هم همین‌طور: جمعِ همه‌ی ردیف‌های کسوراتِ قرارداد.

پس «این ۳٬۲۰۰٬۰۰۰ مزایا از چه ساخته شد؟» جواب نداشت. و بازخواندنش از قرارداد هم
جواب نمی‌دهد، چون قرارداد می‌تواند از آن موقع عوض شده باشد — دقیقاً همان دلیلی
که snapshot برایش وجود دارد.

این جدول همان تفکیک را در لحظه‌ی صدور ذخیره می‌کند: هر ردیف می‌گوید کدام **عامل**
چه مبلغی در این فیش ساخت. حقوقِ پایه، اضافه‌کار، بیمه، مالیات و قسطِ وام هم
ردیفِ خودشان را می‌گیرند تا فیش **کامل** توضیح‌پذیر باشد، نه نیمه.

`factor_id` می‌تواند `NULL` باشد و این عمدی است: حقوقِ پایه و مالیات عاملِ
تعریف‌شده‌ی کاربر نیستند، سیستمی‌اند. `factor_name` هم عکسِ لحظه‌ی ثبت است تا
تغییرِ نامِ عامل، فیشِ پارسال را بازنویسی نکند.

**بدونِ backfill.** فیش‌های پیش از این مهاجرت ردیف ندارند و همان اعدادِ تجمیعیِ
خودشان را نشان می‌دهند؛ ساختنِ تفکیکِ گذشته از قراردادِ **امروز** یعنی نوشتنِ
عددی که هیچ‌وقت محاسبه نشده.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.tenancy import policy_name

revision: str = "0128"
down_revision: Union[str, None] = "0127"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "payslip_lines"


def _enable_rls(table: str) -> None:
    conn = op.get_bind()
    conn.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    conn.execute(sa.text(f"DROP POLICY IF EXISTS {policy_name(table)} ON {table}"))
    conn.execute(
        sa.text(
            f"CREATE POLICY {policy_name(table)} ON {table} "
            "USING (tenant_id = current_setting('app.tenant_id', true)::uuid) "
            "WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)"
        )
    )


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column(
            "payslip_id",
            UUID(as_uuid=True),
            sa.ForeignKey("payslips.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("seq", sa.Integer(), nullable=False),
        #: `NULL` برای اجزای سیستمی (حقوقِ پایه، بیمه، مالیات، قسطِ وام) که عاملِ
        #: تعریف‌شده‌ی کاربر نیستند.
        sa.Column(
            "factor_id",
            UUID(as_uuid=True),
            sa.ForeignKey("payroll_factors.id", ondelete="SET NULL"),
            nullable=True,
        ),
        #: عکسِ لحظه‌ی ثبت — تغییرِ نامِ عامل، فیشِ گذشته را بازنویسی نمی‌کند.
        sa.Column("factor_name", sa.String(150), nullable=False),
        #: `earning` | `deduction` — جهتِ اثر روی خالص.
        sa.Column("direction", sa.String(10), nullable=False),
        #: منشأ: قرارداد، کارکردِ دوره، تنظیماتِ حقوق، یا ماژولِ وام. برای آنکه
        #: کاربر بداند برای عوض‌کردنش کجا باید برود.
        sa.Column("origin", sa.String(20), nullable=False),
        sa.Column("amount", sa.Numeric(18, 0), nullable=False),
        sa.Column("note", sa.Text(), server_default="", nullable=False),
        sa.CheckConstraint("direction IN ('earning', 'deduction')", name="ck_payslip_lines_direction"),
        sa.CheckConstraint(
            "origin IN ('contract', 'attendance', 'settings', 'loan')",
            name="ck_payslip_lines_origin",
        ),
        #: `tenant_id` در قید هست چون گاردِ `test_migration_drift` هر یکتاییِ
        #: سراسری روی جدولِ مستأجرمحور را رد می‌کند — و درست می‌کند.
        sa.UniqueConstraint("tenant_id", "payslip_id", "seq", name="uq_payslip_lines_seq"),
    )
    _enable_rls(TABLE)


def downgrade() -> None:
    op.drop_table(TABLE)
