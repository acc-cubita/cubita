"""قراردادِ حقوق و دستمزد طبقِ سپیدار + جدول‌های مرجعش

Revision ID: 0094
Revises: 0093

## چه چیزی ساخته می‌شود

پنج جدولِ مرجع (محل خدمت، شغل، عوامل حقوق، گروه مالیاتی، شعب بیمه و مالیات)، یک
جدولِ ردیف (`salary_contract_lines`) و بیست‌وچند ستونِ تازه روی `salary_contracts`.

## سه چیزی که عمداً ستونِ تازه **نگرفتند**

۱. **«تاریخ صدور» همان `effective_from` است.** در سپیدار تاریخِ صدور یعنی «محاسبه‌ی
   حقوق از این تاریخ شروع می‌شود» — دقیقاً معنیِ `effective_from`ِ امروز. ستونِ دوم
   یعنی دو تاریخِ ممکن برای یک چیز و بالاخره یکی‌شان عقب می‌ماند.

۲. **«تاریخ استخدام» همان `employees.hire_date` است.** واقعیتِ *شخص* است نه این
   قرارداد؛ فرمِ قرارداد آن را نشان می‌دهد و روی خودِ کارمند می‌نویسد. (و عمداً
   می‌تواند خیلی قبل‌تر از تاریخِ صدور باشد: شرکت شاید سال‌ها با اکسل حقوق داده و
   تازه به کوبیتا آمده.)

۳. **مرکز هزینه جدولِ تازه نگرفت** — `cost_centers` از قبل هست.

## چهار ستونِ مبلغ چه می‌شوند

`base_salary` / `housing_allowance` / `food_allowance` / `other_allowance` سرِ جایشان
می‌مانند چون موتورِ فیشِ حقوقی روی همان‌ها حساب می‌کند. ولی از این پس کاربر آن‌ها را
مستقیم پر نمی‌کند: ردیف‌های `salary_contract_lines` را می‌نویسد و سرویس این چهار را
**از روی همان‌ها** می‌سازد (`payroll_factors.system_key` می‌گوید کدام ردیف کدام ستون
است و بقیه در `other_allowance` جمع می‌شوند). یعنی یک منبعِ ویرایش، نه دو.

قراردادهای قدیمی ردیف ندارند و مقادیرِ ستونی‌شان دست‌نخورده کار می‌کنند.

## هیچ ردیفی کاشته نمی‌شود

جدول‌ها RLS دارند و `INSERT`ِ داخلِ مهاجرت روی جدولِ RLSدار یا صفر ردیف می‌گذارد یا
به مستأجرِ اشتباه می‌رود. عواملِ پیش‌فرض (حقوق پایه، حق مسکن، حق خواروبار، حق اولاد)
با دکمه‌ی صریحِ «ساخت عوامل پیش‌فرض» در صفحه‌ی عوامل ساخته می‌شوند — یک‌بار، به‌خواستِ
کاربر، داخلِ مستأجرِ خودش.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.tenancy import policy_name

revision: str = "0094"
down_revision: Union[str, None] = "0093"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_TABLES = (
    "service_locations",
    "job_titles",
    "payroll_factors",
    "payroll_tax_groups",
    "insurance_tax_branches",
    "salary_contract_lines",
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

    # ── محل خدمت ──────────────────────────────────────────────────────────────
    op.create_table(
        "service_locations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _tenant_column(),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("name2", sa.String(length=150), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        *_timestamps(),
        sa.UniqueConstraint("tenant_id", "code", name="uq_service_locations_tenant_code"),
    )

    # ── شغل ───────────────────────────────────────────────────────────────────
    op.create_table(
        "job_titles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _tenant_column(),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("name2", sa.String(length=150), nullable=False, server_default=""),
        #: رسته شغل — فهرستِ بسته‌ی سپیدار. اعتبارسنجی در اسکیما، نه قیدِ بررسی، چون
        #: این فهرست ممکن است با تغییرِ دستورالعملِ بیمه بلند شود.
        sa.Column("job_family", sa.String(length=50), nullable=False, server_default=""),
        sa.Column("insurance_job_code", sa.String(length=30), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        *_timestamps(),
        sa.UniqueConstraint("tenant_id", "code", name="uq_job_titles_tenant_code"),
    )

    # ── عوامل حقوق و مزایا ────────────────────────────────────────────────────
    op.create_table(
        "payroll_factors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _tenant_column(),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("name2", sa.String(length=150), nullable=False, server_default=""),
        #: مزایا (به نفعِ کارمند) یا کسورات (از حقوقش کم می‌شود).
        sa.Column("category", sa.String(length=20), nullable=False, server_default="benefit"),
        #: قراردادی-ثابت (هر ماه همان) یا متغیر (ماه‌به‌ماه فرق می‌کند).
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="fixed"),
        #: عادی یا فوق‌العاده — مبنای مالیات و بیمه فرق می‌کند.
        sa.Column("is_extraordinary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        #: پلِ عاملِ کاربر به ستون‌های موتورِ فیش: base | housing | food | child.
        #: خالی یعنی عاملِ ساخته‌ی کاربر که در «سایر مزایا» جمع می‌شود.
        sa.Column("system_key", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        *_timestamps(),
        sa.UniqueConstraint("tenant_id", "name", name="uq_payroll_factors_tenant_name"),
        sa.CheckConstraint("category IN ('benefit', 'deduction')", name="ck_payroll_factors_category"),
        sa.CheckConstraint("kind IN ('fixed', 'variable')", name="ck_payroll_factors_kind"),
        sa.CheckConstraint(
            "system_key IN ('', 'base', 'housing', 'food', 'child')",
            name="ck_payroll_factors_system_key",
        ),
    )
    #: هر کلیدِ سیستمی حداکثر یک عامل — وگرنه «حقوق پایه» دوتا می‌شود و ستونِ
    #: `base_salary` نمی‌داند از کدام ساخته شود.
    op.create_index(
        "uq_payroll_factors_tenant_system_key", "payroll_factors", ["tenant_id", "system_key"],
        unique=True, postgresql_where=sa.text("system_key <> ''"),
    )

    # ── گروه مالیاتی ──────────────────────────────────────────────────────────
    op.create_table(
        "payroll_tax_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _tenant_column(),
        sa.Column("name", sa.String(length=150), nullable=False),
        #: مناطق عادی | مناطق محروم | معاف
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="normal"),
        #: چند درصد از مالیاتِ محاسبه‌شده واقعاً وصول می‌شود. محروم = ۵۰، معاف = ۰.
        sa.Column("percent", sa.Numeric(5, 2), nullable=False, server_default="100"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        *_timestamps(),
        sa.UniqueConstraint("tenant_id", "name", name="uq_payroll_tax_groups_tenant_name"),
        sa.CheckConstraint("kind IN ('normal', 'deprived', 'exempt')", name="ck_payroll_tax_groups_kind"),
        sa.CheckConstraint("percent >= 0 AND percent <= 100", name="ck_payroll_tax_groups_percent"),
    )

    # ── شعب بیمه و مالیات ─────────────────────────────────────────────────────
    op.create_table(
        "insurance_tax_branches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _tenant_column(),
        sa.Column("code", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("name", sa.String(length=150), nullable=False),
        #: شعبه‌ی تأمین اجتماعی یا حوزه‌ی مالیاتی — یک جدول، چون شکلشان یکی است و
        #: فرمِ قرارداد هر دو را از یک‌جا می‌خواهد.
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="insurance"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        *_timestamps(),
        sa.UniqueConstraint("tenant_id", "kind", "name", name="uq_insurance_tax_branches_tenant_kind_name"),
        sa.CheckConstraint("kind IN ('insurance', 'tax')", name="ck_insurance_tax_branches_kind"),
    )

    # ── قرارداد: سرصفحه، استخدام، بیمه و مالیات ───────────────────────────────
    for column in (
        #: استخدام = اولین قراردادِ شخص؛ اصلاح قرارداد = هر قراردادِ بعدی.
        sa.Column("contract_type", sa.String(length=20), nullable=False, server_default="hire"),
        sa.Column("number", sa.String(length=30), nullable=False, server_default=""),
        #: تا این تاریخ طبقِ همین قرارداد محاسبه می‌شود. NULL = بی‌انقضا.
        sa.Column("valid_until", sa.Date(), nullable=True),
        #: از این تاریخ به بعد کارکرد اصلاً محاسبه نمی‌شود (پایانِ همکاری).
        sa.Column("service_end_date", sa.Date(), nullable=True),
        sa.Column("employment_type", sa.String(length=30), nullable=False, server_default=""),
        sa.Column("service_location_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("service_locations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("job_title_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("job_titles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("cost_center_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("cost_centers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("tax_group_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("payroll_tax_groups.id", ondelete="SET NULL"), nullable=True),
        sa.Column("tax_branch_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("insurance_tax_branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("insurance_branch_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("insurance_tax_branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("housing_loan_exempt_amount", sa.Numeric(18, 0), nullable=False, server_default="0"),
        sa.Column("is_insured", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_hard_job", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("exempt_employee_insurance", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("exempt_employer_insurance", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("employer_exempt_percent", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("exempt_unemployment_insurance", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("employer_name", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("has_supplementary_insurance", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("supplementary_branch", sa.String(length=150), nullable=False, server_default=""),
        sa.Column("supplementary_insurer", sa.String(length=150), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
    ):
        op.add_column("salary_contracts", column)

    op.create_check_constraint(
        "ck_salary_contracts_type", "salary_contracts", "contract_type IN ('hire', 'amend')"
    )
    op.create_check_constraint(
        "ck_salary_contracts_percent", "salary_contracts",
        "employer_exempt_percent >= 0 AND employer_exempt_percent <= 100 "
        "AND housing_loan_exempt_amount >= 0",
    )
    #: تاریخِ اعتبار و پایانِ خدمت هرگز قبل از تاریخِ صدور نیستند. NULL آزاد است.
    op.create_check_constraint(
        "ck_salary_contracts_dates", "salary_contracts",
        "(valid_until IS NULL OR valid_until >= effective_from) "
        "AND (service_end_date IS NULL OR service_end_date >= effective_from)",
    )

    # ── ردیف‌های حقوق و مزایای ثابت ───────────────────────────────────────────
    op.create_table(
        "salary_contract_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _tenant_column(),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("salary_contracts.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("factor_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("payroll_factors.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("amount", sa.Numeric(18, 0), nullable=False, server_default="0"),
        *_timestamps(),
        #: یک عامل در یک قرارداد یک ردیف — دو ردیفِ «حق مسکن» یعنی جمعِ مبهم.
        sa.UniqueConstraint("tenant_id", "contract_id", "factor_id", name="uq_contract_lines_factor"),
        sa.CheckConstraint("amount >= 0", name="ck_salary_contract_lines_amount"),
    )

    # ── RLS ───────────────────────────────────────────────────────────────────
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
    op.drop_table("salary_contract_lines")
    for name in ("ck_salary_contracts_dates", "ck_salary_contracts_percent", "ck_salary_contracts_type"):
        op.drop_constraint(name, "salary_contracts", type_="check")
    for column in (
        "description", "supplementary_insurer", "supplementary_branch", "has_supplementary_insurance",
        "employer_name", "exempt_unemployment_insurance", "employer_exempt_percent",
        "exempt_employer_insurance", "exempt_employee_insurance", "is_hard_job", "is_insured",
        "housing_loan_exempt_amount", "insurance_branch_id", "tax_branch_id", "tax_group_id",
        "cost_center_id", "job_title_id", "service_location_id", "employment_type",
        "service_end_date", "valid_until", "number", "contract_type",
    ):
        op.drop_column("salary_contracts", column)
    op.drop_table("insurance_tax_branches")
    op.drop_table("payroll_tax_groups")
    op.drop_index("uq_payroll_factors_tenant_system_key", table_name="payroll_factors")
    op.drop_table("payroll_factors")
    op.drop_table("job_titles")
    op.drop_table("service_locations")
