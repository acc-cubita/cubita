from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, field_validator, model_validator

from app.models.payroll import (
    BRANCH_KIND_LABELS,
    BRANCH_KINDS,
    CONTRACT_TYPES,
    EMPLOYMENT_TYPES,
    FACTOR_CATEGORIES,
    FACTOR_DETAIL_CLASSES,
    FACTOR_KINDS,
    FACTOR_SYSTEM_KEYS,
    JOB_FAMILIES,
    TAX_CALC_METHODS,
    TAX_CALC_PURPOSES,
    TAX_GROUP_DEFAULT_PERCENT,
    TAX_GROUP_KINDS,
)


class EmployeeIn(BaseModel):
    """استخدام = فعال‌کردنِ نقشِ کارمند روی یک طرف حساب.

    تا امروز این ورودی نام و کدِ ملی می‌گرفت و کارمندی می‌ساخت که به **هیچ طرف
    حسابی** وصل نبود — هویتِ دومی از همان آدم، بیرونِ مِسترِ مشترک، که اصلاحش
    هیچ‌وقت به آن یکی نمی‌رسید.

    **هر دو شکل پذیرفته می‌شوند و هیچ‌کدام هویتِ یتیم نمی‌سازد:**

    * `contact_id` بدهید → نقش روی همان طرف حساب فعال می‌شود.
    * نام و کدِ ملی بدهید → اول دنبالِ طرف‌حسابی با همان کدِ ملی می‌گردد؛ اگر
      باشد همان استفاده می‌شود (نه رکوردِ تکراری)، اگر نباشد ساخته می‌شود.

    شکلِ دوم برای این مانده که فرمِ «کارمند جدید» سال‌هاست همین را می‌فرستد؛
    شکستنش یعنی رابطِ مستقر تا رسیدنِ باندلِ تازه کار نکند، بی‌آنکه چیزی به
    درستیِ داده اضافه شود.
    """

    contact_id: UUID | None = None
    hire_date: date
    bank_account_number: str = ""

    #: مسیرِ دوم — فقط وقتی `contact_id` نیامده باشد.
    first_name: str | None = None
    last_name: str | None = None
    national_id: str | None = None
    phone: str | None = None
    email: str | None = None

    @model_validator(mode="after")
    def _needs_an_identity(self) -> "EmployeeIn":
        if self.contact_id is not None:
            return self
        if not (self.first_name or "").strip() or not (self.national_id or "").strip():
            raise ValueError(
                "یا طرف حساب را انتخاب کنید، یا نام و کد ملی را بدهید تا طرف حسابش ساخته شود"
            )
        return self


class EmployeeOut(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    national_id: str
    phone: str | None
    email: str | None
    bank_account_number: str
    hire_date: date
    termination_date: date | None
    is_active: bool

    model_config = {"from_attributes": True}


# ── جدول‌های مرجع ─────────────────────────────────────────────────────────────


class ServiceLocationIn(BaseModel):
    code: str
    name: str
    name2: str = ""
    is_active: bool = True

    @model_validator(mode="after")
    def _required(self) -> "ServiceLocationIn":
        if not self.code.strip():
            raise ValueError("کد محل خدمت الزامی است")
        if not self.name.strip():
            raise ValueError("عنوان محل خدمت الزامی است")
        return self


class ServiceLocationOut(BaseModel):
    id: UUID
    code: str
    name: str
    name2: str
    is_active: bool

    model_config = {"from_attributes": True}


class JobTitleIn(BaseModel):
    code: str
    name: str
    name2: str = ""
    job_family: str = ""
    insurance_job_code: str = ""
    is_active: bool = True

    @model_validator(mode="after")
    def _required(self) -> "JobTitleIn":
        if not self.code.strip():
            raise ValueError("کد شغل الزامی است")
        if not self.name.strip():
            raise ValueError("عنوان شغل الزامی است")
        #: رسته در اسکیما بررسی می‌شود نه با قیدِ بررسیِ پایگاه‌داده — این فهرست با
        #: دستورالعملِ بیمه عوض می‌شود و مهاجرت‌دادنِ هر تغییرش بی‌دلیل است.
        if self.job_family and self.job_family not in JOB_FAMILIES:
            raise ValueError("رسته شغل نامعتبر است")
        return self


class JobTitleOut(BaseModel):
    id: UUID
    code: str
    name: str
    name2: str
    job_family: str
    insurance_job_code: str
    is_active: bool

    model_config = {"from_attributes": True}


class PayrollFactorIn(BaseModel):
    name: str
    name2: str = ""
    category: str = "benefit"
    kind: str = "fixed"
    is_extraordinary: bool = False
    #: خالی = عاملِ ساخته‌ی کاربر. کلیدِ سیستمی را فقط «ساخت عوامل پیش‌فرض» می‌گذارد،
    #: چون هر کلید حداکثر یک عامل دارد و دستکاریِ دستی‌اش محاسبه را می‌شکند.
    system_key: str = ""
    is_active: bool = True
    #: ترتیبِ ردیف‌های فیش. **فقط نمایشی** — هیچ محاسبه‌ای از آن نمی‌خوانَد.
    display_priority: int = 0
    #: پروفایلِ حسابداریِ عامل. خالی = حسابِ عمومیِ حقوق، یعنی رفتارِ امروز.
    expense_account_id: UUID | None = None
    expense_detail_class: str = ""
    payable_account_id: UUID | None = None
    payable_detail_class: str = ""

    @model_validator(mode="after")
    def _valid(self) -> "PayrollFactorIn":
        if not self.name.strip():
            raise ValueError("عنوان عامل الزامی است")
        if self.category not in FACTOR_CATEGORIES:
            raise ValueError("طبقه‌ی عامل باید مزایا یا کسورات باشد")
        if self.kind not in FACTOR_KINDS:
            raise ValueError("نوع عامل باید ثابت یا متغیر باشد")
        if self.system_key not in FACTOR_SYSTEM_KEYS:
            raise ValueError("کلید سیستمی نامعتبر است")
        for value in (self.expense_detail_class, self.payable_detail_class):
            if value not in FACTOR_DETAIL_CLASSES:
                raise ValueError("طبقه‌ی تفصیلی نامعتبر است")
        if self.display_priority < 0:
            raise ValueError("اولویت نمایش نمی‌تواند منفی باشد")
        return self


class PayrollFactorPatch(BaseModel):
    """ویرایشِ **جزئیِ** عامل — هر میدانی که نیامده دست نمی‌خورد.

    تا امروز `PATCH` همان `PayrollFactorIn` را می‌گرفت، که `name` را الزامی
    می‌کند؛ پس «فقط این عامل را غیرفعال کن» ۴۲۲ می‌گرفت و عملاً هیچ مسیری برای
    غیرفعال‌کردن نبود — بخشی از همان باگی که `is_active` را بی‌اثر کرده بود.
    """

    name: str | None = None
    name2: str | None = None
    category: str | None = None
    kind: str | None = None
    is_extraordinary: bool | None = None
    is_active: bool | None = None
    display_priority: int | None = None
    expense_account_id: UUID | None = None
    expense_detail_class: str | None = None
    payable_account_id: UUID | None = None
    payable_detail_class: str | None = None

    @model_validator(mode="after")
    def _valid(self) -> "PayrollFactorPatch":
        if self.name is not None and not self.name.strip():
            raise ValueError("عنوان عامل نمی‌تواند خالی باشد")
        if self.category is not None and self.category not in FACTOR_CATEGORIES:
            raise ValueError("طبقه‌ی عامل باید مزایا یا کسورات باشد")
        if self.kind is not None and self.kind not in FACTOR_KINDS:
            raise ValueError("نوع عامل باید ثابت یا متغیر باشد")
        for value in (self.expense_detail_class, self.payable_detail_class):
            if value is not None and value not in FACTOR_DETAIL_CLASSES:
                raise ValueError("طبقه‌ی تفصیلی نامعتبر است")
        if self.display_priority is not None and self.display_priority < 0:
            raise ValueError("اولویت نمایش نمی‌تواند منفی باشد")
        return self


class PayrollFactorOut(BaseModel):
    id: UUID
    name: str
    name2: str
    category: str
    kind: str
    is_extraordinary: bool
    system_key: str
    is_active: bool
    display_priority: int = 0
    expense_account_id: UUID | None = None
    expense_detail_class: str = ""
    payable_account_id: UUID | None = None
    payable_detail_class: str = ""
    #: آیا در حکمی یا فیشی نشسته — گاردِ قفلِ طبقه از همین می‌آید.
    in_use: bool = False
    #: ضریبِ **مؤثرِ** شرکتِ این عامل در هر مبنا — نه ردیف‌های خام.
    #:
    #: عمداً همان چیزی برگردانده می‌شود که موتور استفاده می‌کند، با پیش‌فرض‌ها حل
    #: شده. اگر ردیف‌های خام برمی‌گشت، رابط باید همان قاعده‌ی پیش‌فرض را دوباره
    #: پیاده می‌کرد — و دو پیاده‌سازیِ یک قاعده دیر یا زود از هم جدا می‌افتند.
    participation: dict[str, Decimal] = {}

    model_config = {"from_attributes": True}

    @classmethod
    def of(cls, row, rules=None, *, in_use: bool = False) -> "PayrollFactorOut":
        from app.models.payroll import FACTOR_PURPOSES
        from app.services.factor_participation import coefficient

        out = cls.model_validate(row)
        out.participation = {p: coefficient(row, p, rules) for p in FACTOR_PURPOSES}
        out.in_use = in_use
        return out


class FactorParticipationIn(BaseModel):
    """ضریبِ شرکتِ یک عامل در یک یا چند مبنا. کلید = هدف، مقدار = ضریب (۰..۱)."""

    participation: dict[str, Decimal]

    @model_validator(mode="after")
    def _check(self) -> "FactorParticipationIn":
        from app.models.payroll import FACTOR_PURPOSE_LABELS

        for purpose, value in self.participation.items():
            if purpose not in FACTOR_PURPOSE_LABELS:
                raise ValueError(f"مبنای ناشناخته: {purpose}")
            if not (0 <= value <= 1):
                raise ValueError(f"ضریب «{FACTOR_PURPOSE_LABELS[purpose]}» باید بین ۰ و ۱ باشد")
        return self


class PayrollTaxGroupIn(BaseModel):
    name: str
    kind: str = "normal"
    percent: Decimal | None = None

    @model_validator(mode="after")
    def _valid(self) -> "PayrollTaxGroupIn":
        if not self.name.strip():
            raise ValueError("عنوان گروه مالیاتی الزامی است")
        if self.kind not in TAX_GROUP_KINDS:
            raise ValueError("نوع گروه مالیاتی نامعتبر است")
        #: درصدِ خالی = پیش‌فرضِ همان نوع (عادی ۱۰۰، محروم ۵۰، معاف ۰). عدد آزاد
        #: است چون درصدِ تخفیفِ مناطق محروم قانوناً عوض می‌شود.
        if self.percent is None:
            self.percent = Decimal(TAX_GROUP_DEFAULT_PERCENT[self.kind])
        if not (0 <= self.percent <= 100):
            raise ValueError("درصد باید بین ۰ و ۱۰۰ باشد")
        return self


class PayrollTaxGroupOut(BaseModel):
    id: UUID
    name: str
    kind: str
    percent: Decimal
    is_active: bool

    model_config = {"from_attributes": True}


class InsuranceTaxBranchIn(BaseModel):
    """شعبه‌ی قانونی — یک ورودی برای هر سه نوع، با اعتبارسنجیِ **نوع‌محور**.

    فرمِ مشترک همه‌ی میدان‌ها را نشان می‌دهد، ولی همه‌شان برای همه‌ی نوع‌ها معنا
    ندارند. «نحوه محاسبه مالیات» فقط برای حوزه‌ی مالیاتی است و این‌جا رد می‌شود
    — نه فقط در مرورگر پنهان.
    """

    name: str
    code: str = ""
    kind: str = "insurance"
    is_active: bool = True
    #: طرف حسابِ سازمان — سازمانِ تأمین اجتماعی، امورِ مالیاتی، یا بیمه‌گرِ
    #: تکمیلی. اختیاری، چون شعبه‌های ثبت‌شده‌ی امروز ندارندش و حدس‌زدنش از روی
    #: نام اتصالِ اشتباه می‌سازد. با این پیوند، بدهیِ حقوق به سازمان تفصیلی و
    #: مانده پیدا می‌کند.
    contact_id: UUID | None = None

    # ── هسته‌ی مشترکِ ثبتِ قانونی ──────────────────────────────────────────────
    #: «کد شرکت / شماره پرونده» — پرونده‌ی مالیاتی برای حوزه، کدِ کارگاه برای
    #: تأمین اجتماعی. عمداً بی‌اعتبارسنجیِ قالب: هیچ‌جا اثبات نشده.
    registration_code: str = ""
    workplace_name: str = ""
    workplace_address: str = ""
    employer_name: str = ""
    #: قراردادِ کارفرما با مرجعِ قانونی — **نه** قراردادِ استخدامیِ کارمند.
    agreement_number: str = ""
    #: عددِ سرصفحه‌ی ثبتِ کارگاه. نمی‌گوید *کدام* کارمندان معاف‌اند؛ آن روی حکم است.
    insurance_exempt_count: int = 0
    cost_center_id: UUID | None = None

    # ── سیاستِ نوع‌محور ────────────────────────────────────────────────────────
    #: فقط برای `kind = "tax"`. خالی یعنی «تعیین نشده».
    tax_calculation_method: str = ""

    @model_validator(mode="after")
    def _valid(self) -> "InsuranceTaxBranchIn":
        if not self.name.strip():
            raise ValueError("عنوان شعبه الزامی است")
        if self.kind not in BRANCH_KINDS:
            raise ValueError("نوع شعبه باید بیمه، مالیات یا بیمه تکمیلی باشد")
        if self.insurance_exempt_count < 0:
            raise ValueError("تعداد نفرات معاف نمی‌تواند منفی باشد")

        method = (self.tax_calculation_method or "").strip()
        if method:
            if self.kind != "tax":
                raise ValueError(
                    "«نحوه محاسبه مالیات» فقط برای حوزه مالیاتی معنا دارد؛ "
                    f"برای «{BRANCH_KIND_LABELS.get(self.kind, self.kind)}» خالی بماند"
                )
            if method not in TAX_CALC_METHODS:
                raise ValueError("نحوه محاسبه مالیات نامعتبر است")
        self.tax_calculation_method = method
        return self


class InsuranceTaxBranchOut(BaseModel):
    id: UUID
    code: str
    name: str
    kind: str
    is_active: bool
    contact_id: UUID | None = None
    #: نامِ طرف حساب و کدِ تفصیلی‌اش — خوانده‌شده از خودِ طرف حساب، نه کپی‌شده.
    #: اگر کاربر نامِ سازمان را اصلاح کند، این‌جا هم اصلاح‌شده دیده می‌شود.
    contact_name: str = ""
    analytic_code: str = ""

    registration_code: str = ""
    workplace_name: str = ""
    workplace_address: str = ""
    employer_name: str = ""
    agreement_number: str = ""
    insurance_exempt_count: int = 0
    cost_center_id: UUID | None = None
    cost_center_name: str = ""
    tax_calculation_method: str = ""
    #: `True` یعنی این شعبه روی حکمی نشسته — نوعش دیگر عوض‌شدنی نیست و رابط هم
    #: باید همین را نشان دهد، نه اینکه کاربر بزند و ۴۰۰ بگیرد.
    in_use: bool = False

    model_config = {"from_attributes": True}

    @classmethod
    def of(cls, row, *, in_use: bool = False) -> "InsuranceTaxBranchOut":
        contact = getattr(row, "contact", None)
        analytic = getattr(contact, "analytic", None) if contact is not None else None
        cost_center = getattr(row, "cost_center", None)
        return cls(
            id=row.id,
            code=row.code,
            name=row.name,
            kind=row.kind,
            is_active=row.is_active,
            contact_id=row.contact_id,
            contact_name=(getattr(contact, "name", "") or "") if contact is not None else "",
            analytic_code=(getattr(analytic, "code", "") or "") if analytic is not None else "",
            registration_code=row.registration_code or "",
            workplace_name=row.workplace_name or "",
            workplace_address=row.workplace_address or "",
            employer_name=row.employer_name or "",
            agreement_number=row.agreement_number or "",
            insurance_exempt_count=row.insurance_exempt_count or 0,
            cost_center_id=row.cost_center_id,
            cost_center_name=(getattr(cost_center, "name", "") or "") if cost_center is not None else "",
            tax_calculation_method=row.tax_calculation_method or "",
            in_use=in_use,
        )


# ── قرارداد ───────────────────────────────────────────────────────────────────


class ContractLineIn(BaseModel):
    factor_id: UUID
    amount: Decimal = Decimal(0)


class ContractLineOut(BaseModel):
    id: UUID
    factor_id: UUID
    amount: Decimal
    #: عنوان و طبقه از خودِ عامل خوانده می‌شوند نه از ستونی روی ردیف — تغییرِ نامِ
    #: عامل باید همه‌جا دیده شود.
    factor_name: str = ""
    factor_category: str = "benefit"

    model_config = {"from_attributes": True}


class EmployeeCandidateOut(BaseModel):
    """طرف‌حسابی که تیکِ «کارمند» دارد — ورودیِ فهرستِ «نام کارمند»ِ فرمِ قرارداد.

    `employee_id` خالی یعنی هنوز پرونده‌ی حقوق و دستمزد ندارد؛ اولین قراردادش خودش
    آن را می‌سازد. کاربر نباید یک آدم را دو بار (یک‌بار طرف‌حساب، یک‌بار کارمند) ثبت کند.
    """

    contact_id: UUID
    name: str
    national_id: str | None = None
    employee_id: UUID | None = None
    has_contract: bool = False


class SalaryContractIn(BaseModel):
    """ورودیِ فرمِ «قرارداد جدید».

    دو راه برای گفتنِ اینکه قرارداد مالِ کیست، و هر دو به یک رکورد می‌رسند:

    * `contact_id` — راهِ فرم. طرف‌حسابی که تیکِ «کارمند» دارد؛ اگر هنوز پرونده‌ی
      حقوق و دستمزد ندارد، سرویس از روی همان طرف‌حساب می‌سازدش. یک آدم، یک رکورد.
    * `employee_id` — راهِ قدیمی، برای کدی که از قبل کارمند را دارد.

    **`effective_from` همان «تاریخ صدور» است** و `hire_date` تاریخِ *واقعیِ* استخدام
    که روی خودِ کارمند می‌نشیند و می‌تواند سال‌ها قبل‌تر باشد.
    """

    employee_id: UUID | None = None
    contact_id: UUID | None = None
    effective_from: date
    contract_type: str = "hire"
    number: str = ""
    valid_until: date | None = None
    service_end_date: date | None = None

    #: تاریخِ استخدام روی `employees.hire_date` می‌نشیند، نه روی قرارداد.
    hire_date: date | None = None
    employment_type: str = ""
    service_location_id: UUID | None = None
    job_title_id: UUID | None = None
    cost_center_id: UUID | None = None

    #: ردیف‌های «حقوق و مزایای ثابت» و «سایر مبالغ». اگر بیایند، چهار ستونِ مبلغِ
    #: زیر از روی همین‌ها ساخته می‌شوند و مقدارِ فرستاده‌شده‌شان نادیده می‌رود.
    lines: list[ContractLineIn] = []
    base_salary: Decimal = Decimal(0)
    housing_allowance: Decimal = Decimal(0)
    food_allowance: Decimal = Decimal(0)
    other_allowance: Decimal = Decimal(0)

    tax_group_id: UUID | None = None
    tax_branch_id: UUID | None = None
    insurance_branch_id: UUID | None = None
    housing_loan_exempt_amount: Decimal = Decimal(0)
    is_insured: bool = True
    is_hard_job: bool = False
    exempt_employee_insurance: bool = False
    exempt_employer_insurance: bool = False
    employer_exempt_percent: Decimal = Decimal(0)
    exempt_unemployment_insurance: bool = False
    employer_name: str = ""
    has_supplementary_insurance: bool = False
    supplementary_branch: str = ""
    supplementary_insurer: str = ""
    description: str = ""

    @model_validator(mode="after")
    def validate_positive(self) -> "SalaryContractIn":
        if self.employee_id is None and self.contact_id is None:
            raise ValueError("کارمند انتخاب نشده است")
        if self.contract_type not in CONTRACT_TYPES:
            raise ValueError("نوع قرارداد باید استخدام یا اصلاح قرارداد باشد")
        if self.employment_type and self.employment_type not in EMPLOYMENT_TYPES:
            raise ValueError("نوع استخدام نامعتبر است")
        #: با ردیف، مبلغ از ردیف‌ها می‌آید و همان‌جا بررسی می‌شود؛ بی‌ردیف، همان
        #: قاعده‌ی قدیمی برقرار است تا کدِ موجود نشکند.
        if not self.lines and self.base_salary <= 0:
            raise ValueError("حقوق پایه باید بزرگ‌تر از صفر باشد")
        if self.valid_until and self.valid_until < self.effective_from:
            raise ValueError("تاریخ اعتبار نمی‌تواند قبل از تاریخ صدور باشد")
        if self.service_end_date and self.service_end_date < self.effective_from:
            raise ValueError("تاریخ پایان خدمت نمی‌تواند قبل از تاریخ صدور باشد")
        if not (0 <= self.employer_exempt_percent <= 100):
            raise ValueError("درصد معافیت سهم کارفرما باید بین ۰ و ۱۰۰ باشد")
        return self


class SalaryContractOut(BaseModel):
    id: UUID
    employee_id: UUID
    effective_from: date
    contract_type: str
    number: str
    valid_until: date | None
    service_end_date: date | None
    employment_type: str
    service_location_id: UUID | None
    job_title_id: UUID | None
    cost_center_id: UUID | None
    base_salary: Decimal
    housing_allowance: Decimal
    food_allowance: Decimal
    other_allowance: Decimal
    tax_group_id: UUID | None
    tax_branch_id: UUID | None
    insurance_branch_id: UUID | None
    housing_loan_exempt_amount: Decimal
    is_insured: bool
    is_hard_job: bool
    exempt_employee_insurance: bool
    exempt_employer_insurance: bool
    employer_exempt_percent: Decimal
    exempt_unemployment_insurance: bool
    employer_name: str
    has_supplementary_insurance: bool
    supplementary_branch: str
    supplementary_insurer: str
    description: str
    lines: list[ContractLineOut] = []
    #: نامِ کارمند برای فهرستِ قراردادها — وگرنه فهرست فقط شناسه نشان می‌دهد.
    employee_name: str = ""

    model_config = {"from_attributes": True}


class PayrollPeriodIn(BaseModel):
    year: int
    month: int

    @model_validator(mode="after")
    def validate_month(self) -> "PayrollPeriodIn":
        if not (1 <= self.month <= 12):
            raise ValueError("ماه باید بین ۱ تا ۱۲ باشد")
        return self


class PayrollPeriodOut(BaseModel):
    id: UUID
    year: int
    month: int
    status: str

    model_config = {"from_attributes": True}


class AttendanceIn(BaseModel):
    employee_id: UUID
    period_id: UUID
    worked_days: Decimal = Decimal(30)
    absent_days: Decimal = Decimal(0)
    overtime_hours: Decimal = Decimal(0)


class AttendanceOut(BaseModel):
    id: UUID
    employee_id: UUID
    period_id: UUID
    worked_days: Decimal
    absent_days: Decimal
    overtime_hours: Decimal

    model_config = {"from_attributes": True}


class PayslipLineOut(BaseModel):
    """یک قلمِ فیش — «این عدد از چه ساخته شد».

    `factor_id` برای اجزای سیستمی (حقوقِ پایه، بیمه، مالیات، قسطِ وام) خالی است،
    و `factor_name` عکسِ لحظه‌ی ثبت — نه نامِ امروزِ عامل.
    """

    id: UUID
    seq: int
    factor_id: UUID | None = None
    factor_name: str
    #: `earning` | `deduction`
    direction: str
    #: `contract` | `attendance` | `settings` | `loan` — تا کاربر بداند برای
    #: عوض‌کردنش کجا باید برود.
    origin: str
    amount: Decimal
    note: str = ""

    model_config = {"from_attributes": True}


class PayslipOut(BaseModel):
    id: UUID
    number: int | None
    employee_id: UUID
    period_id: UUID
    base_salary: Decimal
    allowances_total: Decimal
    overtime_pay: Decimal
    gross_pay: Decimal
    insurance_employee_share: Decimal
    insurance_employer_share: Decimal
    taxable_pay: Decimal
    tax_amount: Decimal
    #: دو کسورِ بعد از مالیات، تا فیش جمع بزند:
    #: خالص = ناخالص − بیمه − مالیات − قسطِ وام − سایر کسورات + تعدیلِ رند
    loan_deduction: Decimal
    other_deductions: Decimal
    #: تعدیلِ گِردکردنِ خالص؛ صفر یعنی رند خاموش است (پیش‌فرض).
    rounding_adjustment: Decimal = Decimal(0)
    net_pay: Decimal
    journal_entry_id: UUID | None

    #: تفکیکِ عامل‌به‌عامل. **ستون‌های تجمیعیِ بالا حقیقتِ فیش‌اند** و این ردیف‌ها
    #: توضیحشان؛ جمعشان با خالص برابر است و سرویس هنگامِ صدور همین را می‌سنجد.
    #: فیش‌های پیش از مهاجرتِ ۰۱۲۸ این فهرست را خالی دارند.
    lines: list[PayslipLineOut] = []

    model_config = {"from_attributes": True}


class TaxBracketIn(BaseModel):
    up_to: Decimal | None  # سقف تجمعی سالانه؛ None یعنی نامحدود (باید آخرین ردیف باشد)
    rate: Decimal  # بین ۰ و ۱


def assert_brackets_sane(brackets: list[tuple[Decimal | None, Decimal]]) -> None:
    """پلکانِ مالیات را می‌سنجد — یک تابع، چون دو جا واردش می‌شوند.

    **باگی که این‌جا بسته شد:** موتور فرض می‌کند فهرست **صعودی** است (سقفِ هر پله
    را مرزِ پایینِ پله‌ی بعد می‌گیرد) ولی تا امروز هیچ‌کس این را نمی‌سنجید. با
    پلکانِ نامرتب، مالیات بی‌صدا و بدونِ هیچ خطایی اشتباه درمی‌آمد:

        پله‌ها ۱۰۰@۱۰٪ · ۲۰۰@۲۰٪ · ∞@۳۰٪ ، مبنا ۳۰۰

        مرتب   ⇒ ۶۰   ✓
        نامرتب ⇒ ۱۰۰  ✗   (۶۷٪ اضافه)

    و اسکیما فهرستِ نامرتب را می‌پذیرفت، یعنی از رابط و از API قابلِ ورود بود.

    مدلِ «سقفِ تجمعی» (`up_to`) عمداً به‌جای بازه‌ی `from/to` مانده: با آن، شکاف و
    همپوشانیِ پله‌ها **ساختاراً ناممکن** است و کلِ خانواده‌ی اعتبارسنجی‌هایشان
    بی‌موضوع می‌شود. تنها چیزی که باید سنجیده شود همین ترتیب است.
    """
    if not brackets:
        raise ValueError("حداقل یک پلکان مالیاتی لازم است")
    if brackets[-1][0] is not None:
        raise ValueError("آخرین پلکان مالیاتی باید سقف نامحدود (up_to=null) داشته باشد")

    previous: Decimal | None = None
    for index, (up_to, rate) in enumerate(brackets):
        if not (0 <= rate <= 1):
            raise ValueError("نرخ هر پلکان باید بین ۰ و ۱ باشد")
        if up_to is None:
            #: سقفِ نامحدود فقط در ردیفِ آخر مجاز است — وگرنه ردیف‌های بعدی هرگز
            #: به آن‌ها نمی‌رسد و بی‌صدا نادیده می‌مانند.
            if index != len(brackets) - 1:
                raise ValueError("سقف نامحدود فقط برای آخرین پلکان مجاز است")
            continue
        if up_to <= 0:
            raise ValueError("سقف هر پلکان باید بزرگ‌تر از صفر باشد")
        if previous is not None and up_to <= previous:
            raise ValueError(
                "پلکان‌های مالیاتی باید صعودی باشند؛ سقف هر پله باید از پله‌ی قبل بیشتر باشد"
            )
        previous = up_to


class TaxTableIn(BaseModel):
    """جدولِ مالیات — سرصفحه‌ی قاعده به‌علاوه‌ی پله‌هایش."""

    title: str
    title2: str = ""
    effective_from: date
    #: `None` = جدولِ پیش‌فرض، برای حکم‌هایی که گروهِ مالیاتی ندارند.
    tax_group_id: UUID | None = None
    calculation_type: str = "salary"
    brackets: list[TaxBracketIn]

    @model_validator(mode="after")
    def _valid(self) -> "TaxTableIn":
        if not self.title.strip():
            raise ValueError("عنوان جدول الزامی است")
        if self.calculation_type not in TAX_CALC_PURPOSES:
            raise ValueError("نوع محاسبه باید حقوق یا عیدی باشد")
        assert_brackets_sane([(b.up_to, b.rate) for b in self.brackets])
        return self


class TaxBracketOut(BaseModel):
    seq: int
    #: مرزِ پایینِ این پله — **مشتق** از سقفِ پله‌ی قبل، نه ستون. «از مبلغ»ِ فرم.
    from_amount: Decimal
    up_to: Decimal | None
    rate: Decimal


class TaxTableOut(BaseModel):
    id: UUID
    title: str
    title2: str
    effective_from: date
    tax_group_id: UUID | None
    tax_group_name: str = ""
    calculation_type: str
    brackets: list[TaxBracketOut] = []
    #: فیشی به این جدول استناد کرده؟ آن‌وقت ویرایشش گذشته را عوض نمی‌کند (اعدادِ
    #: فیش عکس‌اند) ولی رابط باید هشدار بدهد.
    in_use: bool = False

    model_config = {"from_attributes": True}

    @classmethod
    def of(cls, table, *, in_use: bool = False) -> "TaxTableOut":
        rows = sorted(
            table.brackets,
            key=lambda b: (b.up_to is None, Decimal(str(b.up_to or 0))),
        )
        brackets: list[TaxBracketOut] = []
        lower = Decimal(0)
        for seq, row in enumerate(rows, start=1):
            brackets.append(
                TaxBracketOut(
                    seq=seq,
                    from_amount=lower,
                    up_to=None if row.up_to is None else Decimal(str(row.up_to)),
                    rate=Decimal(str(row.rate)),
                )
            )
            if row.up_to is not None:
                lower = Decimal(str(row.up_to))
        group = getattr(table, "tax_group", None)
        return cls(
            id=table.id,
            title=table.title,
            title2=table.title2 or "",
            effective_from=table.effective_from,
            tax_group_id=table.tax_group_id,
            tax_group_name=(getattr(group, "name", "") or "") if group is not None else "",
            calculation_type=table.calculation_type,
            brackets=brackets,
            in_use=in_use,
        )


class TaxBreakdownStep(BaseModel):
    seq: int
    from_amount: Decimal
    up_to: Decimal | None
    rate: Decimal
    consumed: Decimal
    tax: Decimal
    cumulative: Decimal


class TaxBreakdownOut(BaseModel):
    """«این مالیات از کجا آمد؟» — همه‌چیز مشتق، هیچ‌چیز ذخیره‌شده."""

    payslip_id: UUID
    tax_amount: Decimal
    #: مبنای **سالانه‌ی** مصرف‌شده. تفکیک در همین سطح معنا دارد، چون موتور
    #: تعدیلِ تجمیعی می‌کند: مالیاتِ ماه سهمی از مالیاتِ سالانه است.
    annual_taxable: Decimal
    annual_exemption: Decimal
    tax_table_id: UUID | None = None
    tax_table_title: str = ""
    tax_group_name: str = ""
    steps: list[TaxBreakdownStep] = []


#: پارامترهای قانونی‌ای که تا مهاجرتِ ۰۱۳۸ داخلِ سورس‌کد ثابت بودند. پیش‌فرضِ هر
#: کدام **همان ثابتی است که جایش را گرفته**، پس فرمی که این‌ها را نفرستد دقیقاً
#: رفتارِ قبلی را می‌گیرد.
class PayrollStatutoryParams(BaseModel):
    insurance_daily_ceiling: Decimal = Decimal(0)  # صفر = بی‌سقف
    unemployment_rate: Decimal = Decimal(0)
    hard_job_rate: Decimal = Decimal(0)
    eidi_base_multiplier: Decimal = Decimal(2)
    severance_days_per_year: int = 30
    monthly_work_days: Decimal = Decimal(30)
    standard_monthly_hours: Decimal = Decimal(194)
    overtime_multiplier: Decimal = Decimal("1.4")
    tax_exempt_coef_social: Decimal = Decimal(1)
    tax_exempt_coef_supplementary: Decimal = Decimal(1)
    tax_exempt_coef_medical: Decimal = Decimal(1)
    #: **کدام عاملِ موجود این نقش را دارد** — نه ستونِ مبلغِ تازه. بی این‌ها دو
    #: ضریبِ بالا بی‌مصرف‌اند، چون کوبیتا نمی‌داند کدام ردیفِ کسور کدام است.
    supplementary_employee_factor_id: UUID | None = None
    supplementary_employer_factor_id: UUID | None = None
    medical_factor_id: UUID | None = None
    allow_negative_tax: bool = False
    payment_rounding_digits: int = 0


def assert_statutory_params_sane(p: "PayrollSettingsIn") -> None:
    """همان قیدهای `CHECK`ِ دیتابیس، ولی با پیامِ فارسی.

    بی این، کاربرِ فرم به‌جای «نرخ باید بین ۰ و ۱ باشد» یک `IntegrityError`ِ خام
    می‌گرفت — همان درسی که در جدولِ مالیات گرفته شد.
    """
    if p.insurance_daily_ceiling < 0:
        raise ValueError("سقف روزانه‌ی بیمه نمی‌تواند منفی باشد (صفر یعنی بی‌سقف)")
    for value, label in (
        (p.unemployment_rate, "نرخ بیمه‌ی بیکاری"),
        (p.hard_job_rate, "نرخ بیمه‌ی مشاغل سخت"),
        (p.tax_exempt_coef_social, "ضریب معافیت بیمه از مالیات"),
        (p.tax_exempt_coef_supplementary, "ضریب معافیت بیمه تکمیلی از مالیات"),
        (p.tax_exempt_coef_medical, "ضریب معافیت بیمه درمان از مالیات"),
    ):
        if not (0 <= value <= 1):
            raise ValueError(f"{label} باید بین ۰ و ۱ باشد")
    if not (0 < p.eidi_base_multiplier <= 12):
        raise ValueError("ضریب مبنای عیدی باید بزرگ‌تر از صفر و حداکثر ۱۲ باشد")
    if not (0 < p.severance_days_per_year <= 365):
        raise ValueError("روزهای مبنای سنوات در هر سال باید بین ۱ و ۳۶۵ باشد")
    if not (0 < p.monthly_work_days <= 31):
        raise ValueError("مبنای روز کاری ماه باید بین ۱ و ۳۱ باشد")
    if not (0 < p.standard_monthly_hours <= 744):
        raise ValueError("ساعت کار ماهانه باید بزرگ‌تر از صفر و حداکثر ۷۴۴ باشد")
    if not (0 < p.overtime_multiplier <= 10):
        raise ValueError("ضریب اضافه‌کار باید بزرگ‌تر از صفر و حداکثر ۱۰ باشد")
    if not (0 <= p.payment_rounding_digits <= 6):
        raise ValueError("تعداد رقم رند پرداخت باید بین ۰ و ۶ باشد")


class PayrollSettingsIn(PayrollStatutoryParams):
    year: int
    insurance_employee_rate: Decimal
    insurance_employer_rate: Decimal
    tax_exemption_annual: Decimal
    tax_brackets: list[TaxBracketIn]
    min_base_wage: Decimal = Decimal(0)
    annual_leave_days: int = 26
    notes: str = ""

    @model_validator(mode="after")
    def validate_brackets(self) -> "PayrollSettingsIn":
        assert_brackets_sane([(b.up_to, b.rate) for b in self.tax_brackets])
        assert_statutory_params_sane(self)
        return self


class PayrollSettingsOut(PayrollStatutoryParams):
    id: UUID
    year: int
    insurance_employee_rate: Decimal
    insurance_employer_rate: Decimal
    tax_exemption_annual: Decimal
    tax_brackets: list[dict]
    min_base_wage: Decimal = Decimal(0)
    annual_leave_days: int = 26
    notes: str

    model_config = {"from_attributes": True}


class LeaveRecordIn(BaseModel):
    employee_id: UUID
    leave_date: date
    days: Decimal
    note: str = ""

    @model_validator(mode="after")
    def _positive(self) -> "LeaveRecordIn":
        if self.days <= 0:
            raise ValueError("تعداد روز مرخصی باید بزرگ‌تر از صفر باشد")
        return self


class LeaveRecordOut(BaseModel):
    id: UUID
    employee_id: UUID
    leave_date: date
    days: Decimal
    note: str

    model_config = {"from_attributes": True}


class BenefitRowOut(BaseModel):
    employee_id: UUID
    employee_name: str
    base_salary: Decimal
    eidi: Decimal
    severance: Decimal
    leave_entitled: Decimal
    leave_used: Decimal
    leave_remaining: Decimal
    leave_value: Decimal


class BenefitsReportOut(BaseModel):
    year: int
    as_of: date
    min_base_wage: Decimal
    annual_leave_days: int
    rows: list[BenefitRowOut]
    total_eidi: Decimal
    total_severance: Decimal
    total_leave_value: Decimal


class BenefitIssueOut(BaseModel):
    kind: str
    amount: Decimal
    journal_entry_number: int | None


class BenefitSettingsIn(BaseModel):
    year: int
    min_base_wage: Decimal = Decimal(0)
    annual_leave_days: int = 26

    @model_validator(mode="after")
    def _check(self) -> "BenefitSettingsIn":
        if self.min_base_wage < 0:
            raise ValueError("حداقل حقوق نمی‌تواند منفی باشد")
        if self.annual_leave_days < 0:
            raise ValueError("روزهای مرخصی نمی‌تواند منفی باشد")
        return self


class BenefitSettingsOut(BaseModel):
    year: int
    min_base_wage: Decimal
    annual_leave_days: int


# ── وام‌های پرسنلی ────────────────────────────────────────────────────────────


class LoanTypeIn(BaseModel):
    code: str
    name: str
    name2: str = ""
    default_installments: int = 12
    is_active: bool = True

    @field_validator("code", "name")
    @classmethod
    def _required(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("کد و عنوان الزامی‌اند")
        return v

    @field_validator("default_installments")
    @classmethod
    def _installments(cls, v: int) -> int:
        if not (1 <= v <= 240):
            raise ValueError("تعدادِ قسطِ پیش‌فرض باید بینِ ۱ و ۲۴۰ باشد")
        return v


class LoanTypeOut(BaseModel):
    id: UUID
    code: str
    name: str
    name2: str
    default_installments: int
    is_active: bool

    model_config = {"from_attributes": True}


class EmployeeLoanIn(BaseModel):
    """وامِ تازه. اقساط ساخته می‌شوند، نه فرستاده — قاعده‌شان سمتِ سرور است."""

    employee_id: UUID
    loan_type_id: UUID | None = None
    amount: Decimal
    loan_date: date
    installment_count: int = 1
    #: سررسیدِ قسطِ اول. خالی = یک ماه بعد از تاریخِ وام.
    first_due_date: date | None = None
    note: str = ""

    @field_validator("amount")
    @classmethod
    def _positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("مبلغِ وام باید بزرگ‌تر از صفر باشد")
        return v


class LoanInstallmentOut(BaseModel):
    id: UUID
    seq: int
    due_date: date
    amount: Decimal
    deducted_period_id: UUID | None

    model_config = {"from_attributes": True}


class EmployeeLoanOut(BaseModel):
    id: UUID
    employee_id: UUID
    employee_name: str = ""
    loan_type_id: UUID | None
    amount: Decimal
    loan_date: date
    installment_count: int
    status: str
    note: str
    #: مانده = جمعِ اقساطِ کسرنشده. مشتق است نه ستون، تا با اقساط از هم نیفتد.
    balance: Decimal = Decimal(0)
    installments: list[LoanInstallmentOut] = []

    model_config = {"from_attributes": True}


# ── تسویه حساب ───────────────────────────────────────────────────────────────


class PayrollSettlementIn(BaseModel):
    employee_id: UUID
    settlement_date: date
    severance_amount: Decimal = Decimal(0)
    leave_payout_amount: Decimal = Decimal(0)
    other_earnings: Decimal = Decimal(0)
    #: خالی بگذارید تا از وام‌های فعالِ همان کارمند خوانده شود.
    loan_balance: Decimal | None = None
    other_deductions: Decimal = Decimal(0)
    note: str = ""

    @model_validator(mode="after")
    def _not_negative(self) -> "PayrollSettlementIn":
        values = (
            self.severance_amount, self.leave_payout_amount, self.other_earnings,
            self.other_deductions,
        )
        if any(v < 0 for v in values) or (self.loan_balance is not None and self.loan_balance < 0):
            raise ValueError("مبالغِ تسویه‌حساب نمی‌توانند منفی باشند")
        return self


class PayrollSettlementOut(BaseModel):
    id: UUID
    employee_id: UUID
    employee_name: str = ""
    settlement_date: date
    severance_amount: Decimal
    leave_payout_amount: Decimal
    other_earnings: Decimal
    loan_balance: Decimal
    other_deductions: Decimal
    net_amount: Decimal
    note: str
    journal_entry_id: UUID | None

    model_config = {"from_attributes": True}


# ── اطلاعاتِ استقرار ──────────────────────────────────────────────────────────


class DeploymentInfoIn(BaseModel):
    """مانده‌های ابتدای استقرار — پرداختیِ پیش از آمدن به کوبیتا.

    بی این عددها پلکانِ مالیاتِ سالانه از صفر شروع می‌شود و مالیات کمتر از واقع
    درمی‌آید؛ برای همین هیچ‌کدام «اختیاریِ بی‌اثر» نیستند.
    """

    employee_id: UUID
    year: int
    cumulative_gross: Decimal = Decimal(0)
    cumulative_tax: Decimal = Decimal(0)
    cumulative_insurance: Decimal = Decimal(0)
    leave_balance_days: Decimal = Decimal(0)
    prior_service_days: int = 0
    note: str = ""

    @model_validator(mode="after")
    def _not_negative(self) -> "DeploymentInfoIn":
        values = (
            self.cumulative_gross, self.cumulative_tax, self.cumulative_insurance,
            self.leave_balance_days, Decimal(self.prior_service_days),
        )
        if any(v < 0 for v in values):
            raise ValueError("مقادیرِ استقرار نمی‌توانند منفی باشند")
        return self


class DeploymentInfoOut(BaseModel):
    id: UUID
    employee_id: UUID
    employee_name: str = ""
    year: int
    cumulative_gross: Decimal
    cumulative_tax: Decimal
    cumulative_insurance: Decimal
    leave_balance_days: Decimal
    prior_service_days: int
    note: str

    model_config = {"from_attributes": True}
