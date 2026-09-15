from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_permission
from app.services.payroll_contracts import activate_employee_role, resolve_employee_contact
from app.services.idempotency import idempotent
from app.models.inventory import Contact
from app.models.payroll import (
    CONTRACT_TYPE_LABELS,
    Attendance,
    Employee,
    EmployeeLoan,
    InsuranceTaxBranch,
    JobTitle,
    LoanType,
    PayrollDeploymentInfo,
    PayrollFactor,
    PayrollFactorParticipation,
    PayrollFactorInput,
    PayrollPeriod,
    PayrollSettings,
    PayrollSettlement,
    PayrollTaxGroup,
    Payslip,
    PayslipLine,
    SalaryContract,
    SalaryContractLine,
    TaxTable,
    ServiceLocation,
)
from app.models.user import User
from app.pagination import Page, PageParams, paginate
from app.schemas.payroll import (
    AttendanceIn,
    AttendanceOut,
    DeploymentInfoIn,
    DeploymentInfoOut,
    FactorInputOut,
    FactorInputsIn,
    EmployeeCandidateOut,
    EmployeeIn,
    EmployeePatch,
    EmployeeLoanIn,
    EmployeeLoanOut,
    EmployeeOut,
    FactorParticipationIn,
    InsuranceTaxBranchIn,
    InsuranceTaxBranchOut,
    JobTitleIn,
    JobTitleOut,
    LoanTypeIn,
    LoanTypeOut,
    PayrollFactorIn,
    PayrollFactorOut,
    PayrollFactorPatch,
    PayrollPeriodIn,
    PayrollPeriodOut,
    PayrollSettingsIn,
    PayrollStatutoryParams,
    PayrollSettingsOut,
    PayrollSettlementIn,
    PayrollSettlementOut,
    PayrollTaxGroupIn,
    PayrollTaxGroupOut,
    PayslipOut,
    SalaryContractIn,
    SalaryContractOut,
    TaxBreakdownOut,
    TaxTableIn,
    TaxTableOut,
    ServiceLocationIn,
    ServiceLocationOut,
)
from app.services import factor_participation, payroll_contracts, payroll_loans
from app.services import chart_codes as cc
from app.services.common import assert_postable_account
from app.services.tax_tables import (
    assert_scope_free,
    build_tax_breakdown,
    mirror_default_tax_table,
    replace_brackets,
    table_is_used,
)
from app.services.payroll import (
    generate_insurance_list_csv,
    generate_payment_list_csv,
    generate_payslips_for_period,
    generate_tax_list_csv,
)

router = APIRouter(tags=["payroll"])


@router.get("/api/employees", response_model=list[EmployeeOut])
def list_employees(db: Session = Depends(get_db), _=Depends(require_permission("payroll", "view"))):
    return db.query(Employee).order_by(Employee.first_name).all()


@router.post("/api/employees", response_model=EmployeeOut, status_code=201)
def create_employee(
    data: EmployeeIn, db: Session = Depends(get_db), _=Depends(require_permission("payroll", "create"))
):
    """نقشِ کارمند را روی یک طرف حسابِ موجود فعال می‌کند.

    **هویتِ تازه‌ای ساخته نمی‌شود.** تا امروز این اندپوینت نام و کدِ ملی می‌گرفت
    و کارمندی می‌ساخت که به هیچ طرف حسابی وصل نبود — همان آدم دو رکورد داشت و
    اصلاحِ یکی به دیگری نمی‌رسید. همان دری که معماریِ «یک آدم، یک رکورد» را از
    پشت دور می‌زد.
    """
    contact = resolve_employee_contact(
        db,
        contact_id=data.contact_id,
        first_name=data.first_name or "",
        last_name=data.last_name or "",
        national_id=data.national_id or "",
        phone=data.phone,
        email=data.email,
    )
    return activate_employee_role(db, contact, data.hire_date, data.bank_account_number)


@router.patch("/api/employees/{employee_id}", response_model=EmployeeOut)
def update_employee(
    employee_id: UUID,
    data: EmployeePatch,
    db: Session = Depends(get_db),
    _=Depends(require_permission("payroll", "update")),
):
    """ویرایشِ پرونده‌ی کارمند — و **درِ خروجِ** کسی که رفته.

    تا امروز این روتر فقط `GET` و `POST` داشت، یعنی پرونده‌ی کارمند پس از ثبت
    تغییرناپذیر بود. مهم‌ترین پیامدش هم نه یک غلطِ املایی، که این بود:
    `Employee.is_active` **تنها گاردِ صدورِ فیشِ حقوقی** است
    (`generate_payslips_for_period`) و هیچ مسیری نمی‌نوشتش — پس کارمندی که رفته
    بود هر دوره فیشِ کامل می‌گرفت، با سند و بیمه و مالیاتش.

    **نام و کدِ ملی این‌جا نیستند** و این عمدی است: آن‌ها روی طرف‌حساب می‌نشینند
    و `PATCH /api/contacts/{id}` اصلاحشان می‌کند. دو مسیر برای یک داده یعنی دو
    حقیقت.

    **غیرفعال‌کردن پاک‌کردن نیست.** فیش‌ها، حکم‌ها و سندهای گذشته دست‌نخورده
    می‌مانند؛ فقط دوره‌های *بعدی* او را نمی‌بینند.
    """
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "کارمند یافت نشد")

    fields = data.model_dump(exclude_unset=True)

    #: تاریخ‌ها با مقدارِ **مؤثر** سنجیده می‌شوند، نه فقط آنچه در همین درخواست
    #: آمده: ویرایشی که تنها `termination_date` را می‌فرستد باید با
    #: `hire_date`ِ ذخیره‌شده مقایسه شود، وگرنه گارد فقط وقتی کار می‌کند که هر
    #: دو با هم بیایند.
    hire = fields.get("hire_date", employee.hire_date)
    termination = fields.get("termination_date", employee.termination_date)
    if hire is not None and termination is not None and termination < hire:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "تاریخ پایان کار نمی‌تواند پیش از تاریخ استخدام باشد",
        )

    for field, value in fields.items():
        setattr(employee, field, value)
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


class _GeneratePayslipsKey(BaseModel):
    """اثرانگشتِ فرمانِ صدور — همان دوره، همان کلید.

    `idempotent(...)` یک مدل می‌خواهد و این اندپوینت بدنه ندارد؛ پس شناسه‌ی دوره
    خودش اثرانگشت می‌شود. این‌طور اگر کلاینت همان کلید را برای دوره‌ی *دیگری*
    بفرستد، تعارض دیده می‌شود نه اینکه پاسخِ دوره‌ی قبلی پس داده شود.
    """

    period_id: UUID


@router.post("/api/payroll-periods/{period_id}/generate-payslips", response_model=list[PayslipOut])
def generate_payslips(
    period_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("payroll", "approve")),
):
    """فیش‌های دوره را صادر می‌کند — **یک بار**، حتی اگر درخواست دوباره برسد.

    داده از قبل هم خراب نمی‌شد: قیدِ یکتای `(employee, period)` و گاردِ
    «دوره نهایی شده» جلوی فیشِ دوم را می‌گرفتند. ولی کاربری که پاسخش در راه گم
    شده بود و دوباره می‌زد، **۴۰۰** می‌گرفت و نمی‌فهمید حقوق صادر شده یا نه —
    برای فرمانی که حقوقِ همه‌ی کارکنان را صادر می‌کند، بدترین جوابِ ممکن.

    حالا اجرای دوم همان فهرستِ اول را پس می‌دهد.
    """
    return idempotent(
        db,
        request,
        user,
        operation="generate_payslips",
        payload=_GeneratePayslipsKey(period_id=period_id),
        run=lambda: generate_payslips_for_period(db, period_id, user),
        #: شناسه‌ی منبع خودِ دوره است، نه یک فیشِ خاص — فرمان دوره‌ای است.
        resource_id=lambda _: period_id,
        #: پاسخِ اجرای اول از خودِ فیش‌ها بازساخته می‌شود، نه از یک کپیِ ذخیره‌شده.
        replay=lambda pid: (
            db.query(Payslip).filter(Payslip.period_id == pid).order_by(Payslip.number).all()
        ),
    )


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


@router.get("/api/payroll-periods/{period_id}/tax-list.csv")
def export_tax_list(
    period_id: UUID, db: Session = Depends(get_db), _=Depends(require_permission("payroll", "view"))
):
    csv_text, period = generate_tax_list_csv(db, period_id)
    filename = f"tax-list-{period.year}-{period.month:02d}.csv"
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/api/payroll-periods/{period_id}/payment-list.csv")
def export_payment_list(
    period_id: UUID, db: Session = Depends(get_db), _=Depends(require_permission("payroll", "view"))
):
    csv_text, period = generate_payment_list_csv(db, period_id)
    filename = f"payment-list-{period.year}-{period.month:02d}.csv"
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

    #: **یک فهرست، نه دو.** پیش از این هر ستون دو بار نوشته می‌شد (یک‌بار در
    #: سازنده، یک‌بار در شاخه‌ی ویرایش) و هر ستونِ تازه‌ای می‌توانست یکی از دو جا
    #: را جا بیندازد — همان باگی که سکوت می‌کند تا ماه‌ها بعد.
    fields = {
        "insurance_employee_rate": data.insurance_employee_rate,
        "insurance_employer_rate": data.insurance_employer_rate,
        "tax_exemption_annual": data.tax_exemption_annual,
        "tax_brackets": brackets,
        "min_base_wage": data.min_base_wage,
        "annual_leave_days": data.annual_leave_days,
        "notes": data.notes,
        **{name: getattr(data, name) for name in PayrollStatutoryParams.model_fields},
    }

    settings = db.query(PayrollSettings).filter(PayrollSettings.year == data.year).first()
    if settings is None:
        settings = PayrollSettings(year=data.year, **fields)
        db.add(settings)
    else:
        for name, value in fields.items():
            setattr(settings, name, value)
    db.flush()

    mirror_default_tax_table(db, year=data.year, brackets=data.tax_brackets)
    db.refresh(settings)
    return settings


# ── جدولِ مالیات ──────────────────────────────────────────────────────────────


def _tax_table_out(db: Session, table: TaxTable) -> TaxTableOut:
    return TaxTableOut.of(table, in_use=table_is_used(db, table.id))


def _check_tax_table(db: Session, data: TaxTableIn, *, table_id=None) -> None:
    """گروه و دامنه را می‌سنجد — **پیش از اینکه شیئی به جلسه اضافه شود**.

    ترتیب اتفاقی نیست: هر کوئری روی جلسه‌ای که یک `TaxTable`ِ نیمه‌ساخته دارد،
    autoflush را راه می‌اندازد و همان جدولِ خالی قیدِ `NOT NULL` را می‌شکند.
    """
    if data.tax_group_id is not None and db.get(PayrollTaxGroup, data.tax_group_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "گروه مالیاتی یافت نشد")
    assert_scope_free(
        db,
        table_id=table_id,
        effective_from=data.effective_from,
        calculation_type=data.calculation_type,
        tax_group_id=data.tax_group_id,
    )


def _apply_tax_table(db: Session, table: TaxTable, data: TaxTableIn) -> None:
    """سرصفحه را می‌نشاند، **بعد** flush، **بعد** پله‌ها.

    پله‌ها `table.id` می‌خواهند، پس جدول باید پیش از آن‌ها flush شده باشد.
    """
    table.title = data.title.strip()
    table.title2 = data.title2.strip()
    table.effective_from = data.effective_from
    table.tax_group_id = data.tax_group_id
    table.calculation_type = data.calculation_type
    db.flush()
    replace_brackets(db, table, [(b.up_to, b.rate) for b in data.brackets])


@router.get("/api/tax-tables", response_model=list[TaxTableOut])
def list_tax_tables(
    calculation_type: str | None = None,
    db: Session = Depends(get_db),
    _=Depends(require_permission("payroll", "view")),
):
    """فهرستِ جدول‌های مالیات — همه‌ی سال‌ها، همه‌ی گروه‌ها، کنارِ هم.

    جدولِ سالِ گذشته **پاک نمی‌شود**؛ تاریخچه سرِ جایش می‌ماند تا محاسبه‌ی گذشته
    بازتولیدپذیر بماند.
    """
    query = db.query(TaxTable)
    if calculation_type:
        query = query.filter(TaxTable.calculation_type == calculation_type)
    rows = query.order_by(TaxTable.effective_from.desc(), TaxTable.title).all()
    used = {
        payslip_table_id
        for (payslip_table_id,) in db.query(Payslip.tax_table_id).filter(Payslip.tax_table_id.isnot(None)).distinct()
    }
    return [TaxTableOut.of(row, in_use=row.id in used) for row in rows]


@router.post("/api/tax-tables", response_model=TaxTableOut, status_code=201)
def create_tax_table(
    data: TaxTableIn, db: Session = Depends(get_db), _=Depends(require_permission("payroll", "create"))
):
    _check_tax_table(db, data)
    table = TaxTable(
        title=data.title.strip(),
        title2=data.title2.strip(),
        effective_from=data.effective_from,
        tax_group_id=data.tax_group_id,
        calculation_type=data.calculation_type,
    )
    db.add(table)
    _apply_tax_table(db, table, data)
    db.refresh(table)
    return _tax_table_out(db, table)


@router.patch("/api/tax-tables/{table_id}", response_model=TaxTableOut)
def update_tax_table(
    table_id: UUID,
    data: TaxTableIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("payroll", "update")),
):
    """ویرایشِ جدول.

    **فیش‌های صادرشده تکان نمی‌خورند** — عددشان از لحظه‌ی صدور عکس است. ولی
    محاسبه‌های *بعدی* از این پس با اعدادِ تازه انجام می‌شوند، پس رابط باید
    بگوید جدول در استفاده بوده.
    """
    table = db.get(TaxTable, table_id)
    if table is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "جدول مالیات یافت نشد")
    _check_tax_table(db, data, table_id=table.id)
    _apply_tax_table(db, table, data)
    db.refresh(table)
    return _tax_table_out(db, table)


@router.delete("/api/tax-tables/{table_id}", status_code=204)
def delete_tax_table(
    table_id: UUID, db: Session = Depends(get_db), _=Depends(require_permission("payroll", "update"))
):
    """حذفِ جدولی که هیچ فیشی به آن استناد نکرده.

    جدولِ استفاده‌شده حذف نمی‌شود: فیشِ پارسال باید بتواند بگوید مالیاتش از کدام
    قاعده آمد، و جدولِ حذف‌شده آن جواب را برای همیشه می‌برد.
    """
    table = db.get(TaxTable, table_id)
    if table is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "جدول مالیات یافت نشد")
    if table_is_used(db, table_id):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "فیش‌هایی به این جدول استناد کرده‌اند و حذفش توضیحِ مالیاتشان را از بین می‌برد. "
            "برای سال یا گروه تازه، جدول تازه بسازید.",
        )
    db.delete(table)
    return Response(status_code=204)


# ─────────────────── ورودیِ عواملِ متغیر در یک دوره ───────────────────
#
# لایه‌ای که نبود. تا مهاجرتِ ۰۱۴۷ عاملِ «متغیر» دقیقاً مثلِ «قراردادی» رفتار
# می‌کرد، پس مأموریت و پاداش نمی‌توانستند ماه‌به‌ماه فرق کنند.


def _period_or_404(db: Session, period_id: UUID) -> PayrollPeriod:
    period = db.get(PayrollPeriod, period_id)
    if period is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "دوره حقوقی یافت نشد")
    return period


def _input_out(row: PayrollFactorInput, employees: dict) -> FactorInputOut:
    employee = employees.get(row.employee_id)
    return FactorInputOut(
        id=row.id,
        employee_id=row.employee_id,
        employee_name=f"{employee.first_name} {employee.last_name}".strip() if employee else "",
        factor_id=row.factor_id,
        factor_name=row.factor.name if row.factor else "",
        factor_category=row.factor.category if row.factor else "",
        amount=Decimal(str(row.amount)),
        notes=row.notes,
    )


@router.get("/api/payroll-periods/{period_id}/factor-inputs", response_model=list[FactorInputOut])
def list_factor_inputs(
    period_id: UUID, db: Session = Depends(get_db), _=Depends(require_permission("payroll", "view"))
):
    _period_or_404(db, period_id)
    rows = (
        db.query(PayrollFactorInput)
        .filter(PayrollFactorInput.period_id == period_id)
        .all()
    )
    employees = {e.id: e for e in db.query(Employee).all()}
    return [_input_out(row, employees) for row in rows]


@router.put("/api/payroll-periods/{period_id}/factor-inputs", response_model=list[FactorInputOut])
def save_factor_inputs(
    period_id: UUID,
    data: FactorInputsIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("payroll", "update")),
):
    """ورودی‌های نام‌برده را می‌نویسد. `amount = 0` ردیف را برمی‌دارد.

    **دوره‌ی فیش‌دار قفل است.** عوض‌کردنِ ورودی پس از صدور یعنی فیشِ صادرشده با
    عددی حساب شده که دیگر در سیستم نیست — همان «هرگز گذشته را بازنویسی نکن».
    برای اصلاح باید فیش‌های دوره باطل و دوباره صادر شوند.
    """
    period = _period_or_404(db, period_id)
    if period.status == "finalized":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "این دوره نهایی شده و ورودی‌هایش قفل است")
    if db.query(Payslip.id).filter(Payslip.period_id == period_id).first() is not None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "برای این دوره فیش صادر شده است. تغییرِ ورودی‌ها عددِ فیشِ صادرشده را "
            "توضیح‌ناپذیر می‌کند؛ اول فیش‌های دوره را باطل کنید.",
        )

    for row in data.rows:
        employee = db.get(Employee, row.employee_id)
        if employee is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "کارمندِ انتخاب‌شده یافت نشد")
        factor = db.get(PayrollFactor, row.factor_id)
        if factor is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "عاملِ انتخاب‌شده یافت نشد")
        #: **فقط عاملِ متغیر.** عاملِ قراردادی مبلغش روی حکم است؛ ورودیِ دوره
        #: برایش یعنی دو حقیقت برای یک عدد.
        if factor.kind != "variable":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"عاملِ «{factor.name}» قراردادی است و مبلغش روی حکم نوشته می‌شود، "
                "نه در ورودیِ دوره.",
            )
        if not factor.is_active:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, f"عاملِ «{factor.name}» غیرفعال است"
            )
        existing = (
            db.query(PayrollFactorInput)
            .filter(
                PayrollFactorInput.employee_id == row.employee_id,
                PayrollFactorInput.period_id == period_id,
                PayrollFactorInput.factor_id == row.factor_id,
            )
            .one_or_none()
        )
        if row.amount <= 0:
            if existing is not None:
                db.delete(existing)
            continue
        if existing is None:
            db.add(
                PayrollFactorInput(
                    employee_id=row.employee_id,
                    period_id=period_id,
                    factor_id=row.factor_id,
                    amount=row.amount,
                    notes=row.notes,
                    created_by_id=user.id,
                )
            )
        else:
            existing.amount = row.amount
            existing.notes = row.notes
    db.flush()
    return list_factor_inputs(period_id, db=db, _=None)  # noqa: S106 — همان نمایش، یک منبع


@router.get("/api/payslips/{payslip_id}/tax-breakdown", response_model=TaxBreakdownOut)
def payslip_tax_breakdown(
    payslip_id: UUID, db: Session = Depends(get_db), _=Depends(require_permission("payroll", "view"))
):
    """«این مالیات از کجا آمد؟» — پله‌به‌پله.

    هیچ‌چیز ذخیره نمی‌شود: از جدولِ ثبت‌شده‌ی همان فیش و مبنایش **بازسازی**
    می‌شود، پس نمی‌تواند با آن‌ها ناسازگار شود.
    """
    return build_tax_breakdown(db, payslip_id)


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
    rules = factor_participation.participation_map(db)
    rows = (
        db.query(PayrollFactor)
        #: **ترتیب از «اولویتِ نمایش» می‌آید، بعد نام.** با اولویتِ یکسان
        #: (پیش‌فرضِ صفر برای همه) ترتیب دقیقاً همان الفباییِ قبلی می‌ماند.
        .order_by(
            PayrollFactor.category,
            PayrollFactor.display_priority,
            PayrollFactor.system_key.desc(),
            PayrollFactor.name,
        )
        .all()
    )
    #: «در استفاده» با **دو** پرس‌وجوی جمعی درمی‌آید، نه دوتا به‌ازای هر عامل.
    used = {row[0] for row in db.query(SalaryContractLine.factor_id).distinct()}
    used |= {row[0] for row in db.query(PayslipLine.factor_id).distinct()}
    return [PayrollFactorOut.of(row, rules, in_use=row.id in used) for row in rows]


@router.post("/api/payroll-factors/defaults", response_model=list[PayrollFactorOut])
def create_default_factors(
    db: Session = Depends(get_db), _=Depends(require_permission("payroll", "create"))
):
    """عوامل پیش‌فرض (حقوق پایه، حق مسکن، حق خواروبار، حق اولاد) را می‌سازد.

    در مهاجرت کاشته نمی‌شوند چون جدول RLS دارد؛ این‌جا داخلِ مستأجرِ خودِ کاربر و
    به‌خواستِ صریحش ساخته می‌شوند. تکرارِ فراخوانی بی‌خطر است.
    """
    return payroll_contracts.ensure_default_factors(db)


def _factor_in_use(db: Session, factor_id: UUID) -> bool:
    """آیا این عامل در حکمی یا فیشی نشسته؟

    یک پرس‌وجوی `EXISTS` روی هرکدام. فیش هم شمرده می‌شود چون `PayslipLine`
    `factor_id` را نگه می‌دارد و همان چیزی است که «چرا این مبلغ؟» را جواب می‌دهد.
    """
    used_in_contract = db.query(SalaryContractLine.id).filter(SalaryContractLine.factor_id == factor_id).first()
    if used_in_contract is not None:
        return True
    return db.query(PayslipLine.id).filter(PayslipLine.factor_id == factor_id).first() is not None


def _assert_factor_accounts(db: Session, fields: dict, row=None) -> None:
    """حسابِ عامل باید واقعاً سند بپذیرد، و سمتش با طبقه‌اش بخواند.

    **مزایا سمتِ هزینه دارد، کسور سمتِ پرداختنی.** یک عاملِ مزایا حسابِ
    *پرداختنیِ* اختصاصی نمی‌گیرد چون مبلغش در خالصِ پرداختنی به کارکنان جمع
    می‌شود و جداکردنش معنیِ «خالصِ بدهی به کارکنان» را می‌شکند؛ و یک عاملِ کسور
    هزینه‌ی کارفرما نیست.
    """
    category = fields.get("category", getattr(row, "category", "benefit"))
    pairs = (
        ("expense_account_id", "expense_detail_class", "benefit", "مزایا", "هزینه", cc.PAYROLL_EXPENSE),
        (
            "payable_account_id", "payable_detail_class", "deduction", "کسورات", "پرداختنی",
            cc.PAYROLL_DEDUCTIONS_PAYABLE,
        ),
    )
    for account_field, detail_field, allowed, label, side, own_role in pairs:
        account_id = fields.get(account_field, getattr(row, account_field, None))
        if account_id is None:
            if fields.get(detail_field) or (row is None and fields.get(detail_field)):
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST, f"طبقه‌ی تفصیلیِ {side} بدون انتخابِ حساب معنی ندارد"
                )
            continue
        if category != allowed:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"حسابِ {side} فقط برای عاملِ «{label}» معنی دارد",
            )
        #: انتخابِ صریحِ حسابِ *پیش‌فرضِ همان سمت* مجاز است — همان چیزی که
        #: خالی‌گذاشتن هم می‌دهد، پس تعارضی نمی‌سازد.
        assert_postable_account(db, account_id, allow_role=own_role, subject=f"حسابِ {side}ِ عامل")


@router.post("/api/payroll-factors", response_model=PayrollFactorOut, status_code=201)
def create_payroll_factor(
    data: PayrollFactorIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("payroll", "create")),
):
    fields = data.model_dump()
    _assert_factor_accounts(db, fields)
    row = PayrollFactor(**fields)
    db.add(row)
    db.flush()
    db.refresh(row)
    return PayrollFactorOut.of(row, factor_participation.participation_map(db))


@router.patch("/api/payroll-factors/{row_id}", response_model=PayrollFactorOut)
def update_payroll_factor(
    row_id: UUID,
    data: PayrollFactorPatch,
    db: Session = Depends(get_db),
    _=Depends(require_permission("payroll", "update")),
):
    row = _fetch(db, PayrollFactor, row_id, "عامل")
    fields = data.model_dump(exclude_unset=True)

    #: **طبقه‌ی عاملِ استفاده‌شده قفل است.** بردنِ یک عامل از «مزایا» به «کسورات»
    #: علامتِ مبلغش را برمی‌گرداند؛ روی عاملی که در حکم یا فیش نشسته یعنی معنیِ
    #: داده‌ی گذشته بی‌صدا عوض شود. همان گاردی که «نوعِ شعبه» دارد.
    if "category" in fields and fields["category"] != row.category and _factor_in_use(db, row_id):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "این عامل در حکم یا فیش استفاده شده و طبقه‌اش قفل است؛ "
            "برای معنیِ تازه عاملِ تازه بسازید و این را غیرفعال کنید.",
        )
    _assert_factor_accounts(db, fields, row)

    for field, value in fields.items():
        setattr(row, field, value)
    db.flush()
    db.refresh(row)
    return PayrollFactorOut.of(row, factor_participation.participation_map(db), in_use=_factor_in_use(db, row_id))


@router.put("/api/payroll-factors/{row_id}/participation", response_model=PayrollFactorOut)
def set_factor_participation(
    row_id: UUID,
    data: FactorParticipationIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("payroll", "update")),
):
    """ضریبِ شرکتِ یک عامل در مبناها را می‌گذارد.

    **ردیفی که با پیش‌فرض یکی است پاک می‌شود، نه ذخیره.** جدول فقط استثناها را
    نگه می‌دارد؛ اگر هر ردیفِ «مثلِ پیش‌فرض» هم ذخیره می‌شد، دو نمایشِ یک حقیقت
    پیدا می‌کردیم و تغییرِ بعدیِ پیش‌فرض به ردیف‌های ذخیره‌شده نمی‌رسید.

    فقط هدف‌هایی که فرستاده شده‌اند لمس می‌شوند؛ بقیه دست نمی‌خورند.
    """
    row = _fetch(db, PayrollFactor, row_id, "عامل")
    existing = {
        p.purpose: p
        for p in db.query(PayrollFactorParticipation).filter(PayrollFactorParticipation.factor_id == row_id).all()
    }
    for purpose, value in data.participation.items():
        default = factor_participation.coefficient(row, purpose, None)
        current = existing.get(purpose)
        if value == default:
            if current is not None:
                db.delete(current)
            continue
        if current is None:
            db.add(
                PayrollFactorParticipation(
                    factor_id=row_id, purpose=purpose, included=value > 0, coefficient=value
                )
            )
        else:
            current.included = value > 0
            current.coefficient = value
    db.flush()
    return PayrollFactorOut.of(row, factor_participation.participation_map(db))


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


def _assert_branch_refs(db: Session, data: InsuranceTaxBranchIn) -> None:
    """طرف حساب و مرکز هزینه‌ی شعبه باید واقعاً وجود داشته باشند.

    بی این گارد، شناسه‌ی اشتباه فقط با خطای کلیدِ خارجیِ پایگاه داده گرفته می‌شد
    — پیامی که می‌گوید چیزی خراب شده، نه اینکه کاربر چه کند.
    """
    if data.contact_id is not None and db.get(Contact, data.contact_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "طرف حساب یافت نشد")
    if data.cost_center_id is not None:
        from app.models.cost_center import CostCenter

        if db.get(CostCenter, data.cost_center_id) is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "مرکز هزینه یافت نشد")


def _branch_in_use(db: Session, branch_id: UUID) -> bool:
    """آیا این شعبه روی حکمی نشسته است؟"""
    return (
        db.query(SalaryContract.id)
        .filter(
            or_(
                SalaryContract.insurance_branch_id == branch_id,
                SalaryContract.tax_branch_id == branch_id,
            )
        )
        .first()
        is not None
    )


@router.get("/api/insurance-tax-branches", response_model=list[InsuranceTaxBranchOut])
def list_insurance_tax_branches(
    kind: str | None = None,
    db: Session = Depends(get_db),
    _=Depends(require_permission("payroll", "view")),
):
    query = db.query(InsuranceTaxBranch)
    if kind:
        #: فیلترِ ساخت‌یافته روی خودِ ستون — نه جست‌وجوی متن در نام. فهرست هر سه
        #: نوع را کنارِ هم نگه می‌دارد، پس تفکیکشان باید قطعی باشد.
        query = query.filter(InsuranceTaxBranch.kind == kind)
    rows = query.order_by(InsuranceTaxBranch.name).all()
    #: «در استفاده؟» با **یک** کوئری برای همه، نه یکی به‌ازای هر ردیف.
    used = {
        branch_id
        for row in db.query(SalaryContract.insurance_branch_id, SalaryContract.tax_branch_id).all()
        for branch_id in row
        if branch_id is not None
    }
    return [InsuranceTaxBranchOut.of(row, in_use=row.id in used) for row in rows]


@router.post("/api/insurance-tax-branches", response_model=InsuranceTaxBranchOut, status_code=201)
def create_insurance_tax_branch(
    data: InsuranceTaxBranchIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("payroll", "create")),
):
    _assert_branch_refs(db, data)
    row = InsuranceTaxBranch(**data.model_dump())
    db.add(row)
    db.flush()
    db.refresh(row)
    return InsuranceTaxBranchOut.of(row)


@router.patch("/api/insurance-tax-branches/{branch_id}", response_model=InsuranceTaxBranchOut)
def update_insurance_tax_branch(
    branch_id: UUID,
    data: InsuranceTaxBranchIn,
    db: Session = Depends(get_db),
    #: `update` و نه `edit` — `edit` اصلاً در `ACTIONS_BY_MODULE["payroll"]` نیست
    #: و `sanitize` بی‌صدا دورش می‌ریزد، پس مسیر برای همه ۴۰۳ می‌شد.
    _=Depends(require_permission("payroll", "update")),
):
    """ویرایشِ شعبه — و تنها راهی که شعبه‌های موجود طرف حساب می‌گیرند.

    بی این مسیر، `contact_id` ستونی می‌شد که فقط شعبه‌های *تازه* می‌توانستند
    پرش کنند، و هر شعبه‌ای که امروز روی قراردادها نشسته تا ابد بی‌هویت می‌ماند.

    حذف عمداً نیست: شعبه روی قراردادهای گذشته نشسته و `is_active = false`
    همان کار را بدونِ از دست دادنِ تاریخ می‌کند («هرگز حذف نکن»).
    """
    row = db.get(InsuranceTaxBranch, branch_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "شعبه یافت نشد")
    _assert_branch_refs(db, data)

    in_use = _branch_in_use(db, branch_id)
    #: **نوع، هویت است.** شعبه‌ای که با کارگاه و شماره‌ی پیمان و زمینه‌ی بیمه‌ای
    #: ثبت شده نباید یک‌شبه حوزه‌ی مالیاتی شود: حکم‌هایی که به آن وصل‌اند معنایشان
    #: زیرِ پا عوض می‌شود، بی‌آنکه چیزی در آن حکم‌ها تغییر کرده باشد. تا وقتی
    #: هیچ حکمی به آن وصل نیست آزاد است.
    if in_use and data.kind != row.kind:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "این شعبه روی حکم‌های حقوقی استفاده شده و نوعش دیگر عوض نمی‌شود. "
            "اگر نوعش اشتباه بوده، شعبه‌ی درست را بسازید و حکم‌ها را به آن ببرید.",
        )

    for field, value in data.model_dump().items():
        setattr(row, field, value)
    db.flush()
    db.refresh(row)
    return InsuranceTaxBranchOut.of(row, in_use=in_use)


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


# ── وام‌های پرسنلی ────────────────────────────────────────────────────────────


def _employee_names(db: Session) -> dict:
    return {
        e.id: f"{e.first_name} {e.last_name}".strip()
        for e in db.query(Employee).all()
    }


def _loan_out(db: Session, loan: EmployeeLoan, names: dict | None = None) -> dict:
    names = names if names is not None else _employee_names(db)
    return {
        "id": loan.id,
        "employee_id": loan.employee_id,
        "employee_name": names.get(loan.employee_id, ""),
        "loan_type_id": loan.loan_type_id,
        "amount": loan.amount,
        "loan_date": loan.loan_date,
        "installment_count": loan.installment_count,
        "status": loan.status,
        "note": loan.note,
        #: مانده مشتق است نه ستون — یک منبع، پس با اقساط از هم نمی‌افتد.
        "balance": payroll_loans.loan_balance(db, loan.id),
        "installments": loan.installments,
    }


@router.get("/api/loan-types", response_model=list[LoanTypeOut])
def list_loan_types(db: Session = Depends(get_db), _=Depends(require_permission("payroll", "view"))):
    return db.query(LoanType).order_by(LoanType.code).all()


@router.post("/api/loan-types", response_model=LoanTypeOut, status_code=201)
def create_loan_type(
    data: LoanTypeIn, db: Session = Depends(get_db), _=Depends(require_permission("payroll", "create"))
):
    if db.query(LoanType).filter(LoanType.code == data.code).first() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "کدِ نوعِ وام تکراری است")
    row = LoanType(**data.model_dump())
    db.add(row)
    db.flush()
    db.refresh(row)
    return row


@router.patch("/api/loan-types/{row_id}", response_model=LoanTypeOut)
def update_loan_type(
    row_id: UUID,
    data: LoanTypeIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("payroll", "update")),
):
    row = db.get(LoanType, row_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "نوعِ وام یافت نشد")
    clash = db.query(LoanType).filter(LoanType.code == data.code, LoanType.id != row_id).first()
    if clash is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "کدِ نوعِ وام تکراری است")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.flush()
    db.refresh(row)
    return row


@router.get("/api/employee-loans", response_model=list[EmployeeLoanOut])
def list_employee_loans(
    employee_id: UUID | None = None,
    status_filter: str | None = None,
    db: Session = Depends(get_db),
    _=Depends(require_permission("payroll", "view")),
):
    query = db.query(EmployeeLoan)
    if employee_id is not None:
        query = query.filter(EmployeeLoan.employee_id == employee_id)
    if status_filter:
        query = query.filter(EmployeeLoan.status == status_filter)
    rows = query.order_by(EmployeeLoan.loan_date.desc()).all()
    names = _employee_names(db)
    return [_loan_out(db, row, names) for row in rows]


@router.post("/api/employee-loans", response_model=EmployeeLoanOut, status_code=201)
def create_employee_loan(
    data: EmployeeLoanIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("payroll", "create")),
):
    """وام + اقساطش. قاعده‌ی زمان‌بندی در سرویس است، نه این‌جا."""
    loan = payroll_loans.create_loan(db, data, user)
    return _loan_out(db, loan)


@router.post("/api/employee-loans/{loan_id}/cancel", response_model=EmployeeLoanOut)
def cancel_employee_loan(
    loan_id: UUID, db: Session = Depends(get_db), _=Depends(require_permission("payroll", "update"))
):
    """لغوِ وام — اقساطِ کسرشده دست نمی‌خورند، فقط دیگر قسطی سررسید نمی‌شود.

    حذف نمی‌کنیم: اقساطی که قبلاً از حقوق کسر شده‌اند واقعیتِ ثبت‌شده‌اند و پاک‌کردنشان
    یعنی فیش‌های گذشته توضیح‌ناپذیر شوند.
    """
    loan = db.get(EmployeeLoan, loan_id)
    if loan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "وام یافت نشد")
    loan.status = "cancelled"
    db.flush()
    return _loan_out(db, loan)


# ── تسویه حساب ───────────────────────────────────────────────────────────────


def _settlement_out(settlement: PayrollSettlement, names: dict) -> dict:
    row = {c.name: getattr(settlement, c.name) for c in PayrollSettlement.__table__.columns}
    row["employee_name"] = names.get(settlement.employee_id, "")
    return row


@router.get("/api/payroll-settlements", response_model=list[PayrollSettlementOut])
def list_settlements(db: Session = Depends(get_db), _=Depends(require_permission("payroll", "view"))):
    names = _employee_names(db)
    rows = db.query(PayrollSettlement).order_by(PayrollSettlement.settlement_date.desc()).all()
    return [_settlement_out(row, names) for row in rows]


@router.post("/api/payroll-settlements", response_model=PayrollSettlementOut, status_code=201)
def create_settlement(
    data: PayrollSettlementIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("payroll", "create")),
):
    """تسویه‌حسابِ پایانِ کار — یک ردیف به‌ازای هر کارمند.

    `loan_balance` اگر فرستاده نشود از وام‌های *فعالِ* همان کارمند خوانده می‌شود،
    نه دستی: عددی که کاربر تایپ کند می‌تواند با اقساطِ واقعی نخواند.
    """
    employee = db.get(Employee, data.employee_id)
    if employee is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "کارمند یافت نشد")
    if db.query(PayrollSettlement).filter(
        PayrollSettlement.employee_id == data.employee_id
    ).first() is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "برای این کارمند تسویه‌حساب ثبت شده؛ اصلاحش ویرایشِ همان ردیف است.",
        )

    loan_balance = (
        data.loan_balance
        if data.loan_balance is not None
        else payroll_loans.employee_loan_balance(db, data.employee_id)
    )
    earnings = data.severance_amount + data.leave_payout_amount + data.other_earnings
    net = earnings - loan_balance - data.other_deductions

    row = PayrollSettlement(
        employee_id=data.employee_id,
        settlement_date=data.settlement_date,
        severance_amount=data.severance_amount,
        leave_payout_amount=data.leave_payout_amount,
        other_earnings=data.other_earnings,
        loan_balance=loan_balance,
        other_deductions=data.other_deductions,
        #: خالصِ منفی ممکن است (بدهیِ وام بیشتر از مزایا) و پنهانش نمی‌کنیم.
        net_amount=net,
        note=data.note,
        created_by_id=user.id,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return _settlement_out(row, _employee_names(db))


# ── اطلاعاتِ استقرار ──────────────────────────────────────────────────────────


@router.get("/api/payroll-deployment", response_model=list[DeploymentInfoOut])
def list_deployment_info(
    year: int | None = None,
    db: Session = Depends(get_db),
    _=Depends(require_permission("payroll", "view")),
):
    query = db.query(PayrollDeploymentInfo)
    if year is not None:
        query = query.filter(PayrollDeploymentInfo.year == year)
    names = _employee_names(db)
    rows = query.order_by(PayrollDeploymentInfo.year.desc()).all()
    out = []
    for row in rows:
        item = {c.name: getattr(row, c.name) for c in PayrollDeploymentInfo.__table__.columns}
        item["employee_name"] = names.get(row.employee_id, "")
        out.append(item)
    return out


@router.put("/api/payroll-deployment", response_model=DeploymentInfoOut)
def upsert_deployment_info(
    data: DeploymentInfoIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("payroll", "update")),
):
    """یک ردیف برای هر (کارمند، سال) — دوباره فرستادن ویرایش است، نه ردیفِ دوم.

    `PUT` است نه `POST` چون همین معنا را دارد: این وضعیتِ استقرارِ آن کارمند در آن
    سال است، و دو وضعیتِ متفاوت برای یک سال بی‌معناست.
    """
    if db.get(Employee, data.employee_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "کارمند یافت نشد")

    row = (
        db.query(PayrollDeploymentInfo)
        .filter(
            PayrollDeploymentInfo.employee_id == data.employee_id,
            PayrollDeploymentInfo.year == data.year,
        )
        .first()
    )
    if row is None:
        row = PayrollDeploymentInfo(**data.model_dump())
        db.add(row)
    else:
        for field, value in data.model_dump().items():
            setattr(row, field, value)
    db.flush()
    db.refresh(row)

    item = {c.name: getattr(row, c.name) for c in PayrollDeploymentInfo.__table__.columns}
    item["employee_name"] = _employee_names(db).get(row.employee_id, "")
    return item
