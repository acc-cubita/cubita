"""وام‌های پرسنلی، تسویه حساب، و اطلاعاتِ استقرار

Revision ID: 0095
Revises: 0094

## چهار جدولِ تازه، هیچ ستونی روی جدولِ موجود عوض نمی‌شود

### چرا وام **دو** جدول است نه یکی

می‌شد مبلغِ وام و تعدادِ قسط را در یک ردیف نگه داشت و قسطِ ماهانه را تقسیم کرد. ولی
کسرِ ماهانه باید بداند **کدام** قسط سررسید شده و کدام قبلاً کسر شده — و اقساط در عمل
مساوی نمی‌مانند (قسطِ آخر گرد می‌شود، کاربر یک قسط را می‌بخشد، یک ماه کسر نمی‌شود).
با یک جدول، هر کدام از این‌ها یعنی محاسبه‌ی دوباره از روی حدس. با جدولِ قسط، هر قسط
یک واقعیتِ ثبت‌شده است.

`deducted_period_id` روی قسط می‌گوید در کدام دوره‌ی حقوقی کسر شد — پس ابطالِ یک دوره
می‌تواند اقساطش را آزاد کند، و هیچ قسطی دوبار کسر نمی‌شود.

### تسویه حساب چرا `BenefitRun` نیست

`benefit_runs` هر مزیت را **جدا** صادر می‌کند (عیدی، سنوات، بازخریدِ مرخصی) و برای
همان ساخته شده. تسویه‌حسابِ پایانِ کار یک چیزِ دیگر است: همه‌ی این‌ها منهای بدهیِ وام
در **یک** سند، با یک عددِ خالص که به کارمند پرداخت می‌شود. ریختنش در `benefit_runs`
یعنی آن جدول هم «یک مزیت» باشد هم «جمعِ چند مزیت منهای بدهی» — دو معنا در یک ستون.

### اطلاعاتِ استقرار — مهم‌ترینِ این چهارتا

شرکتی که وسطِ سال از اکسل به کوبیتا می‌آید، پرداختیِ ماه‌های گذشته‌اش این‌جا نیست.
مالیاتِ حقوق **پلکانی و سالانه** است: بی‌این عدد، پلکان از صفر شروع می‌شود و مالیاتِ
ماه‌های باقی‌مانده کمتر از واقع درمی‌آید — خطایی که تا ممیزیِ سالِ بعد دیده نمی‌شود.

مانده‌ی مرخصی و سنواتِ قبلی هم همین‌جاست، به همان دلیل: بدونشان، کارمندی که ده سال
سابقه دارد از دیدِ نرم‌افزار تازه‌وارد است.

**یک ردیف به‌ازای هر کارمند در هر سالِ مالی**، و قیدِ یکتایی همین را نگه می‌دارد.

## هیچ ردیفی کاشته نمی‌شود

هر چهار جدول RLS دارند و `INSERT`ِ داخلِ مهاجرت روی جدولِ RLSدار یا صفر ردیف
می‌گذارد یا به مستأجرِ اشتباه می‌رود — همان قاعده‌ی ۰۰۹۴.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.tenancy import policy_name

revision: str = "0095"
down_revision: Union[str, None] = "0094"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_TABLES = (
    "loan_types",
    "employee_loans",
    "employee_loan_installments",
    "payroll_settlements",
    "payroll_deployment_info",
)


def _tenant_column() -> sa.Column:
    return sa.Column(
        "tenant_id", postgresql.UUID(as_uuid=True),
        sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True,
    )


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def upgrade() -> None:
    conn = op.get_bind()

    # ── نوع وام ───────────────────────────────────────────────────────────────
    op.create_table(
        "loan_types",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _tenant_column(),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("name2", sa.String(length=150), nullable=False, server_default=""),
        #: پیش‌فرضِ فرم، نه قانون: هر وام تعدادِ قسطِ خودش را دارد.
        sa.Column("default_installments", sa.Integer(), nullable=False, server_default="12"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        *_timestamps(),
        sa.UniqueConstraint("tenant_id", "code", name="uq_loan_types_tenant_code"),
        sa.CheckConstraint(
            "default_installments > 0 AND default_installments <= 240",
            name="ck_loan_types_installments",
        ),
    )

    # ── وامِ پرسنلی ────────────────────────────────────────────────────────────
    op.create_table(
        "employee_loans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _tenant_column(),
        sa.Column(
            "employee_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True,
        ),
        #: نوعِ وام پاک‌شدنی است بی‌آنکه وام‌های ثبت‌شده از بین بروند.
        sa.Column(
            "loan_type_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("loan_types.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("amount", sa.Numeric(18, 0), nullable=False),
        sa.Column("loan_date", sa.Date(), nullable=False),
        sa.Column("installment_count", sa.Integer(), nullable=False, server_default="1"),
        #: active = در حالِ کسر · settled = تسویه‌شده · cancelled = لغوشده.
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_by_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"), nullable=False,
        ),
        *_timestamps(),
        sa.CheckConstraint("amount > 0", name="ck_employee_loans_amount"),
        sa.CheckConstraint(
            "installment_count > 0 AND installment_count <= 240",
            name="ck_employee_loans_installments",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'settled', 'cancelled')", name="ck_employee_loans_status"
        ),
    )

    # ── قسط ───────────────────────────────────────────────────────────────────
    op.create_table(
        "employee_loan_installments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _tenant_column(),
        sa.Column(
            "loan_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employee_loans.id", ondelete="CASCADE"), nullable=False, index=True,
        ),
        #: شماره‌ی قسط از ۱ — ترتیبِ سررسید را بی‌ابهام می‌کند حتی اگر دو قسط یک روز باشند.
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 0), nullable=False),
        #: کدام دوره‌ی حقوقی این قسط را کسر کرد. NULL = هنوز کسر نشده. با ابطالِ آن
        #: دوره دوباره NULL می‌شود، پس هیچ قسطی دوبار کسر نمی‌شود و هیچ‌کدام هم گم نمی‌شود.
        sa.Column(
            "deducted_period_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("payroll_periods.id", ondelete="SET NULL"), nullable=True,
        ),
        *_timestamps(),
        sa.UniqueConstraint("tenant_id", "loan_id", "seq", name="uq_loan_installments_loan_seq"),
        sa.CheckConstraint("amount > 0", name="ck_loan_installments_amount"),
        sa.CheckConstraint("seq > 0", name="ck_loan_installments_seq"),
    )

    # ── تسویه حساب ────────────────────────────────────────────────────────────
    op.create_table(
        "payroll_settlements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _tenant_column(),
        sa.Column(
            "employee_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True,
        ),
        sa.Column("settlement_date", sa.Date(), nullable=False),
        #: اجزای تسویه. هر کدام جدا می‌ماند چون کارمند حق دارد بداند عددِ خالص از
        #: کجا آمده — و ممیزِ بیمه و مالیات هم همین تفکیک را می‌خواهد.
        sa.Column("severance_amount", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("leave_payout_amount", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("other_earnings", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("loan_balance", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("other_deductions", sa.Numeric(18, 0), nullable=False, server_default="0"),
        #: خالص **ذخیره** می‌شود نه محاسبه‌ی هربار: مبنای پرداخت است و اگر بعداً
        #: نرخی عوض شود، عددی که پرداخت شده نباید عقب‌گرد کند.
        sa.Column("net_amount", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "journal_entry_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("journal_entries.id"), nullable=True,
        ),
        sa.Column(
            "created_by_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"), nullable=False,
        ),
        *_timestamps(),
        #: یک تسویه‌ی نهایی برای هر کارمند. اگر اشتباه بود، اصلاحش ویرایشِ همان
        #: ردیف است نه ردیفِ دوم — وگرنه دو خالصِ متفاوت در سابقه می‌ماند.
        sa.UniqueConstraint("tenant_id", "employee_id", name="uq_payroll_settlements_employee"),
        sa.CheckConstraint(
            "severance_amount >= 0 AND leave_payout_amount >= 0 AND other_earnings >= 0 "
            "AND loan_balance >= 0 AND other_deductions >= 0",
            name="ck_payroll_settlements_amounts",
        ),
    )

    # ── اطلاعاتِ استقرار ───────────────────────────────────────────────────────
    op.create_table(
        "payroll_deployment_info",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _tenant_column(),
        sa.Column(
            "employee_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True,
        ),
        #: سالِ مالیِ شمسی که این عددها به آن مربوط‌اند.
        sa.Column("year", sa.Integer(), nullable=False),
        #: پرداختیِ تجمیعی تا لحظه‌ی استقرار — پایه‌ی پلکانِ مالیاتِ سالانه.
        sa.Column("cumulative_gross", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("cumulative_tax", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("cumulative_insurance", sa.Numeric(18, 0), nullable=False, server_default="0"),
        #: مانده‌ی مرخصی و سابقه‌ی قبلی — وگرنه کارمندِ ده‌ساله تازه‌وارد دیده می‌شود.
        sa.Column("leave_balance_days", sa.Numeric(6, 2), nullable=False, server_default="0"),
        sa.Column("prior_service_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        *_timestamps(),
        sa.UniqueConstraint(
            "tenant_id", "employee_id", "year", name="uq_payroll_deployment_employee_year"
        ),
        sa.CheckConstraint(
            "cumulative_gross >= 0 AND cumulative_tax >= 0 AND cumulative_insurance >= 0 "
            "AND leave_balance_days >= 0 AND prior_service_days >= 0",
            name="ck_payroll_deployment_amounts",
        ),
    )

    for table in _NEW_TABLES:
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


def downgrade() -> None:
    for table in reversed(_NEW_TABLES):
        op.drop_table(table)
