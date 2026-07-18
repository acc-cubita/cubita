from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.accounting import JournalLine
from app.models.banking import BankAccount, BankStatementLine, BankTransaction, Check, PettyCashTransaction
from app.models.user import User
from app.schemas.banking import (
    BankDepositWithdrawIn,
    BankStatementLineIn,
    CheckIn,
    PettyCashChargeIn,
    PettyCashExpenseIn,
)
from app.services import chart_codes as cc
from app.services.common import get_account, make_journal_entry as _make_journal_entry
from app.services.period_close import assert_period_open

# چرخه‌ی مجاز وضعیت هر چک: از وضعیت فعلی، کدام وضعیت‌های بعدی مجازند
RECEIVABLE_TRANSITIONS = {
    "in_hand": {"deposited", "endorsed"},
    "deposited": {"cleared", "bounced"},
}
PAYABLE_TRANSITIONS = {
    "issued": {"cleared", "bounced"},
}


def create_check(db: Session, data: CheckIn, user: User) -> Check:
    assert_period_open(db, data.issue_date)

    initial_status = "in_hand" if data.type == "receivable" else "issued"

    if data.type == "receivable":
        # چک دریافتنی بابت مطالبات مشتری: از حساب دریافتنی به چک‌های دریافتنی منتقل می‌شود
        lines = [
            JournalLine(account_id=get_account(db, cc.CHECKS_RECEIVABLE).id, debit=data.amount, credit=0),
            JournalLine(account_id=get_account(db, cc.ACCOUNTS_RECEIVABLE).id, debit=0, credit=data.amount),
        ]
        description = f"دریافت چک شماره {data.number} بابت مطالبات"
    else:
        # چک پرداختنی بابت بدهی به تأمین‌کننده: از حساب پرداختنی به چک‌های پرداختنی منتقل می‌شود
        lines = [
            JournalLine(account_id=get_account(db, cc.ACCOUNTS_PAYABLE).id, debit=data.amount, credit=0),
            JournalLine(account_id=get_account(db, cc.CHECKS_PAYABLE).id, debit=0, credit=data.amount),
        ]
        description = f"صدور چک شماره {data.number} بابت بدهی"

    journal_entry = _make_journal_entry(db, data.issue_date, description, "check", user, lines)

    check = Check(
        type=data.type,
        number=data.number,
        bank_name=data.bank_name,
        amount=data.amount,
        issue_date=data.issue_date,
        due_date=data.due_date,
        status=initial_status,
        description=data.description,
        contact_id=data.contact_id,
        created_by_id=user.id,
    )
    db.add(check)
    db.commit()
    db.refresh(check)
    return check


def update_check_status(db: Session, check_id: UUID, new_status: str, bank_account_id: UUID | None, user: User) -> Check:
    check = db.get(Check, check_id)
    if check is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "چک یافت نشد")

    transitions = RECEIVABLE_TRANSITIONS if check.type == "receivable" else PAYABLE_TRANSITIONS
    allowed = transitions.get(check.status, set())
    if new_status not in allowed:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"انتقال وضعیت از «{check.status}» به «{new_status}» مجاز نیست",
        )

    if new_status in ("cleared", "bounced", "endorsed"):
        assert_period_open(db, check.due_date)

    journal_entry = None
    if new_status == "deposited":
        if bank_account_id is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "برای واریز چک، انتخاب حساب بانکی لازم است")
        check.bank_account_id = bank_account_id
        # هنوز اثر مالی جدیدی ثبت نمی‌شود؛ چک فقط از نظر فیزیکی به بانک سپرده شده

    elif new_status == "cleared":
        bank_account = db.get(BankAccount, check.bank_account_id) if check.type == "receivable" else (
            db.get(BankAccount, bank_account_id) if bank_account_id else None
        )
        if bank_account is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "حساب بانکی مشخص نیست")
        if check.type == "receivable":
            lines = [
                JournalLine(account_id=bank_account.gl_account_id, debit=check.amount, credit=0),
                JournalLine(account_id=get_account(db, cc.CHECKS_RECEIVABLE).id, debit=0, credit=check.amount),
            ]
        else:
            lines = [
                JournalLine(account_id=get_account(db, cc.CHECKS_PAYABLE).id, debit=check.amount, credit=0),
                JournalLine(account_id=bank_account.gl_account_id, debit=0, credit=check.amount),
            ]
        journal_entry = _make_journal_entry(
            db, check.due_date, f"وصول/کسر چک شماره {check.number}", "check", user, lines
        )
        bank_txn_amount = check.amount if check.type == "receivable" else -check.amount
        db.add(
            BankTransaction(
                bank_account_id=bank_account.id,
                transaction_date=check.due_date,
                amount=bank_txn_amount,
                description=f"چک شماره {check.number}",
                source_type="check_clear",
                source_id=check.id,
                journal_entry_id=journal_entry.id,
                created_by_id=user.id,
            )
        )
        check.bank_account_id = bank_account.id

    elif new_status == "bounced":
        if check.type == "receivable":
            lines = [
                JournalLine(account_id=get_account(db, cc.ACCOUNTS_RECEIVABLE).id, debit=check.amount, credit=0),
                JournalLine(account_id=get_account(db, cc.CHECKS_RECEIVABLE).id, debit=0, credit=check.amount),
            ]
        else:
            lines = [
                JournalLine(account_id=get_account(db, cc.CHECKS_PAYABLE).id, debit=check.amount, credit=0),
                JournalLine(account_id=get_account(db, cc.ACCOUNTS_PAYABLE).id, debit=0, credit=check.amount),
            ]
        journal_entry = _make_journal_entry(
            db, check.due_date, f"برگشت چک شماره {check.number}", "check", user, lines
        )

    elif new_status == "endorsed":
        lines = [
            JournalLine(account_id=get_account(db, cc.ACCOUNTS_PAYABLE).id, debit=check.amount, credit=0),
            JournalLine(account_id=get_account(db, cc.CHECKS_RECEIVABLE).id, debit=0, credit=check.amount),
        ]
        journal_entry = _make_journal_entry(
            db, check.due_date, f"خرج کردن چک شماره {check.number} بابت پرداخت", "check", user, lines
        )

    check.status = new_status
    db.commit()
    db.refresh(check)
    return check


def create_bank_transaction(db: Session, data: BankDepositWithdrawIn, user: User) -> BankTransaction:
    assert_period_open(db, data.transaction_date)

    bank_account = db.get(BankAccount, data.bank_account_id)
    if bank_account is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "حساب بانکی یافت نشد")

    is_deposit = data.amount > 0
    lines = (
        [
            JournalLine(account_id=bank_account.gl_account_id, debit=data.amount, credit=0),
            JournalLine(account_id=data.counter_account_id, debit=0, credit=data.amount),
        ]
        if is_deposit
        else [
            JournalLine(account_id=data.counter_account_id, debit=-data.amount, credit=0),
            JournalLine(account_id=bank_account.gl_account_id, debit=0, credit=-data.amount),
        ]
    )
    journal_entry = _make_journal_entry(
        db, data.transaction_date, data.description or ("واریز بانکی" if is_deposit else "برداشت بانکی"), "bank", user, lines
    )

    txn = BankTransaction(
        bank_account_id=data.bank_account_id,
        transaction_date=data.transaction_date,
        amount=data.amount,
        description=data.description,
        journal_entry_id=journal_entry.id,
        created_by_id=user.id,
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


def create_petty_cash_charge(db: Session, data: PettyCashChargeIn, user: User) -> PettyCashTransaction:
    assert_period_open(db, data.transaction_date)

    lines = [
        JournalLine(account_id=get_account(db, cc.PETTY_CASH).id, debit=data.amount, credit=0),
        JournalLine(account_id=data.source_account_id, debit=0, credit=data.amount),
    ]
    journal_entry = _make_journal_entry(db, data.transaction_date, "شارژ تنخواه‌گردان", "petty_cash", user, lines)
    txn = PettyCashTransaction(
        type="charge",
        transaction_date=data.transaction_date,
        amount=data.amount,
        description=data.description,
        counter_account_id=data.source_account_id,
        journal_entry_id=journal_entry.id,
        created_by_id=user.id,
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


def create_petty_cash_expense(db: Session, data: PettyCashExpenseIn, user: User) -> PettyCashTransaction:
    assert_period_open(db, data.transaction_date)

    lines = [
        JournalLine(account_id=data.expense_account_id, debit=data.amount, credit=0),
        JournalLine(account_id=get_account(db, cc.PETTY_CASH).id, debit=0, credit=data.amount),
    ]
    journal_entry = _make_journal_entry(
        db, data.transaction_date, data.description or "هزینه‌کرد تنخواه‌گردان", "petty_cash", user, lines
    )
    txn = PettyCashTransaction(
        type="expense",
        transaction_date=data.transaction_date,
        amount=data.amount,
        description=data.description,
        counter_account_id=data.expense_account_id,
        journal_entry_id=journal_entry.id,
        created_by_id=user.id,
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


def import_statement_lines(db: Session, bank_account_id: UUID, lines: list[BankStatementLineIn]) -> list[BankStatementLine]:
    bank_account = db.get(BankAccount, bank_account_id)
    if bank_account is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "حساب بانکی یافت نشد")

    statement_lines = [
        BankStatementLine(bank_account_id=bank_account_id, line_date=line.line_date, amount=line.amount, description=line.description)
        for line in lines
    ]
    db.add_all(statement_lines)
    db.commit()
    for line in statement_lines:
        db.refresh(line)
    return statement_lines


def auto_match_statement(db: Session, bank_account_id: UUID) -> int:
    """تطبیق خودکار: هر ردیف صورت‌حساب بدون تطبیق را با یک تراکنش سیستمِ تطبیق‌نشده با همان مبلغ و تاریخ نزدیک (±۳ روز) جفت می‌کند."""
    unmatched_lines = (
        db.query(BankStatementLine)
        .filter(BankStatementLine.bank_account_id == bank_account_id, BankStatementLine.matched_transaction_id.is_(None))
        .all()
    )
    unreconciled_txns = (
        db.query(BankTransaction)
        .filter(BankTransaction.bank_account_id == bank_account_id, BankTransaction.is_reconciled.is_(False))
        .all()
    )

    used_txn_ids: set[UUID] = set()
    matched_count = 0
    for line in unmatched_lines:
        for txn in unreconciled_txns:
            if txn.id in used_txn_ids:
                continue
            if Decimal(txn.amount) == Decimal(line.amount) and abs((txn.transaction_date - line.line_date).days) <= 3:
                line.matched_transaction_id = txn.id
                txn.is_reconciled = True
                used_txn_ids.add(txn.id)
                matched_count += 1
                break

    db.commit()
    return matched_count


def match_statement_line(db: Session, line_id: UUID, transaction_id: UUID) -> BankStatementLine:
    line = db.get(BankStatementLine, line_id)
    if line is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ردیف صورت‌حساب یافت نشد")
    txn = db.get(BankTransaction, transaction_id)
    if txn is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "تراکنش بانکی یافت نشد")
    if txn.bank_account_id != line.bank_account_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "این تراکنش متعلق به همین حساب بانکی نیست")

    if line.matched_transaction_id is not None:
        previous = db.get(BankTransaction, line.matched_transaction_id)
        if previous is not None:
            previous.is_reconciled = False

    line.matched_transaction_id = txn.id
    txn.is_reconciled = True
    db.commit()
    db.refresh(line)
    return line


def unmatch_statement_line(db: Session, line_id: UUID) -> BankStatementLine:
    line = db.get(BankStatementLine, line_id)
    if line is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ردیف صورت‌حساب یافت نشد")

    if line.matched_transaction_id is not None:
        txn = db.get(BankTransaction, line.matched_transaction_id)
        if txn is not None:
            txn.is_reconciled = False
        line.matched_transaction_id = None
        db.commit()
        db.refresh(line)
    return line


def get_reconciliation_summary(db: Session, bank_account_id: UUID) -> dict:
    lines = db.query(BankStatementLine).filter(BankStatementLine.bank_account_id == bank_account_id).all()
    unmatched_lines = [line for line in lines if line.matched_transaction_id is None]
    unreconciled_txns = (
        db.query(BankTransaction)
        .filter(BankTransaction.bank_account_id == bank_account_id, BankTransaction.is_reconciled.is_(False))
        .all()
    )
    statement_total = sum((Decimal(line.amount) for line in lines), Decimal(0))
    return {
        "statement_total": statement_total,
        "matched_count": len(lines) - len(unmatched_lines),
        "unmatched_statement_lines": unmatched_lines,
        "unreconciled_system_transactions": unreconciled_txns,
    }


def get_petty_cash_balance(db: Session) -> Decimal:
    charges = db.query(PettyCashTransaction).filter(PettyCashTransaction.type == "charge").all()
    expenses = db.query(PettyCashTransaction).filter(PettyCashTransaction.type == "expense").all()
    total_charge = sum((Decimal(t.amount) for t in charges), Decimal(0))
    total_expense = sum((Decimal(t.amount) for t in expenses), Decimal(0))
    return total_charge - total_expense
