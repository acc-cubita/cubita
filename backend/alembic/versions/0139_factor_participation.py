"""«مشمولِ بیمه» یک پرچم بود، و قاعده‌ی واقعی به‌ازای هر هدف فرق می‌کند

Revision ID: 0139
Revises: 0138

## نقصی که بسته می‌شود

یک عاملِ حقوق در کوبیتا سه صفت داشت: دسته، نوع، و «فوق‌العاده». هیچ‌کدام
نمی‌گفتند این عامل در **کدام محاسبه** شرکت می‌کند. نتیجه‌اش دو فرضِ سخت بود:

    مبنای بیمه و مالیات  =  کلِ ناخالص            ← هر چیزی مشمول است
    مبنای عیدی/سنوات/مرخصی =  فقط «حقوق پایه»      ← هیچ مزایایی شمرده نمی‌شود

فرمِ مرجع هر دو را رد می‌کند: گریدِ «عوامل مشمول بیمه بی‌تأثیر در مزد روزانه و
ماهانه» نشان می‌دهد یک عامل می‌تواند مشمولِ بیمه باشد ولی مبنای مزد را تکان
ندهد؛ و «عوامل مؤثر در مبنای بازخرید مرخصی / عیدی / سنوات» نشان می‌دهد آن سه
مبنا از چند عامل ساخته می‌شوند، نه از حقوقِ پایه‌ی تنها.

## جدولِ استثناها، نه جدولِ همه‌چیز

`payroll_factor_participations` فقط **انحراف از پیش‌فرض** را ثبت می‌کند. نبودنِ
ردیف یعنی «پیش‌فرض»، و پیش‌فرض عمداً همان رفتارِ امروز است:

    نبودِ ردیف، هدفِ بیمه/مالیات      →  شریک، با ضریبِ ۱
    نبودِ ردیف، هدفِ عیدی/سنوات/مرخصی →  شریک فقط اگر عاملِ «حقوق پایه» باشد

این عدمِ‌تقارن تصادفی نیست: **دقیقاً همان چیزی است که کد امروز انجام می‌دهد.**
پس این مهاجرت هیچ ردیفی نمی‌نویسد و عددِ هیچ فیش، عیدی، سنوات یا بازخریدی عوض
نمی‌شود. از فردا کاربر می‌تواند استثنا تعریف کند؛ تا وقتی نکند، هیچ‌چیز فرق
نمی‌کند.

## و سه ارجاعِ عامل که ضریب‌های معافیت را زنده می‌کنند

`0138` ضریبِ معافیتِ بیمه‌ی تأمین اجتماعی از مالیات را آورد. دو ضریبِ دیگرِ فرمِ
مرجع — بیمه‌ی تکمیلی و بیمه‌ی درمان — بی‌مصرف می‌ماندند، چون کوبیتا نمی‌دانست
**کدام ردیفِ کسور** بیمه‌ی تکمیلی است و کدام درمان. حالا سه ارجاع به عاملِ موجود
این را می‌گویند (همان الگوی «کدام عامل این نقش را دارد» که فرمِ مرجع دارد)، و
آن‌وقت دو ضریب معنا پیدا می‌کنند.

همه‌شان `NULL` می‌مانند تا کاربر خودش نسبت بدهد — یعنی امروز هیچ کسری از مبنای
مالیات کم نمی‌شود، درست مثل دیروز.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.tenancy import policy_name

revision = "0139"
down_revision = "0138"
branch_labels = None
depends_on = None

FACTOR_PURPOSES = ("insurance_base", "tax_base", "eidi_base", "severance_base", "leave_base")

#: سه نقشِ عاملِ بیمه‌ی تکمیلی/درمان روی تنظیماتِ سال.
_FACTOR_REFS = (
    "supplementary_employee_factor_id",
    "supplementary_employer_factor_id",
    "medical_factor_id",
)

_COEFFICIENTS = (
    ("tax_exempt_coef_supplementary", "ck_payroll_settings_coef_supplementary"),
    ("tax_exempt_coef_medical", "ck_payroll_settings_coef_medical"),
)


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
        "payroll_factor_participations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "factor_id",
            UUID(as_uuid=True),
            sa.ForeignKey("payroll_factors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("purpose", sa.String(30), nullable=False),
        sa.Column("included", sa.Boolean(), server_default="true", nullable=False),
        #: ضریب `Numeric` است نه `Float` — سهمِ کسری (نیمی از حقِ مسئولیت در مبنای
        #: سنوات) قاعده‌ی محتملی است و نباید به خطای دودویی بخورد.
        sa.Column("coefficient", sa.Numeric(6, 4), server_default="1", nullable=False),
        sa.CheckConstraint(
            "purpose IN " + str(FACTOR_PURPOSES), name="ck_factor_participations_purpose"
        ),
        sa.CheckConstraint("coefficient >= 0 AND coefficient <= 1", name="ck_factor_participations_coefficient"),
    )
    #: `tenant_id` در ایندکسِ یکتا هست — بی آن، عاملِ یک مستأجر ردیفِ مستأجرِ دیگر
    #: را مسدود می‌کرد و `test_migration_drift` هم همین را می‌گیرد.
    op.create_index(
        "uq_factor_participations_factor_purpose",
        "payroll_factor_participations",
        ["tenant_id", "factor_id", "purpose"],
        unique=True,
    )
    op.create_index(
        "ix_factor_participations_purpose", "payroll_factor_participations", ["tenant_id", "purpose"]
    )
    _enable_rls("payroll_factor_participations")

    for name in _FACTOR_REFS:
        op.add_column(
            "payroll_settings",
            sa.Column(
                name,
                UUID(as_uuid=True),
                sa.ForeignKey("payroll_factors.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
    for name, check in _COEFFICIENTS:
        op.add_column(
            "payroll_settings",
            sa.Column(name, sa.Numeric(5, 4), nullable=False, server_default="1"),
        )
        op.create_check_constraint(check, "payroll_settings", f"{name} >= 0 AND {name} <= 1")


def downgrade() -> None:
    for name, check in _COEFFICIENTS:
        op.drop_constraint(check, "payroll_settings", type_="check")
        op.drop_column("payroll_settings", name)
    for name in reversed(_FACTOR_REFS):
        op.drop_column("payroll_settings", name)
    op.drop_index("ix_factor_participations_purpose", table_name="payroll_factor_participations")
    op.drop_index("uq_factor_participations_factor_purpose", table_name="payroll_factor_participations")
    op.drop_table("payroll_factor_participations")
