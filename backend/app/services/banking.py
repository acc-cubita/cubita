from collections import Counter
from datetime import date as date_, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.accounting import JournalLine
from app.models.banking import (
    BankAccount,
    BankStatementLine,
    BankTransaction,
    PettyCashTransaction,
)
from app.models.user import User
from app.schemas.banking import (
    BankDepositWithdrawIn,
    BankStatementLineIn,
    PettyCashChargeIn,
    PettyCashExpenseIn,
)
from app.services import chart_codes as cc
from app.services.common import (
    get_account,
    make_journal_entry as _make_journal_entry,
)
from app.services.period_close import assert_period_open

def create_bank_transaction(db: Session, data: BankDepositWithdrawIn, user: User) -> BankTransaction:
    assert_period_open(db, data.transaction_date)

    bank_account = db.get(BankAccount, data.bank_account_id)
    if bank_account is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "حساب بانکی یافت نشد")

    is_deposit = data.amount > 0
    lines = (
        [
            JournalLine(
                account_id=bank_account.gl_account_id,
                analytic_id=bank_account.analytic_id,
                debit=data.amount,
                credit=0,
            ),
            JournalLine(account_id=data.counter_account_id, debit=0, credit=data.amount),
        ]
        if is_deposit
        else [
            JournalLine(account_id=data.counter_account_id, debit=-data.amount, credit=0),
            JournalLine(
                account_id=bank_account.gl_account_id,
                analytic_id=bank_account.analytic_id,
                debit=0,
                credit=-data.amount,
            ),
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
    db.flush()
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
    db.flush()
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
    db.flush()
    db.refresh(txn)
    return txn


def _line_fingerprint(line_date, amount, description: str) -> tuple:
    """اثرِ محتوایی برای ردیفِ **بی‌مرجع**.

    شرح عمداً نرمال می‌شود: فایل‌های بانک همان تراکنش را با فاصله‌گذاریِ متفاوت
    صادر می‌کنند و بدونِ نرمال‌سازی، وارداتِ دوباره «تازه» به‌نظر می‌رسید.
    """
    return (line_date, Decimal(str(amount)), " ".join((description or "").split()))


def import_statement_lines(db: Session, bank_account_id: UUID, lines: list[BankStatementLineIn]) -> list[BankStatementLine]:
    """وارداتِ ردیف‌های صورت‌حساب — **بی‌اثر در تکرار**.

    تا امروز این تابع یک `add_all`ِ خام بود و جدول هیچ قیدِ یکتایی نداشت، پس وارد
    کردنِ دوباره‌ی یک فایل کلِ ردیف‌ها را **دوبرابر** می‌کرد. و چون
    `auto_match_statement` با «مبلغِ برابر و تاریخِ ±۳ روز» جفت می‌کند، نسخه‌های
    تکراری به تراکنش‌های دیگری می‌چسبیدند و مغایرت‌گیری را وارونه می‌کردند.

    **دو سطحِ تشخیص، چون همه‌ی بانک‌ها مرجع نمی‌دهند:**

    * `external_ref` دارد → کلیدِ قطعی. ردیفی که مرجعش قبلاً آمده رد می‌شود، و
      ایندکسِ یکتای جزئی در دیتابیس هم پشتش ایستاده.
    * مرجع ندارد → **شمارشِ ردیف‌های هم‌شکل**، نه حذفِ ساده. اگر فایل دو ردیفِ
      یکسان دارد و دوتا از قبل هست، هیچ‌کدام اضافه نمی‌شود؛ اگر سه‌تا دارد و دوتا
      هست، یکی اضافه می‌شود. پس دو تراکنشِ واقعاً یکسانِ یک روز قربانیِ گاردِ
      تکرار نمی‌شوند.

    **جهتِ خطا عمدی است:** واردنکردنِ یک ردیف دیده می‌شود (کاربر می‌بیند کمتر از
    آنچه فرستاده برگشته)، ولی واردکردنِ دوباره بی‌صدا دفتر را خراب می‌کند.

    خروجی فقط ردیف‌های **ساخته‌شده** است؛ تفاوتِ تعدادِ ارسالی و برگشتی یعنی
    چند ردیف تکراری بوده.
    """
    bank_account = db.get(BankAccount, bank_account_id)
    if bank_account is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "حساب بانکی یافت نشد")

    #: فقط بازه‌ی خودِ فایل خوانده می‌شود، نه کلِ تاریخچه — صورت‌حسابِ چندساله
    #: وگرنه هر واردات را به یک پویشِ کامل تبدیل می‌کرد.
    span = [line.line_date for line in lines]
    existing = (
        db.query(BankStatementLine)
        .filter(
            BankStatementLine.bank_account_id == bank_account_id,
            BankStatementLine.line_date >= min(span),
            BankStatementLine.line_date <= max(span),
        )
        .all()
    )
    seen_refs = {row.external_ref for row in existing if row.external_ref}
    existing_shapes: Counter = Counter(
        _line_fingerprint(row.line_date, row.amount, row.description)
        for row in existing
        if not row.external_ref
    )

    created: list[BankStatementLine] = []
    batch_refs: set[str] = set()
    incoming_shapes: Counter = Counter()
    for line in lines:
        ref = (line.external_ref or "").strip() or None
        if ref is not None:
            #: `batch_refs` هم لازم است: یک فایل می‌تواند خودش ردیفِ تکراری داشته
            #: باشد و بدونِ این، ایندکسِ یکتا با IntegrityError کلِ واردات را
            #: می‌انداخت به‌جای اینکه تکراری را رد کند.
            if ref in seen_refs or ref in batch_refs:
                continue
            batch_refs.add(ref)
        else:
            shape = _line_fingerprint(line.line_date, line.amount, line.description)
            incoming_shapes[shape] += 1
            if incoming_shapes[shape] <= existing_shapes.get(shape, 0):
                continue
        created.append(
            BankStatementLine(
                bank_account_id=bank_account_id,
                line_date=line.line_date,
                amount=line.amount,
                description=line.description,
                external_ref=ref,
            )
        )

    db.add_all(created)
    db.flush()
    for row in created:
        db.refresh(row)
    return created


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

    db.flush()
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
    db.flush()
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
        db.flush()
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
