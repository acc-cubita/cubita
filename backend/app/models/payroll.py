import uuid
from datetime import date as date_

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.tenant import TenantMixin

PAYROLL_PERIOD_STATUSES = ("draft", "finalized")

#: چرخه‌ی عمرِ وامِ پرسنلی. `settled` یعنی همه‌ی اقساط کسر شده‌اند؛ `cancelled`
#: یعنی وام لغو شد و اقساطِ کسرنشده‌اش دیگر سررسید نمی‌شوند.
LOAN_STATUSES = ("active", "settled", "cancelled")

# ── جدول‌های مرجعِ حقوق و دستمزد ───────────────────────────────────────────────
#
# جریانِ استخدام از طرف‌حساب شروع می‌شود: اول شخص در «طرف حساب جدید» با تیکِ «کارمند»
# ثبت می‌شود، بعد این‌جا برایش «قرارداد جدید» زده می‌شود. این جدول‌ها فهرست‌هایی‌اند
# که آن فرم از آن‌ها انتخاب می‌کند.

#: رسته شغل — فهرستِ بسته‌ی سپیدار (مبنای کدِ شغلِ بیمه).
JOB_FAMILIES = (
    "مالی", "مهندسی فرهنگی", "امور اجتماعی", "فناوری اطلاعات", "بهداشت و درمان",
    "فنی مهندسی", "خدمات", "کشاورزی و محیط زیست", "بازاریابی و فروش", "حراست و نگهبانی",
    "کارگری", "ترابری", "تولیدی", "کنترل کیفی", "تحقیقات", "انبارداری", "فضا",
    "اعضای هیئت علمی دانشگاه",
)

#: نوعِ استخدام — فهرستِ بسته‌ی سپیدار.
EMPLOYMENT_TYPES = (
    "سایر", "پیمانی", "رسمی", "رسمی آزمایشی", "قراردادی", "روزمزد", "خرید خدمت",
    "مأمور", "ساعتی", "رسمی فصلی", "کارمزدی", "شرکتی",
)

#: نوعِ قرارداد. «استخدام» اولین قراردادِ هر شخص است و «اصلاح قرارداد» هر قراردادِ
#: بعدی — پس تا وقتی استخدام ثبت نشده، اصلاح معنایی ندارد.
CONTRACT_TYPES = ("hire", "amend")
CONTRACT_TYPE_LABELS = {"hire": "استخدام", "amend": "اصلاح قرارداد"}

FACTOR_CATEGORIES = ("benefit", "deduction")
FACTOR_CATEGORY_LABELS = {"benefit": "مزایا", "deduction": "کسورات"}
FACTOR_KINDS = ("fixed", "variable")
FACTOR_KIND_LABELS = {"fixed": "قراردادی (ثابت)", "variable": "متغیر"}

#: کلیدِ سیستمیِ عامل — پلِ عاملِ کاربر به ستون‌های موتورِ فیشِ حقوقی. خالی یعنی
#: عاملِ ساخته‌ی کاربر که در «سایر مزایا» جمع می‌شود.
FACTOR_SYSTEM_KEYS = ("", "base", "housing", "food", "child")
DEFAULT_FACTORS = (
    ("حقوق پایه", "base"),
    ("حق مسکن", "housing"),
    ("حق خواروبار", "food"),
    ("حق اولاد", "child"),
)

TAX_GROUP_KINDS = ("normal", "deprived", "exempt")
TAX_GROUP_KIND_LABELS = {
    "normal": "مناطق عادی",
    "deprived": "مناطق محروم",
    "exempt": "معاف",
}
#: درصدِ پیش‌فرضِ هر نوع — کاربر می‌تواند عوضش کند، ولی این‌ها نقطه‌ی شروع‌اند.
TAX_GROUP_DEFAULT_PERCENT = {"normal": 100, "deprived": 50, "exempt": 0}

#: سه نوعِ شعبه‌ی قانونی — **هر سه در همان فرم و همان فهرست**، نه سه زیرسیستمِ
#: موازی. «بیمه تکمیلی» نوعِ سومِ همان کرکره است، پس `supplementary_branch`ِ
#: متنیِ روی حکم باید سرانجام به همین مِستر برسد.
BRANCH_KINDS = ("insurance", "tax", "supplementary")
BRANCH_KIND_LABELS = {
    "insurance": "شعبه بیمه",
    "tax": "حوزه مالیاتی",
    "supplementary": "بیمه تکمیلی",
}

#: «نحوه محاسبه مالیات» — **فقط برای حوزه‌ی مالیاتی**.
#:
#: در فهرستِ شعب، ردیفِ مالیاتی «تعدیل ماهانه» دارد و ردیفِ تأمین اجتماعی همین
#: ستون را **خالی** نشان می‌دهد. یعنی وجودِ میدان در فرمِ مشترک به معنای
#: کاربردش برای هر نوع نیست، و این تفاوت باید سمتِ سرور فهمیده شود نه فقط با
#: غیرفعال‌کردنِ یک ورودی در مرورگر.
#:
#: فهرست عمداً به همان مقادیرِ **دیده‌شده** بسته است — همان کاری که `0131` با
#: `FREIGHT_BASES` کرد: قید این‌جاست تا روشی که موتوری برایش وجود ندارد از درِ
#: پشتی وارد پایگاه داده نشود.
#:
#: **و هنوز مصرف نمی‌شود:** موتورِ مالیاتِ امروز تعدیلِ تجمیعی انجام می‌دهد و این
#: ستون را نمی‌خواند. داده‌ی ثبتِ قانونی است، نه سوییچِ محاسبه.
#: هدفِ محاسبه‌ی یک جدولِ مالیات. فقط دو مقدارِ **دیده‌شده** — «حقوق» و «عیدی» —
#: و قید این‌جاست تا هدفی که موتوری برایش وجود ندارد وارد پایگاه داده نشود.
#: افزودنِ هدفِ سوم یک مهاجرتِ یک‌خطی است؛ ساختارِ جدول هیچ‌جا «دقیقاً دو» را فرض
#: نمی‌کند و همین مهم است.
TAX_CALC_PURPOSES = ("salary", "eidi")
TAX_CALC_PURPOSE_LABELS = {"salary": "حقوق", "eidi": "عیدی"}

TAX_CALC_METHODS = ("monthly", "annual", "none")
TAX_CALC_METHOD_LABELS = {
    "monthly": "تعدیل ماهانه",
    "annual": "تعدیل سالانه",
    "none": "بدون تعدیل",
}



#: جهتِ اثرِ یک قلمِ فیش روی خالص.
PAYSLIP_LINE_DIRECTIONS = ("earning", "deduction")

#: از کجا آمده — تا کاربر بداند برای عوض‌کردنش کجا باید برود.
PAYSLIP_LINE_ORIGINS = ("contract", "attendance", "settings", "loan")


class Employee(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "employees"

    __table_args__ = (
        UniqueConstraint("tenant_id", "national_id", name="uq_employees_tenant_national_id"),
    )

    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    national_id: Mapped[str] = mapped_column(String(20), index=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    bank_account_number: Mapped[str] = mapped_column(String(50), default="")
    hire_date: Mapped[date_] = mapped_column(Date)
    termination_date: Mapped[date_ | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    contracts: Mapped[list["SalaryContract"]] = relationship(back_populates="employee", order_by="SalaryContract.effective_from")


class SalaryContract(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """قراردادِ حقوقی. قراردادِ جاری یک کارمند در تاریخ X = آخرینی که `effective_from` آن <= X است.

    **`effective_from` همان «تاریخ صدور»ِ فرمِ سپیدار است** — یعنی «محاسبه‌ی حقوق از
    این تاریخ شروع می‌شود». ستونِ دومی برایش نساختیم چون دو تاریخ برای یک معنا،
    بالاخره از هم عقب می‌مانند.

    سه تاریخ سه معنای متفاوت دارند و هیچ‌کدام جای دیگری را نمی‌گیرند:

    * `effective_from` (تاریخ صدور) — محاسبه از این‌جا شروع می‌شود.
    * `valid_until` (تاریخ اعتبار) — تا این‌جا طبقِ همین قرارداد محاسبه می‌شود.
    * `service_end_date` (تاریخ پایان خدمت) — از این‌جا به بعد کارکرد اصلاً محاسبه
      نمی‌شود.

    و **تاریخ استخدام** اصلاً این‌جا نیست: واقعیتِ *شخص* است نه این قرارداد، پس روی
    `employees.hire_date` می‌نشیند. عمداً می‌تواند سال‌ها قبل از تاریخِ صدور باشد —
    شرکتی که تا دیروز با اکسل حقوق می‌داد، کارمندش را که تازه استخدام نکرده.
    """

    __tablename__ = "salary_contracts"
    __table_args__ = (
        CheckConstraint(f"contract_type IN {CONTRACT_TYPES}", name="ck_salary_contracts_type"),
        CheckConstraint(
            "employer_exempt_percent >= 0 AND employer_exempt_percent <= 100 "
            "AND housing_loan_exempt_amount >= 0",
            name="ck_salary_contracts_percent",
        ),
        CheckConstraint(
            "(valid_until IS NULL OR valid_until >= effective_from) "
            "AND (service_end_date IS NULL OR service_end_date >= effective_from)",
            name="ck_salary_contracts_dates",
        ),
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), index=True)
    effective_from: Mapped[date_] = mapped_column(Date)

    # ── سرصفحه ────────────────────────────────────────────────────────────────
    #: «استخدام» اولین قراردادِ هر شخص است؛ سرویس نمی‌گذارد دومی هم استخدام باشد و
    #: نمی‌گذارد اولی اصلاح باشد.
    contract_type: Mapped[str] = mapped_column(String(20), default="hire", server_default="hire")
    number: Mapped[str] = mapped_column(String(30), default="", server_default="")
    valid_until: Mapped[date_ | None] = mapped_column(Date, nullable=True)
    service_end_date: Mapped[date_ | None] = mapped_column(Date, nullable=True)

    # ── اطلاعات استخدامی ──────────────────────────────────────────────────────
    employment_type: Mapped[str] = mapped_column(String(30), default="", server_default="")
    service_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("service_locations.id", ondelete="SET NULL"), nullable=True
    )
    job_title_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_titles.id", ondelete="SET NULL"), nullable=True
    )
    #: مرکز هزینه جدولِ خودش را دارد و این‌جا فقط به آن وصل می‌شویم — هزینه‌ی حقوق
    #: باید در همان گزارشِ مرکز هزینه‌ای دیده شود که بقیه‌ی هزینه‌ها دیده می‌شوند.
    cost_center_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cost_centers.id", ondelete="SET NULL"), nullable=True
    )

    # ── حقوق و مزایای ثابت (ستونی) ────────────────────────────────────────────
    #: این چهار ستون ورودیِ موتورِ فیشِ حقوقی‌اند و **دیگر مستقیم پر نمی‌شوند**:
    #: سرویس آن‌ها را از `lines` می‌سازد (`PayrollFactor.system_key` می‌گوید کدام
    #: ردیف کدام ستون است و بقیه در `other_allowance` جمع می‌شوند). قراردادهای
    #: قدیمی ردیف ندارند و مقادیرِ ستونی‌شان دست‌نخورده کار می‌کنند.
    base_salary: Mapped[float] = mapped_column(Numeric(18, 0))
    housing_allowance: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    food_allowance: Mapped[float] = mapped_column(Numeric(18, 0), default=0)
    other_allowance: Mapped[float] = mapped_column(Numeric(18, 0), default=0)

    # ── سایر اطلاعات: بیمه و مالیات ───────────────────────────────────────────
    tax_group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payroll_tax_groups.id", ondelete="SET NULL"), nullable=True
    )
    tax_branch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("insurance_tax_branches.id", ondelete="SET NULL"), nullable=True
    )
    insurance_branch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("insurance_tax_branches.id", ondelete="SET NULL"), nullable=True
    )
    housing_loan_exempt_amount: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    is_insured: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    is_hard_job: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    exempt_employee_insurance: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    exempt_employer_insurance: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    employer_exempt_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=0, server_default="0")
    exempt_unemployment_insurance: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    employer_name: Mapped[str] = mapped_column(String(200), default="", server_default="")
    has_supplementary_insurance: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    supplementary_branch: Mapped[str] = mapped_column(String(150), default="", server_default="")
    supplementary_insurer: Mapped[str] = mapped_column(String(150), default="", server_default="")
    description: Mapped[str] = mapped_column(Text, default="", server_default="")

    employee: Mapped["Employee"] = relationship(back_populates="contracts")
    lines: Mapped[list["SalaryContractLine"]] = relationship(
        back_populates="contract", cascade="all, delete-orphan"
    )


class PayrollPeriod(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "payroll_periods"
    __table_args__ = (
        CheckConstraint(f"status IN {PAYROLL_PERIOD_STATUSES}", name="ck_payroll_periods_status"),
        CheckConstraint("month BETWEEN 1 AND 12", name="ck_payroll_periods_month_range"),
        UniqueConstraint("tenant_id", "year", "month", name="uq_payroll_periods_tenant_year_month"),
    )

    year: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="draft")


class Attendance(TenantMixin, UUIDPKMixin, Base):
    """کارکرد ماهانه‌ی ساده (حضور/غیاب دستی)؛ اتصال به دستگاه حضور و غیاب در فاز بعد."""

    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint("tenant_id", "employee_id", "period_id", name="uq_attendance_tenant_employee_id_period_id"),
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), index=True)
    period_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("payroll_periods.id"), index=True)
    worked_days: Mapped[float] = mapped_column(Numeric(5, 2), default=30)
    absent_days: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    overtime_hours: Mapped[float] = mapped_column(Numeric(6, 2), default=0)


class Payslip(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """فیش حقوقی. اعداد در لحظه‌ی صدور از روی حکم حقوقی جاری و کارکرد همان دوره محاسبه و اسنپ‌شات می‌شوند."""

    __tablename__ = "payslips"
    __table_args__ = (
        UniqueConstraint("tenant_id", "number", name="uq_payslips_tenant_number"),
        UniqueConstraint("tenant_id", "employee_id", "period_id", name="uq_payslips_tenant_employee_id_period_id"),
    )

    number: Mapped[int | None] = mapped_column(nullable=True, index=True)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), index=True)
    period_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("payroll_periods.id"), index=True)

    base_salary: Mapped[float] = mapped_column(Numeric(18, 0))
    allowances_total: Mapped[float] = mapped_column(Numeric(18, 0))
    overtime_pay: Mapped[float] = mapped_column(Numeric(18, 0))
    gross_pay: Mapped[float] = mapped_column(Numeric(18, 0))
    insurance_employee_share: Mapped[float] = mapped_column(Numeric(18, 0))
    insurance_employer_share: Mapped[float] = mapped_column(Numeric(18, 0))
    taxable_pay: Mapped[float] = mapped_column(Numeric(18, 0))
    tax_amount: Mapped[float] = mapped_column(Numeric(18, 0))
    #: دو کسورِ بعد از مالیات. جدا نگه داشته می‌شوند چون دو منشأ دارند و کارمند حق
    #: دارد بداند کدام است: قسطِ وام خودکار از ماژولِ وام می‌آید، «سایر کسورات» از
    #: ردیف‌های کسوراتِ قراردادِ خودش. با این دو، فیش دوباره جمع می‌زند:
    #: خالص = ناخالص − بیمه − مالیات − قسطِ وام − سایر کسورات
    loan_deduction: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    other_deductions: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    net_pay: Mapped[float] = mapped_column(Numeric(18, 0))

    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True, index=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    # ── عکسِ شعبه‌ی قانونیِ لحظه‌ی صدور ─────────────────────────────────────────
    #
    #: **چرا عکس و نه پیوند.** فایلِ بیمه و فایلِ مالیات باید *بازتولیدپذیر*
    #: باشند: اگر کارگاه سالِ بعد دوباره ثبت شود و کد یا نامش عوض شود، فایلِ
    #: پارسال باید همان چیزی را بدهد که پارسال داد. خواندنِ مِسترِ امروز یعنی
    #: خروجیِ یک دوره‌ی بسته بی‌صدا عوض شود.
    #:
    #: همان الگوی `PayslipLine.factor_name` که از قبل این‌جاست — و همان تفاوتی که
    #: با **هویتِ کارمند** دارد: اصلاحِ نامِ یک آدم باید به فایل برسد (غلطِ تایپی
    #: بوده)، ولی ثبتِ تازه‌ی کارگاه نباید گذشته را بازنویسی کند (رویدادِ واقعیِ
    #: تازه‌ای بوده).
    #:
    #: `NULL` یعنی فیشی که پیش از این مهاجرت صادر شده؛ خروجی برای آن‌ها به حلِ
    #: زنده برمی‌گردد، چون عکسی وجود ندارد که برگردانده شود.
    insurance_branch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("insurance_tax_branches.id", ondelete="SET NULL"), nullable=True
    )
    insurance_branch_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    insurance_branch_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    tax_branch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("insurance_tax_branches.id", ondelete="SET NULL"), nullable=True
    )
    tax_branch_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    tax_branch_name: Mapped[str | None] = mapped_column(String(150), nullable=True)

    #: **کدام قاعده این مالیات را ساخت.**
    #:
    #: `tax_amount` یک عدد بود و بس. با این پیوند می‌شود پرسید «مالیاتِ مرداد از
    #: کدام جدول آمد؟» و جواب گرفت — و تفکیکِ پله‌به‌پله از همین‌جا بازسازی
    #: می‌شود (`tax_breakdown`)، بی‌آنکه چیزی اضافه ذخیره شود.
    #:
    #: `RESTRICT` روی جدول: جدولی که فیشی به آن استناد کرده حذف‌شدنی نیست.
    #: `NULL` = فیشِ پیش از مهاجرتِ ۰۱۳۷.
    tax_table_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tax_tables.id", ondelete="RESTRICT"), nullable=True
    )

    #: تفکیکِ عامل‌به‌عاملِ همین فیش. **ستون‌های تجمیعیِ بالا حقیقتِ فیش‌اند** و این
    #: ردیف‌ها توضیحشان؛ سرویس هنگامِ صدور هر دو را با هم می‌نویسد و تستی جمعشان
    #: را مقابلِ هم می‌گذارد.
    lines: Mapped[list["PayslipLine"]] = relationship(
        back_populates="payslip", cascade="all, delete-orphan", order_by="PayslipLine.seq"
    )


class PayslipLine(TenantMixin, UUIDPKMixin, Base):
    """یک قلمِ فیش: کدام عامل، چه مبلغی، از کجا.

    **چرا لازم است.** فیش اعدادش را snapshot می‌گیرد و این درست است — حقوقِ تیر با
    جدولِ مالیاتِ مرداد بازمحاسبه نمی‌شود. ولی تا امروز snapshot در سطحِ *جمع* بود:
    `allowances_total` یک عدد، و هر عاملی که `housing`/`food` نبود اول در
    `other_allowance`ِ قرارداد جمع می‌شد و بعد در آن یک عدد. پس «این مبلغ از چه
    ساخته شد؟» جواب نداشت، و بازخواندنش از قرارداد هم جواب نمی‌دهد چون قرارداد
    می‌تواند از آن موقع عوض شده باشد.

    `factor_id` عمداً `NULL`پذیر است: حقوقِ پایه، بیمه، مالیات و قسطِ وام عاملِ
    تعریف‌شده‌ی کاربر نیستند. و `factor_name` عکسِ لحظه‌ی ثبت است، وگرنه تغییرِ
    نامِ یک عامل فیشِ پارسال را بازنویسی می‌کرد.
    """

    __tablename__ = "payslip_lines"
    __table_args__ = (
        CheckConstraint(f"direction IN {PAYSLIP_LINE_DIRECTIONS}", name="ck_payslip_lines_direction"),
        CheckConstraint(f"origin IN {PAYSLIP_LINE_ORIGINS}", name="ck_payslip_lines_origin"),
        UniqueConstraint("tenant_id", "payslip_id", "seq", name="uq_payslip_lines_seq"),
    )

    payslip_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payslips.id", ondelete="CASCADE"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer)
    factor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payroll_factors.id", ondelete="SET NULL"), nullable=True
    )
    factor_name: Mapped[str] = mapped_column(String(150))
    direction: Mapped[str] = mapped_column(String(10))
    origin: Mapped[str] = mapped_column(String(20))
    amount: Mapped[float] = mapped_column(Numeric(18, 0))
    note: Mapped[str] = mapped_column(Text, default="", server_default="")

    payslip: Mapped["Payslip"] = relationship(back_populates="lines")


class PayrollSettings(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """نرخ‌های بیمه/مالیات حقوق. این نرخ‌ها هرسال طبق قانون بودجه/تأمین اجتماعی تغییر می‌کنند —
    مقادیر seed شده صرفاً placeholder هستند و باید قبل از صدور فیش واقعی توسط کاربر تأیید/ویرایش شوند."""

    __tablename__ = "payroll_settings"

    __table_args__ = (
        UniqueConstraint("tenant_id", "year", name="uq_payroll_settings_tenant_year"),
    )

    year: Mapped[int] = mapped_column(Integer)
    insurance_employee_rate: Mapped[float] = mapped_column(Numeric(5, 4))
    insurance_employer_rate: Mapped[float] = mapped_column(Numeric(5, 4))
    tax_exemption_annual: Mapped[float] = mapped_column(Numeric(18, 0))
    # لیست پلکان مالیات سالانه: [{"up_to": <سقف تجمعی یا null برای نامحدود>, "rate": <نرخ 0..1>}, ...] به ترتیب صعودی
    tax_brackets: Mapped[list] = mapped_column(JSONB)
    #: حداقل حقوق ماهانه‌ی مصوبِ همان سال — پایه‌ی سقف/کفِ عیدی (۲ تا ۳ برابر). صفر = بدون سقف.
    min_base_wage: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    #: روزهای مرخصی استحقاقیِ سالانه (قانون کار: ۲۶ روز کاری).
    annual_leave_days: Mapped[int] = mapped_column(Integer, default=26, server_default="26")
    notes: Mapped[str] = mapped_column(Text, default="")


class LeaveRecord(TenantMixin, UUIDPKMixin, Base):
    """یک مرخصیِ استفاده‌شده. مانده‌ی مرخصی = استحقاقی − جمعِ همین رکوردها در همان سال."""

    __tablename__ = "leave_records"

    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), index=True)
    leave_date: Mapped[date_] = mapped_column(Date)
    days: Mapped[float] = mapped_column(Numeric(5, 2))
    note: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))


class BenefitRun(TenantMixin, UUIDPKMixin, Base):
    """ثبتِ صدورِ یک مزیت (عیدی/سنوات/بازخریدِ مرخصی) با سندِ حسابداری، تا دوباره صادر نشود."""

    __tablename__ = "benefit_runs"

    kind: Mapped[str] = mapped_column(String(20))  # eidi | severance | leave_payout
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    employee_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(18, 0))
    run_date: Mapped[date_] = mapped_column(Date)
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True, index=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))


class ServiceLocation(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """محل خدمت: انبار، شعبه‌ی ۳ فروشگاه، دفتر مرکزی.

    جایی که کارمند واقعاً کار می‌کند. جدا از مرکز هزینه است: مرکز هزینه می‌گوید
    هزینه‌اش به کدام حساب می‌رود، محل خدمت می‌گوید خودش کجاست. یک نفر می‌تواند در
    انبار کار کند ولی هزینه‌اش به مرکزِ «فروش» برود.
    """

    __tablename__ = "service_locations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_service_locations_tenant_code"),
    )

    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(150))
    name2: Mapped[str] = mapped_column(String(150), default="", server_default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class JobTitle(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """شغل: عنوانِ شغلیِ کارمند، به‌علاوه‌ی رسته و کدِ شغلِ بیمه.

    کدِ شغلِ بیمه در لیستِ تأمین اجتماعی لازم است؛ نگه‌داشتنش روی شغل یعنی هر کارمندِ
    آن شغل خودبه‌خود درست ثبت می‌شود، به‌جای اینکه هر بار دستی تایپ شود.
    """

    __tablename__ = "job_titles"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_job_titles_tenant_code"),)

    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(150))
    name2: Mapped[str] = mapped_column(String(150), default="", server_default="")
    job_family: Mapped[str] = mapped_column(String(50), default="", server_default="")
    insurance_job_code: Mapped[str] = mapped_column(String(30), default="", server_default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class PayrollFactor(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """یک عاملِ حقوق یا کسور: حقوق پایه، حق اولاد، بیمه‌ی تکمیلی، وام…

    `system_key` پلِ این جدول به موتورِ فیشِ حقوقی است. موتور روی چهار ستونِ
    `salary_contracts` حساب می‌کند؛ سرویس آن چهار را از ردیف‌های قرارداد می‌سازد و
    این کلید می‌گوید کدام ردیف کدام ستون است. عاملِ بی‌کلید در «سایر مزایا» جمع
    می‌شود — پس کاربر می‌تواند هرچه خواست بسازد بی‌آنکه محاسبه بشکند.
    """

    __tablename__ = "payroll_factors"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_payroll_factors_tenant_name"),
        CheckConstraint(f"category IN {FACTOR_CATEGORIES}", name="ck_payroll_factors_category"),
        CheckConstraint(f"kind IN {FACTOR_KINDS}", name="ck_payroll_factors_kind"),
        CheckConstraint(
            "system_key IN ('', 'base', 'housing', 'food', 'child')",
            name="ck_payroll_factors_system_key",
        ),
        #: هر کلیدِ سیستمی حداکثر یک عامل، وگرنه «حقوق پایه» دوتا می‌شود و ستونِ
        #: `base_salary` نمی‌داند از کدام ساخته شود.
        Index(
            "uq_payroll_factors_tenant_system_key", "tenant_id", "system_key",
            unique=True, postgresql_where=text("system_key <> ''"),
        ),
    )

    name: Mapped[str] = mapped_column(String(150))
    name2: Mapped[str] = mapped_column(String(150), default="", server_default="")
    category: Mapped[str] = mapped_column(String(20), default="benefit", server_default="benefit")
    kind: Mapped[str] = mapped_column(String(20), default="fixed", server_default="fixed")
    is_extraordinary: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    system_key: Mapped[str] = mapped_column(String(20), default="", server_default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class PayrollTaxGroup(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """گروه مالیاتی: مناطق عادی، مناطق محروم، معاف.

    `percent` می‌گوید چند درصد از مالیاتِ محاسبه‌شده واقعاً وصول می‌شود — مناطق محروم
    نصف، معاف صفر. عدد است نه پرچم، چون درصدِ تخفیفِ مناطق محروم قانوناً عوض می‌شود.
    """

    __tablename__ = "payroll_tax_groups"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_payroll_tax_groups_tenant_name"),
        CheckConstraint(f"kind IN {TAX_GROUP_KINDS}", name="ck_payroll_tax_groups_kind"),
        CheckConstraint("percent >= 0 AND percent <= 100", name="ck_payroll_tax_groups_percent"),
    )

    name: Mapped[str] = mapped_column(String(150))
    kind: Mapped[str] = mapped_column(String(20), default="normal", server_default="normal")
    percent: Mapped[float] = mapped_column(Numeric(5, 2), default=100, server_default="100")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class TaxTable(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """جدولِ مالیاتِ حقوق: یک قاعده‌ی قانونیِ تاریخ‌دار، نه «نرخِ جاری».

    تا امروز پلکانِ مالیات یک ستونِ JSONB روی `PayrollSettings` بود، یکتا روی
    `(مستأجر، سال)`. یعنی یک بُعد داشت — سال — در حالی که قاعده‌ی واقعی سه بُعد
    دارد:

        (تاریخِ اجرا، گروهِ مالیاتی، نوعِ محاسبه)  →  پلکان

    و این سه هم‌زمان لازم‌اند: در یک سال، «عادی» و «مناطق محروم» دو **جدولِ
    مستقل** دارند، و «حقوق» و «عیدی» هم دو جدولِ مستقلِ دیگر.

    **چرا تاریخِ اجرا و نه سال.** قانون لزوماً اولِ فروردین عوض نمی‌شود. جدولِ
    مؤثر آخرین جدولی است که `effective_from` آن از تاریخِ محاسبه نگذشته — و
    هرگز از روی *عنوان* پیدا نمی‌شود. عنوان فقط نمایشی است.

    **جدولِ تازه جای قبلی را نمی‌گیرد.** سالِ تازه یعنی رکوردِ تازه؛ جدول‌های
    سال‌های قبل می‌مانند تا محاسبه‌ی گذشته بازتولیدپذیر بماند.

    **شعبه این‌جا نیست، و عمداً.** «نحوه محاسبه مالیات» (تعدیل ماهانه/سالانه)
    روی شعبه می‌نشیند و می‌گوید *چطور* تعدیل شود؛ این جدول می‌گوید *چه نرخی* روی
    *چه پایه‌ای*. یک جدول را چند شعبه می‌توانند استفاده کنند.
    """

    __tablename__ = "tax_tables"
    __table_args__ = (
        CheckConstraint(
            f"calculation_type IN {TAX_CALC_PURPOSES}", name="ck_tax_tables_calculation_type"
        ),
        #: **یکتاییِ قاعده، نه یکتاییِ عنوان.** دو جدولِ هم‌زمان با همان گروه و
        #: همان نوعِ محاسبه، محاسبه را مبهم می‌کند و حل‌کننده باید بی‌صدا یکی را
        #: انتخاب کند — که همان چیزی است که نباید بشود.
        #:
        #: `COALESCE` چون «بی‌گروه» خودش یک حالتِ معتبر است: جدولِ پیش‌فرضی که
        #: برای حکم‌های بدونِ گروهِ مالیاتی به کار می‌رود.
        Index(
            "uq_tax_tables_scope",
            "tenant_id",
            "effective_from",
            "calculation_type",
            text("COALESCE(tax_group_id, '00000000-0000-0000-0000-000000000000'::uuid)"),
            unique=True,
        ),
    )

    #: عنوان و عنوانِ دوم — **فقط نمایشی**. حل‌کننده هرگز متنشان را نمی‌خواند.
    title: Mapped[str] = mapped_column(String(200))
    title2: Mapped[str] = mapped_column(String(200), default="", server_default="")

    #: تاریخِ شروعِ اعتبار. تاریخِ پایان عمداً ستون ندارد: از جدولِ بعدیِ همان
    #: دامنه مشتق می‌شود، و دو منبع برای یک بازه بالاخره از هم عقب می‌مانند.
    effective_from: Mapped[date_] = mapped_column(Date, index=True)

    #: `NULL` یعنی **جدولِ پیش‌فرض** — برای حکم‌هایی که گروهِ مالیاتی ندارند.
    tax_group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payroll_tax_groups.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    tax_group: Mapped["PayrollTaxGroup | None"] = relationship(lazy="joined")

    #: هدفِ محاسبه: حقوقِ ماهانه یا عیدی. **جدولِ حقوق برای عیدی به کار نمی‌رود**
    #: — پله‌ها و آستانه‌هایشان یکی نیستند.
    calculation_type: Mapped[str] = mapped_column(String(20), default="salary", server_default="salary")

    brackets: Mapped[list["TaxTableBracket"]] = relationship(
        back_populates="table", cascade="all, delete-orphan", order_by="TaxTableBracket.seq"
    )


class TaxTableBracket(TenantMixin, UUIDPKMixin, Base):
    """یک پله‌ی تصاعدیِ جدولِ مالیات.

    **مدلِ «سقفِ تجمعی» و نه «از/تا»** — تصمیمی که از پیاده‌سازیِ قبلی می‌آید و
    عمداً حفظ شد: با سقفِ تجمعی، مرزِ پایینِ هر پله سقفِ پله‌ی قبل است، پس
    **شکاف و همپوشانیِ پله‌ها ساختاراً ناممکن‌اند**. با `from/to`ِ آزاد هر دو
    ممکن‌اند و باید با اعتبارسنجی جلویشان گرفته شود؛ این‌جا موضوعیت ندارند.

    «مبلغ جزء» و «مبلغ کل» ستون ندارند: هر دو از سقف و نرخ **مشتق** می‌شوند، و
    ذخیره‌شان یعنی دو حقیقت که با ویرایشِ یک نرخ از هم جدا می‌افتند.
    """

    __tablename__ = "tax_table_brackets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "table_id", "seq", name="uq_tax_table_brackets_seq"),
        CheckConstraint("rate >= 0 AND rate <= 1", name="ck_tax_table_brackets_rate"),
        CheckConstraint("up_to IS NULL OR up_to > 0", name="ck_tax_table_brackets_up_to"),
    )

    table_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tax_tables.id", ondelete="CASCADE"), index=True
    )
    #: ترتیبِ نمایش. **مرجعِ محاسبه نیست** — موتور از روی `up_to` مرتب می‌کند، تا
    #: یک ردیفِ جابه‌جا در رابط مالیات را عوض نکند.
    seq: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    #: سقفِ تجمعیِ سالانه. `NULL` یعنی نامحدود — و **فقط ردیفِ آخر**.
    #: عددِ جادوییِ «۹۹٬۹۹۹٬۹۹۹٬۹۹۹» عمداً استفاده نشد.
    up_to: Mapped[float | None] = mapped_column(Numeric(18, 0), nullable=True)
    #: نرخ به‌صورتِ کسر (۰٫۰۷۵ = ۷٫۵٪). شش رقمِ اعشار، چون نرخِ اعشاری واقعی است
    #: و `Numeric` — نه `float` — چون این یک محاسبه‌ی مالیِ قانونی است.
    rate: Mapped[float] = mapped_column(Numeric(9, 6), default=0, server_default="0")

    table: Mapped["TaxTable"] = relationship(back_populates="brackets")


class InsuranceTaxBranch(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """شعبه‌ی قانونی: تأمین اجتماعی، حوزه‌ی مالیاتی، یا بیمه‌ی تکمیلی.

    **یک مِستر برای هر سه**، نه سه زیرسیستمِ موازی — چون فرم یکی است، فهرست یکی
    است، و هر سه نوع از همان کرکره انتخاب می‌شوند. `kind` تفکیکشان می‌کند.

    ساختارش دو لایه است:

    * **هسته‌ی مشترکِ ثبت** — هویت، طرف حساب، شناسه‌ی ثبت، کارگاه، کارفرما،
      نشانی، شماره‌ی پیمان، نفراتِ معاف، مرکز هزینه. این‌ها برای هر سه نوع
      معنا دارند، حتی اگر همه‌ی نوع‌ها همه‌شان را پر نکنند.
    * **سیاستِ نوع‌محور** — `tax_calculation_method` که **فقط** برای حوزه‌ی
      مالیاتی است. در فهرستِ شعب، ردیفِ مالیاتی مقدار دارد و ردیفِ تأمین
      اجتماعی همان ستون را خالی نشان می‌دهد.

    این مِستر **ثبت** است نه نرخ: نرخِ بیمه‌ی کارمند و کارفرما، سقف و کفِ بیمه،
    و بیمه‌ی بیکاری هیچ‌کدام این‌جا نیستند و نباید بیایند — از `PayrollSettings`
    می‌آیند.
    """

    __tablename__ = "insurance_tax_branches"
    __table_args__ = (
        UniqueConstraint("tenant_id", "kind", "name", name="uq_insurance_tax_branches_tenant_kind_name"),
        CheckConstraint(f"kind IN {BRANCH_KINDS}", name="ck_insurance_tax_branches_kind"),
        #: **قیدِ نوع‌محور، در خودِ پایگاه داده.** غیرفعال‌کردنِ ورودی در مرورگر
        #: کافی نیست: یک درخواستِ مستقیمِ API می‌تواند «نحوه محاسبه مالیات» را روی
        #: شعبه‌ی بیمه بنشاند و آن‌وقت فهرست چیزی نشان می‌دهد که معنا ندارد.
        CheckConstraint(
            "tax_calculation_method = '' OR kind = 'tax'",
            name="ck_insurance_tax_branches_tax_method_is_tax_only",
        ),
        CheckConstraint(
            f"tax_calculation_method = '' OR tax_calculation_method IN {TAX_CALC_METHODS}",
            name="ck_insurance_tax_branches_tax_method",
        ),
        CheckConstraint(
            "insurance_exempt_count >= 0", name="ck_insurance_tax_branches_exempt_count"
        ),
    )

    code: Mapped[str] = mapped_column(String(20), default="", server_default="")
    name: Mapped[str] = mapped_column(String(150))
    kind: Mapped[str] = mapped_column(String(20), default="insurance", server_default="insurance")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    #: **هویتِ حسابداریِ شعبه**.
    #:
    #: شعبه تا امروز فقط یک نام بود، در حالی که بدهیِ بیمه و مالیاتِ تکلیفی
    #: واقعاً **به همان سازمان پرداخت می‌شود** — و پرداخت طرفِ حساب می‌خواهد.
    #: پیوند به `Contact` است نه به تفصیلی: طرف حساب از قبل `analytic_id` دارد،
    #: و شناسه‌اش پایدار می‌ماند حتی وقتی کد و عنوانِ تفصیلی عوض شوند.
    #:
    #: **یکتا نیست، و عمداً:** یک سازمان می‌تواند چند شعبه داشته باشد.
    #: `NULL` یعنی «هنوز وصل نشده» — شعبه‌های پیش از این مهاجرت همه همین‌اند.
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    contact: Mapped["Contact | None"] = relationship(lazy="joined")  # noqa: F821

    # ── هسته‌ی مشترکِ ثبتِ قانونی ──────────────────────────────────────────────

    #: «کد شرکت / شماره پرونده». عمداً **عمومی** نام‌گذاری شده و نه
    #: `tax_file_number`: برچسبِ فرم خودش ترکیبی است، و معنایش با نوعِ شعبه عوض
    #: می‌شود — پرونده‌ی مالیاتی برای حوزه، کدِ کارگاه برای تأمین اجتماعی.
    #: قالب و طولش هیچ‌جا اثبات نشده، پس هیچ اعتبارسنجیِ عددی روی آن نیست.
    registration_code: Mapped[str] = mapped_column(String(50), default="", server_default="")

    #: کارگاهِ ثبت‌شده نزدِ مرجع. **«محل خدمت» نیست** — `ServiceLocation` می‌گوید
    #: کارمند کجا کار می‌کند، این می‌گوید کارفرما زیرِ کدام کارگاه ثبت شده. ممکن
    #: است روزی نگاشت پیدا کنند، ولی یکی‌کردنشان امروز شاهدی ندارد.
    workplace_name: Mapped[str] = mapped_column(String(200), default="", server_default="")
    #: نشانیِ کارگاه — **نشانیِ خودِ سازمان نیست**؛ آن روی طرف حساب است.
    workplace_address: Mapped[str] = mapped_column(Text, default="", server_default="")
    #: نامِ کارفرما همان‌طور که نزدِ مرجع ثبت شده. ممکن است با نامِ حقوقیِ شرکت
    #: یکی باشد و ممکن است نباشد؛ تا وقتی سیاستش روشن نشده، این‌جا مستقل می‌ماند
    #: و از مِسترِ شرکت خوانده یا بازنویسی نمی‌شود.
    employer_name: Mapped[str] = mapped_column(String(200), default="", server_default="")

    #: «شماره پیمان» — قراردادِ کارفرما با مرجعِ قانونی. **قراردادِ استخدامیِ
    #: کارمند نیست** و هیچ کلیدِ خارجی‌ای به `SalaryContract` ندارد.
    agreement_number: Mapped[str] = mapped_column(String(50), default="", server_default="")

    #: «نفرات معاف از بیمه» — یک عددِ سرصفحه‌ی ثبتِ کارگاه.
    #:
    #: **این عدد نمی‌گوید کدام کارمندان معاف‌اند** و نباید طوری رفتار شود که
    #: بگوید: معافیتِ واقعی کارمند‌به‌کارمند روی خودِ حکم است
    #: (`exempt_employee_insurance` و برادرانش). ترکیبِ این دو یعنی دو حقیقت، و
    #: هیچ محاسبه‌ای این عدد را نمی‌خواند.
    insurance_exempt_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    #: بُعدِ مرکز هزینه‌ی شعبه — از همان مِسترِ مشترک.
    #:
    #: **«محل خدمت» نیست و «حسابِ هزینه» هم نیست.** و هیچ سندی از روی آن زده
    #: نمی‌شود: نقشش در ثبتِ حسابداریِ حقوق هیچ‌جا اثبات نشده، پس ذخیره می‌شود و
    #: نمایش داده می‌شود، ولی قاعده‌ی ثبتی از آن ساخته نمی‌شود.
    cost_center_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cost_centers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    cost_center: Mapped["CostCenter | None"] = relationship(lazy="joined")  # noqa: F821

    # ── سیاستِ نوع‌محور ────────────────────────────────────────────────────────

    #: «نحوه محاسبه مالیات» — **فقط برای `kind = 'tax'`**، با قیدِ پایگاه داده.
    #: خالی یعنی «تعیین نشده». هنوز هیچ محاسبه‌ای نمی‌خواندش.
    tax_calculation_method: Mapped[str] = mapped_column(
        String(30), default="", server_default=""
    )

    #: **هویتِ حسابداریِ شعبه** (مهاجرت ۰۱۳۶).
    #:
    #: شعبه تا امروز فقط یک نام بود، در حالی که بدهیِ بیمه و مالیاتِ تکلیفی
    #: واقعاً **به همان سازمان پرداخت می‌شود** — و پرداخت طرفِ حساب می‌خواهد.
    #: پیوند به `Contact` است نه به تفصیلی: طرف حساب از قبل `analytic_id` دارد،
    #: و شناسه‌اش پایدار می‌ماند حتی وقتی کد و عنوانِ تفصیلی عوض شوند.
    #:
    #: `NULL` یعنی «هنوز وصل نشده» — شعبه‌های پیش از ۰۱۳۶ همه همین‌اند و دقیقاً
    #: مثلِ قبل کار می‌کنند.
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    contact: Mapped["Contact | None"] = relationship(lazy="joined")  # noqa: F821


class SalaryContractLine(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """یک ردیفِ «حقوق و مزایای ثابت» یا «سایر مبالغ» روی یک قرارداد."""

    __tablename__ = "salary_contract_lines"
    __table_args__ = (
        UniqueConstraint("tenant_id", "contract_id", "factor_id", name="uq_contract_lines_factor"),
        CheckConstraint("amount >= 0", name="ck_salary_contract_lines_amount"),
    )

    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("salary_contracts.id", ondelete="CASCADE"), index=True
    )
    factor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payroll_factors.id", ondelete="RESTRICT")
    )
    amount: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")

    contract: Mapped["SalaryContract"] = relationship(back_populates="lines")
    factor: Mapped["PayrollFactor"] = relationship(lazy="joined")


class LoanType(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """نوعِ وامِ پرسنلی: وامِ ضروری، وامِ مسکن، مساعده…

    جدولِ مرجعِ ساده، مثلِ `ServiceLocation`. `default_installments` فقط پیش‌فرضِ
    فرم است نه قانون — هر وام تعدادِ قسطِ خودش را روی خودش دارد.
    """

    __tablename__ = "loan_types"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_loan_types_tenant_code"),
        CheckConstraint(
            "default_installments > 0 AND default_installments <= 240",
            name="ck_loan_types_installments",
        ),
    )

    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(150))
    name2: Mapped[str] = mapped_column(String(150), default="", server_default="")
    default_installments: Mapped[int] = mapped_column(Integer, default=12, server_default="12")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class EmployeeLoan(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """وامی که به کارمند داده شده و قسط‌به‌قسط از حقوقش کسر می‌شود.

    مبلغ و تعدادِ قسط این‌جاست، ولی **قسطِ ماهانه از این‌ها حساب نمی‌شود** — اقساط
    رکوردِ خودشان را دارند. دلیلش در مهاجرتِ ۰۰۹۵ نوشته شده: اقساط در عمل مساوی
    نمی‌مانند و کسرِ ماهانه باید بداند کدام قسط سررسید شده، نه اینکه هر بار تقسیم کند.
    """

    __tablename__ = "employee_loans"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_employee_loans_amount"),
        CheckConstraint(
            "installment_count > 0 AND installment_count <= 240",
            name="ck_employee_loans_installments",
        ),
        CheckConstraint(f"status IN {LOAN_STATUSES}", name="ck_employee_loans_status"),
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), index=True
    )
    #: نوعِ وام پاک‌شدنی است بی‌آنکه وام‌های ثبت‌شده از بین بروند.
    loan_type_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("loan_types.id", ondelete="SET NULL"), nullable=True
    )
    amount: Mapped[float] = mapped_column(Numeric(18, 0))
    loan_date: Mapped[date_] = mapped_column(Date)
    installment_count: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    status: Mapped[str] = mapped_column(String(20), default="active", server_default="active")
    note: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    installments: Mapped[list["EmployeeLoanInstallment"]] = relationship(
        back_populates="loan", cascade="all, delete-orphan", order_by="EmployeeLoanInstallment.seq"
    )


class EmployeeLoanInstallment(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """یک قسطِ وام. سررسید، مبلغ، و اینکه در کدام دوره کسر شد."""

    __tablename__ = "employee_loan_installments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "loan_id", "seq", name="uq_loan_installments_loan_seq"),
        CheckConstraint("amount > 0", name="ck_loan_installments_amount"),
        CheckConstraint("seq > 0", name="ck_loan_installments_seq"),
    )

    loan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employee_loans.id", ondelete="CASCADE"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer)
    due_date: Mapped[date_] = mapped_column(Date)
    amount: Mapped[float] = mapped_column(Numeric(18, 0))
    #: NULL = هنوز کسر نشده. با ابطالِ آن دوره دوباره NULL می‌شود، پس نه قسطی دوبار
    #: کسر می‌شود نه قسطی گم.
    deducted_period_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payroll_periods.id", ondelete="SET NULL"), nullable=True
    )

    loan: Mapped["EmployeeLoan"] = relationship(back_populates="installments")


class PayrollSettlement(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """تسویه‌حسابِ پایانِ کار — همه‌ی اجزا در یک سند، با یک خالصِ پرداختی.

    این `BenefitRun` نیست: آن هر مزیت را جدا صادر می‌کند، این همه‌شان را منهای بدهیِ
    وام یک‌جا می‌بندد. اجزا جدا می‌مانند چون کارمند حق دارد بداند خالص از کجا آمده و
    ممیزِ بیمه و مالیات هم همین تفکیک را می‌خواهد.
    """

    __tablename__ = "payroll_settlements"
    __table_args__ = (
        #: یک تسویه‌ی نهایی برای هر کارمند؛ اصلاحش ویرایشِ همان ردیف است نه ردیفِ دوم.
        UniqueConstraint("tenant_id", "employee_id", name="uq_payroll_settlements_employee"),
        CheckConstraint(
            "severance_amount >= 0 AND leave_payout_amount >= 0 AND other_earnings >= 0 "
            "AND loan_balance >= 0 AND other_deductions >= 0",
            name="ck_payroll_settlements_amounts",
        ),
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), index=True
    )
    settlement_date: Mapped[date_] = mapped_column(Date)
    severance_amount: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    leave_payout_amount: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    other_earnings: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    loan_balance: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    other_deductions: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    #: **ذخیره** می‌شود نه محاسبه‌ی هربار: مبنای پرداخت است و نباید با تغییرِ بعدیِ
    #: نرخ‌ها عقب‌گرد کند.
    net_amount: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    note: Mapped[str] = mapped_column(Text, default="", server_default="")
    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True, index=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))


class PayrollDeploymentInfo(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """مانده‌های ابتدای استقرار — آنچه پیش از آمدن به کوبیتا اتفاق افتاده.

    **بی این رکورد، مالیاتِ حقوق کمتر از واقع درمی‌آید.** مالیات پلکانی و سالانه
    است؛ شرکتی که مهرماه از اکسل می‌آید، اگر پرداختیِ شش ماهِ گذشته را ندهد، پلکان
    از صفر شروع می‌شود و خطا تا ممیزیِ سالِ بعد دیده نمی‌شود.

    مانده‌ی مرخصی و سابقه‌ی قبلی هم به همین دلیل این‌جاست: بدونشان کارمندِ ده‌ساله
    از دیدِ نرم‌افزار تازه‌وارد است.
    """

    __tablename__ = "payroll_deployment_info"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "employee_id", "year", name="uq_payroll_deployment_employee_year"
        ),
        CheckConstraint(
            "cumulative_gross >= 0 AND cumulative_tax >= 0 AND cumulative_insurance >= 0 "
            "AND leave_balance_days >= 0 AND prior_service_days >= 0",
            name="ck_payroll_deployment_amounts",
        ),
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), index=True
    )
    year: Mapped[int] = mapped_column(Integer)
    cumulative_gross: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    cumulative_tax: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    cumulative_insurance: Mapped[float] = mapped_column(Numeric(18, 0), default=0, server_default="0")
    leave_balance_days: Mapped[float] = mapped_column(Numeric(6, 2), default=0, server_default="0")
    prior_service_days: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    note: Mapped[str] = mapped_column(Text, default="", server_default="")
