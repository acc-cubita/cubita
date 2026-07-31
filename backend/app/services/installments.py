from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.jalali import add_jalali_months
from app.models.counters import DOC_INSTALLMENT_PLAN
from app.models.installments import Installment, InstallmentPlan
from app.models.inventory import Contact
from app.models.user import User
from app.schemas.installments import InstallmentPayIn, InstallmentPlanIn
from app.schemas.treasury import TreasuryTransactionIn
from app.services import treasury as treasury_service
from app.services.numbering import next_document_number
from app.services.period_close import assert_period_open


def _installment_status(inst: Installment, today: date) -> str:
    paid = Decimal(inst.paid_amount)
    amount = Decimal(inst.amount)
    if paid >= amount:
        return "paid"
    if paid > 0:
        return "partial"
    if inst.due_date < today:
        return "overdue"
    return "pending"


def _serialize(plan: InstallmentPlan) -> dict:
    today = date.today()
    total_paid = Decimal(0)
    overdue_amount = Decimal(0)
    overdue_count = 0
    next_due: date | None = None
    lines = []
    for inst in plan.installments:
        paid = Decimal(inst.paid_amount)
        amount = Decimal(inst.amount)
        remaining = amount - paid
        st = _installment_status(inst, today)
        total_paid += paid
        if remaining > 0 and next_due is None:
            next_due = inst.due_date
        if st == "overdue":
            overdue_amount += remaining
            overdue_count += 1
        lines.append({
            "id": inst.id,
            "seq": inst.seq,
            "due_date": inst.due_date,
            "amount": amount,
            "paid_amount": paid,
            "remaining": remaining,
            "paid_date": inst.paid_date,
            "status": st,
        })

    financed = Decimal(plan.total_amount) - Decimal(plan.down_payment)
    scheduled = sum((Decimal(i.amount) for i in plan.installments), Decimal(0))
    return {
        "id": plan.id,
        "number": plan.number,
        "contact_id": plan.contact_id,
        "contact_name": plan.contact.name if plan.contact else "—",
        "sales_invoice_id": plan.sales_invoice_id,
        "title": plan.title,
        "total_amount": Decimal(plan.total_amount),
        "down_payment": Decimal(plan.down_payment),
        "financed": financed,
        "num_installments": plan.num_installments,
        "interval_months": plan.interval_months,
        "start_date": plan.start_date,
        "status": plan.status,
        "notes": plan.notes,
        "installments": lines,
        "total_paid": total_paid,
        "total_remaining": scheduled - total_paid,
        "next_due_date": next_due,
        "overdue_amount": overdue_amount,
        "overdue_count": overdue_count,
    }


def _plans_query(db: Session):
    return db.query(InstallmentPlan).options(
        selectinload(InstallmentPlan.installments), selectinload(InstallmentPlan.contact)
    )


def list_plans(db: Session) -> list[dict]:
    plans = _plans_query(db).order_by(InstallmentPlan.created_at.desc()).all()
    return [_serialize(p) for p in plans]


def get_plan(db: Session, plan_id: UUID) -> dict:
    plan = _plans_query(db).filter(InstallmentPlan.id == plan_id).first()
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "قرارداد اقساط یافت نشد")
    return _serialize(plan)


def create_plan(db: Session, data: InstallmentPlanIn, user: User) -> dict:
    contact = db.get(Contact, data.contact_id)
    if contact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "مشتری یافت نشد")

    financed = Decimal(data.total_amount) - Decimal(data.down_payment)
    n = data.num_installments
    base = (financed // n)  # تومانِ کامل
    remainder = financed - base * n  # به آخرین قسط اضافه می‌شود

    plan = InstallmentPlan(
        number=next_document_number(db, DOC_INSTALLMENT_PLAN),
        contact_id=data.contact_id,
        sales_invoice_id=data.sales_invoice_id,
        title=data.title or "فروش اقساطی",
        total_amount=data.total_amount,
        down_payment=data.down_payment,
        num_installments=n,
        interval_months=data.interval_months,
        start_date=data.start_date,
        status="active",
        notes=data.notes,
        created_by_id=user.id,
    )
    for k in range(1, n + 1):
        amount = base + (remainder if k == n else Decimal(0))
        plan.installments.append(Installment(
            seq=k,
            due_date=add_jalali_months(data.start_date, (k - 1) * data.interval_months),
            amount=amount,
        ))
    db.add(plan)
    db.flush()
    db.refresh(plan)
    return _serialize(plan)


def pay_installment(db: Session, plan_id: UUID, installment_id: UUID, data: InstallmentPayIn, user: User) -> dict:
    plan = _plans_query(db).filter(InstallmentPlan.id == plan_id).first()
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "قرارداد اقساط یافت نشد")
    if plan.status != "active":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "این قرارداد فعال نیست")

    inst = next((i for i in plan.installments if i.id == installment_id), None)
    if inst is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "قسط یافت نشد")

    remaining = Decimal(inst.amount) - Decimal(inst.paid_amount)
    if data.amount > remaining:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"مبلغ بیشتر از باقیمانده‌ی قسط ({remaining}) است")

    # دریافتِ خزانه‌ی واقعی: بدهکار صندوق/بانک، بستانکار حساب‌های دریافتنی.
    assert_period_open(db, data.transaction_date)
    treasury_service.create_receipt(
        db,
        TreasuryTransactionIn(
            transaction_date=data.transaction_date,
            contact_id=plan.contact_id,
            amount=data.amount,
            method=data.method,
            bank_account_id=data.bank_account_id,
            description=f"قسط {inst.seq} قرارداد {plan.number} — {plan.contact.name if plan.contact else ''}".strip(),
        ),
        user,
    )

    inst.paid_amount = Decimal(inst.paid_amount) + data.amount
    if Decimal(inst.paid_amount) >= Decimal(inst.amount):
        inst.paid_date = data.transaction_date

    if all(Decimal(i.paid_amount) >= Decimal(i.amount) for i in plan.installments):
        plan.status = "completed"

    db.flush()
    db.refresh(plan)
    return _serialize(plan)


def cancel_plan(db: Session, plan_id: UUID) -> dict:
    plan = _plans_query(db).filter(InstallmentPlan.id == plan_id).first()
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "قرارداد اقساط یافت نشد")
    # پرداخت‌های انجام‌شده (دریافت‌های خزانه) سرِ جایشان می‌مانند؛ فقط قرارداد لغو می‌شود.
    plan.status = "cancelled"
    db.flush()
    db.refresh(plan)
    return _serialize(plan)
