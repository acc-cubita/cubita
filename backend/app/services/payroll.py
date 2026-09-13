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
from app.services import payroll_loans
from app.services.common import get_account, get_or_create_account, make_journal_entry
from app.services.period_close import assert_period_open

# طبق قانون کار ایران: پایه‌ی ساعتی از تقسیم بر ۱۹۴ ساعت کاری استاندارد ماهانه و ضریب اضافه‌کاری ۱.۴ به‌دست می‌آید.
STANDARD_MONTHLY_HOURS = Decimal("194")
OVERTIME_MULTIPLIER = Decimal("1.4")


def _round(value: Decimal) -> Decimal:
    return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def calc_overtime_pay(base_salary: Decimal, overtime_hours: Decimal) -> Decimal:
    if overtime_hours <= 0:
        return Decimal(0)
    hourly_rate = base_salary / STANDARD_MONTHLY_HOURS
    return _round(hourly_rate * OVERTIME_MULTIPLIER * overtime_hours)


def calc_insurance_shares(insurable_pay: Decimal, employee_rate: Decimal, employer_rate: Decimal) -> tuple[Decimal, Decimal]:
    return _round(insurable_pay * employee_rate), _round(insurable_pay * employer_rate)


def calc_annual_tax(annual_taxable: Decimal, brackets: list[dict]) -> Decimal:
    """محاسبه‌ی پلکانی مالیات سالانه. brackets صعودی و هر ردیف {"up_to": سقف تجمعی یا None, "rate": نرخ}."""
    if annual_taxable <= 0:
        return Decimal(0)

    tax = Decimal(0)
    lower = Decimal(0)
    for bracket in brackets:
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

    مقدارِ منفی برنمی‌گرداند: اگر ماهی کم‌درآمد باعث شود مالیاتِ تجمیعیِ لازم از
    آنچه تا حالا کسر شده کمتر باشد، **مسترد نمی‌کنیم** — استردادِ مالیات کارِ
    تعدیلِ پایانِ سال است، نه فیشِ ماهانه.
    """
    months = max(1, min(12, month_index))
    ytd_taxable = max(Decimal(0), prior_taxable + monthly_taxable)

    #: سالانه‌سازی به نسبتِ ماه‌های سپری‌شده — نه ضرب در ۱۲ که ماه‌های نیامده را هم
    #: به حساب می‌آورد.
    annualized = ytd_taxable * 12 / months
    annual_after_exemption = max(Decimal(0), annualized - annual_exemption)
    annual_tax = calc_annual_tax(annual_after_exemption, brackets) * tax_percent / 100

    tax_due_to_date = annual_tax * months / 12
    return max(Decimal(0), _round(tax_due_to_date - prior_tax))


def get_current_contract(db: Session, employee_id: UUID, as_of) -> SalaryContract | None:
    return (
        db.query(SalaryContract)
        .filter(SalaryContract.employee_id == employee_id, SalaryContract.effective_from <= as_of)
        .order_by(SalaryContract.effective_from.desc())
        .first()
    )


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
) -> dict:
    """اعدادِ یک فیش.

    چهار پارامترِ کلیدواژه‌ایِ آخر سابقه‌ی سالِ جاری و گروهِ مالیاتی‌اند. پیش‌فرضشان
    «ماهِ اول، بی‌سابقه، صد درصد» است — یعنی همان رفتارِ قبلی — تا فراخوانی‌های
    موجود دست‌نخورده بمانند.
    """
    worked_days = attendance.worked_days if attendance else Decimal(30)
    overtime_hours = attendance.overtime_hours if attendance else Decimal(0)

    proration = min(Decimal(1), Decimal(worked_days) / Decimal(30))
    base_salary = _round(Decimal(contract.base_salary) * proration)
    allowances_total = _round(
        (Decimal(contract.housing_allowance) + Decimal(contract.food_allowance) + Decimal(contract.other_allowance))
        * proration
    )
    overtime_pay = calc_overtime_pay(Decimal(contract.base_salary), Decimal(overtime_hours))

    gross_pay = base_salary + allowances_total + overtime_pay
    insurance_employee_share, insurance_employer_share = calc_insurance_shares(
        gross_pay, Decimal(settings.insurance_employee_rate), Decimal(settings.insurance_employer_rate)
    )
    taxable_pay = max(Decimal(0), gross_pay - insurance_employee_share)
    tax_amount = calc_cumulative_monthly_tax(
        monthly_taxable=taxable_pay,
        prior_taxable=prior_taxable if prior_taxable is not None else Decimal(0),
        prior_tax=prior_tax if prior_tax is not None else Decimal(0),
        month_index=month_index,
        annual_exemption=Decimal(settings.tax_exemption_annual),
        brackets=settings.tax_brackets,
        tax_percent=tax_percent if tax_percent is not None else Decimal(100),
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

    for employee in employees:
        contract = get_current_contract(db, employee.id, as_of)
        if contract is None:
            continue  # کارمندی بدون حکم حقوقی فعال، از این دوره صرف‌نظر می‌شود

        prior = _year_to_date(db, employee.id, period)
        amounts = compute_payslip_amounts(
            contract,
            attendance_by_employee.get(employee.id),
            settings,
            #: ماهِ شمسیِ دوره همان شماره‌ی ماه در سالِ مالی است (۱ = فروردین).
            month_index=period.month,
            prior_taxable=prior["taxable"],
            prior_tax=prior["tax"],
            tax_percent=_tax_percent(db, contract),
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
            number=payslip_number, employee_id=employee.id, period_id=period_id, created_by_id=user.id, **amounts
        )
        payslip.lines = [PayslipLine(**row) for row in breakdown]
        db.add(payslip)
        payslips.append(payslip)

        total_gross += amounts["gross_pay"]
        total_insurance_employee += amounts["insurance_employee_share"]
        total_insurance_employer += amounts["insurance_employer_share"]
        total_tax += amounts["tax_amount"]
        total_net += amounts["net_pay"]

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

    who = employee_identities(db, [employee.id for _, employee in rows])

    body = []
    total_taxable = Decimal(0)
    total_tax = Decimal(0)
    for payslip, employee in rows:
        taxable = Decimal(payslip.taxable_pay)
        tax = Decimal(payslip.tax_amount)
        person = who[employee.id]
        body.append(
            [
                person.national_id,
                person.first_name,
                person.last_name,
                str(payslip.gross_pay),
                str(taxable),
                str(tax),
            ]
        )
        total_taxable += taxable
        total_tax += tax

    text = _csv_text(
        ["کد ملی", "نام", "نام خانوادگی", "ناخالص حقوق", "درآمد مشمول مالیات", "مالیات"],
        body,
        ["جمع کل", "", "", "", str(total_taxable), str(total_tax)],
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
        ["کد ملی", "نام", "نام خانوادگی", "حقوق مشمول بیمه", "سهم بیمه کارمند", "سهم بیمه کارفرما", "جمع بیمه"]
    )

    who = employee_identities(db, [employee.id for _, employee in rows])

    total_employee = Decimal(0)
    total_employer = Decimal(0)
    for payslip, employee in rows:
        employee_share = Decimal(payslip.insurance_employee_share)
        employer_share = Decimal(payslip.insurance_employer_share)
        person = who[employee.id]
        writer.writerow(
            [
                person.national_id,
                person.first_name,
                person.last_name,
                str(payslip.gross_pay),
                str(employee_share),
                str(employer_share),
                str(employee_share + employer_share),
            ]
        )
        total_employee += employee_share
        total_employer += employer_share

    writer.writerow([])
    writer.writerow(["جمع کل", "", "", "", str(total_employee), str(total_employer), str(total_employee + total_employer)])

    # BOM ابتدای فایل تا اکسل متن فارسی UTF-8 را درست نمایش دهد
    return "﻿" + buffer.getvalue(), period
