"""وامِ پرسنلی: زمان‌بندیِ اقساط، مانده، و کسر در دوره‌ی حقوقی.

سه قاعده که هر مسیرِ دیگری هم باید بگیردشان، پس این‌جا می‌مانند نه در روتر:

۱. **اقساط رکورد دارند، محاسبه نمی‌شوند.** مبلغِ وام تقسیم بر تعدادِ قسط، عددی است
   که هر بار می‌تواند فرق کند (گرد شدن، بخشیدنِ یک قسط، ماهی که کسر نشد). با ردیفِ
   قسط، هر قسط یک واقعیتِ ثبت‌شده است.

۲. **باقی‌مانده‌ی تقسیم روی قسطِ آخر می‌نشیند.** ۱۰٬۰۰۰٬۰۰۱ ریال در سه قسط یعنی دو
   قسطِ ۳٬۳۳۳٬۳۳۳ و یک قسطِ ۳٬۳۳۳٬۳۳۵ — نه سه قسط که جمعشان یک ریال کم بیاورد.

۳. **هیچ قسطی دوبار کسر نمی‌شود.** `deducted_period_id` می‌گوید کدام دوره کسرش کرد؛
   کسرِ دوباره‌ی همان قسط ممکن نیست، و ابطالِ دوره آزادش می‌کند.
"""
from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.payroll import (
    EmployeeLoan,
    EmployeeLoanInstallment,
    Employee,
    PayrollPeriod,
)

#: سقفِ تعدادِ قسط — همان قیدِ بررسیِ دیتابیس، تا خطا پیش از رسیدن به آن‌جا فارسی باشد.
MAX_INSTALLMENTS = 240


def _add_months(start: date, months: int) -> date:
    """سررسیدِ قسطِ n اُم: همان روزِ ماه، n ماه بعد.

    روزِ ۳۱ در ماهِ ۳۰روزه به آخرِ همان ماه می‌افتد، نه به ماهِ بعد — وگرنه سررسیدها
    یکی‌یکی جلو می‌خزند و قسطِ دوازدهم یک ماه دیرتر می‌شود.
    """
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    #: آخرین روزِ ماهِ مقصد
    if month == 12:
        last = date(year + 1, 1, 1)
    else:
        last = date(year, month + 1, 1)
    from datetime import timedelta

    last_day = (last - timedelta(days=1)).day
    return date(year, month, min(start.day, last_day))


def build_installments(amount: Decimal, count: int, first_due: date) -> list[tuple[int, date, Decimal]]:
    """(شماره، سررسید، مبلغ) برای هر قسط. جمعشان **دقیقاً** برابرِ مبلغِ وام است."""
    if count < 1 or count > MAX_INSTALLMENTS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"تعدادِ قسط باید بینِ ۱ و {MAX_INSTALLMENTS} باشد",
        )
    if amount <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "مبلغِ وام باید بزرگ‌تر از صفر باشد")

    base = (amount / count).to_integral_value(rounding="ROUND_DOWN")
    rows = []
    for seq in range(1, count + 1):
        #: قاعده‌ی ۲ — باقی‌مانده روی قسطِ آخر، نه پخش‌شده و نه گم‌شده.
        value = base if seq < count else amount - base * (count - 1)
        rows.append((seq, _add_months(first_due, seq - 1), value))
    return rows


def create_loan(db: Session, data, user) -> EmployeeLoan:
    """وام + اقساطش، در یک تراکنش. وامِ بی‌قسط ساخته نمی‌شود."""
    employee = db.get(Employee, data.employee_id)
    if employee is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "کارمند یافت نشد")

    loan = EmployeeLoan(
        employee_id=data.employee_id,
        loan_type_id=data.loan_type_id,
        amount=data.amount,
        loan_date=data.loan_date,
        installment_count=data.installment_count,
        note=data.note,
        created_by_id=user.id,
    )
    db.add(loan)
    db.flush()

    first_due = data.first_due_date or _add_months(data.loan_date, 1)
    for seq, due, value in build_installments(
        Decimal(data.amount), data.installment_count, first_due
    ):
        db.add(
            EmployeeLoanInstallment(loan_id=loan.id, seq=seq, due_date=due, amount=value)
        )
    db.flush()
    db.refresh(loan)
    return loan


def loan_balance(db: Session, loan_id: UUID) -> Decimal:
    """مانده = جمعِ اقساطی که هنوز کسر نشده‌اند."""
    total = (
        db.query(func.coalesce(func.sum(EmployeeLoanInstallment.amount), 0))
        .filter(
            EmployeeLoanInstallment.loan_id == loan_id,
            EmployeeLoanInstallment.deducted_period_id.is_(None),
        )
        .scalar()
    )
    return Decimal(total)


def employee_loan_balance(db: Session, employee_id: UUID) -> Decimal:
    """مانده‌ی همه‌ی وام‌های *فعالِ* یک کارمند — عددی که تسویه‌حساب کسر می‌کند."""
    total = (
        db.query(func.coalesce(func.sum(EmployeeLoanInstallment.amount), 0))
        .join(EmployeeLoan, EmployeeLoanInstallment.loan_id == EmployeeLoan.id)
        .filter(
            EmployeeLoan.employee_id == employee_id,
            EmployeeLoan.status == "active",
            EmployeeLoanInstallment.deducted_period_id.is_(None),
        )
        .scalar()
    )
    return Decimal(total)


def due_installments(db: Session, employee_id: UUID, as_of: date) -> list[EmployeeLoanInstallment]:
    """اقساطِ سررسیدشده و کسرنشده‌ی یک کارمند تا تاریخِ داده‌شده."""
    return (
        db.query(EmployeeLoanInstallment)
        .join(EmployeeLoan, EmployeeLoanInstallment.loan_id == EmployeeLoan.id)
        .filter(
            EmployeeLoan.employee_id == employee_id,
            EmployeeLoan.status == "active",
            EmployeeLoanInstallment.deducted_period_id.is_(None),
            EmployeeLoanInstallment.due_date <= as_of,
        )
        .order_by(EmployeeLoanInstallment.due_date, EmployeeLoanInstallment.seq)
        .all()
    )


def period_end(period: PayrollPeriod) -> date:
    """آخرین روزِ دوره به میلادی — مبنای «کدام قسط سررسید شده».

    از همان تابعی می‌آید که موتورِ فیش استفاده می‌کند، نه محاسبه‌ی موازی: اگر روزی
    تعریفِ «پایانِ دوره» عوض شود، کسرِ قسط و صدورِ فیش با هم عوض می‌شوند.
    """
    from app.services.payroll import _period_as_of_date

    return _period_as_of_date(period)


def deduct_for_period(db: Session, employee_id: UUID, period: PayrollPeriod) -> Decimal:
    """اقساطِ سررسیدشده را به این دوره نسبت می‌دهد و جمعشان را برمی‌گرداند.

    **کسرِ دوباره ممکن نیست**: قسطی که `deducted_period_id` دارد دیگر در فهرستِ
    سررسید نمی‌آید. اگر دوره ابطال شود، `release_period` آزادشان می‌کند.
    """
    total = Decimal(0)
    for installment in due_installments(db, employee_id, period_end(period)):
        installment.deducted_period_id = period.id
        total += Decimal(installment.amount)

    #: وامی که دیگر قسطِ کسرنشده ندارد، تسویه‌شده است.
    for loan in (
        db.query(EmployeeLoan)
        .filter(EmployeeLoan.employee_id == employee_id, EmployeeLoan.status == "active")
        .all()
    ):
        if loan_balance(db, loan.id) == 0:
            loan.status = "settled"
    db.flush()
    return total


def release_period(db: Session, period_id: UUID) -> int:
    """اقساطِ یک دوره را آزاد می‌کند — برای وقتی که دوره ابطال می‌شود.

    وامی که به‌خاطرِ همان دوره «تسویه‌شده» شمرده شده بود، دوباره فعال می‌شود؛ وگرنه
    وامی با مانده‌ی مثبت در وضعیتِ تسویه‌شده جا می‌ماند و دیگر کسر نمی‌شود.
    """
    rows = (
        db.query(EmployeeLoanInstallment)
        .filter(EmployeeLoanInstallment.deducted_period_id == period_id)
        .all()
    )
    loan_ids = {row.loan_id for row in rows}
    for row in rows:
        row.deducted_period_id = None
    db.flush()

    for loan in db.query(EmployeeLoan).filter(EmployeeLoan.id.in_(loan_ids or [None])).all():
        if loan.status == "settled" and loan_balance(db, loan.id) > 0:
            loan.status = "active"
    db.flush()
    return len(rows)
