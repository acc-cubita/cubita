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

BRANCH_KINDS = ("insurance", "tax")
BRANCH_KIND_LABELS = {"insurance": "شعبه بیمه", "tax": "حوزه مالیاتی"}



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
    net_pay: Mapped[float] = mapped_column(Numeric(18, 0))

    journal_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))


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
        UUID(as_uuid=True), ForeignKey("journal_entries.id"), nullable=True
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


class InsuranceTaxBranch(TenantMixin, UUIDPKMixin, TimestampMixin, Base):
    """شعبه‌ی تأمین اجتماعی یا حوزه‌ی مالیاتی.

    یک جدول برای هر دو، چون شکلشان یکی است (کد + عنوان) و فرمِ قرارداد هر دو را از
    یک‌جا می‌خواهد. `kind` تفکیکشان می‌کند.
    """

    __tablename__ = "insurance_tax_branches"
    __table_args__ = (
        UniqueConstraint("tenant_id", "kind", "name", name="uq_insurance_tax_branches_tenant_kind_name"),
        CheckConstraint(f"kind IN {BRANCH_KINDS}", name="ck_insurance_tax_branches_kind"),
    )

    code: Mapped[str] = mapped_column(String(20), default="", server_default="")
    name: Mapped[str] = mapped_column(String(150))
    kind: Mapped[str] = mapped_column(String(20), default="insurance", server_default="insurance")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


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
