"""پیمانکاری — پیمان (فازِ ۱)، متممِ پیمان (فازِ ۲) و صورت‌وضعیتِ دریافتی (فازِ ۳).

هیچ‌کدام سندِ حسابداری نمی‌زنند — صورت‌وضعیت هم مثلِ پیمان/متمم فقط رکورد است؛
اثرِ مالیِ واقعی به فازِ تسویه‌حساب موکول شده (تصمیمِ صریحِ کاربر).
"""
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.contracting import Contract, ContractAmendment, ContractStatement
from app.models.inventory import Contact
from app.models.user import User
from app.schemas.contracting import ContractAmendmentIn, ContractIn, ContractStatementIn
from app.services.numbering import next_document_number

#: متمم روی پیمانِ به‌پایان‌رسیده معنا ندارد — همان وضعیت‌های پایانیِ `_TRANSITIONS`.
_CLOSED_STATUSES = ("terminated", "completed", "cancelled")

#: گذارِ مجازِ وضعیت. نبودنِ یک زوج در این نگاشت یعنی آن گذار رد می‌شود.
_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "draft": ("active", "cancelled"),
    "active": ("suspended", "terminated", "completed"),
    "suspended": ("active", "terminated"),
    "terminated": (),
    "completed": (),
    "cancelled": (),
}


def create_contract(db: Session, data: ContractIn, user: User) -> Contract:
    contact = db.get(Contact, data.contact_id)
    if contact is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "طرف‌حساب یافت نشد")

    contract = Contract(
        number=next_document_number(db, "contract"),
        external_reference=data.external_reference,
        contact_id=data.contact_id,
        subject=data.subject,
        total_amount=data.total_amount,
        start_date=data.start_date,
        end_date=data.end_date,
        retention_percent=data.retention_percent,
        advance_percent=data.advance_percent,
        cost_center_id=data.cost_center_id,
        notes=data.notes,
        status="draft",
        created_by_id=user.id,
    )
    db.add(contract)
    db.flush()
    db.refresh(contract)
    return contract


def change_contract_status(db: Session, contract_id, new_status: str, user: User) -> Contract:
    contract = db.get(Contract, contract_id)
    if contract is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "پیمان یافت نشد")

    allowed = _TRANSITIONS.get(contract.status, ())
    if new_status not in allowed:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"گذار از «{contract.status}» به «{new_status}» مجاز نیست",
        )

    contract.status = new_status
    db.flush()
    db.refresh(contract)
    return contract


def create_contract_amendment(db: Session, data: ContractAmendmentIn, user: User) -> ContractAmendment:
    contract = db.get(Contract, data.contract_id)
    if contract is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "پیمان یافت نشد")
    if contract.status in _CLOSED_STATUSES:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "این پیمان به وضعیتِ پایانی رسیده — متممِ تازه نمی‌پذیرد",
        )
    if data.new_end_date is not None and data.new_end_date < contract.start_date:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "تاریخِ پایانِ تازه نمی‌تواند پیش از شروعِ پیمان باشد")

    amendment = ContractAmendment(
        number=next_document_number(db, "contract_amendment"),
        contract_id=data.contract_id,
        date=data.date,
        description=data.description,
        amount_delta=data.amount_delta,
        new_end_date=data.new_end_date,
        notes=data.notes,
        created_by_id=user.id,
    )
    db.add(amendment)
    if data.new_end_date is not None:
        contract.end_date = data.new_end_date
    db.flush()
    db.refresh(amendment)
    return amendment


def create_contract_statement(db: Session, data: ContractStatementIn, user: User) -> ContractStatement:
    contract = db.get(Contract, data.contract_id)
    if contract is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "پیمان یافت نشد")
    if contract.status in _CLOSED_STATUSES:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "این پیمان به وضعیتِ پایانی رسیده — صورت‌وضعیتِ تازه نمی‌پذیرد",
        )

    gross = data.gross_amount
    retention_amount = round(gross * Decimal(contract.retention_percent) / 100)
    advance_deduction = round(gross * Decimal(contract.advance_percent) / 100)
    net_amount = gross - retention_amount - advance_deduction - data.other_deductions

    statement = ContractStatement(
        number=next_document_number(db, "contract_statement"),
        contract_id=data.contract_id,
        date=data.date,
        gross_amount=data.gross_amount,
        retention_percent=contract.retention_percent,
        advance_percent=contract.advance_percent,
        retention_amount=retention_amount,
        advance_deduction=advance_deduction,
        other_deductions=data.other_deductions,
        net_amount=net_amount,
        notes=data.notes,
        created_by_id=user.id,
    )
    db.add(statement)
    db.flush()
    db.refresh(statement)
    return statement
