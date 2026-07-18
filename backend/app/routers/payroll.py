from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_permission
from app.models.payroll import Attendance, Employee, PayrollPeriod, PayrollSettings, Payslip, SalaryContract
from app.models.user import User
from app.pagination import Page, PageParams, paginate
from app.schemas.payroll import (
    AttendanceIn,
    AttendanceOut,
    EmployeeIn,
    EmployeeOut,
    PayrollPeriodIn,
    PayrollPeriodOut,
    PayrollSettingsIn,
    PayrollSettingsOut,
    PayslipOut,
    SalaryContractIn,
    SalaryContractOut,
)
from app.services.payroll import generate_insurance_list_csv, generate_payslips_for_period

router = APIRouter(tags=["payroll"])


@router.get("/api/employees", response_model=list[EmployeeOut])
def list_employees(db: Session = Depends(get_db), _=Depends(require_permission("payroll", "view"))):
    return db.query(Employee).order_by(Employee.first_name).all()


@router.post("/api/employees", response_model=EmployeeOut, status_code=201)
def create_employee(
    data: EmployeeIn, db: Session = Depends(get_db), _=Depends(require_permission("payroll", "create"))
):
    employee = Employee(**data.model_dump())
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee


@router.get("/api/salary-contracts", response_model=list[SalaryContractOut])
def list_salary_contracts(
    employee_id: UUID | None = None,
    db: Session = Depends(get_db),
    _=Depends(require_permission("payroll", "view")),
):
    query = db.query(SalaryContract)
    if employee_id is not None:
        query = query.filter(SalaryContract.employee_id == employee_id)
    return query.order_by(SalaryContract.effective_from.desc()).all()


@router.post("/api/salary-contracts", response_model=SalaryContractOut, status_code=201)
def create_salary_contract(
    data: SalaryContractIn, db: Session = Depends(get_db), _=Depends(require_permission("payroll", "create"))
):
    if db.get(Employee, data.employee_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "کارمند یافت نشد")
    contract = SalaryContract(**data.model_dump())
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return contract


@router.get("/api/payroll-periods", response_model=list[PayrollPeriodOut])
def list_payroll_periods(db: Session = Depends(get_db), _=Depends(require_permission("payroll", "view"))):
    return db.query(PayrollPeriod).order_by(PayrollPeriod.year.desc(), PayrollPeriod.month.desc()).all()


@router.post("/api/payroll-periods", response_model=PayrollPeriodOut, status_code=201)
def create_payroll_period(
    data: PayrollPeriodIn, db: Session = Depends(get_db), _=Depends(require_permission("payroll", "create"))
):
    existing = (
        db.query(PayrollPeriod).filter(PayrollPeriod.year == data.year, PayrollPeriod.month == data.month).first()
    )
    if existing is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "این دوره قبلاً ساخته شده است")
    period = PayrollPeriod(year=data.year, month=data.month)
    db.add(period)
    db.commit()
    db.refresh(period)
    return period


@router.put("/api/attendance", response_model=AttendanceOut)
def upsert_attendance(
    data: AttendanceIn, db: Session = Depends(get_db), _=Depends(require_permission("payroll", "update"))
):
    record = (
        db.query(Attendance)
        .filter(Attendance.employee_id == data.employee_id, Attendance.period_id == data.period_id)
        .first()
    )
    if record is None:
        record = Attendance(**data.model_dump())
        db.add(record)
    else:
        record.worked_days = data.worked_days
        record.absent_days = data.absent_days
        record.overtime_hours = data.overtime_hours
    db.commit()
    db.refresh(record)
    return record


@router.get("/api/attendance", response_model=list[AttendanceOut])
def list_attendance(
    period_id: UUID, db: Session = Depends(get_db), _=Depends(require_permission("payroll", "view"))
):
    return db.query(Attendance).filter(Attendance.period_id == period_id).all()


@router.post("/api/payroll-periods/{period_id}/generate-payslips", response_model=list[PayslipOut])
def generate_payslips(
    period_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("payroll", "approve")),
):
    return generate_payslips_for_period(db, period_id, user)


@router.get("/api/payroll-periods/{period_id}/insurance-list.csv")
def export_insurance_list(
    period_id: UUID, db: Session = Depends(get_db), _=Depends(require_permission("payroll", "view"))
):
    csv_text, period = generate_insurance_list_csv(db, period_id)
    filename = f"insurance-list-{period.year}-{period.month:02d}.csv"
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/api/payslips", response_model=Page[PayslipOut])
def list_payslips(
    period_id: UUID | None = None,
    employee_id: UUID | None = None,
    db: Session = Depends(get_db),
    params: PageParams = Depends(),
    _=Depends(require_permission("payroll", "view")),
):
    query = db.query(Payslip)
    if period_id is not None:
        query = query.filter(Payslip.period_id == period_id)
    if employee_id is not None:
        query = query.filter(Payslip.employee_id == employee_id)
    # number از sequence می‌آید و یکتاست
    items, next_cursor = paginate(query, [Payslip.number], params, descending=False)
    return Page(items=items, next_cursor=next_cursor)


@router.get("/api/payroll-settings", response_model=list[PayrollSettingsOut])
def list_payroll_settings(db: Session = Depends(get_db), _=Depends(require_permission("payroll", "view"))):
    return db.query(PayrollSettings).order_by(PayrollSettings.year.desc()).all()


@router.put("/api/payroll-settings", response_model=PayrollSettingsOut)
def upsert_payroll_settings(
    data: PayrollSettingsIn, db: Session = Depends(get_db), _=Depends(require_permission("payroll", "update"))
):
    # brackets صریحاً به dict قابل‌سریالایز JSON تبدیل می‌شوند (Decimal به‌صورت خام قابل ذخیره در JSONB نیست)
    brackets = [{"up_to": str(b.up_to) if b.up_to is not None else None, "rate": str(b.rate)} for b in data.tax_brackets]

    settings = db.query(PayrollSettings).filter(PayrollSettings.year == data.year).first()
    if settings is None:
        settings = PayrollSettings(
            year=data.year,
            insurance_employee_rate=data.insurance_employee_rate,
            insurance_employer_rate=data.insurance_employer_rate,
            tax_exemption_annual=data.tax_exemption_annual,
            tax_brackets=brackets,
            notes=data.notes,
        )
        db.add(settings)
    else:
        settings.insurance_employee_rate = data.insurance_employee_rate
        settings.insurance_employer_rate = data.insurance_employer_rate
        settings.tax_exemption_annual = data.tax_exemption_annual
        settings.tax_brackets = brackets
        settings.notes = data.notes
    db.commit()
    db.refresh(settings)
    return settings
