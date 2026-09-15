"""پیمانکاری — پیمان (فازِ ۱)، متممِ پیمان (فازِ ۲)، صورت‌وضعیتِ دریافتی (فازِ ۳) و
تسویه‌حسابِ پیمان (فازِ ۴).

فقط تسویه‌حساب سندِ حسابداری می‌زند — پیمان/متمم/صورت‌وضعیت هرسه فقط رکوردند
(تصمیمِ صریحِ کاربر). سه فازِ اول را اینجا نگه داشتیم، جدا نکردیم؛ همه یک دامنه‌اند
و ارجاعِ بینشان (تسویه‌حساب به صورت‌وضعیت‌ها، صورت‌وضعیت به پیمان) در یک فایل روشن‌تر
از پخش‌شدن در چند فایلِ کوچک است.
"""
from datetime import date as date_
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.accounting import JournalEntry, JournalLine
from app.models.contracting import Contract, ContractAmendment, ContractSettlement, ContractStatement
from app.models.inventory import Contact
from app.models.user import User
from app.schemas.contracting import (
    ContractAmendmentIn,
    ContractIn,
    ContractSettlementIn,
    ContractStatementIn,
)
from app.services import chart_codes as cc
from app.services.common import get_account, get_or_create_account, make_journal_entry
from app.services.numbering import next_document_number
from app.services.period_close import assert_period_open
from app.services.voiding import guard_no_active_allocations, reverse_journal_entry

#: متمم/صورت‌وضعیت روی پیمانِ به‌پایان‌رسیده معنا ندارد — همان وضعیت‌های پایانیِ `_TRANSITIONS`.
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


# ─────────────────────── تسویه‌حسابِ پیمان (فازِ ۴) — سندِ واقعی ───────────────────────


def _contract_revenue_account(db: Session):
    return get_or_create_account(
        db, cc.CONTRACT_REVENUE,
        code=cc.DEFAULT_CODE_BY_ROLE[cc.CONTRACT_REVENUE],
        name="درآمدِ پیمانکاری", acc_type="income", parent_code="4",
    )


def _contract_retention_receivable_account(db: Session):
    return get_or_create_account(
        db, cc.CONTRACT_RETENTION_RECEIVABLE,
        code=cc.DEFAULT_CODE_BY_ROLE[cc.CONTRACT_RETENTION_RECEIVABLE],
        name="سپرده‌ی حسن انجامِ کار نزدِ کارفرما", acc_type="asset", parent_code="11",
    )


def _contract_advance_received_account(db: Session):
    return get_or_create_account(
        db, cc.CONTRACT_ADVANCE_RECEIVED,
        code=cc.DEFAULT_CODE_BY_ROLE[cc.CONTRACT_ADVANCE_RECEIVED],
        name="پیش‌دریافتِ پیمان", acc_type="liability", parent_code="21",
    )


def _contract_other_deductions_account(db: Session):
    return get_or_create_account(
        db, cc.CONTRACT_OTHER_DEDUCTIONS,
        code=cc.DEFAULT_CODE_BY_ROLE[cc.CONTRACT_OTHER_DEDUCTIONS],
        name="سایرِ کسوراتِ صورت‌وضعیت", acc_type="expense", parent_code="5",
    )


def create_contract_settlement(db: Session, data: ContractSettlementIn, user: User) -> ContractSettlement:
    contract = db.get(Contract, data.contract_id)
    if contract is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "پیمان یافت نشد")

    already = (
        db.query(ContractSettlement)
        .filter(ContractSettlement.contract_id == contract.id, ContractSettlement.voided_at.is_(None))
        .first()
    )
    if already is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "این پیمان قبلاً تسویه شده — ابطالِ تسویه‌ی قبلی لازم است")

    statements = db.query(ContractStatement).filter(ContractStatement.contract_id == contract.id).all()
    if not statements:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "این پیمان هنوز صورت‌وضعیتی ندارد — چیزی برای تسویه نیست")

    gross = sum((Decimal(s.gross_amount) for s in statements), Decimal(0))
    retention = sum((Decimal(s.retention_amount) for s in statements), Decimal(0))
    advance = sum((Decimal(s.advance_deduction) for s in statements), Decimal(0))
    other = sum((Decimal(s.other_deductions) for s in statements), Decimal(0))
    net = sum((Decimal(s.net_amount) for s in statements), Decimal(0))

    amendments = db.query(ContractAmendment).filter(ContractAmendment.contract_id == contract.id).all()
    contract_value = Decimal(contract.total_amount) + sum(
        (Decimal(a.amount_delta) for a in amendments), Decimal(0)
    )

    assert_period_open(db, data.date)

    receivable = get_account(db, cc.ACCOUNTS_RECEIVABLE)
    revenue_account = _contract_revenue_account(db)

    lines: list[JournalLine] = []
    head = f"تسویه‌حسابِ پیمانِ شماره {contract.number}"
    if net != 0:
        lines.append(JournalLine(
            account_id=receivable.id, analytic_id=contract.contact.analytic_id if contract.contact else None,
            debit=net, credit=0, description=head,
        ))
    if retention != 0:
        lines.append(JournalLine(
            account_id=_contract_retention_receivable_account(db).id, debit=retention, credit=0,
            description=f"{head} — آزادسازیِ سپرده",
        ))
    if advance != 0:
        lines.append(JournalLine(
            account_id=_contract_advance_received_account(db).id, debit=advance, credit=0,
            description=f"{head} — تسویه‌ی پیش‌پرداخت",
        ))
    if other != 0:
        lines.append(JournalLine(
            account_id=_contract_other_deductions_account(db).id, debit=other, credit=0,
            description=f"{head} — سایرِ کسورات",
        ))
    lines.append(JournalLine(account_id=revenue_account.id, debit=0, credit=gross, description=head))

    entry = make_journal_entry(db, data.date, head, "contract_settlement", user, lines)

    settlement = ContractSettlement(
        number=next_document_number(db, "contract_settlement"),
        contract_id=contract.id,
        date=data.date,
        gross_amount=gross,
        retention_amount=retention,
        advance_amount=advance,
        other_deductions=other,
        net_amount=net,
        contract_value_at_settlement=contract_value,
        notes=data.notes,
        journal_entry_id=entry.id,
        created_by_id=user.id,
    )
    db.add(settlement)
    db.flush()
    db.refresh(settlement)
    return settlement


def void_contract_settlement(
    db: Session, user: User, settlement_id: UUID, reason: str, void_date: date_ | None = None
) -> ContractSettlement:
    settlement = (
        db.query(ContractSettlement)
        .filter(ContractSettlement.id == settlement_id)
        .with_for_update()
        .one_or_none()
    )
    if settlement is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "تسویه‌حساب یافت نشد")
    if settlement.voided_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "این تسویه‌حساب قبلاً باطل شده")
    guard_no_active_allocations(db, "contract_settlement", settlement.id, "تسویه‌حساب")

    effective_date = void_date or settlement.date
    assert_period_open(db, effective_date)

    entry = db.get(JournalEntry, settlement.journal_entry_id) if settlement.journal_entry_id else None
    if entry is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "این تسویه‌حساب سندِ حسابداری ندارد؛ ابطالش چیزی را برنمی‌گرداند")

    clean = reason.strip()
    reverse_journal_entry(
        db, entry, void_date=effective_date, user=user,
        description=f"ابطالِ تسویه‌حسابِ شماره {settlement.number}" + (f" — {clean}" if clean else ""),
    )
    settlement.voided_at = datetime.now(timezone.utc)
    settlement.voided_by_id = user.id
    settlement.void_reason = clean
    db.flush()
    return settlement
