"""«متغیر» متغیر نبود — لایه‌ی ورودیِ دوره‌ای ساخته می‌شود.

Revision ID: 0147
Revises: 0146

**پروب.** عاملی به نامِ «مأموریت» با `kind = 'variable'` ساختم، روی حکم گذاشتم،
و دو ماهِ پیاپی فیش صادر کردم:

    ماهِ ۱: مأموریت — ۵٬۰۰۰٬۰۰۰  (origin: contract)
    ماهِ ۲: مأموریت — ۵٬۰۰۰٬۰۰۰  (origin: contract)

دقیقاً یک عدد. فرم می‌گفت «قراردادی (ثابت) / متغیر» ولی **هر دو یک رفتار
داشتند**: مبلغ از `salary_contract_lines.amount` می‌آمد و در نسبتِ کارکرد ضرب
می‌شد. `PayrollFactor.kind` نوشته می‌شد، اعتبارسنجی می‌شد، برگردانده می‌شد — و
هیچ‌جا خوانده نمی‌شد.

یعنی مأموریت، پاداش، کارانه و مساعده نمی‌توانستند ماه‌به‌ماه فرق کنند. برای
عوض‌کردنِ یک ماه باید **حکمِ حقوقی** ویرایش می‌شد؛ یعنی شرایطِ استخدام بازنویسی
می‌شد تا پاداشِ یک ماه داده شود.

## لایه‌ی گمشده

کوبیتا پنج لایه از شش لایه‌ی عامل را داشت: تعریف، فعال‌سازی، مشارکت، مبلغِ حکم،
و نتیجه. **ورودیِ دوره‌ای** نبود — تنها ورودیِ دوره‌ای `attendance` بود با سه
ستونِ ثابت (روزِ کارکرد، غیبت، ساعتِ اضافه‌کار) و بس.

    payroll_factor_inputs(employee_id, period_id, factor_id, amount, notes)

یکتا روی `(tenant, employee, period, factor)` — یک عامل در یک دوره برای یک
کارمند یک عدد دارد، نه دو.

## چرا عاملِ متغیر روی حکم ننشیند

اگر یک عامل هم مبلغِ حکم داشته باشد و هم ورودیِ دوره، ناخالص دو بار می‌شمردش.
راهِ سرراست تفریق‌کردنِ ردیفِ حکم بود؛ ولی آن یعنی ستونِ `other_allowance` و
مبنای بیمه و مالیات هر سه باید وارونه حساب شوند، و هر سه جای اشتباه‌اند.

پس قاعده از **شکلِ داده** می‌آید نه از حساب‌وکتاب: حکم شرایطِ **ماندگار** را
می‌گوید، و مبلغِ متغیر شرطِ ماندگار نیست. گاردش فقط روی **ذخیره‌ی تازه** است —
دقیقاً مثلِ گاردِ `is_active` که مهاجرتِ ۰۱۴۰ گذاشت — پس حکم‌های موجود دست
نمی‌خورند و فیش‌های صادرشده بازنویسی نمی‌شوند.

## بدونِ backfill

جدول خالی متولد می‌شود، و جدولِ خالی یعنی **هیچ عددی عوض نشده**: هر فیشی که
امروز صادر می‌شود فردا هم همان عدد را می‌دهد.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.tenancy import policy_name

revision: str = "0147"
down_revision: Union[str, None] = "0146"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "payroll_factor_inputs"
#: ردیفِ فیش باید بتواند بگوید «این عدد از ورودیِ دوره آمد». بی این، مبلغِ
#: مأموریتِ این ماه با برچسبِ `contract` ثبت می‌شد و «کجا باید عوضش کرد؟» به
#: حکمِ حقوقی اشاره می‌کرد — جای اشتباه.
PAYSLIP_ORIGINS = ("contract", "attendance", "settings", "loan", "input")
OLD_PAYSLIP_ORIGINS = ("contract", "attendance", "settings", "loan")


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
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "employee_id",
            UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "period_id",
            UUID(as_uuid=True),
            sa.ForeignKey("payroll_periods.id", ondelete="CASCADE"),
            nullable=False,
        ),
        #: **`RESTRICT`، نه `CASCADE`.** حذفِ یک عامل نباید مبلغی را که کاربر
        #: برای یک دوره وارد کرده بی‌صدا ببرد — همان تصمیمی که
        #: `salary_contract_lines.factor_id` از قبل گرفته.
        sa.Column(
            "factor_id",
            UUID(as_uuid=True),
            sa.ForeignKey("payroll_factors.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_by_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        #: منفی بی‌معنی است: جهتِ عدد از **طبقه‌ی عامل** می‌آید (مزایا یا کسور)،
        #: نه از علامتش. اجازه‌دادن به منفی یعنی دو راه برای گفتنِ یک چیز.
        sa.CheckConstraint("amount >= 0", name="ck_payroll_factor_inputs_amount"),
    )
    op.create_index(f"ix_{TABLE}_tenant_id", TABLE, ["tenant_id"])
    op.create_index(f"ix_{TABLE}_period_id", TABLE, ["period_id"])
    #: یک عامل در یک دوره برای یک کارمند **یک** عدد دارد. بی این، تلاشِ دوباره‌ی
    #: شبکه دو ردیف می‌ساخت و ناخالص بی‌صدا دو برابر می‌شد.
    op.create_index(
        "uq_payroll_factor_inputs_row",
        TABLE,
        ["tenant_id", "employee_id", "period_id", "factor_id"],
        unique=True,
    )
    _enable_rls(TABLE)

    #: اعتبارسنجیِ `CHECK` یک اسکنِ مستقیمِ heap است و — برخلافِ کلیدِ خارجی —
    #: مشمولِ RLS نیست، پس `rls_disabled` لازم ندارد (`app/migration_utils.py`).
    op.drop_constraint("ck_payslip_lines_origin", "payslip_lines", type_="check")
    op.create_check_constraint(
        "ck_payslip_lines_origin", "payslip_lines", f"origin IN {PAYSLIP_ORIGINS}"
    )


def downgrade() -> None:
    #: **`downgrade` می‌تواند شکست بخورد — و باید.** اگر فیشی با ردیفِ
    #: `origin = 'input'` صادر شده باشد، قیدِ باریک‌ترِ قدیم نمی‌پذیردش. پاک‌کردنِ
    #: آن ردیف‌ها یعنی بازنویسیِ فیشِ صادرشده؛ خطا بهتر از آن است.
    op.drop_constraint("ck_payslip_lines_origin", "payslip_lines", type_="check")
    op.create_check_constraint(
        "ck_payslip_lines_origin", "payslip_lines", f"origin IN {OLD_PAYSLIP_ORIGINS}"
    )
    op.drop_index("uq_payroll_factor_inputs_row", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_period_id", table_name=TABLE)
    op.drop_index(f"ix_{TABLE}_tenant_id", table_name=TABLE)
    op.drop_table(TABLE)
