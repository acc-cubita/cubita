from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_permission
from app.models.inventory import Contact
from app.models.payroll import (
    CONTRACT_TYPE_LABELS,
    Attendance,
    Employee,
    InsuranceTaxBranch,
    JobTitle,
    PayrollFactor,
    PayrollPeriod,
    PayrollSettings,
    PayrollTaxGroup,
    Payslip,
    SalaryContract,
    ServiceLocation,
)
from app.models.user import User
from app.pagination import Page, PageParams, paginate
from app.schemas.payroll import (
    AttendanceIn,
    AttendanceOut,
    EmployeeCandidateOut,
    EmployeeIn,
    EmployeeOut,
    InsuranceTaxBranchIn,
    InsuranceTaxBranchOut,
    JobTitleIn,
    JobTitleOut,
    PayrollFactorIn,
    PayrollFactorOut,
    PayrollPeriodIn,
    PayrollPeriodOut,
    PayrollSettingsIn,
    PayrollSettingsOut,
    PayrollTaxGroupIn,
    PayrollTaxGroupOut,
    PayslipOut,
    SalaryContractIn,
    SalaryContractOut,
    ServiceLocationIn,
    ServiceLocationOut,
)
from app.services import payroll_contracts
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
    db.flush()
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
    rows = query.order_by(SalaryContract.effective_from.desc()).all()
    return [payroll_contracts.contract_out(row) for row in rows]


@router.post("/api/salary-contracts", response_model=SalaryContractOut, status_code=201)
def create_salary_contract(
    data: SalaryContractIn, db: Session = Depends(get_db), _=Depends(require_permission("payroll", "create"))
):
    """قراردادِ تازه — و اگر کارمند هنوز پرونده ندارد، از روی طرف‌حسابش ساخته می‌شود.

    قاعده‌های «استخدام یک‌بار» و «چهار ستونِ مبلغ از ردیف‌ها» در
    [سرویسِ قرارداد](../services/payroll_contracts.py) نگه داشته می‌شوند، نه این‌جا —
    تا هر مسیرِ دیگری که قرارداد بسازد هم همان‌ها را بگیرد.
    """
    contract = payroll_contracts.create_contract(db, data)
    return payroll_contracts.contract_out(contract)


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
    db.flush()
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
    db.flush()
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
            min_base_wage=data.min_base_wage,
            annual_leave_days=data.annual_leave_days,
            notes=data.notes,
        )
        db.add(settings)
    else:
        settings.insurance_employee_rate = data.insurance_employee_rate
        settings.insurance_employer_rate = data.insurance_employer_rate
        settings.tax_exemption_annual = data.tax_exemption_annual
        settings.tax_brackets = brackets
        settings.min_base_wage = data.min_base_wage
        settings.annual_leave_days = data.annual_leave_days
        settings.notes = data.notes
    db.flush()
    db.refresh(settings)
    return settings


# ── جدول‌های مرجعِ حقوق و دستمزد ───────────────────────────────────────────────
#
# پنج فهرستِ ساده با یک الگو: `GET` می‌خواند، `POST` می‌سازد، `PATCH` ویرایش می‌کند.
# حذف عمداً نیست — رکوردی که در قراردادی استفاده شده نباید ناپدید شود؛ `is_active`
# آن را از فهرستِ انتخاب بیرون می‌برد بی‌آنکه قراردادهای قدیمی بی‌مرجع شوند.


def _fetch(db: Session, model, row_id: UUID, label: str):
    row = db.get(model, row_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{label} یافت نشد")
    return row


@router.get("/api/service-locations", response_model=list[ServiceLocationOut])
def list_service_locations(
    db: Session = Depends(get_db), _=Depends(require_permission("payroll", "view"))
):
    return db.query(ServiceLocation).order_by(ServiceLocation.code).all()


@router.post("/api/service-locations", response_model=ServiceLocationOut, status_code=201)
def create_service_location(
    data: ServiceLocationIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("payroll", "create")),
):
    row = ServiceLocation(**data.model_dump())
    db.add(row)
    db.flush()
    db.refresh(row)
    return row


@router.patch("/api/service-locations/{row_id}", response_model=ServiceLocationOut)
def update_service_location(
    row_id: UUID,
    data: ServiceLocationIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("payroll", "update")),
):
    row = _fetch(db, ServiceLocation, row_id, "محل خدمت")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.flush()
    db.refresh(row)
    return row


@router.get("/api/job-titles", response_model=list[JobTitleOut])
def list_job_titles(db: Session = Depends(get_db), _=Depends(require_permission("payroll", "view"))):
    return db.query(JobTitle).order_by(JobTitle.code).all()


@router.post("/api/job-titles", response_model=JobTitleOut, status_code=201)
def create_job_title(
    data: JobTitleIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("payroll", "create")),
):
    row = JobTitle(**data.model_dump())
    db.add(row)
    db.flush()
    db.refresh(row)
    return row


@router.patch("/api/job-titles/{row_id}", response_model=JobTitleOut)
def update_job_title(
    row_id: UUID,
    data: JobTitleIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("payroll", "update")),
):
    row = _fetch(db, JobTitle, row_id, "شغل")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.flush()
    db.refresh(row)
    return row


@router.get("/api/payroll-factors", response_model=list[PayrollFactorOut])
def list_payroll_factors(
    db: Session = Depends(get_db), _=Depends(require_permission("payroll", "view"))
):
    return (
        db.query(PayrollFactor)
        .order_by(PayrollFactor.category, PayrollFactor.system_key.desc(), PayrollFactor.name)
        .all()
    )


@router.post("/api/payroll-factors/defaults", response_model=list[PayrollFactorOut])
def create_default_factors(
    db: Session = Depends(get_db), _=Depends(require_permission("payroll", "create"))
):
    """عوامل پیش‌فرض (حقوق پایه، حق مسکن، حق خواروبار، حق اولاد) را می‌سازد.

    در مهاجرت کاشته نمی‌شوند چون جدول RLS دارد؛ این‌جا داخلِ مستأجرِ خودِ کاربر و
    به‌خواستِ صریحش ساخته می‌شوند. تکرارِ فراخوانی بی‌خطر است.
    """
    return payroll_contracts.ensure_default_factors(db)


@router.post("/api/payroll-factors", response_model=PayrollFactorOut, status_code=201)
def create_payroll_factor(
    data: PayrollFactorIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("payroll", "create")),
):
    row = PayrollFactor(**data.model_dump())
    db.add(row)
    db.flush()
    db.refresh(row)
    return row


@router.patch("/api/payroll-factors/{row_id}", response_model=PayrollFactorOut)
def update_payroll_factor(
    row_id: UUID,
    data: PayrollFactorIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("payroll", "update")),
):
    row = _fetch(db, PayrollFactor, row_id, "عامل")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.flush()
    db.refresh(row)
    return row


@router.get("/api/payroll-tax-groups", response_model=list[PayrollTaxGroupOut])
def list_payroll_tax_groups(
    db: Session = Depends(get_db), _=Depends(require_permission("payroll", "view"))
):
    return db.query(PayrollTaxGroup).order_by(PayrollTaxGroup.name).all()


@router.post("/api/payroll-tax-groups", response_model=PayrollTaxGroupOut, status_code=201)
def create_payroll_tax_group(
    data: PayrollTaxGroupIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("payroll", "create")),
):
    row = PayrollTaxGroup(**data.model_dump())
    db.add(row)
    db.flush()
    db.refresh(row)
    return row


@router.get("/api/insurance-tax-branches", response_model=list[InsuranceTaxBranchOut])
def list_insurance_tax_branches(
    kind: str | None = None,
    db: Session = Depends(get_db),
    _=Depends(require_permission("payroll", "view")),
):
    query = db.query(InsuranceTaxBranch)
    if kind:
        query = query.filter(InsuranceTaxBranch.kind == kind)
    return query.order_by(InsuranceTaxBranch.name).all()


@router.post("/api/insurance-tax-branches", response_model=InsuranceTaxBranchOut, status_code=201)
def create_insurance_tax_branch(
    data: InsuranceTaxBranchIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("payroll", "create")),
):
    row = InsuranceTaxBranch(**data.model_dump())
    db.add(row)
    db.flush()
    db.refresh(row)
    return row


# ── فرمِ قرارداد ──────────────────────────────────────────────────────────────


@router.get("/api/payroll/employee-candidates", response_model=list[EmployeeCandidateOut])
def list_employee_candidates(
    q: str = "",
    db: Session = Depends(get_db),
    _=Depends(require_permission("payroll", "view")),
):
    """فهرستِ «نام کارمند»ِ فرمِ قرارداد — طرف‌حساب‌هایی که تیکِ «کارمند» دارند."""
    return payroll_contracts.employee_candidates(db, q)


@router.get("/api/payroll/contract-types", response_model=dict)
def contract_types_for(
    employee_id: UUID | None = None,
    contact_id: UUID | None = None,
    db: Session = Depends(get_db),
    _=Depends(require_permission("payroll", "view")),
):
    """کدام نوعِ قرارداد برای این شخص مجاز است.

    «استخدام» اولین قرارداد است؛ تا وقتی ثبت نشده «اصلاح قرارداد» اصلاً در فهرست
    نمی‌آید، و بعد از آن دیگر «استخدام» نمی‌آید.
    """
    if employee_id is None and contact_id is not None:
        contact = db.get(Contact, contact_id)
        employee_id = contact.employee_id if contact is not None else None
    allowed = payroll_contracts.allowed_contract_types(db, employee_id)
    return {
        "allowed": allowed,
        "labels": {key: CONTRACT_TYPE_LABELS[key] for key in allowed},
    }
