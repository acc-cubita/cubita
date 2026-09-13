"""پارامترهای قانونیِ حقوق از سورس‌کد به تنظیمات می‌آیند

Revision ID: 0138
Revises: 0137

## نقصی که بسته می‌شود

پنج عددِ قانونی داخلِ کد ثابت بودند:

    STANDARD_MONTHLY_HOURS = 194      services/payroll.py
    OVERTIME_MULTIPLIER    = 1.4      services/payroll.py
    _YEAR_DIVISOR          = 365      services/benefits.py   ← سنواتِ ۳۰ روز
    _DAILY_DIVISOR         = 30       services/benefits.py
    base * 2                          services/benefits.py   ← ضریبِ مبنای عیدی

هر پنج‌تا هرسال با قانونِ بودجه/کار عوض می‌شوند. عددِ قانونی در کد یعنی هر تغییرِ
مصوبه یک استقرار می‌خواهد — و یعنی هیچ مستأجری نمی‌تواند عددِ خودش را داشته باشد.

## و سه چیزی که اصلاً نبودند

**سقفِ روزانه‌ی بیمه.** نرخ روی *کلِ* ناخالص می‌خورد. حقوقِ بالای سقف، بیمه‌ی
بیش از واقع کسر می‌کرد.

**نرخِ بیمه‌ی بیکاری و مشاغل سخت.** فقط سهمِ کارمند و کارفرما وجود داشت.

**ضریبِ معافیتِ بیمه از مالیات.** `taxable = ناخالص − سهمِ بیمه` بود، یعنی ضریبِ
۱ ثابت در کد. (ضریبِ بیمه‌ی تکمیلی و درمان در `0139` می‌آید، کنارِ عاملی که
معلوم می‌کند کدام ردیفِ کسور کدام است — بی آن، ستون بی‌مصرف بود.)

## هیچ عددی عوض نمی‌شود

پیش‌فرضِ هر ستون **دقیقاً همان رفتارِ امروز** است:

    سقفِ بیمه              = ۰      ← صفر یعنی «بی‌سقف»، رفتارِ فعلی
    نرخِ بیکاری / سخت       = ۰      ← امروز اصلاً اعمال نمی‌شوند
    ضریبِ عیدی             = ۲      ← همان `base * 2`
    روزهای سنوات در سال     = ۳۰     ← همان یک‌ماه‌به‌ازای‌هر‌سال
    روزهای ماه             = ۳۰     ← همان `_DAILY_DIVISOR`
    ساعتِ ماهانه            = ۱۹۴    ← همان `STANDARD_MONTHLY_HOURS`
    ضریبِ اضافه‌کار          = ۱٫۴    ← همان `OVERTIME_MULTIPLIER`
    ضریبِ معافیتِ بیمه       = ۱      ← همان کسرِ کاملِ سهمِ بیمه
    رندِ پرداخت             = ۰ رقم  ← یعنی بدونِ رند
    مالیاتِ منفی            = ممنوع   ← همان `max(0, …)` که در کد بود

پس `UPDATE`ی روی داده لازم نیست و هیچ فیشی، بسته یا باز، تکان نمی‌خورد. عدد از
فردا **در تنظیمات** است و ویرایش‌شدنی — به‌جای اینکه در کد باشد.
"""
import sqlalchemy as sa
from alembic import op

revision = "0138"
down_revision = "0137"
branch_labels = None
depends_on = None


#: (نام، نوع، پیش‌فرضِ سرور) — پیش‌فرض‌ها عمداً همان ثابت‌های امروزند.
_COLUMNS = (
    ("insurance_daily_ceiling", sa.Numeric(18, 0), "0"),
    ("unemployment_rate", sa.Numeric(5, 4), "0"),
    ("hard_job_rate", sa.Numeric(5, 4), "0"),
    ("eidi_base_multiplier", sa.Numeric(5, 2), "2"),
    ("severance_days_per_year", sa.Integer(), "30"),
    ("monthly_work_days", sa.Numeric(5, 2), "30"),
    ("standard_monthly_hours", sa.Numeric(6, 2), "194"),
    ("overtime_multiplier", sa.Numeric(5, 2), "1.4"),
    ("tax_exempt_coef_social", sa.Numeric(5, 4), "1"),
    ("payment_rounding_digits", sa.Integer(), "0"),
)

_CHECKS = (
    ("ck_payroll_settings_ceiling", "insurance_daily_ceiling >= 0"),
    ("ck_payroll_settings_unemployment_rate", "unemployment_rate >= 0 AND unemployment_rate <= 1"),
    ("ck_payroll_settings_hard_job_rate", "hard_job_rate >= 0 AND hard_job_rate <= 1"),
    ("ck_payroll_settings_eidi_multiplier", "eidi_base_multiplier > 0 AND eidi_base_multiplier <= 12"),
    ("ck_payroll_settings_severance_days", "severance_days_per_year > 0 AND severance_days_per_year <= 365"),
    ("ck_payroll_settings_month_days", "monthly_work_days > 0 AND monthly_work_days <= 31"),
    ("ck_payroll_settings_month_hours", "standard_monthly_hours > 0 AND standard_monthly_hours <= 744"),
    ("ck_payroll_settings_overtime_multiplier", "overtime_multiplier > 0 AND overtime_multiplier <= 10"),
    ("ck_payroll_settings_coef_social", "tax_exempt_coef_social >= 0 AND tax_exempt_coef_social <= 1"),
    ("ck_payroll_settings_rounding_digits", "payment_rounding_digits >= 0 AND payment_rounding_digits <= 6"),
)


def upgrade() -> None:
    for name, type_, default in _COLUMNS:
        op.add_column(
            "payroll_settings",
            sa.Column(name, type_, nullable=False, server_default=default),
        )
    #: «مالیاتِ منفی محاسبه نشود» یک *سیاست* است، نه یک `if` پراکنده در فرمول.
    #: پیش‌فرضِ `false` همان رفتارِ امروز است — امروز هیچ‌جا منفی برنمی‌گردد.
    op.add_column(
        "payroll_settings",
        sa.Column("allow_negative_tax", sa.Boolean(), nullable=False, server_default="false"),
    )
    for name, condition in _CHECKS:
        op.create_check_constraint(name, "payroll_settings", condition)

    #: **تعدیلِ رند روی خودِ فیش می‌نشیند، نه فقط در سند.**
    #:
    #: بی این ستون، گِردکردنِ خالص تساویِ «خالص = ناخالص − بیمه − مالیات − قسط −
    #: سایر کسورات» را می‌شکست و گاردِ `assert_breakdown_matches` صدور را متوقف
    #: می‌کرد — به‌درستی، چون آن‌وقت عددِ فیش ناتوضیح‌پذیر می‌شد. با این ستون،
    #: تعدیل یک ردیفِ دیدنیِ فیش است و کارمند می‌داند چند ریال بابتِ رند است.
    #:
    #: صفر روی همه‌ی فیش‌های موجود = دقیقاً رفتارِ امروز، چون رندِ پیش‌فرض صفر است.
    op.add_column(
        "payslips",
        sa.Column("rounding_adjustment", sa.Numeric(18, 0), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("payslips", "rounding_adjustment")
    for name, _condition in _CHECKS:
        op.drop_constraint(name, "payroll_settings", type_="check")
    op.drop_column("payroll_settings", "allow_negative_tax")
    for name, _type, _default in reversed(_COLUMNS):
        op.drop_column("payroll_settings", name)
