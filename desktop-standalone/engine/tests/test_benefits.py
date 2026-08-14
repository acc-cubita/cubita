"""مزایای پایان سال/کار — عیدی (کف/سقف/تسهیم)، سنوات، مرخصی، و صدورِ سند."""
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.accounting import JournalEntry
from app.models.payroll import BenefitRun, Employee, LeaveRecord, PayrollSettings, SalaryContract
from app.schemas.payroll import LeaveRecordIn
from app.services import chart_codes as cc
from app.services.benefits import (
    calc_eidi,
    calc_leave,
    calc_severance,
    get_benefits_report,
    issue_eidi,
    issue_leave_payout,
    issue_severance,
    record_leave,
)
from app.services.common import get_account
from app.jalali import jalali_to_gregorian, persian_year_end

# سالِ شمسی (۱۴۰۴ = ۲۰۲۵-۰۳-۲۱ تا ۲۰۲۶-۰۳-۲۰). تاریخ‌هایی که باید داخلِ این سال
# بیفتند با jalali_to_gregorian ساخته می‌شوند تا فیلترِ سالِ شمسی درست بسنجدشان.
YEAR = 1404


def _employee(db, *, hire=date(2024, 1, 1), termination=None, base=10_000_000, nid=None):
    emp = Employee(
        first_name="علی", last_name="رضایی", national_id=nid or str(uuid4())[:10],
        hire_date=hire, termination_date=termination, is_active=True,
    )
    db.add(emp)
    db.flush()
    db.add(SalaryContract(employee_id=emp.id, effective_from=hire, base_salary=Decimal(base)))
    db.flush()
    return emp


def _settings(db, *, min_wage=6_000_000, leave_days=26):
    s = PayrollSettings(
        year=YEAR, insurance_employee_rate=Decimal("0.07"), insurance_employer_rate=Decimal("0.23"),
        tax_exemption_annual=Decimal(0), tax_brackets=[{"up_to": None, "rate": "0.10"}],
        min_base_wage=Decimal(min_wage), annual_leave_days=leave_days,
    )
    db.add(s)
    db.flush()
    return s


def _contract(db, emp):
    return db.query(SalaryContract).filter(SalaryContract.employee_id == emp.id).first()


def test_eidi_two_months_capped_at_three_times_minwage(db):
    emp = _employee(db, base=10_000_000)
    s = _settings(db, min_wage=6_000_000)
    # ۲×۱۰م = ۲۰م، سقف ۳×۶م = ۱۸م → ۱۸م (کارکردِ کاملِ سال)
    assert calc_eidi(_contract(db, emp), s, emp, YEAR) == Decimal(18_000_000)


def test_eidi_floored_at_two_times_minwage(db):
    emp = _employee(db, base=2_000_000)
    s = _settings(db, min_wage=6_000_000)
    # ۲×۲م = ۴م، کف ۲×۶م = ۱۲م → ۱۲م
    assert calc_eidi(_contract(db, emp), s, emp, YEAR) == Decimal(12_000_000)


def test_eidi_no_minwage_means_no_clamp(db):
    emp = _employee(db, base=10_000_000)
    s = _settings(db, min_wage=0)
    assert calc_eidi(_contract(db, emp), s, emp, YEAR) == Decimal(20_000_000)


def test_eidi_prorated_for_partial_year(db):
    # استخدام از اولِ مهرِ ۱۴۰۴ (ماهِ هفتمِ شمسی) → حدوداً نیمه‌ی دومِ سال
    emp = _employee(db, hire=jalali_to_gregorian(YEAR, 7, 1), base=10_000_000)
    s = _settings(db, min_wage=0)
    eidi = calc_eidi(_contract(db, emp), s, emp, YEAR)
    assert Decimal(9_000_000) < eidi < Decimal(11_000_000)  # حدود نصفِ ۲۰م


def test_severance_one_month_per_year(db):
    emp = _employee(db, hire=date(2023, 12, 31), base=9_000_000)
    sev = calc_severance(_contract(db, emp), emp, date(2025, 12, 31))
    # حدود دو سال سابقه → ~۲ ماه پایه
    assert Decimal(17_000_000) < sev < Decimal(19_000_000)


def test_leave_balance_and_value(db):
    emp = _employee(db, base=9_000_000)  # دستمزد روزانه = ۳۰۰٬۰۰۰
    s = _settings(db, leave_days=26)
    db.add(LeaveRecord(employee_id=emp.id, leave_date=jalali_to_gregorian(YEAR, 5, 1), days=Decimal(10), created_by_id=_uid(db)))
    db.flush()
    entitled, used, remaining, value = calc_leave(db, _contract(db, emp), s, emp, YEAR)
    assert entitled == Decimal("26.00")
    assert used == Decimal(10)
    assert remaining == Decimal("16.00")
    assert value == Decimal(4_800_000)  # ۱۶ × ۳۰۰٬۰۰۰


def _uid(db):
    from app.models.user import User

    return db.query(User).first().id


def test_report_totals(db, user):
    _employee(db, base=10_000_000, nid="a1")
    _employee(db, base=8_000_000, nid="a2")
    _settings(db, min_wage=0)
    rep = get_benefits_report(db, YEAR)
    assert len(rep["rows"]) == 2
    assert rep["total_eidi"] == Decimal(20_000_000) + Decimal(16_000_000)


def test_issue_eidi_posts_and_guards(db, user):
    _employee(db, base=10_000_000)
    _settings(db, min_wage=0)
    result = issue_eidi(db, YEAR, user, run_date=persian_year_end(YEAR))
    assert result["amount"] == Decimal(20_000_000)

    entry = db.query(JournalEntry).filter(JournalEntry.source_type == "payroll_benefit").one()
    exp = get_account(db, cc.PAYROLL_EXPENSE)
    pay = get_account(db, cc.PAYROLL_PAYABLE)
    lines = {l.account_id: l for l in entry.lines}
    assert lines[exp.id].debit == Decimal(20_000_000)
    assert lines[pay.id].credit == Decimal(20_000_000)

    with pytest.raises(HTTPException) as exc:  # دوباره صادر نمی‌شود
        issue_eidi(db, YEAR, user, run_date=persian_year_end(YEAR))
    assert exc.value.status_code == 400


def test_issue_severance_guards(db, user):
    emp = _employee(db, hire=date(2023, 1, 1), base=9_000_000)
    r = issue_severance(db, emp.id, user, as_of=persian_year_end(YEAR))
    assert r["amount"] > 0
    assert db.query(BenefitRun).filter(BenefitRun.kind == "severance").count() == 1
    with pytest.raises(HTTPException):
        issue_severance(db, emp.id, user, as_of=persian_year_end(YEAR))


def test_record_leave_then_payout(db, user):
    emp = _employee(db, base=9_000_000)
    _settings(db, leave_days=26)
    record_leave(db, LeaveRecordIn(employee_id=emp.id, leave_date=jalali_to_gregorian(YEAR, 4, 1), days=Decimal(6)), user)
    # مانده = ۲۶ − ۶ = ۲۰ روز × ۳۰۰٬۰۰۰ = ۶م
    r = issue_leave_payout(db, emp.id, YEAR, user, run_date=persian_year_end(YEAR))
    assert r["amount"] == Decimal(6_000_000)
    with pytest.raises(HTTPException):
        issue_leave_payout(db, emp.id, YEAR, user, run_date=persian_year_end(YEAR))


def test_unknown_employee_severance_404(db, user):
    with pytest.raises(HTTPException) as exc:
        issue_severance(db, uuid4(), user)
    assert exc.value.status_code == 404
