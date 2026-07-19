import csv
import io
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.accounting import JournalLine
from app.models.payroll import (
    Attendance,
    Employee,
    PayrollPeriod,
    PayrollSettings,
    Payslip,
    SalaryContract,
)
from app.models.user import User
from app.services import chart_codes as cc
from app.services.common import get_account, make_journal_entry
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


def get_current_contract(db: Session, employee_id: UUID, as_of) -> SalaryContract | None:
    return (
        db.query(SalaryContract)
        .filter(SalaryContract.employee_id == employee_id, SalaryContract.effective_from <= as_of)
        .order_by(SalaryContract.effective_from.desc())
        .first()
    )


def _period_as_of_date(period: PayrollPeriod):
    from calendar import monthrange
    from datetime import date

    return date(period.year, period.month, monthrange(period.year, period.month)[1])


def compute_payslip_amounts(
    contract: SalaryContract, attendance: Attendance | None, settings: PayrollSettings
) -> dict:
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
    tax_amount = calc_monthly_tax(taxable_pay, Decimal(settings.tax_exemption_annual), settings.tax_brackets)
    net_pay = gross_pay - insurance_employee_share - tax_amount

    return {
        "base_salary": base_salary,
        "allowances_total": allowances_total,
        "overtime_pay": overtime_pay,
        "gross_pay": gross_pay,
        "insurance_employee_share": insurance_employee_share,
        "insurance_employer_share": insurance_employer_share,
        "taxable_pay": taxable_pay,
        "tax_amount": tax_amount,
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

    for employee in employees:
        contract = get_current_contract(db, employee.id, as_of)
        if contract is None:
            continue  # کارمندی بدون حکم حقوقی فعال، از این دوره صرف‌نظر می‌شود

        amounts = compute_payslip_amounts(contract, attendance_by_employee.get(employee.id), settings)
        payslip_number = db.execute(text("SELECT nextval('payslip_number_seq')")).scalar_one()
        payslip = Payslip(
            number=payslip_number, employee_id=employee.id, period_id=period_id, created_by_id=user.id, **amounts
        )
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

    total_employee = Decimal(0)
    total_employer = Decimal(0)
    for payslip, employee in rows:
        employee_share = Decimal(payslip.insurance_employee_share)
        employer_share = Decimal(payslip.insurance_employer_share)
        writer.writerow(
            [
                employee.national_id,
                employee.first_name,
                employee.last_name,
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
