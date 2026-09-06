"""قراردادِ حقوق و دستمزد: از طرف‌حساب تا رکوردِ قرارداد.

جریانی که این ماژول پیاده می‌کند، همان جریانِ واقعیِ استخدام است:

۱. شخص در «طرف حساب جدید» با تیکِ **کارمند** ثبت می‌شود.
۲. در حقوق و دستمزد «قرارداد جدید» زده می‌شود و نامش از همان طرف‌حساب‌ها می‌آید.
۳. اگر هنوز پرونده‌ی حقوق و دستمزد ندارد، **همین‌جا از روی طرف‌حساب ساخته می‌شود** —
   کاربر یک آدم را دو بار ثبت نمی‌کند.

سه قاعده‌ای که این‌جا نگه داشته می‌شوند و جای دیگری نگهبان ندارند:

* **«استخدام» فقط یک بار.** اولین قراردادِ هر شخص استخدام است و بعدی‌ها اصلاح
  قرارداد؛ نه دو استخدام ممکن است نه اصلاحِ بی‌استخدام.
* **چهار ستونِ مبلغ از ردیف‌ها ساخته می‌شوند، نه دستی.** موتورِ فیشِ حقوقی روی
  `base_salary`/`housing_allowance`/`food_allowance`/`other_allowance` حساب می‌کند و
  کاربر ردیف‌های عوامل را می‌نویسد. `PayrollFactor.system_key` نگاشتشان می‌کند و هر
  عاملِ بی‌کلید در «سایر مزایا» جمع می‌شود — پس عاملِ ساخته‌ی کاربر محاسبه را
  نمی‌شکند. یک منبعِ ویرایش، نه دو.
* **تاریخِ استخدام روی کارمند می‌نشیند، نه روی قرارداد.** واقعیتِ شخص است و می‌تواند
  سال‌ها قبل از تاریخِ صدور باشد.
"""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.inventory import Contact
from app.models.payroll import (
    DEFAULT_FACTORS,
    Employee,
    PayrollFactor,
    SalaryContract,
    SalaryContractLine,
)
from app.schemas.payroll import SalaryContractIn

#: کدام کلیدِ سیستمی به کدام ستونِ مبلغ می‌رود. هر عاملِ مزایایِ بی‌کلید در
#: `other_allowance` جمع می‌شود؛ کسورات اصلاً وارد این چهار ستون نمی‌شوند چون
#: موتورِ فیش آن‌ها را جدا حساب می‌کند.
_SYSTEM_KEY_COLUMN = {
    "base": "base_salary",
    "housing": "housing_allowance",
    "food": "food_allowance",
}


def ensure_default_factors(db: Session) -> list[PayrollFactor]:
    """عوامل پیش‌فرض را می‌سازد اگر نباشند و همه‌ی عوامل را برمی‌گرداند.

    **چرا این‌جا و نه در مهاجرت:** `payroll_factors` جدولِ مستأجرمحور با RLS است و
    `INSERT`ِ داخلِ مهاجرت یا صفر ردیف می‌گذارد یا به مستأجرِ اشتباه می‌رود. پس ساختِ
    پیش‌فرض‌ها کارِ یک درخواستِ صریحِ کاربر است، داخلِ مستأجرِ خودش. تکرارش هم بی‌خطر
    است: هرچه هست دست نمی‌خورد.
    """
    existing = {row.system_key for row in db.query(PayrollFactor).all() if row.system_key}
    for name, key in DEFAULT_FACTORS:
        if key in existing:
            continue
        db.add(PayrollFactor(name=name, system_key=key, category="benefit", kind="fixed"))
    db.flush()
    return db.query(PayrollFactor).order_by(PayrollFactor.system_key.desc(), PayrollFactor.name).all()


def employee_candidates(db: Session, q: str = "") -> list[dict]:
    """طرف‌حساب‌هایی که تیکِ «کارمند» دارند — فهرستِ «نام کارمند»ِ فرمِ قرارداد."""
    query = db.query(Contact).filter(Contact.is_employee.is_(True), Contact.is_system.is_(False))
    if q.strip():
        query = query.filter(Contact.name.ilike(f"%{q.strip()}%"))
    rows = query.order_by(Contact.name).limit(200).all()

    with_contract = {
        contract.employee_id for contract in db.query(SalaryContract.employee_id).all()
    } if rows else set()
    return [
        {
            "contact_id": c.id,
            "name": c.name,
            "national_id": c.national_id,
            "employee_id": c.employee_id,
            "has_contract": c.employee_id is not None and c.employee_id in with_contract,
        }
        for c in rows
    ]


def resolve_employee(db: Session, data: SalaryContractIn) -> Employee:
    """کارمندِ این قرارداد را پیدا یا از روی طرف‌حساب می‌سازد.

    ساختِ خودکار عمدی است: کاربر شخص را یک‌بار به‌عنوانِ طرف‌حساب ثبت کرده و
    نباید مجبور شود همان نام و کد ملی را دوباره در «کارمند» تایپ کند.
    """
    if data.employee_id is not None:
        employee = db.get(Employee, data.employee_id)
        if employee is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "کارمند یافت نشد")
        return employee

    contact = db.get(Contact, data.contact_id)
    if contact is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "طرف حساب یافت نشد")
    if not contact.is_employee:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "این طرف حساب کارمند نیست؛ اول در فرمِ طرف حساب تیکِ «کارمند» را بزنید.",
        )

    if contact.employee_id is not None:
        employee = db.get(Employee, contact.employee_id)
        if employee is not None:
            return employee

    hire_date = data.hire_date or data.effective_from
    #: کدِ ملی روی کارمند یکتاست. طرف‌حسابِ بی‌کدِ ملی نباید جلوی استخدام را بگیرد،
    #: پس رشته‌ی خالی می‌رود و کاربر بعداً در پرونده‌ی کارمند کاملش می‌کند.
    employee = Employee(
        first_name=(contact.first_name or contact.name).strip(),
        last_name=(contact.last_name or "").strip(),
        national_id=(contact.national_id or "").strip(),
        phone=contact.phone,
        email=contact.email,
        hire_date=hire_date,
    )
    db.add(employee)
    db.flush()
    contact.employee_id = employee.id
    return employee


def assert_contract_type(db: Session, employee_id: UUID, contract_type: str) -> None:
    """«استخدام» اولین قرارداد است و «اصلاح قرارداد» هر قراردادِ بعدی."""
    has_hire = (
        db.query(SalaryContract)
        .filter(
            SalaryContract.employee_id == employee_id,
            SalaryContract.contract_type == "hire",
        )
        .first()
        is not None
    )
    if contract_type == "hire" and has_hire:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "برای این کارمند قراردادِ استخدام ثبت شده است؛ تغییرِ بعدی «اصلاح قرارداد» است.",
        )
    if contract_type == "amend" and not has_hire:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "تا وقتی قراردادِ استخدام ثبت نشده، اصلاح قرارداد معنایی ندارد.",
        )


def allowed_contract_types(db: Session, employee_id: UUID | None) -> list[str]:
    """کدام نوعِ قرارداد برای این کارمند مجاز است — ورودیِ کشوییِ فرم."""
    if employee_id is None:
        return ["hire"]
    has_hire = (
        db.query(SalaryContract)
        .filter(
            SalaryContract.employee_id == employee_id,
            SalaryContract.contract_type == "hire",
        )
        .first()
        is not None
    )
    return ["amend"] if has_hire else ["hire"]


def amounts_from_lines(db: Session, lines) -> dict[str, Decimal]:
    """چهار ستونِ مبلغ را از ردیف‌های قرارداد می‌سازد.

    فقط مزایا وارد این چهار می‌شوند؛ کسورات ردیفِ خودشان را دارند و موتورِ فیش
    جداگانه می‌خواندشان. عاملِ بی‌کلید در «سایر مزایا» جمع می‌شود.
    """
    totals = {
        "base_salary": Decimal(0),
        "housing_allowance": Decimal(0),
        "food_allowance": Decimal(0),
        "other_allowance": Decimal(0),
    }
    for line in lines:
        factor = db.get(PayrollFactor, line.factor_id)
        if factor is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "عاملِ انتخاب‌شده یافت نشد")
        if factor.category != "benefit":
            continue
        column = _SYSTEM_KEY_COLUMN.get(factor.system_key, "other_allowance")
        totals[column] += Decimal(line.amount)
    return totals


def create_contract(db: Session, data: SalaryContractIn) -> SalaryContract:
    employee = resolve_employee(db, data)
    assert_contract_type(db, employee.id, data.contract_type)

    fields = data.model_dump(exclude={"lines", "contact_id", "employee_id", "hire_date"})
    if data.lines:
        fields.update(amounts_from_lines(db, data.lines))
        if fields["base_salary"] <= 0:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "ردیفِ «حقوق پایه» با مبلغِ بزرگ‌تر از صفر لازم است.",
            )

    contract = SalaryContract(employee_id=employee.id, **fields)
    db.add(contract)
    db.flush()

    for line in data.lines:
        db.add(
            SalaryContractLine(
                contract_id=contract.id, factor_id=line.factor_id, amount=line.amount
            )
        )

    #: تاریخِ استخدام واقعیتِ شخص است: روی کارمند می‌نشیند، نه روی قرارداد. فقط
    #: قراردادِ استخدام آن را می‌نویسد — اصلاحِ قرارداد نباید تاریخِ استخدام را عوض کند.
    if data.hire_date and data.contract_type == "hire":
        employee.hire_date = data.hire_date
    if data.service_end_date:
        employee.termination_date = data.service_end_date

    db.flush()
    db.refresh(contract)
    return contract


def contract_out(contract: SalaryContract) -> dict:
    """قرارداد + ردیف‌هایش + نامِ کارمند، آماده‌ی پاسخ."""
    row = {c.name: getattr(contract, c.name) for c in SalaryContract.__table__.columns}
    row["lines"] = [
        {
            "id": line.id,
            "factor_id": line.factor_id,
            "amount": line.amount,
            "factor_name": line.factor.name if line.factor else "",
            "factor_category": line.factor.category if line.factor else "benefit",
        }
        for line in contract.lines
    ]
    employee = contract.employee
    row["employee_name"] = f"{employee.first_name} {employee.last_name}".strip() if employee else ""
    return row
