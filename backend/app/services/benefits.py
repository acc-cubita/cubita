"""مزایای پایان سال و پایان کار — عیدی، سنوات (پایان خدمت) و مرخصی.

قواعدِ قانون کار ایران (ساده‌شده و قابلِ‌تنظیم؛ ارقامِ مصوب هرسال تغییر می‌کنند):
- **عیدی:** دو ماه حقوقِ پایه، محدود به بازه‌ی [۲×، ۳×] حداقلِ حقوقِ ماهانه‌ی همان سال،
  و به‌نسبتِ روزهای کارکرد در سال. (اگر `min_base_wage` صفر باشد، سقف/کف اعمال نمی‌شود.)
- **سنوات/پایان خدمت:** یک ماه حقوقِ پایه به‌ازای هر سال سابقه = پایه × (روزهای سابقه ÷ ۳۶۵).
- **مرخصی:** استحقاقیِ سالانه (پیش‌فرض ۲۶ روز) به‌نسبتِ کارکرد، منهای مرخصی‌های استفاده‌شده؛
  طلبِ مرخصی = ماندهٔ روز × دستمزدِ روزانه (پایه ÷ ۳۰).

**سال = سالِ شمسی** (همان قراردادِ ماژول حقوق: `PayrollPeriod.year`/`PayrollSettings.year`).
بازه‌ی هر سال از اولِ فروردین تا آخرِ اسفندِ همان سالِ شمسی است و برای فیلترِ تاریخ‌ها
(که در دیتابیس میلادی‌اند) به مرزِ میلادیِ متناظر تبدیل می‌شود. صدورِ هر مزیت یک
`BenefitRun` ثبت می‌کند تا دوباره صادر نشود، و مثل فیشِ حقوق یک سندِ دوطرفه می‌زند:
بدهکارِ هزینه‌ی حقوق، بستانکارِ حقوقِ پرداختنی.
"""
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.jalali import days_in_jalali_year, gregorian_to_jalali, persian_year_end, persian_year_start
from app.models.accounting import JournalLine
from app.models.payroll import BenefitRun, Employee, LeaveRecord, PayrollSettings
from app.models.user import User
from app.schemas.payroll import LeaveRecordIn
from app.services import chart_codes as cc
from app.services.common import get_account, make_journal_entry
from app.services.payroll import get_current_contract
from app.services.period_close import assert_period_open
from app.services.tax_tables import eidi_tax

_DAILY_DIVISOR = Decimal(30)  # ماه = ۳۰ روز
_YEAR_DIVISOR = Decimal(365)


def _round(v: Decimal) -> Decimal:
    return v.quantize(Decimal(1), rounding=ROUND_HALF_UP)


def _days_in_year(year: int) -> int:
    # سالِ شمسی: ۳۶۵ یا ۳۶۶ روز
    return days_in_jalali_year(year)


def _employed_days_in_year(emp: Employee, year: int) -> int:
    # بازه‌ی سالِ شمسی، به مرزِ میلادی
    start = max(emp.hire_date, persian_year_start(year))
    end = persian_year_end(year)
    if emp.termination_date is not None and emp.termination_date < end:
        end = emp.termination_date
    if end < start:
        return 0
    return (end - start).days + 1


def _year_proration(emp: Employee, year: int) -> Decimal:
    return Decimal(_employed_days_in_year(emp, year)) / Decimal(_days_in_year(year))


def calc_eidi(contract, settings, emp: Employee, year: int) -> Decimal:
    base = Decimal(contract.base_salary)
    full = base * 2
    min_wage = Decimal(getattr(settings, "min_base_wage", 0) or 0)
    if min_wage > 0:
        full = max(min(full, min_wage * 3), min_wage * 2)  # کف ۲×، سقف ۳×
    return _round(full * _year_proration(emp, year))


def calc_severance(contract, emp: Employee, as_of: date) -> Decimal:
    base = Decimal(contract.base_salary)
    end = as_of
    if emp.termination_date is not None and emp.termination_date < as_of:
        end = emp.termination_date
    service_days = (end - emp.hire_date).days
    if service_days <= 0:
        return Decimal(0)
    return _round(base * Decimal(service_days) / _YEAR_DIVISOR)


def _leave_used(db: Session, employee_id: UUID, year: int) -> Decimal:
    total = (
        db.query(func.coalesce(func.sum(LeaveRecord.days), 0))
        .filter(
            LeaveRecord.employee_id == employee_id,
            LeaveRecord.leave_date >= persian_year_start(year),
            LeaveRecord.leave_date <= persian_year_end(year),
        )
        .scalar()
    )
    return Decimal(total)


def calc_leave(db: Session, contract, settings, emp: Employee, year: int) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    entitled_days = Decimal(getattr(settings, "annual_leave_days", 26) or 26)
    entitled = (entitled_days * _year_proration(emp, year)).quantize(Decimal("0.01"))
    used = _leave_used(db, emp.id, year)
    remaining = entitled - used
    daily = Decimal(contract.base_salary) / _DAILY_DIVISOR
    value = _round(max(Decimal(0), remaining) * daily)
    return entitled, used, remaining, value


def _settings_for(db: Session, year: int) -> PayrollSettings | None:
    return db.query(PayrollSettings).filter(PayrollSettings.year == year).first()


def _employed_in_year(emp: Employee, year: int) -> bool:
    return _employed_days_in_year(emp, year) > 0


def get_benefits_report(db: Session, year: int, as_of: date | None = None) -> dict:
    as_of = as_of or persian_year_end(year)
    settings = _settings_for(db, year)
    employees = db.query(Employee).order_by(Employee.first_name, Employee.last_name).all()

    rows = []
    total_eidi = total_sev = total_leave = Decimal(0)
    for emp in employees:
        if not _employed_in_year(emp, year):
            continue
        contract = get_current_contract(db, emp.id, as_of)
        if contract is None:
            continue
        eidi = calc_eidi(contract, settings, emp, year)
        severance = calc_severance(contract, emp, as_of)
        entitled, used, remaining, value = calc_leave(db, contract, settings, emp, year)
        rows.append(
            {
                "employee_id": emp.id,
                "employee_name": f"{emp.first_name} {emp.last_name}".strip(),
                "base_salary": Decimal(contract.base_salary),
                "eidi": eidi,
                "severance": severance,
                "leave_entitled": entitled,
                "leave_used": used,
                "leave_remaining": remaining,
                "leave_value": value,
            }
        )
        total_eidi += eidi
        total_sev += severance
        total_leave += value

    return {
        "year": year,
        "as_of": as_of,
        "min_base_wage": Decimal(getattr(settings, "min_base_wage", 0) or 0),
        "annual_leave_days": int(getattr(settings, "annual_leave_days", 26) or 26),
        "rows": rows,
        "total_eidi": total_eidi,
        "total_severance": total_sev,
        "total_leave_value": total_leave,
    }


def set_benefit_settings(db: Session, year: int, min_base_wage: Decimal, annual_leave_days: int) -> dict:
    """فقط دو فیلدِ مزایا را روی تنظیماتِ سال می‌گذارد — بی‌آنکه به نرخ بیمه/مالیات دست بزند.

    اگر ردیفِ تنظیماتِ سال هنوز نباشد، با پلکانِ placeholderِ نرخ‌صفر ساخته می‌شود؛ همان
    گاردِ موجود جلوی صدورِ فیشِ حقوق با این تنظیماتِ ناقص را می‌گیرد، پس ساختنش امن است.
    """
    settings = _settings_for(db, year)
    if settings is None:
        settings = PayrollSettings(
            year=year,
            insurance_employee_rate=Decimal(0),
            insurance_employer_rate=Decimal(0),
            tax_exemption_annual=Decimal(0),
            tax_brackets=[{"up_to": None, "rate": "0"}],
            min_base_wage=min_base_wage,
            annual_leave_days=annual_leave_days,
        )
        db.add(settings)
    else:
        settings.min_base_wage = min_base_wage
        settings.annual_leave_days = annual_leave_days
    db.flush()
    return {"year": year, "min_base_wage": Decimal(settings.min_base_wage), "annual_leave_days": int(settings.annual_leave_days)}


# --- مرخصی: ثبت و فهرست --------------------------------------------------------------


def record_leave(db: Session, data: LeaveRecordIn, user: User) -> LeaveRecord:
    if db.get(Employee, data.employee_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "کارمند یافت نشد")
    rec = LeaveRecord(
        employee_id=data.employee_id, leave_date=data.leave_date, days=data.days, note=data.note, created_by_id=user.id
    )
    db.add(rec)
    db.flush()
    db.refresh(rec)
    return rec


def list_leave(db: Session, employee_id: UUID | None = None) -> list[LeaveRecord]:
    q = db.query(LeaveRecord)
    if employee_id:
        q = q.filter(LeaveRecord.employee_id == employee_id)
    return q.order_by(LeaveRecord.leave_date.desc()).all()


# --- صدور (ثبت سند) -----------------------------------------------------------------


def _post_benefit(
    db: Session, description: str, amount: Decimal, run_date: date, user: User, *, tax: Decimal = Decimal(0)
):
    """سندِ مزیت: بدهکارِ هزینه‌ی حقوق، بستانکارِ پرداختنی — و مالیات اگر باشد.

    بی مالیات دوخطی می‌ماند، دقیقاً مثلِ قبل. با مالیات سه‌خطی می‌شود: هزینه
    همچنان ناخالص است (هزینه‌ی کارفرما عوض نشده)، ولی بخشی از آن به‌جای جیبِ
    کارمند به «بیمه و مالیات پرداختنی» می‌رود.
    """
    lines = [JournalLine(account_id=get_account(db, cc.PAYROLL_EXPENSE).id, debit=amount, credit=0)]
    if tax > 0:
        lines.append(
            JournalLine(
                account_id=get_account(db, cc.PAYROLL_PAYABLE).id,
                debit=0,
                credit=amount - tax,
                description=description,
            )
        )
        lines.append(
            JournalLine(
                account_id=get_account(db, cc.INSURANCE_TAX_PAYABLE).id,
                debit=0,
                credit=tax,
                description=f"مالیات {description}",
            )
        )
    else:
        lines.append(
            JournalLine(
                account_id=get_account(db, cc.PAYROLL_PAYABLE).id, debit=0, credit=amount, description=description
            )
        )
    return make_journal_entry(db, run_date, description, "payroll_benefit", user, lines)


def issue_eidi(db: Session, year: int, user: User, run_date: date | None = None) -> dict:
    if db.query(BenefitRun).filter(BenefitRun.kind == "eidi", BenefitRun.year == year).first() is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"عیدیِ سال {year} قبلاً صادر شده است")
    run_date = run_date or min(date.today(), persian_year_end(year))
    assert_period_open(db, run_date)

    report = get_benefits_report(db, year, as_of=persian_year_end(year))
    total = Decimal(report["total_eidi"])
    if total <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "برای این سال عیدیِ قابلِ صدوری وجود ندارد")

    #: **عیدی جدولِ مالیاتِ خودش را دارد، نه جدولِ حقوق.**
    #:
    #: آستانه‌ها و پله‌هایشان یکی نیستند، پس استفاده از جدولِ حقوق برای عیدی یک
    #: عددِ اشتباه می‌دهد که هیچ‌چیز آشکارش نمی‌کند.
    #:
    #: تا وقتی کاربر جدولِ عیدی تعریف نکرده، `None` برمی‌گردد و عیدی **بی‌مالیات**
    #: می‌ماند — همان رفتارِ امروز. ساختنِ خودکارِ جدولِ عیدی یعنی یک مهاجرت
    #: بی‌خبر مالیات کسر کند، و آن تصمیمِ کاربر است نه ما.
    tax = eidi_tax(db, total, on=run_date)

    entry = _post_benefit(db, f"عیدی و پاداش سال {year}", total, run_date, user, tax=tax)
    run = BenefitRun(kind="eidi", year=year, amount=total, run_date=run_date, journal_entry_id=entry.id, created_by_id=user.id)
    db.add(run)
    db.flush()
    return {"kind": "eidi", "amount": total, "tax": tax, "journal_entry_number": entry.number}


def issue_severance(db: Session, employee_id: UUID, user: User, as_of: date | None = None) -> dict:
    emp = db.get(Employee, employee_id)
    if emp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "کارمند یافت نشد")
    if db.query(BenefitRun).filter(BenefitRun.kind == "severance", BenefitRun.employee_id == employee_id).first() is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "سنوات این کارمند قبلاً صادر شده است")
    as_of = as_of or emp.termination_date or date.today()
    contract = get_current_contract(db, employee_id, as_of)
    if contract is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "این کارمند حکمِ حقوقی ندارد")
    amount = calc_severance(contract, emp, as_of)
    if amount <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "سابقه‌ی خدمت برای محاسبه‌ی سنوات کافی نیست")
    assert_period_open(db, as_of)

    name = f"{emp.first_name} {emp.last_name}".strip()
    entry = _post_benefit(db, f"سنوات پایان خدمت — {name}", amount, as_of, user)
    run = BenefitRun(
        kind="severance", year=gregorian_to_jalali(as_of)[0], employee_id=employee_id, amount=amount, run_date=as_of,
        journal_entry_id=entry.id, created_by_id=user.id,
    )
    db.add(run)
    db.flush()
    return {"kind": "severance", "amount": amount, "journal_entry_number": entry.number}


def issue_leave_payout(db: Session, employee_id: UUID, year: int, user: User, run_date: date | None = None) -> dict:
    emp = db.get(Employee, employee_id)
    if emp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "کارمند یافت نشد")
    existing = (
        db.query(BenefitRun)
        .filter(BenefitRun.kind == "leave_payout", BenefitRun.employee_id == employee_id, BenefitRun.year == year)
        .first()
    )
    if existing is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "بازخریدِ مرخصیِ این کارمند برای این سال قبلاً ثبت شده است")

    as_of = run_date or min(date.today(), persian_year_end(year))
    contract = get_current_contract(db, employee_id, persian_year_end(year))
    if contract is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "این کارمند حکمِ حقوقی ندارد")
    _, _, _, value = calc_leave(db, contract, _settings_for(db, year), emp, year)
    if value <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ماندهٔ مرخصیِ قابلِ بازخریدی وجود ندارد")
    assert_period_open(db, as_of)

    name = f"{emp.first_name} {emp.last_name}".strip()
    entry = _post_benefit(db, f"بازخرید مرخصی سال {year} — {name}", value, as_of, user)
    run = BenefitRun(
        kind="leave_payout", year=year, employee_id=employee_id, amount=value, run_date=as_of,
        journal_entry_id=entry.id, created_by_id=user.id,
    )
    db.add(run)
    db.flush()
    return {"kind": "leave_payout", "amount": value, "journal_entry_number": entry.number}
