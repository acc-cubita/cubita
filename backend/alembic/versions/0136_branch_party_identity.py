"""شعبه‌ی بیمه و مالیات یک اسمِ متنی بود، نه یک هویتِ قابلِ ردیابی

Revision ID: 0136
Revises: 0134

## نقصی که بسته می‌شود

`insurance_tax_branches` تا امروز چهار ستون داشت: `code`، `name`، `kind`،
`is_active`. یعنی «شعبه ۱۲ تأمین اجتماعی» یک **رشته** بود و بس.

این تا وقتی بی‌ضرر است که شعبه فقط برچسب باشد. ولی نیست: بدهیِ بیمه و مالیاتِ
تکلیفیِ حقوق **به همان سازمان پرداخت می‌شود**، و آن پرداخت طرفِ حساب می‌خواهد —
یک `Contact` با تفصیلیِ خودش. تا امروز این دو هیچ پیوندی نداشتند، پس:

    فیشِ حقوق  →  «مالیات پرداختنی»  →  ؟
                   «بیمه پرداختنی»    →  ؟

کسی که بخواهد بداند «بدهیِ ما به حوزه‌ی مالیاتیِ شمالِ تهران چه‌قدر است»،
جوابی ندارد — چون آن حوزه در دفترِ کوبیتا **وجود ندارد**؛ فقط نامش روی قرارداد
نشسته.

## چرا `contact_id` و نه یک زیرسیستمِ موازی

کوبیتا از قبل مِسترِ طرف حساب را دارد، و طرف حساب از قبل تفصیلی دارد
(`contacts.analytic_id`). پس هویتِ حسابداریِ شعبه **ساخته نمی‌شود، وصل می‌شود**:

    شعبه ──contact_id──▶ طرف حساب ──analytic_id──▶ تفصیلی

این عمداً پیوند به *طرف حساب* است و نه به تفصیلی: کدِ تفصیلی رشته‌ای است که
کاربر می‌تواند عوضش کند، و پیوندِ متنی همان چیزی است که این مهاجرت دارد از بین
می‌برد. شناسه‌ی پایدارِ طرف حساب ثابت می‌ماند حتی اگر کد و عنوان عوض شوند.

## `nullable` می‌ماند — و این تصمیم است، نه تنبلی

شعبه‌های ثبت‌شده‌ی امروز طرف حساب ندارند و حدس‌زدنش ممکن نیست: نامِ «شعبه ۱۲»
با هیچ طرف‌حسابی تطبیق قطعی ندارد، و اتصالِ اشتباه بدتر از اتصالِ نداشته است.
پس **بدونِ backfill**: شعبه‌ی بی‌طرف‌حساب دقیقاً همان‌طور کار می‌کند که تا دیروز
می‌کرد، و کاربر هر وقت خواست وصلش می‌کند.

`ondelete="SET NULL"` هم به همین دلیل: حذفِ یک طرف حساب نباید شعبه‌ای را که
روی ده‌ها قرارداد نشسته از بین ببرد.

## نوعِ سوم: بیمه‌ی تکمیلی

کرکره‌ی «نوع» در همان فرم **سه** گزینه دارد: تأمین اجتماعی، وزارت دارایی، بیمه
تکمیلی. پس `BRANCH_KINDS` از دوتایی به سه‌تایی می‌رود و قیدِ `kind` بازساخته
می‌شود. (`salary_contracts.supplementary_branch` فعلاً متنِ آزاد می‌ماند —
مهاجرتش به پیوند وقتی است که معلوم شود چه محاسبه‌ای می‌کند.)

## هسته‌ی مشترکِ ثبتِ قانونی

فهرستِ شعب ستون‌هایی دارد که هر سه نوع در همان جدول نشان می‌دهند: کد شرکت /
شماره پرونده، شماره پیمان، نفرات معاف از بیمه، نحوه محاسبه مالیات، نام کارگاه،
نام کارفرما، نشانی کارگاه. این‌ها روی همین مِستر می‌نشینند، نه روی سه جدولِ
جدا.

`registration_code` عمداً **عمومی** نام‌گذاری شده و نه `tax_file_number`:
برچسبِ فرم خودش ترکیبی است («کد شرکت / شماره پرونده») و معنایش با نوعِ شعبه عوض
می‌شود — پرونده‌ی مالیاتی برای حوزه، کدِ کارگاه برای تأمین اجتماعی. هیچ
اعتبارسنجیِ طول/قالب روی آن نیست چون هیچ‌جا اثبات نشده.

## و یک قید که کارِ اصلیِ این فصل است

    ردیفِ مالیاتی:        نحوه محاسبه مالیات = تعدیل ماهانه
    ردیفِ تأمین اجتماعی:  نحوه محاسبه مالیات = خالی

یعنی **وجودِ میدان در فرمِ مشترک ≠ کاربردش برای هر نوع**. و این باید سمتِ سرور
فهمیده شود، نه با غیرفعال‌کردنِ یک ورودی در مرورگر — وگرنه یک درخواستِ مستقیمِ
API روشی بی‌معنا را روی شعبه‌ی بیمه می‌نشاند:

    CHECK (tax_calculation_method = '' OR kind = 'tax')

فهرستِ مقادیر هم به همان سه‌تای دیده‌شده بسته است — همان کاری که `0131` با
`FREIGHT_BASES` کرد. **و هنوز هیچ محاسبه‌ای نمی‌خواندش:** موتورِ مالیاتِ امروز
تعدیلِ تجمیعی می‌کند و این ستون داده‌ی ثبتِ قانونی است، نه سوییچِ محاسبه.

## عکسِ شعبه روی فیش

فایلِ بیمه امروز شعبه را از مِسترِ **جاری** می‌خواند. یعنی اگر کارگاه دوباره
ثبت شود و کدش عوض شود، بازتولیدِ فایلِ پارسال عددِ امسال را می‌دهد — بی‌صدا.

پس فیش شعبه‌ی مؤثرِ لحظه‌ی صدور را **عکس می‌گیرد**، همان‌طور که
`payslip_lines.factor_name` از قبل می‌گیرد. و این دقیقاً عکسِ تصمیمِ **هویتِ
کارمند** است، به دلیلی روشن: اصلاحِ نامِ یک آدم غلطِ تایپی را درست می‌کند و باید
به فایل برسد؛ ثبتِ تازه‌ی کارگاه رویدادِ واقعیِ تازه‌ای است و نباید گذشته را
بازنویسی کند.

`NULL` یعنی فیشِ پیش از این مهاجرت — خروجی برایشان به حلِ زنده برمی‌گردد، چون
عکسی نیست که برگردانده شود.

## آنچه این مهاجرت **نمی‌سازد**

* **نرخِ بیمه روی شعبه.** نه سهمِ کارمند، نه سهمِ کارفرما، نه بیمه‌ی بیکاری، نه
  سقف و کف. فرمِ شعبه هیچ‌کدام را ندارد؛ این مِستر **ثبت** است نه نرخ، و نرخ از
  `payroll_settings` می‌آید.
* **«کدام کارمندان معاف‌اند» از روی `insurance_exempt_count`.** آن عدد سرصفحه‌ی
  ثبتِ کارگاه است؛ معافیتِ واقعی کارمند‌به‌کارمند روی خودِ حکم نشسته
  (`exempt_employee_insurance`). ترکیبشان یعنی دو حقیقت.
* **قاعده‌ی ثبتیِ مرکز هزینه.** ستون ذخیره می‌شود، ولی هیچ سندی از رویش زده
  نمی‌شود: نقشش در حسابداریِ حقوق هیچ‌جا اثبات نشده.
* **یکی‌کردنِ کارگاه با محل خدمت.** `service_locations` سرِ جایش می‌ماند؛
  کارگاهِ ثبت‌شده زمینه‌ی *قانونی* است و محلِ خدمت زمینه‌ی *استخدامی*.
* **کلیدِ خارجی از شماره‌ی پیمان به حکم.** «شماره پیمان» قراردادِ کارفرما با
  مرجع است، نه قراردادِ استخدامیِ کارمند.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0136"
down_revision: Union[str, None] = "0134"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: هر سه گزینه‌ی کرکره‌ی «نوع» در فرمِ شعبه. تا امروز فقط دوتا مجاز بود.
BRANCH_KINDS = ("insurance", "tax", "supplementary")

#: فقط مقادیرِ **دیده‌شده** — همان قاعده‌ی `FREIGHT_BASES` در `0131`: قید این‌جاست
#: تا روشی که موتوری برایش وجود ندارد از درِ پشتی وارد پایگاه داده نشود.
TAX_CALC_METHODS = ("monthly", "annual", "none")

#: ستون‌های متنیِ هسته‌ی مشترکِ ثبت. همه پیش‌فرضِ خالی دارند، پس هیچ شعبه‌ی
#: موجودی تکان نمی‌خورد.
_TEXT_COLUMNS = (
    ("registration_code", sa.String(50)),
    ("workplace_name", sa.String(200)),
    ("workplace_address", sa.Text()),
    ("employer_name", sa.String(200)),
    ("agreement_number", sa.String(50)),
    ("tax_calculation_method", sa.String(30)),
)

#: عکسِ شعبه روی فیش. `NULL` یعنی «فیشِ پیش از این مهاجرت» و خروجی برای آن به
#: حلِ زنده برمی‌گردد — پس **بدونِ backfill**: عکس‌گرفتنِ *امروز* از فیشی که
#: پارسال صادر شده دقیقاً همان دروغی است که این ستون‌ها برای جلوگیری‌اش هستند.
_SNAPSHOT_COLUMNS = (
    ("insurance_branch_id", UUID(as_uuid=True)),
    ("insurance_branch_code", sa.String(20)),
    ("insurance_branch_name", sa.String(150)),
    ("tax_branch_id", UUID(as_uuid=True)),
    ("tax_branch_code", sa.String(20)),
    ("tax_branch_name", sa.String(150)),
)


def _quoted(values) -> str:
    return ", ".join(f"'{v}'" for v in values)


def upgrade() -> None:
    op.add_column(
        "insurance_tax_branches",
        sa.Column("contact_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_insurance_tax_branches_contact",
        "insurance_tax_branches",
        "contacts",
        ["contact_id"],
        ["id"],
        ondelete="SET NULL",
    )
    #: ایندکس چون پرسشِ طبیعیِ این ستون وارونه است: «کدام شعبه به این طرف حساب
    #: وصل است؟» — از سمتِ صورت‌حسابِ سازمان، نه از سمتِ شعبه.
    op.create_index(
        "ix_insurance_tax_branches_contact_id",
        "insurance_tax_branches",
        ["contact_id"],
    )

    # ── نوعِ سوم ───────────────────────────────────────────────────────────────
    op.drop_constraint("ck_insurance_tax_branches_kind", "insurance_tax_branches")
    op.create_check_constraint(
        "ck_insurance_tax_branches_kind",
        "insurance_tax_branches",
        f"kind IN ({_quoted(BRANCH_KINDS)})",
    )

    # ── هسته‌ی مشترکِ ثبتِ قانونی ──────────────────────────────────────────────
    for name, type_ in _TEXT_COLUMNS:
        op.add_column(
            "insurance_tax_branches",
            sa.Column(name, type_, server_default="", nullable=False),
        )
    op.add_column(
        "insurance_tax_branches",
        sa.Column("insurance_exempt_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "insurance_tax_branches",
        sa.Column("cost_center_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_insurance_tax_branches_cost_center",
        "insurance_tax_branches",
        "cost_centers",
        ["cost_center_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_insurance_tax_branches_cost_center_id",
        "insurance_tax_branches",
        ["cost_center_id"],
    )
    op.create_check_constraint(
        "ck_insurance_tax_branches_exempt_count",
        "insurance_tax_branches",
        "insurance_exempt_count >= 0",
    )

    # ── سیاستِ نوع‌محور، در خودِ پایگاه داده ────────────────────────────────────
    op.create_check_constraint(
        "ck_insurance_tax_branches_tax_method_is_tax_only",
        "insurance_tax_branches",
        "tax_calculation_method = '' OR kind = 'tax'",
    )
    op.create_check_constraint(
        "ck_insurance_tax_branches_tax_method",
        "insurance_tax_branches",
        f"tax_calculation_method = '' OR tax_calculation_method IN ({_quoted(TAX_CALC_METHODS)})",
    )

    # ── عکسِ شعبه روی فیش ──────────────────────────────────────────────────────
    for name, type_ in _SNAPSHOT_COLUMNS:
        op.add_column("payslips", sa.Column(name, type_, nullable=True))
    for column in ("insurance_branch_id", "tax_branch_id"):
        op.create_foreign_key(
            f"fk_payslips_{column}",
            "payslips",
            "insurance_tax_branches",
            [column],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    for column in ("insurance_branch_id", "tax_branch_id"):
        op.drop_constraint(f"fk_payslips_{column}", "payslips", type_="foreignkey")
    for name, _ in _SNAPSHOT_COLUMNS:
        op.drop_column("payslips", name)

    op.drop_constraint("ck_insurance_tax_branches_tax_method", "insurance_tax_branches")
    op.drop_constraint("ck_insurance_tax_branches_tax_method_is_tax_only", "insurance_tax_branches")
    op.drop_constraint("ck_insurance_tax_branches_exempt_count", "insurance_tax_branches")
    op.drop_index("ix_insurance_tax_branches_cost_center_id", table_name="insurance_tax_branches")
    op.drop_constraint(
        "fk_insurance_tax_branches_cost_center", "insurance_tax_branches", type_="foreignkey"
    )
    op.drop_column("insurance_tax_branches", "cost_center_id")
    op.drop_column("insurance_tax_branches", "insurance_exempt_count")
    for name, _ in _TEXT_COLUMNS:
        op.drop_column("insurance_tax_branches", name)

    #: شعبه‌های «بیمه تکمیلی» پیش از تنگ‌کردنِ قید باید بروند، وگرنه قیدِ دوتایی
    #: روی داده‌ی موجود نمی‌نشیند و `downgrade` وسطِ کار می‌شکند.
    op.execute("DELETE FROM insurance_tax_branches WHERE kind = 'supplementary'")
    op.drop_constraint("ck_insurance_tax_branches_kind", "insurance_tax_branches")
    op.create_check_constraint(
        "ck_insurance_tax_branches_kind",
        "insurance_tax_branches",
        "kind IN ('insurance', 'tax')",
    )

    op.drop_index("ix_insurance_tax_branches_contact_id", table_name="insurance_tax_branches")
    op.drop_constraint(
        "fk_insurance_tax_branches_contact", "insurance_tax_branches", type_="foreignkey"
    )
    op.drop_column("insurance_tax_branches", "contact_id")
