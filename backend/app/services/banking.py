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
    Check,
    Checkbook,
    PettyCashTransaction,
)
from app.models.treasury import TreasuryTransaction
from app.models.user import User
from app.schemas.banking import (
    BankDepositWithdrawIn,
    BankStatementLineIn,
    CheckbookIn,
    CheckIn,
    PettyCashChargeIn,
    PettyCashExpenseIn,
    PosSettlementIn,
)
from app.services import chart_codes as cc
from app.services.common import (
    get_account,
    get_or_create_account,
    make_journal_entry as _make_journal_entry,
)
from app.services.period_close import assert_period_open

# چرخه‌ی مجاز وضعیت هر چک: از وضعیت فعلی، کدام وضعیت‌های بعدی مجازند
RECEIVABLE_TRANSITIONS = {
    # `returned` = استرداد: چک را بدونِ وصول به صاحبش پس می‌دهیم. فقط از «نزدِ ما»
    # ممکن است؛ چکی که به بانک سپرده شده اول باید برگردد.
    "in_hand": {"deposited", "endorsed", "returned"},
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
        checkbook_id=data.checkbook_id,
        created_by_id=user.id,
    )
    db.add(check)
    db.flush()
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

    if new_status in ("cleared", "bounced", "endorsed", "returned"):
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

    elif new_status == "returned":
        # استرداد اثرِ ثبتِ اولیه را برمی‌گرداند: طلب از «اسنادِ دریافتنی» به همان
        # «حساب‌های دریافتنی»ِ طرف‌حساب برمی‌گردد — دقیقاً معکوسِ لحظه‌ی دریافتِ چک.
        # با `bounced` یکی نیست؛ آن‌جا بانک برگشت زده و اینجا ما پس داده‌ایم، و
        # تفکیکشان برای پیگیریِ سابقه‌ی طرف‌حساب مهم است.
        lines = [
            JournalLine(account_id=get_account(db, cc.ACCOUNTS_RECEIVABLE).id, debit=check.amount, credit=0),
            JournalLine(account_id=get_account(db, cc.CHECKS_RECEIVABLE).id, debit=0, credit=check.amount),
        ]
        journal_entry = _make_journal_entry(
            db, check.due_date, f"استرداد چک شماره {check.number} به صاحبش", "check", user, lines
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
    db.flush()
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


def import_statement_lines(db: Session, bank_account_id: UUID, lines: list[BankStatementLineIn]) -> list[BankStatementLine]:
    bank_account = db.get(BankAccount, bank_account_id)
    if bank_account is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "حساب بانکی یافت نشد")

    statement_lines = [
        BankStatementLine(bank_account_id=bank_account_id, line_date=line.line_date, amount=line.amount, description=line.description)
        for line in lines
    ]
    db.add_all(statement_lines)
    db.flush()
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


# ---------------------------------------------------------------------------
# دسته چک
# ---------------------------------------------------------------------------


def list_checkbooks(db: Session) -> list[dict]:
    """دسته‌چک‌ها با شمارِ برگِ خرج‌شده.

    «چند برگ مانده» را از روی چک‌های وصل‌شده می‌شماریم نه از یک شمارنده‌ی جدا:
    شمارنده با هر ابطال/حذفِ چک از واقعیت فاصله می‌گرفت.
    """
    used = dict(
        db.query(Check.checkbook_id, func.count(Check.id))
        .filter(Check.checkbook_id.isnot(None))
        .group_by(Check.checkbook_id)
        .all()
    )
    rows = (
        db.query(Checkbook, BankAccount.name)
        .outerjoin(BankAccount, BankAccount.id == Checkbook.bank_account_id)
        .order_by(Checkbook.created_at.desc())
        .all()
    )
    return [
        {
            "id": book.id,
            "bank_account_id": book.bank_account_id,
            "bank_account_name": bank_name or "",
            "serial": book.serial,
            "first_number": book.first_number,
            "last_number": book.last_number,
            "leaf_count": book.leaf_count,
            "used_count": used.get(book.id, 0),
            "remaining_count": max(book.leaf_count - used.get(book.id, 0), 0),
            "issue_date": book.issue_date,
            "description": book.description,
            "is_active": book.is_active,
        }
        for book, bank_name in rows
    ]


def create_checkbook(db: Session, data: CheckbookIn, user: User) -> Checkbook:
    bank = db.get(BankAccount, data.bank_account_id)
    if bank is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "حساب بانکی یافت نشد")

    first = data.first_number.strip()
    last = data.last_number.strip()
    if not first or not last:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "شماره‌ی اولین و آخرین برگ لازم است")

    # اگر هر دو عددی‌اند، شمارِ برگ را خودمان حساب می‌کنیم — کاربر نباید ریاضی کند.
    leaf_count = data.leaf_count
    if leaf_count <= 0 and first.isdigit() and last.isdigit():
        leaf_count = int(last) - int(first) + 1
    if leaf_count <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "تعداد برگ باید مثبت باشد")

    duplicate = (
        db.query(Checkbook)
        .filter(Checkbook.bank_account_id == bank.id, Checkbook.serial == data.serial.strip())
        .first()
    )
    if data.serial.strip() and duplicate is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "دسته‌چکی با این سری برای همین حساب ثبت شده است")

    book = Checkbook(
        bank_account_id=bank.id,
        serial=data.serial.strip(),
        first_number=first,
        last_number=last,
        leaf_count=leaf_count,
        issue_date=data.issue_date,
        description=data.description.strip(),
        is_active=True,
        created_by_id=user.id,
    )
    db.add(book)
    db.flush()
    db.refresh(book)
    return book


def set_checkbook_active(db: Session, checkbook_id: UUID, is_active: bool) -> Checkbook:
    book = db.get(Checkbook, checkbook_id)
    if book is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "دسته‌چک یافت نشد")
    book.is_active = is_active
    db.flush()
    db.refresh(book)
    return book


def delete_checkbook(db: Session, checkbook_id: UUID) -> None:
    """فقط دسته‌ی دست‌نخورده حذف می‌شود.

    دسته‌ای که برگ خورده سابقه‌ی چک‌های صادرشده است؛ حذفش آن چک‌ها را بی‌ریشه
    می‌کند. به‌جای حذف، «بستن» (is_active=false) کارِ درست است و پیام همین را می‌گوید.
    """
    book = db.get(Checkbook, checkbook_id)
    if book is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "دسته‌چک یافت نشد")
    used = db.query(Check).filter(Check.checkbook_id == book.id).count()
    if used:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"از این دسته {used} برگ صادر شده است؛ به‌جای حذف آن را ببندید.",
        )
    db.delete(book)
    db.flush()


def next_check_number(db: Session, checkbook_id: UUID) -> str:
    """شماره‌ی برگِ بعدیِ این دسته — پیشنهاد، نه قفل.

    از بزرگ‌ترین شماره‌ی مصرف‌شده جلو می‌رود، نه از شمارِ برگ‌ها: اگر کاربر برگی را
    از وسط خرج کرده باشد، شمارش ساده شماره‌ی تکراری پیشنهاد می‌داد.
    """
    book = db.get(Checkbook, checkbook_id)
    if book is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "دسته‌چک یافت نشد")
    numbers = [
        c.number
        for c in db.query(Check).filter(Check.checkbook_id == book.id).all()
        if (c.number or "").isdigit()
    ]
    if not book.first_number.isdigit():
        return ""
    width = len(book.first_number)
    nxt = (max(int(n) for n in numbers) + 1) if numbers else int(book.first_number)
    if book.last_number.isdigit() and nxt > int(book.last_number):
        return ""
    return str(nxt).zfill(width)


# ---------------------------------------------------------------------------
# تسویه‌ی کارتخوان
# ---------------------------------------------------------------------------
#
# فروشِ کارتی در لحظه‌ی رسید به حسابِ بانک بدهکار می‌شود، ولی پول همان لحظه نمی‌نشیند:
# شرکتِ پرداخت چند روز بعد جمعِ چند تراکنش را **منهای کارمزد** واریز می‌کند. پس تسویه
# اینجا یعنی «این تراکنش‌های کارتی در آن واریز آمدند» + ثبتِ کارمزد به‌عنوانِ هزینه.
# خودِ مبلغِ ناخالص دوباره ثبت نمی‌شود؛ وگرنه درآمد دوبار می‌آمد.


def pos_pending_settlements(
    db: Session, *, terminal_no: str | None, date_from: date_ | None, date_to: date_ | None
) -> list[dict]:
    """رسیدهای کارتیِ تسویه‌نشده، گروه‌بندی‌شده بر اساسِ پایانه و روز."""
    query = db.query(TreasuryTransaction).filter(
        TreasuryTransaction.paid_via == "pos_terminal",
        TreasuryTransaction.settled_at.is_(None),
    )
    if terminal_no:
        query = query.filter(TreasuryTransaction.terminal_no == terminal_no)
    if date_from is not None:
        query = query.filter(TreasuryTransaction.transaction_date >= date_from)
    if date_to is not None:
        query = query.filter(TreasuryTransaction.transaction_date <= date_to)

    groups: dict[tuple[str, date_], dict] = {}
    for txn in query.order_by(TreasuryTransaction.transaction_date).all():
        key = (txn.terminal_no or "", txn.transaction_date)
        row = groups.setdefault(
            key,
            {
                "terminal_no": txn.terminal_no or "",
                "transaction_date": txn.transaction_date,
                "count": 0,
                "gross_amount": Decimal(0),
            },
        )
        row["count"] += 1
        row["gross_amount"] += Decimal(txn.amount)
    return sorted(groups.values(), key=lambda r: (r["transaction_date"], r["terminal_no"]))


def settle_pos(db: Session, data: PosSettlementIn, user: User) -> dict:
    """تسویه‌ی یک واریزِ کارتخوان: علامت‌زدنِ رسیدها + ثبتِ کارمزد.

    کارمزد اختیاری است؛ اگر صفر باشد فقط علامت می‌خورد و هیچ سندی صادر نمی‌شود —
    سندِ صفرْ دفتر را شلوغ می‌کند بی‌آنکه چیزی بگوید.
    """
    assert_period_open(db, data.settlement_date)

    query = db.query(TreasuryTransaction).filter(
        TreasuryTransaction.paid_via == "pos_terminal",
        TreasuryTransaction.settled_at.is_(None),
        TreasuryTransaction.transaction_date >= data.date_from,
        TreasuryTransaction.transaction_date <= data.date_to,
    )
    if data.terminal_no:
        query = query.filter(TreasuryTransaction.terminal_no == data.terminal_no)
    rows = query.all()
    if not rows:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "رسیدِ کارتیِ تسویه‌نشده‌ای در این بازه نیست")

    gross = sum(Decimal(r.amount) for r in rows)
    fee = Decimal(data.fee_amount or 0)
    if fee < 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "کارمزد نمی‌تواند منفی باشد")
    if fee > gross:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "کارمزد از جمعِ تراکنش‌ها بیشتر است")

    settlement_txn = None
    if fee > 0:
        bank = db.get(BankAccount, data.bank_account_id) if data.bank_account_id else None
        if bank is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "برای ثبتِ کارمزد، حساب بانکی لازم است")
        fee_account = get_or_create_account(
            db,
            cc.BANK_FEE,
            code=cc.DEFAULT_CODE_BY_ROLE[cc.BANK_FEE],
            name="کارمزد و هزینه‌های بانکی",
            acc_type="expense",
            parent_code="5",
        )
        entry = _make_journal_entry(
            db,
            data.settlement_date,
            f"کارمزدِ تسویه‌ی کارتخوان{f' {data.terminal_no}' if data.terminal_no else ''}",
            "bank",
            user,
            [
                JournalLine(account_id=fee_account.id, debit=fee, credit=0),
                JournalLine(account_id=bank.gl_account_id, debit=0, credit=fee),
            ],
        )
        settlement_txn = BankTransaction(
            bank_account_id=bank.id,
            transaction_date=data.settlement_date,
            amount=-fee,
            description="کارمزدِ تسویه‌ی کارتخوان",
            source_type="pos_settlement",
            journal_entry_id=entry.id,
            created_by_id=user.id,
        )
        db.add(settlement_txn)
        db.flush()

    now = datetime.now(timezone.utc)
    for row in rows:
        row.settled_at = now
        row.settlement_txn_id = settlement_txn.id if settlement_txn is not None else None
    db.flush()

    return {
        "settled_count": len(rows),
        "gross_amount": gross,
        "fee_amount": fee,
        "net_amount": gross - fee,
    }
