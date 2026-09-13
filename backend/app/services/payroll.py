import csv
import io
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.counters import DOC_PAYSLIP
from app.services.numbering import next_document_number
from app.models.accounting import JournalLine
from app.models.inventory import Contact
from app.models.payroll import (
    Attendance,
    Employee,
    PayrollPeriod,
    PayrollSettings,
    Payslip,
    PayslipLine,
    SalaryContract,
)
from app.models.user import User
from app.services import chart_codes as cc
from app.services import factor_participation, payroll_loans
from app.services.common import get_account, get_or_create_account, make_journal_entry
from app.services.period_close import assert_period_open
from app.services.tax_tables import bracket_rows, resolve_tax_table

#: **پیش‌فرض، نه قانون.** تا مهاجرتِ ۰۱۳۸ این دو عدد قانونِ سخت‌کدشده بودند؛ حالا
#: `payroll_settings` می‌گویدشان و این‌ها فقط مقدارِ پیش‌فرضِ همان ستون‌ها هستند تا
#: فراخوانی‌هایی که تنظیمات ندارند (تست‌های ریاضی) دست‌نخورده بمانند.
STANDARD_MONTHLY_HOURS = Decimal("194")
OVERTIME_MULTIPLIER = Decimal("1.4")
MONTHLY_WORK_DAYS = Decimal("30")


def _round(value: Decimal) -> Decimal:
    return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def policy_value(settings, name: str, fallback: Decimal) -> Decimal:
    """یک پارامترِ قانونی از تنظیمات، با پیش‌فرضِ «همان رفتارِ قبلی».

    `getattr` عمدی است: `compute_payslip_amounts` از چند مسیر صدا زده می‌شود و
    بعضی‌شان شیءِ ساختگی می‌دهند. نبودِ ستون نباید محاسبه را بشکند — باید همان
    عددی را بدهد که پیش از مهاجرتِ ۰۱۳۸ می‌داد.

    **صفر مقدارِ معتبری است** و به پیش‌فرض برنمی‌گردد: سقفِ صفر یعنی «بی‌سقف»، نرخِ
    صفر یعنی «غیرفعال»، و ضریبِ معافیتِ صفر یعنی «هیچ بخشی از بیمه از مالیات کم
    نشود» — هر سه انتخابِ صریحِ کاربرند، نه نبودِ مقدار.
    """
    raw = getattr(settings, name, None)
    if raw is None or raw == "":
        return fallback
    return Decimal(str(raw))


def _line_amount_for(contract, factor_id, proration: Decimal) -> Decimal:
    """مبلغِ ردیفِ قرارداد برای یک عاملِ مشخص، به نسبتِ کارکرد. نبود = صفر.

    `factor_id` وقتی `None` است که کاربر هنوز نقشِ بیمه‌ی تکمیلی/درمان را به هیچ
    عاملی نداده — و آن‌وقت ضریبِ معافیتش روی هیچ مبلغی نمی‌نشیند، که همان رفتارِ
    امروز است.
    """
    if factor_id is None:
        return Decimal(0)
    for line in getattr(contract, "lines", []) or []:
        if line.factor_id == factor_id:
            return Decimal(str(line.amount)) * proration
    return Decimal(0)


def calc_overtime_pay(
    base_salary: Decimal,
    overtime_hours: Decimal,
    *,
    monthly_hours: Decimal | None = None,
    multiplier: Decimal | None = None,
) -> Decimal:
    if overtime_hours <= 0:
        return Decimal(0)
    hourly_rate = base_salary / (monthly_hours or STANDARD_MONTHLY_HOURS)
    return _round(hourly_rate * (multiplier or OVERTIME_MULTIPLIER) * overtime_hours)


def calc_insurance_shares(
    insurable_pay: Decimal,
    employee_rate: Decimal,
    employer_rate: Decimal,
    *,
    ceiling: Decimal | None = None,
) -> tuple[Decimal, Decimal]:
    """سهمِ کارمند و کارفرما از دستمزدِ مشمولِ بیمه.

    `ceiling` سقفِ **ماهانه**‌ی دستمزدِ مشمول است (سقفِ روزانه × روزهای ماه).
    `None` یا صفر یعنی بی‌سقف — رفتاری که تا پیش از مهاجرتِ ۰۱۳۸ تنها رفتارِ ممکن
    بود، چون کوبیتا اصلاً سقف نداشت و نرخ را روی کلِ ناخالص می‌زد.
    """
    if ceiling is not None and ceiling > 0:
        insurable_pay = min(insurable_pay, ceiling)
    return _round(insurable_pay * employee_rate), _round(insurable_pay * employer_rate)


def contract_insurance_rates(contract, settings) -> tuple[Decimal, Decimal]:
    """نرخِ مؤثرِ بیمه‌ی این **حکم** — سهمِ کارمند و سهمِ کارفرما.

    **پنج پرچمِ مرده.** `salary_contracts` از قبل این‌ها را داشت و **هیچ‌کدام
    خوانده نمی‌شدند**؛ کاربر «معاف از بیمه» را تیک می‌زد و بیمه همچنان کامل کسر
    می‌شد. پروب: حکمی با `is_insured=False` و `exempt_employee_insurance=True`
    باز هم ۲۱٬۰۰۰٬۰۰۰ سهمِ کارمند می‌گرفت.

    معنیِ هرکدام از برچسبِ خودِ فرم می‌آید:

        is_insured                     «مشمول بیمه تأمین اجتماعی»
        exempt_employee_insurance      «معاف از بیمه سهم کارمند»
        exempt_employer_insurance      «معاف از بیمه سهم کارفرما»
        employer_exempt_percent        «درصد معافیت سهم کارفرما»
        exempt_unemployment_insurance  «معاف از بیمه بیکاری»
        is_hard_job                    «شغل سخت و زیان‌آور»

    **درصدِ صفر با تیکِ معافیت یعنی معافیتِ کامل.** فرم آن میدان را فقط وقتی
    نشان می‌دهد که تیک خورده باشد، و خواندنِ «صفر درصد معاف» یعنی تیک هیچ کاری
    نکند — همان باگی که این تابع می‌بندد. پس درصد یک **تعدیلِ اختیاری** است، نه
    شرطِ فعال‌شدن.

    پیش‌فرضِ حکم (`is_insured=True` و بقیه خاموش) دقیقاً همان نرخ‌های تنظیمات را
    می‌دهد، پس هیچ حکمی که این پرچم‌ها را دست نزده باشد عوض نمی‌شود.
    """
    if not bool(getattr(contract, "is_insured", True)):
        return Decimal(0), Decimal(0)

    employee_rate = (
        Decimal(0)
        if bool(getattr(contract, "exempt_employee_insurance", False))
        else Decimal(str(settings.insurance_employee_rate))
    )

    employer_rate = Decimal(str(settings.insurance_employer_rate))
    if bool(getattr(contract, "exempt_employer_insurance", False)):
        percent = Decimal(str(getattr(contract, "employer_exempt_percent", 0) or 0))
        employer_rate *= (Decimal(100) - (percent if percent > 0 else Decimal(100))) / Decimal(100)

    #: بیمه‌ی بیکاری و مشاغل سخت هر دو سهمِ **کارفرما**یند و به نرخِ او افزوده
    #: می‌شوند. معافیتِ درصدیِ بالا عمداً رویشان اعمال نمی‌شود: برچسبِ فرم
    #: «درصد معافیت سهم کارفرما» است و این دو نرخِ مستقل‌اند، نه بخشی از آن.
    if not bool(getattr(contract, "exempt_unemployment_insurance", False)):
        employer_rate += policy_value(settings, "unemployment_rate", Decimal(0))
    if bool(getattr(contract, "is_hard_job", False)):
        employer_rate += policy_value(settings, "hard_job_rate", Decimal(0))

    return employee_rate, employer_rate


def round_payment(amount: Decimal, digits: int) -> Decimal:
    """خالصِ پرداختی را تا `digits` رقم گِرد می‌کند. صفر = بدونِ رند.

    **یک‌جا و قطعی.** فصلِ مرجع صریح است که رند نباید در محاسبه، سند، فایلِ بانک و
    رابط جداگانه و متفاوت انجام شود؛ همه‌ی آن‌ها باید از همین یک تابع بگذرند.
    """
    if digits <= 0:
        return _round(amount)
    step = Decimal(10) ** digits
    return (amount / step).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * step


def _ascending(brackets: list[dict]) -> list[dict]:
    """پلکان را صعودی می‌کند — گاردِ دومِ باگِ ترتیب.

    اعتبارسنجیِ ورودی جلوی پلکانِ نامرتبِ *تازه* را می‌گیرد، ولی هر مستأجری که
    پیش از آن یک فهرستِ نامرتب ذخیره کرده باشد همچنان مالیاتِ اشتباه می‌گرفت.
    مرتب‌سازی این‌جا آن داده را هم درست می‌کند، بی‌آنکه چیزی را بازنویسی کند.

    سقفِ `None` یعنی نامحدود، پس همیشه آخر می‌نشیند.
    """
    return sorted(
        brackets,
        key=lambda b: (b.get("up_to") is None, Decimal(str(b.get("up_to") or 0))),
    )


def calc_annual_tax(annual_taxable: Decimal, brackets: list[dict]) -> Decimal:
    """محاسبه‌ی پلکانی مالیات سالانه. هر ردیف {"up_to": سقف تجمعی یا None, "rate": نرخ}."""
    if annual_taxable <= 0:
        return Decimal(0)

    tax = Decimal(0)
    lower = Decimal(0)
    for bracket in _ascending(brackets):
        rate = Decimal(str(bracket["rate"]))
        up_to = bracket["up_to"]
        upper = Decimal(str(up_to)) if up_to is not None else None

        portion_ceiling = annual_taxable if upper is None else min(annual_taxable, upper)
        portion = portion_ceiling - lower
        if portion > 0:
            tax += portion * rate

        if upper is None or annual_taxable <= upper:
            break
        lower = upper

    return _round(tax)


def calc_monthly_tax(monthly_taxable: Decimal, annual_exemption: Decimal, brackets: list[dict]) -> Decimal:
    """طبق روش متداول محاسبه‌ی مالیات حقوق: حقوق ماهانه سالانه می‌شود، معافیت سالانه کسر و پلکان روی مازاد اعمال می‌شود،
    سپس مالیات سالانه بر ۱۲ تقسیم می‌شود تا مالیات همان ماه به‌دست آید."""
    annual_taxable = monthly_taxable * 12
    annual_after_exemption = max(Decimal(0), annual_taxable - annual_exemption)
    annual_tax = calc_annual_tax(annual_after_exemption, brackets)
    return _round(annual_tax / 12)


def calc_cumulative_monthly_tax(
    *,
    monthly_taxable: Decimal,
    prior_taxable: Decimal,
    prior_tax: Decimal,
    month_index: int,
    annual_exemption: Decimal,
    brackets: list[dict],
    tax_percent: Decimal = Decimal(100),
    allow_negative: bool = False,
) -> Decimal:
    """مالیاتِ این ماه، بر مبنای **تجمیعیِ سال** نه فقط همین ماه.

    روشِ `calc_monthly_tax` هر ماه را جدا سالانه می‌کند و فرض می‌گیرد حقوق تمامِ سال
    همین است. تا وقتی حقوق یکنواخت است جواب می‌دهد، ولی دو جا می‌شکند:

    * **درآمدِ ناهموار.** پاداشِ یک ماه، آن ماه را به پلکانِ بالا می‌برد و ماه‌های
      بعد دوباره از پایین شروع می‌کنند؛ جمعِ سال با مالیاتِ واقعیِ سالانه نمی‌خواند.
    * **استقرارِ وسطِ سال.** شرکتی که مهرماه از اکسل می‌آید، شش ماهِ اولِ کارمند را
      نمی‌بیند و پلکان از صفر شروع می‌شود — مالیات کمتر از واقع کسر می‌شود و تا
      ممیزیِ سالِ بعد کسی نمی‌فهمد.

    روشِ این‌جا: درآمدِ مشمولِ **از ابتدای سال تا همین ماه** جمع می‌شود، به نسبتِ
    ماه‌های گذشته سالانه می‌شود، مالیاتِ سالانه‌اش حساب و به همان نسبت سهمِ تا امروز
    گرفته می‌شود؛ آنچه قبلاً کسر شده کم می‌شود و باقی مالیاتِ همین ماه است.

    **در حالتِ یکنواخت و بدونِ سابقه، جوابش دقیقاً همان `calc_monthly_tax` است** —
    ماهِ اولِ سال با سابقه‌ی صفر همان فرمولِ قبلی را می‌دهد.

    `tax_percent` سهمِ گروهِ مالیاتی است: مناطقِ عادی ۱۰۰، مناطقِ محروم ۵۰، معاف ۰.
    روی مالیاتِ *سالانه* اعمال می‌شود نه ماهانه، وگرنه با کسرِ «قبلاً پرداخت‌شده»
    ناسازگار می‌شد.

    `allow_negative` سیاستِ «مالیاتِ منفی محاسبه نشود» است — یک تنظیم، نه یک `if`
    پراکنده در فرمول. پیش‌فرضش (`False`) همان رفتارِ همیشگی است: اگر ماهی کم‌درآمد
    باعث شود مالیاتِ تجمیعیِ لازم از آنچه تا حالا کسر شده کمتر باشد، **مسترد
    نمی‌کنیم** — استردادِ مالیات کارِ تعدیلِ پایانِ سال است، نه فیشِ ماهانه. با
    `True` همان مقدارِ منفی برگردانده می‌شود و فیش آن را به کارمند پس می‌دهد.
    """
    months = max(1, min(12, month_index))
    ytd_taxable = max(Decimal(0), prior_taxable + monthly_taxable)

    #: سالانه‌سازی به نسبتِ ماه‌های سپری‌شده — نه ضرب در ۱۲ که ماه‌های نیامده را هم
    #: به حساب می‌آورد.
    annualized = ytd_taxable * 12 / months
    annual_after_exemption = max(Decimal(0), annualized - annual_exemption)
    annual_tax = calc_annual_tax(annual_after_exemption, brackets) * tax_percent / 100

    tax_due_to_date = annual_tax * months / 12
    this_month = _round(tax_due_to_date - prior_tax)
    return this_month if allow_negative else max(Decimal(0), this_month)


def get_current_contract(db: Session, employee_id: UUID, as_of) -> SalaryContract | None:
    return (
        db.query(SalaryContract)
        .filter(SalaryContract.employee_id == employee_id, SalaryContract.effective_from <= as_of)
        .order_by(SalaryContract.effective_from.desc())
        .first()
    )


def _branch_snapshot(db: Session, contract: SalaryContract) -> dict:
    """کد و نامِ شعبه‌های قانونیِ حکم، برای نشستن روی فیش.

    شش ستون، دو شعبه. `None` یعنی حکم آن شعبه را تعیین نکرده — و همان `None` روی
    فیش می‌ماند، چون «تعیین نشده» با «خالی» یکی نیست و خروجی باید بتواند
    تفکیکشان کند از فیشِ پیش از این مهاجرت که اصلاً عکسی ندارد.
    """
    from app.models.payroll import InsuranceTaxBranch

    wanted = {
        "insurance": getattr(contract, "insurance_branch_id", None),
        "tax": getattr(contract, "tax_branch_id", None),
    }
    ids = {value for value in wanted.values() if value is not None}
    rows = (
        {row.id: row for row in db.query(InsuranceTaxBranch).filter(InsuranceTaxBranch.id.in_(ids)).all()}
        if ids
        else {}
    )

    snapshot: dict = {}
    for prefix, branch_id in wanted.items():
        branch = rows.get(branch_id) if branch_id is not None else None
        snapshot[f"{prefix}_branch_id"] = branch.id if branch is not None else None
        snapshot[f"{prefix}_branch_code"] = (branch.code or "") if branch is not None else None
        snapshot[f"{prefix}_branch_name"] = (branch.name or "") if branch is not None else None
    return snapshot


def _tax_percent(db: Session, contract: SalaryContract) -> Decimal:
    """سهمِ گروهِ مالیاتیِ قرارداد: عادی ۱۰۰، مناطقِ محروم ۵۰، معاف ۰.

    تا امروز این عدد ذخیره می‌شد و هیچ‌جا ضرب نمی‌شد؛ «مناطق محروم» فقط یک برچسب
    بود. بی گروهِ مالیاتی، ۱۰۰ درصد — یعنی همان رفتارِ قبلی.
    """
    from app.models.payroll import PayrollTaxGroup

    group_id = getattr(contract, "tax_group_id", None)
    if group_id is None:
        return Decimal(100)
    group = db.get(PayrollTaxGroup, group_id)
    return Decimal(group.percent) if group is not None else Decimal(100)


def _year_to_date(db: Session, employee_id: UUID, period: PayrollPeriod) -> dict:
    """درآمدِ مشمول و مالیاتِ کسرشده‌ی همین کارمند از ابتدای سالِ مالی تا این دوره.

    دو منبع دارد و هر دو لازم‌اند:

    * **فیش‌های صادرشده‌ی همین سال** — ماه‌هایی که خودِ کوبیتا حساب کرده.
    * **اطلاعاتِ استقرار** — ماه‌هایی که شرکت هنوز با اکسل کار می‌کرده. بی این،
      پلکانِ مالیات از صفر شروع می‌شود و مالیاتِ ماه‌های باقی‌مانده کمتر از واقع
      درمی‌آید.

    درآمدِ مشمولِ استقرار = پرداختیِ تجمیعی منهای بیمه‌ی کسرشده‌ی تجمیعی، دقیقاً
    همان تعریفی که موتور برای `taxable_pay` دارد.
    """
    from app.models.payroll import PayrollDeploymentInfo

    rows = (
        db.query(Payslip.taxable_pay, Payslip.tax_amount)
        .join(PayrollPeriod, Payslip.period_id == PayrollPeriod.id)
        .filter(
            Payslip.employee_id == employee_id,
            PayrollPeriod.year == period.year,
            PayrollPeriod.month < period.month,
        )
        .all()
    )
    taxable = sum((Decimal(r[0]) for r in rows), Decimal(0))
    tax = sum((Decimal(r[1]) for r in rows), Decimal(0))

    deployment = (
        db.query(PayrollDeploymentInfo)
        .filter(
            PayrollDeploymentInfo.employee_id == employee_id,
            PayrollDeploymentInfo.year == period.year,
        )
        .first()
    )
    if deployment is not None:
        taxable += max(
            Decimal(0),
            Decimal(deployment.cumulative_gross) - Decimal(deployment.cumulative_insurance),
        )
        tax += Decimal(deployment.cumulative_tax)

    return {"taxable": taxable, "tax": tax}


def _employee_loan_account(db: Session):
    """حسابِ «وام و مساعده‌ی کارکنان» — دارایی، نه هزینه.

    `get_or_create_account` است نه `get_account`: این نقش تازه اضافه شده و چارتِ
    کسب‌وکارهایی که از قبل ساخته شده‌اند آن را ندارد. اولین وامی که کسر شود، حساب را
    می‌سازد؛ بی این کار، صدورِ فیش برای هر مشتریِ قدیمی با خطای ۵۰۰ می‌شکست.
    """
    return get_or_create_account(
        db,
        cc.EMPLOYEE_LOAN,
        code=cc.DEFAULT_CODE_BY_ROLE[cc.EMPLOYEE_LOAN],
        name="وام و مساعده‌ی کارکنان",
        acc_type="asset",
        parent_code="11",
    )


def _payroll_deductions_account(db: Session):
    """«سایر کسورِ حقوق پرداختنی» — بدهی.

    پولی که از کارمند نگه داشته شده (بیمه‌ی تکمیلی، صندوق، …) و به شخصِ ثالث
    بدهکاریم. مثلِ حسابِ وام با `get_or_create_account` ساخته می‌شود تا چارتِ
    کسب‌وکارهای موجود نشکند.
    """
    return get_or_create_account(
        db,
        cc.PAYROLL_DEDUCTIONS_PAYABLE,
        code=cc.DEFAULT_CODE_BY_ROLE[cc.PAYROLL_DEDUCTIONS_PAYABLE],
        name="سایر کسور حقوق پرداختنی",
        acc_type="liability",
        parent_code="21",
    )


def _payroll_rounding_account(db: Session):
    """«تعدیلِ رندِ حقوق» — هزینه، هم‌خانواده‌ی `SALES_ROUNDING`."""
    return get_or_create_account(
        db,
        cc.PAYROLL_ROUNDING,
        code=cc.DEFAULT_CODE_BY_ROLE[cc.PAYROLL_ROUNDING],
        name="تعدیل رند حقوق",
        acc_type="expense",
        parent_code="5",
    )


def _period_as_of_date(period: PayrollPeriod):
    # دوره‌ی حقوق شمسی است (سال/ماهِ شمسی)؛ تاریخِ سررسیدِ سند = آخرین روزِ همان ماهِ
    # شمسی، به میلادی (که در دفتر ذخیره می‌شود).
    from app.jalali import persian_month_end

    return persian_month_end(period.year, period.month)


def contract_deductions(contract: SalaryContract) -> Decimal:
    """جمعِ ردیف‌های *کسوراتِ* قرارداد (تبِ «سایر مبالغ»).

    تا امروز این ردیف‌ها بی‌صدا نادیده گرفته می‌شدند: `payroll_contracts` هر عاملی
    را که `benefit` نبود رد می‌کرد، پس کاربر بیمه‌ی تکمیلی را وارد می‌کرد و هیچ‌جا
    کسر نمی‌شد.

    مثلِ قسطِ وام از **خالص** کم می‌شوند نه از ناخالص: کسورِ اختیاری مبنای بیمه و
    مالیات را تغییر نمی‌دهد.
    """
    total = Decimal(0)
    for line in getattr(contract, "lines", []) or []:
        factor = getattr(line, "factor", None)
        if factor is not None and factor.category == "deduction":
            total += Decimal(line.amount)
    return total


def payslip_breakdown(
    contract: SalaryContract,
    amounts: dict,
    *,
    proration: Decimal,
    overtime_hours: Decimal,
) -> list[dict]:
    """تفکیکِ عامل‌به‌عاملِ یک فیش — «این عدد از چه ساخته شد؟».

    **این لایه‌ی توضیح است، نه لایه‌ی محاسبه.** اعداد از `amounts` می‌آیند که
    سرویسِ محاسبه ساخته؛ این‌جا هیچ ریاضیِ تازه‌ای انجام نمی‌شود جز خردکردنِ
    `allowances_total` و `other_deductions` به اجزایشان. اگر دو فرمول می‌شد،
    جمعِ ردیف‌ها دیر یا زود از خودِ فیش جدا می‌افتاد — و تستی همین را قفل می‌کند.

    **ترتیب معنی دارد:** اول درآمدها به ترتیبِ منشأ (قرارداد، بعد کارکرد)، بعد
    کسورها. کاربر فیش را از بالا به پایین می‌خواند.

    ردیف‌های قرارداد **همان تناسبِ کارکرد** را می‌خورند که خودِ محاسبه اعمال کرده
    (`proration`)، وگرنه جمعِ ردیف‌ها با عددِ فیش نمی‌خواند برای کارمندی که تمامِ
    ماه را کار نکرده.
    """
    rows: list[dict] = []

    def add(name, direction, origin, amount, *, factor_id=None, note=""):
        amount = Decimal(amount)
        #: صفر ردیف نمی‌گیرد. فیشی با ده ردیفِ صفر، توضیح‌پذیرتر نیست — شلوغ‌تر است.
        if amount == 0:
            return
        rows.append(
            {
                "factor_id": factor_id,
                "factor_name": name,
                "direction": direction,
                "origin": origin,
                "amount": amount,
                "note": note,
            }
        )

    # ── درآمدها ──────────────────────────────────────────────────────────────
    add(
        "حقوق پایه",
        "earning",
        "contract",
        amounts["base_salary"],
        note="" if proration >= 1 else f"به نسبتِ کارکرد ({proration * 100:.0f}٪)",
    )

    #: مزایای قرارداد، **عامل به عامل**. تا امروز هر عاملی که `housing`/`food`
    #: نبود در `other_allowance` جمع می‌شد و بعد در `allowances_total` — پس
    #: «بیمه‌ی تکمیلی» و «حقِ اولاد» یک عدد می‌شدند.
    benefit_total = Decimal(0)
    for line in getattr(contract, "lines", []) or []:
        factor = getattr(line, "factor", None)
        if factor is None or factor.category != "benefit":
            continue
        #: **عاملِ «حقوق پایه» این‌جا نمی‌آید.** دسته‌اش `benefit` است (همه‌ی
        #: عوامل پیش‌فرض همین‌اند) ولی مبلغش از قبل در `base_salary` نشسته و
        #: ردیفِ خودش را بالاتر گرفته. دوباره آوردنش یعنی پایه دو بار شمرده شود.
        if factor.system_key == "base":
            continue
        amount = _round(Decimal(line.amount) * proration)
        benefit_total += amount
        add(factor.name, "earning", "contract", amount, factor_id=factor.id)

    #: باقی‌مانده‌ی مزایا — مزایایی که روی ستون‌های قرارداد نشسته‌اند ولی ردیفِ
    #: عاملی ندارند (قراردادهای پیش از مدلِ عامل‌محور). نادیده‌گرفتنش یعنی جمعِ
    #: ردیف‌ها با فیش نخواند.
    residual = Decimal(amounts["allowances_total"]) - benefit_total
    add("سایر مزایا", "earning", "contract", residual, note="بدونِ عاملِ تفکیک‌شده")

    add(
        "اضافه‌کار",
        "earning",
        "attendance",
        amounts["overtime_pay"],
        note=f"{overtime_hours:g} ساعت" if overtime_hours else "",
    )

    # ── کسورها ───────────────────────────────────────────────────────────────
    add("بیمه سهم کارمند", "deduction", "settings", amounts["insurance_employee_share"])
    add("مالیات بر درآمد حقوق", "deduction", "settings", amounts["tax_amount"])

    deduction_total = Decimal(0)
    for line in getattr(contract, "lines", []) or []:
        factor = getattr(line, "factor", None)
        if factor is None or factor.category != "deduction":
            continue
        amount = _round(Decimal(line.amount) * proration)
        deduction_total += amount
        add(factor.name, "deduction", "contract", amount, factor_id=factor.id)

    residual_deduction = Decimal(amounts["other_deductions"]) - deduction_total
    add("سایر کسورات", "deduction", "contract", residual_deduction, note="بدونِ عاملِ تفکیک‌شده")

    add("قسط وام", "deduction", "loan", amounts["loan_deduction"])

    #: تعدیلِ رند — مثبت یعنی خالص بالا گِرد شده (به نفعِ کارمند)، منفی یعنی پایین.
    #: یک ردیفِ دیدنی، نه چند ریالِ بی‌توضیح در ته فیش.
    adjustment = Decimal(amounts.get("rounding_adjustment", 0))
    if adjustment > 0:
        add("تعدیل رند", "earning", "settings", adjustment)
    elif adjustment < 0:
        add("تعدیل رند", "deduction", "settings", -adjustment)

    for index, row in enumerate(rows, start=1):
        row["seq"] = index
    return rows


def assert_breakdown_matches(amounts: dict, rows: list[dict]) -> None:
    """جمعِ ردیف‌ها باید دقیقاً خالصِ فیش را بدهد.

    این گارد این‌جاست چون تفکیک و محاسبه دو کد هستند و دو کد دیر یا زود از هم
    جدا می‌افتند. اگر عاملِ تازه‌ای به محاسبه اضافه شود و این‌جا نیاید، همین
    گارد همان لحظه می‌گیردش — نه ماه‌ها بعد سرِ شکایتِ کارمند.
    """
    earnings = sum((r["amount"] for r in rows if r["direction"] == "earning"), Decimal(0))
    deductions = sum((r["amount"] for r in rows if r["direction"] == "deduction"), Decimal(0))
    if earnings - deductions != Decimal(amounts["net_pay"]):
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "تفکیکِ فیش با خالصِ محاسبه‌شده نمی‌خواند؛ صدور متوقف شد تا عددِ "
            f"ناتوضیح‌پذیر ثبت نشود (تفکیک: {earnings - deductions}، فیش: {amounts['net_pay']})",
        )


def compute_payslip_amounts(
    contract: SalaryContract,
    attendance: Attendance | None,
    settings: PayrollSettings,
    *,
    month_index: int = 1,
    prior_taxable: Decimal | None = None,
    prior_tax: Decimal | None = None,
    tax_percent: Decimal | None = None,
    brackets: list[dict] | None = None,
    participation: dict | None = None,
) -> dict:
    """اعدادِ یک فیش.

    چهار پارامترِ کلیدواژه‌ایِ آخر سابقه‌ی سالِ جاری و گروهِ مالیاتی‌اند. پیش‌فرضشان
    «ماهِ اول، بی‌سابقه، صد درصد» است — یعنی همان رفتارِ قبلی — تا فراخوانی‌های
    موجود دست‌نخورده بمانند.
    """
    month_days = policy_value(settings, "monthly_work_days", MONTHLY_WORK_DAYS)
    worked_days = attendance.worked_days if attendance else month_days
    overtime_hours = attendance.overtime_hours if attendance else Decimal(0)

    proration = min(Decimal(1), Decimal(worked_days) / month_days)
    base_salary = _round(Decimal(contract.base_salary) * proration)
    allowances_total = _round(
        (Decimal(contract.housing_allowance) + Decimal(contract.food_allowance) + Decimal(contract.other_allowance))
        * proration
    )
    overtime_pay = calc_overtime_pay(
        Decimal(contract.base_salary),
        Decimal(overtime_hours),
        monthly_hours=policy_value(settings, "standard_monthly_hours", STANDARD_MONTHLY_HOURS),
        multiplier=policy_value(settings, "overtime_multiplier", OVERTIME_MULTIPLIER),
    )

    gross_pay = base_salary + allowances_total + overtime_pay
    #: سقفِ **ماهانه** = سقفِ روزانه × روزهای ماه، و به نسبتِ کارکرد کوچک می‌شود:
    #: کسی که نصفِ ماه کار کرده نصفِ سقف را دارد، وگرنه سقف برای او بی‌اثر می‌شد.
    daily_ceiling = policy_value(settings, "insurance_daily_ceiling", Decimal(0))
    monthly_ceiling = _round(daily_ceiling * month_days * proration) if daily_ceiling > 0 else None
    employee_rate, employer_rate = contract_insurance_rates(contract, settings)
    #: **مبنای بیمه ≠ ناخالص، اگر کاربر استثنایی تعریف کرده باشد.** جدولِ مشارکت
    #: خالی یعنی مبنا همان ناخالص است — دقیقاً رفتارِ پیش از مهاجرتِ ۰۱۳۹.
    insurance_base = gross_pay - _round(
        factor_participation.excluded_from_wage_base(contract, "insurance_base", proration, participation)
    )
    insurance_employee_share, insurance_employer_share = calc_insurance_shares(
        max(Decimal(0), insurance_base),
        employee_rate,
        employer_rate,
        ceiling=monthly_ceiling,
    )
    #: مبنای مالیات: ناخالص منهای عواملِ غیرمشمول، منهای سهمِ بیمه‌هایی که طبق
    #: ضریبِ معافیت از مبنا کم می‌شوند. تا مهاجرتِ ۰۱۳۸ ضریبِ تأمین اجتماعی عددِ
    #: ثابتِ ۱ بود و دو ضریبِ دیگر اصلاً وجود نداشتند.
    tax_base = gross_pay - _round(
        factor_participation.excluded_from_wage_base(contract, "tax_base", proration, participation)
    )
    exempt = _round(insurance_employee_share * policy_value(settings, "tax_exempt_coef_social", Decimal(1)))
    exempt += _round(
        _line_amount_for(contract, getattr(settings, "supplementary_employee_factor_id", None), proration)
        * policy_value(settings, "tax_exempt_coef_supplementary", Decimal(1))
    )
    exempt += _round(
        _line_amount_for(contract, getattr(settings, "medical_factor_id", None), proration)
        * policy_value(settings, "tax_exempt_coef_medical", Decimal(1))
    )
    #: «قسط وام مسکن معاف از مالیات» — ششمین ستونِ حکم که نوشته می‌شد و هیچ‌جا
    #: خوانده نمی‌شد. مبلغِ ماهانه است، پس به نسبتِ کارکرد کوچک می‌شود مثلِ بقیه.
    #: صفر (پیش‌فرض) = رفتارِ امروز.
    exempt += _round(Decimal(str(getattr(contract, "housing_loan_exempt_amount", 0) or 0)) * proration)
    taxable_pay = max(Decimal(0), tax_base - exempt)
    tax_amount = calc_cumulative_monthly_tax(
        monthly_taxable=taxable_pay,
        prior_taxable=prior_taxable if prior_taxable is not None else Decimal(0),
        prior_tax=prior_tax if prior_tax is not None else Decimal(0),
        month_index=month_index,
        annual_exemption=Decimal(settings.tax_exemption_annual),
        #: پله‌ها از **جدولِ مالیاتِ مؤثر** می‌آیند وقتی داده شده باشند. اگر نه،
        #: همان ستونِ `payroll_settings` — مسیرِ میراثی، برای فراخوانی‌هایی که
        #: جدول ندارند.
        brackets=brackets if brackets is not None else settings.tax_brackets,
        tax_percent=tax_percent if tax_percent is not None else Decimal(100),
        allow_negative=bool(getattr(settings, "allow_negative_tax", False)),
    )

    #: کسوراتِ قرارداد بعد از مالیات کم می‌شوند — مبنای بیمه و مالیات را تکان
    #: نمی‌دهند. قسطِ وام در `generate_payslips_for_period` جدا اضافه می‌شود، چون
    #: به دوره وابسته است نه به قرارداد.
    other_deductions = _round(contract_deductions(contract) * proration)
    net_pay = gross_pay - insurance_employee_share - tax_amount - other_deductions

    return {
        "base_salary": base_salary,
        "allowances_total": allowances_total,
        "overtime_pay": overtime_pay,
        "gross_pay": gross_pay,
        "insurance_employee_share": insurance_employee_share,
        "insurance_employer_share": insurance_employer_share,
        "taxable_pay": taxable_pay,
        "tax_amount": tax_amount,
        "loan_deduction": Decimal(0),
        "other_deductions": other_deductions,
        #: رند **بعد از** کسرِ قسطِ وام اعمال می‌شود، و قسط به دوره وابسته است نه
        #: به قرارداد؛ پس این‌جا صفر می‌ماند و `generate_payslips_for_period`
        #: پُرش می‌کند. رندکردنِ این‌جا را قسطِ بعدی به‌هم می‌زد.
        "rounding_adjustment": Decimal(0),
        "net_pay": net_pay,
    }


def _is_placeholder_tax_config(settings: PayrollSettings) -> bool:
    """آیا پلکان مالیات هنوز همان مقدار placeholder ساخته‌شده در seed است؟

    seed عمداً پلکان را با نرخ صفر می‌سازد تا هیچ عددی به‌اشتباه مبنای قانونی فرض نشود،
    ولی هیچ چیزی جلوی صدور فیش با همان مقدار را نمی‌گرفت — نتیجه‌اش فیش با مالیات صفر
    کسرشده است که مسئولیت قانونی کارفرماست. مالیات حقوق در ایران هرگز در همه‌ی پلکان‌ها
    صفر نیست (معافیت، درآمد پایین را پوشش می‌دهد)، پس نرخِ سراسر صفر بدون ابهام یعنی
    تنظیمات واقعی هنوز وارد نشده.
    """
    brackets = settings.tax_brackets or []
    if not brackets:
        return True
    return all(Decimal(str(b.get("rate", "0"))) == 0 for b in brackets)


def generate_payslips_for_period(db: Session, period_id: UUID, user: User) -> list[Payslip]:
    period = db.get(PayrollPeriod, period_id)
    if period is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "دوره حقوقی یافت نشد")
    if period.status == "finalized":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "این دوره قبلاً نهایی شده؛ امکان صدور مجدد نیست")

    settings = db.query(PayrollSettings).filter(PayrollSettings.year == period.year).first()
    if settings is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"تنظیمات حقوق (نرخ بیمه/مالیات) برای سال {period.year} ثبت نشده است",
        )

    if _is_placeholder_tax_config(settings):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"پلکان مالیات سال {period.year} هنوز مقدار placeholder (نرخ صفر) دارد. صدور فیش با این "
            "تنظیمات یعنی مالیات حقوق صفر کسر می‌شود که مسئولیت قانونی کارفرماست. ابتدا با "
            "PUT /api/payroll-settings ارقام رسمی همان سال را ثبت کنید.",
        )

    already_issued = db.query(Payslip).filter(Payslip.period_id == period_id).count()
    if already_issued > 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "برای این دوره قبلاً فیش صادر شده است")

    as_of = _period_as_of_date(period)
    assert_period_open(db, as_of)

    employees = db.query(Employee).filter(Employee.is_active.is_(True)).all()
    attendance_by_employee = {
        a.employee_id: a for a in db.query(Attendance).filter(Attendance.period_id == period_id).all()
    }

    payslips: list[Payslip] = []
    total_gross = Decimal(0)
    total_insurance_employee = Decimal(0)
    total_insurance_employer = Decimal(0)
    total_tax = Decimal(0)
    total_net = Decimal(0)
    total_loan_deduction = Decimal(0)
    total_other_deductions = Decimal(0)
    total_rounding = Decimal(0)
    #: یک‌بار خوانده می‌شود و برای **همه‌ی** فیش‌های دوره همین می‌ماند — یک اجرا،
    #: یک نسخه‌ی منسجم از تنظیمات. اگر وسطِ اجرا کسی تنظیم را عوض کند، نصفِ
    #: کارکنان با قاعده‌ی قدیم و نصف با قاعده‌ی تازه حساب می‌شدند.
    rounding_digits = int(getattr(settings, "payment_rounding_digits", 0) or 0)
    #: همان دلیل: استثناهای مشارکتِ عامل یک‌بار خوانده می‌شوند و برای همه‌ی
    #: فیش‌های این دوره همان می‌مانند.
    participation = factor_participation.participation_map(db)

    for employee in employees:
        contract = get_current_contract(db, employee.id, as_of)
        if contract is None:
            continue  # کارمندی بدون حکم حقوقی فعال، از این دوره صرف‌نظر می‌شود

        prior = _year_to_date(db, employee.id, period)

        #: **کدام قاعده؟** جدولِ مؤثرِ همین تاریخ، برای گروهِ مالیاتیِ همین حکم.
        #: اگر جدولی نبود (داده‌ی پیش از ۰۱۳۷، یا جدولِ حذف‌شده) به ستونِ
        #: `payroll_settings` و ضربِ درصدِ گروه برمی‌گردد — رفتارِ دیروز، تا
        #: هیچ مستأجری بی‌محاسبه نماند.
        table = resolve_tax_table(
            db, on=as_of, tax_group_id=getattr(contract, "tax_group_id", None), calculation_type="salary"
        )
        amounts = compute_payslip_amounts(
            contract,
            attendance_by_employee.get(employee.id),
            settings,
            brackets=bracket_rows(table) if table is not None else None,
            #: ماهِ شمسیِ دوره همان شماره‌ی ماه در سالِ مالی است (۱ = فروردین).
            month_index=period.month,
            prior_taxable=prior["taxable"],
            prior_tax=prior["tax"],
            #: **درصدِ گروه فقط در مسیرِ میراثی ضرب می‌شود.** جدولِ گروه نرخ‌هایش
            #: را از قبل دارد (مهاجرتِ ۰۱۳۷ ضرب را یک‌بار در داده منجمد کرد)، و
            #: ضربِ دوباره یعنی «مناطق محروم» ۲۵٪ بگیرد به‌جای ۵۰٪.
            tax_percent=Decimal(100) if table is not None else _tax_percent(db, contract),
            participation=participation,
        )

        #: اقساطِ سررسیدشده‌ی وام از **خالص** کم می‌شوند، نه از ناخالص: بازپرداختِ
        #: وام هزینه‌ی کارفرما نیست و مبنای بیمه و مالیات را تغییر نمی‌دهد — فقط
        #: بخشی از همان خالص به‌جای جیبِ کارمند، بدهیِ وامش را می‌بندد.
        loan_deduction = payroll_loans.deduct_for_period(db, employee.id, period)
        if loan_deduction:
            #: بیش از خالص کسر نمی‌شود؛ باقی‌اش سرِ جایش می‌ماند برای ماهِ بعد.
            loan_deduction = min(loan_deduction, amounts["net_pay"])
            amounts["net_pay"] -= loan_deduction
        amounts["loan_deduction"] = loan_deduction
        total_loan_deduction += loan_deduction

        #: **رند، یک‌جا و آخرِ همه.** فصلِ مرجع صریح است که رند نباید در محاسبه،
        #: سند، فایلِ بانک و رابط جداگانه انجام شود. این‌جا تنها جایی است که خالص
        #: گِرد می‌شود؛ باقیِ سیستم همین عدد را برمی‌دارد.
        rounded_net = round_payment(amounts["net_pay"], rounding_digits)
        amounts["rounding_adjustment"] = rounded_net - amounts["net_pay"]
        amounts["net_pay"] = rounded_net
        total_rounding += amounts["rounding_adjustment"]

        #: تفکیک **در همان لحظه** ساخته می‌شود، از همان قراردادی که محاسبه با آن
        #: انجام شد. ساختنش بعداً یعنی خواندنِ قراردادِ *آن‌موقع* — که ممکن است
        #: دیگر وجود نداشته باشد.
        attendance_row = attendance_by_employee.get(employee.id)
        worked = Decimal(attendance_row.worked_days) if attendance_row else Decimal(30)
        breakdown = payslip_breakdown(
            contract,
            amounts,
            proration=min(Decimal(1), worked / Decimal(30)),
            overtime_hours=Decimal(attendance_row.overtime_hours) if attendance_row else Decimal(0),
        )
        assert_breakdown_matches(amounts, breakdown)

        payslip_number = next_document_number(db, DOC_PAYSLIP)
        payslip = Payslip(
            number=payslip_number,
            employee_id=employee.id,
            period_id=period_id,
            created_by_id=user.id,
            #: عکسِ شعبه‌ی قانونی **در همان لحظه**، از همان حکمی که محاسبه با آن
            #: انجام شد. خواندنش بعداً یعنی خواندنِ مِسترِ *امروز* — و آن‌وقت
            #: بازتولیدِ فایلِ بیمه‌ی یک دوره‌ی بسته عددِ دیگری می‌دهد.
            **_branch_snapshot(db, contract),
            #: **کدام قاعده این مالیات را ساخت.** بی این پیوند، `tax_amount` یک
            #: عددِ بی‌توضیح است و «چرا این‌قدر؟» جوابی ندارد.
            tax_table_id=table.id if table is not None else None,
            **amounts,
        )
        payslip.lines = [PayslipLine(**row) for row in breakdown]
        db.add(payslip)
        payslips.append(payslip)

        total_gross += amounts["gross_pay"]
        total_insurance_employee += amounts["insurance_employee_share"]
        total_insurance_employer += amounts["insurance_employer_share"]
        total_tax += amounts["tax_amount"]
        total_net += amounts["net_pay"]
        total_other_deductions += amounts["other_deductions"]

    if not payslips:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "هیچ کارمند فعالی با حکم حقوقی معتبر برای این دوره یافت نشد")

    # سند حسابداری جمعی دوره: هزینه‌ی حقوق ناخالص + سهم بیمه کارفرما در برابر بدهی به کارکنان/بیمه و مالیات پرداختنی
    total_employer_cost = total_gross + total_insurance_employer
    journal_lines = [
        JournalLine(account_id=get_account(db, cc.PAYROLL_EXPENSE).id, debit=total_employer_cost, credit=0),
        JournalLine(
            account_id=get_account(db, cc.PAYROLL_PAYABLE).id,
            debit=0,
            credit=total_net,
            description="خالص پرداختنی به کارکنان",
        ),
        JournalLine(
            account_id=get_account(db, cc.INSURANCE_TAX_PAYABLE).id,
            debit=0,
            credit=total_insurance_employee + total_insurance_employer,
            description="سهم بیمه کارمند و کارفرما",
        ),
        JournalLine(
            account_id=get_account(db, cc.INSURANCE_TAX_PAYABLE).id,
            debit=0,
            credit=total_tax,
            description="مالیات حقوق پرداختنی",
        ),
    ]
    #: بازپرداختِ وام: خالصِ پرداختنی به کارکنان کمتر شده و همان مبلغ از مانده‌ی
    #: وامِ کارکنان (دارایی) کم می‌شود. سند بدونِ این ردیف متوازن نمی‌ماند.
    if total_loan_deduction:
        journal_lines.append(
            JournalLine(
                account_id=_employee_loan_account(db).id,
                debit=0,
                credit=total_loan_deduction,
                description="بازپرداختِ اقساطِ وامِ کارکنان",
            )
        )
    #: **باگی که تا امروز سند را نامتوازن می‌کرد.** ردیف‌های کسوراتِ قرارداد خالص
    #: را کم می‌کردند ولی هیچ ردیفِ بستانکاری نداشتند، پس سندِ حقوقِ هر قراردادی
    #: که کسور داشت دقیقاً به همان اندازه بدهکارِ بیشتر ثبت می‌شد. تراز آزمایشی
    #: به‌هم می‌خورد و هیچ نگهبانی خبر نمی‌داد.
    #:
    #: این پول از کارمند نگه داشته شده و به شخصِ ثالث بدهکاریم — بدهی است، نه
    #: کاهشِ هزینه.
    if total_other_deductions:
        journal_lines.append(
            JournalLine(
                account_id=_payroll_deductions_account(db).id,
                debit=0,
                credit=total_other_deductions,
                description="سایر کسورِ حقوق (نگه‌داشته از کارکنان)",
            )
        )
    #: تعدیلِ رند. مثبت یعنی خالص بالا گِرد شده، پس چند ریال بیشتر پرداختنی است و
    #: همان‌قدر هزینه‌ی رند بدهکار می‌شود؛ منفی برعکس. **داخلِ هزینه‌ی حقوق گم
    #: نمی‌شود** تا هزینه‌ی حقوقِ دفتر با جمعِ فیش‌ها بخواند.
    if total_rounding:
        rounding_account = _payroll_rounding_account(db)
        journal_lines.append(
            JournalLine(
                account_id=rounding_account.id,
                debit=total_rounding if total_rounding > 0 else 0,
                credit=-total_rounding if total_rounding < 0 else 0,
                description="تعدیلِ گِرد کردنِ خالصِ حقوق",
            )
        )
    journal_entry = make_journal_entry(
        db, as_of, f"حقوق و دستمزد دوره {period.year}/{period.month:02d}", "payroll", user, journal_lines
    )

    for payslip in payslips:
        payslip.journal_entry_id = journal_entry.id
    period.status = "finalized"

    db.flush()
    for payslip in payslips:
        db.refresh(payslip)
    return payslips


def _period_payslips(db: Session, period_id: UUID) -> tuple[list, PayrollPeriod]:
    """فیش‌های یک دوره به‌همراه کارمندشان — پایه‌ی هر سه خروجیِ CSV.

    یک تابع، سه خروجی: اگر هرکدام کوئریِ خودش را می‌زد، فیلترِ «فیشِ همین دوره» سه
    جا تکرار می‌شد و اصلاحِ یکی، دوتای دیگر را عقب می‌گذاشت.
    """
    period = db.get(PayrollPeriod, period_id)
    if period is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "دوره حقوقی یافت نشد")

    rows = (
        db.query(Payslip, Employee)
        .join(Employee, Payslip.employee_id == Employee.id)
        .filter(Payslip.period_id == period_id)
        .order_by(Employee.first_name, Employee.last_name)
        .all()
    )
    if not rows:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "برای این دوره هنوز فیشی صادر نشده است")
    return rows, period



# ─────────────────────── هویتِ کارمند: یک آدم، یک حقیقت ───────────────────────


@dataclass(frozen=True)
class EmployeeIdentity:
    """نام و شناسه‌ی کارمند، از **طرف حسابِ متصل**.

    `Employee` هنگامِ استخدام نام و کدِ ملی و تلفن را از طرف حساب کپی می‌کرد و
    بعد هرگز همگام نمی‌شد. نتیجه دو حقیقت از یک آدم بود — و چون هر سه خروجیِ
    قانونی (مالیات، بیمه، دیسکتِ پرداخت) از همان کپی می‌خواندند، **اصلاحِ نام یا
    کدِ ملی هیچ‌وقت به فایلِ بانک و اظهارنامه نمی‌رسید**.

    حالا یک جا حل می‌شود: اگر طرف حسابی به این کارمند وصل باشد، هویت از آن‌جا
    می‌آید. ستون‌های خودِ `Employee` **پشتیبان** می‌مانند، نه حقیقتِ دوم — برای
    کارمندانِ میراثی که هنوز طرف حساب ندارند.

    **این‌جا چیزی ذخیره نمی‌شود.** فیشِ صادرشده اعدادش را snapshot دارد و آن
    درست است؛ ولی نامِ روی فایلِ بانکِ *این ماه* باید نامِ امروزِ آن آدم باشد، نه
    نامی که سالِ پیش موقعِ استخدام کپی شده.
    """

    first_name: str
    last_name: str
    national_id: str
    phone: str
    #: `True` یعنی هویت از طرف حساب آمد. `False` یعنی کارمندِ بی‌طرف‌حساب — که
    #: از این پس ساخته نمی‌شود ولی ممکن است از قبل مانده باشد.
    from_contact: bool

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


def employee_identities(db: Session, employee_ids: list[UUID]) -> dict[UUID, EmployeeIdentity]:
    """هویتِ چند کارمند با **یک** کوئری — نه یکی به‌ازای هر ردیفِ فایل."""
    if not employee_ids:
        return {}
    employees = {e.id: e for e in db.query(Employee).filter(Employee.id.in_(employee_ids)).all()}
    contacts = {
        c.employee_id: c
        for c in db.query(Contact).filter(Contact.employee_id.in_(employee_ids)).all()
    }
    out: dict[UUID, EmployeeIdentity] = {}
    for employee_id in employee_ids:
        employee = employees.get(employee_id)
        contact = contacts.get(employee_id)
        if contact is not None:
            #: نامِ تفکیک‌شده ترجیح دارد؛ طرف‌حسابِ یک‌تکه (شرکت) `name` دارد و
            #: `first_name` ندارد، پس آن‌جا کلِ نام در نامِ کوچک می‌نشیند.
            first = (contact.first_name or contact.name or "").strip()
            last = (contact.last_name or "").strip()
            out[employee_id] = EmployeeIdentity(
                first_name=first,
                last_name=last,
                #: کدِ ملیِ خالیِ طرف حساب به کپیِ کارمند برنمی‌گردد — اگر کاربر
                #: پاکش کرده، فایل هم باید خالی باشد تا دیده شود، نه اینکه
                #: مقدارِ کهنه را بی‌صدا جا بزند.
                national_id=(contact.national_id or "").strip(),
                phone=(contact.phone or "").strip(),
                from_contact=True,
            )
        elif employee is not None:
            out[employee_id] = EmployeeIdentity(
                first_name=(employee.first_name or "").strip(),
                last_name=(employee.last_name or "").strip(),
                national_id=(employee.national_id or "").strip(),
                phone=(employee.phone or "").strip(),
                from_contact=False,
            )
    return out


def employee_identity(db: Session, employee_id: UUID) -> EmployeeIdentity | None:
    return employee_identities(db, [employee_id]).get(employee_id)


# ────────────────── شعبه‌ی بیمه و حوزه‌ی مالیاتی در فایلِ قانونی ──────────────────


@dataclass(frozen=True)
class BranchRef:
    """کد و عنوانِ شعبه‌ای که یک کارمند زیرِ آن بیمه یا مالیات می‌دهد."""

    code: str
    name: str


#: کدام ستونِ قرارداد برای کدام نوعِ شعبه. `BRANCH_KINDS` مقادیرِ مجاز را دارد و
#: این نگاشت فقط می‌گوید هرکدام روی قرارداد کجا نشسته است.
_BRANCH_COLUMN = {"insurance": "insurance_branch_id", "tax": "tax_branch_id"}


def payslip_branches(db: Session, rows, as_of, *, kind: str) -> dict[UUID, BranchRef]:
    """شعبه‌ی هر ردیفِ فایل — **اول از عکسِ فیش**، بعد از حکمِ زنده.

    ترتیب مهم است و کلِ نکته‌ی همین‌جاست: فیشی که عکس دارد هرگز به مِسترِ امروز
    نگاه نمی‌کند، پس بازتولیدِ فایلِ یک دوره‌ی بسته همیشه همان عدد را می‌دهد حتی
    اگر کارگاه دوباره ثبت شده و کدش عوض شده باشد.

    حلِ زنده فقط برای فیش‌هایی است که **پیش از مهاجرتِ ۰۱۳۶** صادر شده‌اند و
    عکسی ندارند. برای آن‌ها بهترین کاری که می‌شود کرد همان حکمِ آن تاریخ است؛
    اختراعِ عکسی که گرفته نشده، دروغِ تازه‌ای می‌سازد.
    """
    snapshot: dict[UUID, BranchRef] = {}
    needs_live: list[UUID] = []
    for payslip, employee in rows:
        code = getattr(payslip, f"{kind}_branch_code", None)
        name = getattr(payslip, f"{kind}_branch_name", None)
        if code is None and name is None:
            #: هر دو `None` یعنی عکسی گرفته نشده. رشته‌ی خالی یعنی عکس گرفته شد و
            #: شعبه‌ای نبود — که جوابِ قطعی است، نه جای برگشت به مِستر.
            needs_live.append(employee.id)
            continue
        snapshot[employee.id] = BranchRef(code=code or "", name=name or "")

    if needs_live:
        snapshot.update(employee_branches(db, needs_live, as_of, kind=kind))
    return snapshot


def employee_branches(db: Session, employee_ids: list[UUID], as_of, *, kind: str) -> dict[UUID, BranchRef]:
    """شعبه‌ی هر کارمند در تاریخِ `as_of`، از **حکمِ جاری‌اش**.

    تا امروز `tax_branch_id` و `insurance_branch_id` روی قرارداد نشسته بودند و
    **هیچ‌جا خوانده نمی‌شدند** — نه در محاسبه، نه در خروجی. یعنی کاربر شعبه را
    انتخاب می‌کرد و هیچ اتفاقی نمی‌افتاد. فایلِ بیمه و مالیات اولین جایی است که
    این انتخاب واقعاً به کار می‌آید: سازمان می‌خواهد بداند هر نفر زیرِ کدام شعبه
    است.

    شعبه از **حکمِ همان تاریخ** می‌آید و نه از آخرین حکم: کارمندی که ماهِ پیش
    منتقل شده، در فایلِ ماهِ پیش باید زیرِ شعبه‌ی قبلی بیاید.

    یک کوئری برای قراردادها و یکی برای شعبه‌ها — نه یکی به‌ازای هر ردیفِ فایل.
    """
    column = _BRANCH_COLUMN.get(kind)
    if not employee_ids or column is None:
        return {}

    #: همه‌ی حکم‌های *مؤثرِ* این کارکنان، تازه‌ترین اول. اولین ردیفِ هر کارمند
    #: حکمِ جاری‌اش است — همان معیارِ `get_current_contract`، ولی یک‌جا.
    contracts = (
        db.query(SalaryContract)
        .filter(
            SalaryContract.employee_id.in_(employee_ids),
            SalaryContract.effective_from <= as_of,
        )
        .order_by(SalaryContract.employee_id, SalaryContract.effective_from.desc())
        .all()
    )
    branch_of: dict[UUID, UUID] = {}
    seen: set[UUID] = set()
    for contract in contracts:
        if contract.employee_id in seen:
            continue
        #: **فقط حکمِ جاری.** اگر حکمِ جاری شعبه ندارد، کارمند شعبه ندارد — سُر
        #: خوردن به حکمِ قبلی یعنی فایل شعبه‌ای را گزارش کند که کاربر عمداً از
        #: حکمِ تازه برداشته.
        seen.add(contract.employee_id)
        branch_id = getattr(contract, column, None)
        if branch_id is not None:
            branch_of[contract.employee_id] = branch_id

    if not branch_of:
        return {}

    from app.models.payroll import InsuranceTaxBranch

    branches = {
        row.id: BranchRef(code=(row.code or "").strip(), name=(row.name or "").strip())
        for row in db.query(InsuranceTaxBranch)
        .filter(InsuranceTaxBranch.id.in_(set(branch_of.values())))
        .all()
    }
    return {
        employee_id: branches[branch_id]
        for employee_id, branch_id in branch_of.items()
        if branch_id in branches
    }


def _csv_text(header: list[str], body: list[list[str]], footer: list[str] | None = None) -> str:
    """CSVِ فارسی‌خوان برای اکسل.

    BOM ابتدای فایل لازم است، وگرنه اکسلِ ویندوز UTF-8 را windows-1256 می‌خواند و
    همه‌ی متنِ فارسی به‌هم می‌ریزد — همان تله‌ای که لیستِ بیمه یک بار خورد.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    for row in body:
        writer.writerow(row)
    if footer is not None:
        writer.writerow([])
        writer.writerow(footer)
    return "﻿" + buffer.getvalue()


def generate_tax_list_csv(db: Session, period_id: UUID) -> tuple[str, PayrollPeriod]:
    """فایلِ مالیات بر درآمدِ حقوقِ دوره.

    مثلِ لیستِ بیمه، **قالبِ ستون‌ها عمومی است** و پیش از ارسالِ رسمی به سامانه‌ی
    مالیاتی باید با آخرین مشخصاتش تطبیق داده شود. این‌جا مبنای مشمول و مالیاتِ
    محاسبه‌شده‌ی همان فیش می‌آید — نه محاسبه‌ی دوباره، تا عددِ فایل و عددِ فیشِ
    کارمند هیچ‌وقت دو تا نشوند.
    """
    rows, period = _period_payslips(db, period_id)

    employee_ids = [employee.id for _, employee in rows]
    who = employee_identities(db, employee_ids)
    #: حوزه‌ی مالیاتی از **عکسِ فیش**؛ برای فیش‌های پیش از ۰۱۳۶ از حکمِ همان
    #: دوره — نه از آخرین حکم و نه از مِسترِ امروز.
    branches = payslip_branches(db, rows, _period_as_of_date(period), kind="tax")

    body = []
    total_taxable = Decimal(0)
    total_tax = Decimal(0)
    for payslip, employee in rows:
        taxable = Decimal(payslip.taxable_pay)
        tax = Decimal(payslip.tax_amount)
        person = who[employee.id]
        branch = branches.get(employee.id)
        body.append(
            [
                person.national_id,
                person.first_name,
                person.last_name,
                #: حوزه خالی می‌ماند اگر حکم تعیینش نکرده — پرکردنش با حدس یعنی
                #: فایل چیزی را به سازمان بگوید که کسی تصمیمش نگرفته.
                branch.code if branch else "",
                branch.name if branch else "",
                str(payslip.gross_pay),
                str(taxable),
                str(tax),
            ]
        )
        total_taxable += taxable
        total_tax += tax

    text = _csv_text(
        [
            "کد ملی",
            "نام",
            "نام خانوادگی",
            "کد حوزه مالیاتی",
            "حوزه مالیاتی",
            "ناخالص حقوق",
            "درآمد مشمول مالیات",
            "مالیات",
        ],
        body,
        ["جمع کل", "", "", "", "", "", str(total_taxable), str(total_tax)],
    )
    return text, period


def generate_payment_list_csv(db: Session, period_id: UUID) -> tuple[str, PayrollPeriod]:
    """دیسکتِ پرداختِ بانک — خالصِ پرداختیِ هر کارمند به شماره‌حسابش.

    کارمندِ بی‌شماره‌حساب **حذف نمی‌شود**؛ ردیفش با شماره‌حسابِ خالی می‌آید. حذفش
    یعنی فایل بی‌صدا کمتر از حقوقِ واقعی را منتقل می‌کند و کسی تا شکایتِ کارمند
    نمی‌فهمد. ستونِ خالی در فایل دیده می‌شود.
    """
    rows, period = _period_payslips(db, period_id)

    who = employee_identities(db, [employee.id for _, employee in rows])

    body = []
    total = Decimal(0)
    for payslip, employee in rows:
        net = Decimal(payslip.net_pay)
        person = who[employee.id]
        body.append(
            [
                #: شماره‌حساب همچنان روی خودِ کارمند است — مقصدِ پرداخت واقعیتِ
                #: *استخدام* است نه هویتِ شخص، و طرف حساب ستونش را ندارد.
                employee.bank_account_number or "",
                person.full_name,
                person.national_id,
                str(net),
            ]
        )
        total += net

    text = _csv_text(
        ["شماره حساب", "نام و نام خانوادگی", "کد ملی", "مبلغ خالص پرداختی"],
        body,
        ["جمع کل", "", "", str(total)],
    )
    return text, period


def generate_insurance_list_csv(db: Session, period_id: UUID) -> tuple[str, PayrollPeriod]:
    """خروجی CSV لیست بیمه‌ی دوره برای ارسال به تأمین اجتماعی. توجه: فرمت ستون‌ها عمومی و قابل‌بازبینی است؛
    قبل از ارسال رسمی حتماً با آخرین مشخصات سامانه‌ی لیست بیمه تطبیق داده شود."""
    period = db.get(PayrollPeriod, period_id)
    if period is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "دوره حقوقی یافت نشد")

    rows = (
        db.query(Payslip, Employee)
        .join(Employee, Payslip.employee_id == Employee.id)
        .filter(Payslip.period_id == period_id)
        .order_by(Employee.first_name, Employee.last_name)
        .all()
    )
    if not rows:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "برای این دوره هنوز فیشی صادر نشده است")

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "کد ملی",
            "نام",
            "نام خانوادگی",
            "کد شعبه بیمه",
            "شعبه بیمه",
            "حقوق مشمول بیمه",
            "سهم بیمه کارمند",
            "سهم بیمه کارفرما",
            "جمع بیمه",
        ]
    )

    employee_ids = [employee.id for _, employee in rows]
    who = employee_identities(db, employee_ids)
    #: شعبه‌ی بیمه از **عکسِ فیش**. بازتولیدِ فایلِ یک دوره‌ی بسته نباید با ثبتِ
    #: تازه‌ی کارگاه عوض شود؛ فیش‌های پیش از ۰۱۳۶ به حکمِ همان دوره برمی‌گردند.
    branches = payslip_branches(db, rows, _period_as_of_date(period), kind="insurance")

    total_employee = Decimal(0)
    total_employer = Decimal(0)
    for payslip, employee in rows:
        employee_share = Decimal(payslip.insurance_employee_share)
        employer_share = Decimal(payslip.insurance_employer_share)
        person = who[employee.id]
        branch = branches.get(employee.id)
        writer.writerow(
            [
                person.national_id,
                person.first_name,
                person.last_name,
                branch.code if branch else "",
                branch.name if branch else "",
                str(payslip.gross_pay),
                str(employee_share),
                str(employer_share),
                str(employee_share + employer_share),
            ]
        )
        total_employee += employee_share
        total_employer += employer_share

    writer.writerow([])
    writer.writerow(
        [
            "جمع کل",
            "",
            "",
            "",
            "",
            "",
            str(total_employee),
            str(total_employer),
            str(total_employee + total_employer),
        ]
    )

    # BOM ابتدای فایل تا اکسل متن فارسی UTF-8 را درست نمایش دهد
    return "﻿" + buffer.getvalue(), period
