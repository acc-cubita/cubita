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
from app.models.pos_terminal import PosTerminal
from app.models.treasury import TreasuryTransaction
from app.models.user import User
from app.schemas.banking import (
    BankDepositWithdrawIn,
    BankStatementLineIn,
    CheckIn,
    PettyCashChargeIn,
    PettyCashExpenseIn,
    PosSettlementIn,
)
from app.services import chart_codes as cc
from app.services import checkbooks
from app.services.common import (
    get_account,
    get_or_create_account,
    make_journal_entry as _make_journal_entry,
)
from app.services.period_close import assert_period_open

#: گرافِ وضعیتِ چکِ دریافتنی. **هیچ حالتی نباید بن‌بست باشد** مگر واقعاً پایانِ راه
#: باشد (`cleared`، `bounced`، `returned`).
#:
#: تا پیش از این `endorsed` کلید نداشت، یعنی چکی که خرج شده بود برای همیشه قفل
#: می‌شد و «برگشت از خرج کردن» ناممکن بود. `deposited` هم راهِ بازگشت نداشت، با
#: آن‌که کامنتِ همین‌جا و متنِ صفحه‌ی «استرداد چک» هر دو وعده‌اش را می‌دادند.
RECEIVABLE_TRANSITIONS = {
    # `returned` = استرداد: چک را بدونِ وصول به صاحبش پس می‌دهیم. فقط از «نزدِ ما»
    # ممکن است؛ چکی که به بانک سپرده شده اول باید برگردد.
    "in_hand": {"deposited", "endorsed", "returned"},
    # بازگشت از بانک بدونِ واخواست — بانک برگ را پس داده ولی برگشت نزده.
    "deposited": {"cleared", "bounced", "in_hand"},
    # برگشت از خرج کردن: گیرنده برگ را به ما پس داده.
    "endorsed": {"in_hand"},
}
PAYABLE_TRANSITIONS = {
    "issued": {"cleared", "bounced"},
}


def _resolve_leaf(db: Session, data: CheckIn) -> Checkbook | None:
    """دسته‌ی این چک را پیدا و برگش را می‌سنجد.

    دو چیزِ جدا که قاطی‌شان نکنیم:

    * **یکپارچگی** — اگر دسته‌ای انتخاب شده، شماره باید از همان دسته و خرج‌نشده
      باشد. این همیشه سنجیده می‌شود، در هر سیاستی؛ بدونش «برگِ مانده» عددِ دروغ
      می‌دهد و همان کاغذ دو بار خرج می‌شود.
    * **سیاست** — اینکه چکِ پرداختنی *اجازه دارد* بی‌دسته باشد یا نه، انتخابِ
      کسب‌وکار است و پیش‌فرضش «دارد» (رفتارِ امروز).

    چکِ دریافتنی دسته ندارد: کاغذش مالِ ما نیست و شماره‌اش را طرفِ مقابل نوشته.
    """
    if data.type == "receivable":
        return None

    if data.checkbook_id is None:
        if checkbooks.get_control_mode(db) == "book":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "طبقِ تنظیماتِ این کسب‌وکار، چکِ پرداختنی باید از یک دسته‌چک صادر "
                "شود. از صفحه‌ی «دسته چک» دسته را انتخاب و برگ را صادر کنید.",
            )
        return None

    book = checkbooks.resolve(db, data.checkbook_id)
    checkbooks.assert_leaf_available(db, book, data.number.strip())
    return book


def assert_sayad_free(db: Session, sayad_id: str, *, exclude_check_id: UUID | None = None) -> None:
    """کد صیادی روی یک چکِ دیگر ثبت نشده باشد (§۱۱).

    کد در سطحِ **کشور** یکتاست — یک برگ، یک کد. پس تکراری‌بودنش یعنی یا دو بار
    ثبت شده یا اشتباه تایپ شده؛ هیچ‌کدام حالتی نیست که بخواهیم نگه داریم.
    ایندکسِ جزئیِ `uq_checks_tenant_sayad` پشتیبانِ همین است در سطحِ پایگاه‌داده.
    """
    sayad = (sayad_id or "").strip()
    if not sayad:
        return
    query = db.query(Check).filter(Check.sayad_id == sayad)
    if exclude_check_id is not None:
        query = query.filter(Check.id != exclude_check_id)
    twin = query.first()
    if twin is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"کد صیادی {sayad} قبلاً روی چکِ شماره‌ی {twin.number} ثبت شده است",
        )


def new_check_row(db: Session, data: CheckIn, user: User, *, receipt_id: UUID | None = None) -> Check:
    """ردیفِ چک — **بدونِ سند حسابداری**.

    از `create_check` جدا شد چون رسیدِ دریافت چکش را در سندِ *خودش* ثبت می‌کند:
    یک رسید یک سند دارد (§۳۰)، پس چکِ داخلِ رسید نباید سندِ دومی بزند. اثرِ
    حسابداری‌اش یکی است — بدهکارِ «چک‌های دریافتنی»، بستانکارِ حسابِ طرفِ مقابل —
    فقط این‌که آن دو ردیف در سندِ رسید جمع می‌شوند به‌جای سندِ جدا.

    گاردهای برگ و صیادی این‌جا می‌مانند تا هر دو مسیر یکسان بسنجند.
    """
    book = _resolve_leaf(db, data)
    assert_sayad_free(db, data.sayad_id)
    return Check(
        type=data.type,
        number=data.number,
        bank_name=data.bank_name,
        amount=data.amount,
        issue_date=data.issue_date,
        due_date=data.due_date,
        status="in_hand" if data.type == "receivable" else "issued",
        description=data.description,
        description2=data.description2,
        contact_id=data.contact_id,
        checkbook_id=book.id if book else None,
        #: حسابِ بانکی از خودِ دسته می‌آید. تا مهاجرتِ ۰۱۰۸ چکِ پرداختنی تا لحظه‌ی
        #: وصول هیچ حسابی نداشت و آن‌وقت **دوباره** از کاربر پرسیده می‌شد — با
        #: آنکه دسته از روزِ اول می‌دانستش.
        bank_account_id=book.bank_account_id if book else None,
        receipt_id=receipt_id,
        sayad_id=data.sayad_id,
        back_number=data.back_number,
        branch_name=data.branch_name,
        branch_code=data.branch_code,
        account_number=data.account_number,
        owner_name=data.owner_name,
        created_by_id=user.id,
    )


def create_check(db: Session, data: CheckIn, user: User) -> Check:
    assert_period_open(db, data.issue_date)

    check = new_check_row(db, data, user)

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

    _make_journal_entry(db, data.issue_date, description, "check", user, lines)

    db.add(check)
    db.flush()
    db.refresh(check)
    return check


def _clearing_account(db: Session, check: Check, sent_id: UUID | None) -> BankAccount:
    """حسابی که پول از آن کم/به آن اضافه می‌شود هنگامِ وصول.

    چکِ پرداختنیِ صادرشده از یک دسته‌چک، حسابش را از همان دسته دارد؛ پرسیدنِ
    دوباره‌اش هم اضافه است هم راهی برای ناسازگاری — تعهد روی یک حساب ثبت شده بود
    و پول از حسابِ دیگری کم می‌شد. پس حسابِ ناهمخوانِ ارسالی **رد** می‌شود،
    نه اینکه بی‌صدا یکی ترجیح داده شود.
    """
    own = db.get(BankAccount, check.bank_account_id) if check.bank_account_id else None
    if check.type == "receivable":
        #: چکِ دریافتنی حسابش را در «واگذاری به بانک» گرفته، نه از دسته‌چک.
        if own is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "حساب بانکی مشخص نیست")
        return own

    sent = db.get(BankAccount, sent_id) if sent_id else None
    if own is not None and sent is not None and sent.id != own.id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"این چک از حسابِ «{own.name}» صادر شده است؛ وصولش از حسابِ دیگری ثبت نمی‌شود",
        )
    account = own or sent
    if account is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "حساب بانکی مشخص نیست")
    return account


def update_check_status(db: Session, check_id: UUID, new_status: str, bank_account_id: UUID | None, user: User) -> Check:
    check = db.get(Check, check_id)
    if check is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "چک یافت نشد")
    if check.voided_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "چک باطل شده است و عملیات تازه نمی‌پذیرد")

    transitions = RECEIVABLE_TRANSITIONS if check.type == "receivable" else PAYABLE_TRANSITIONS
    allowed = transitions.get(check.status, set())
    if new_status not in allowed:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"انتقال وضعیت از «{check.status}» به «{new_status}» مجاز نیست",
        )

    # گاردِ دوره فقط برای انتقال‌هایی که واقعاً سند می‌زنند. واگذاری به بانک و
    # بازگشت از آن اثرِ مالی ندارند، پس دوره‌ی بسته دلیلی برای مسدودکردنشان نیست.
    makes_entry = new_status in ("cleared", "bounced", "endorsed", "returned") or (
        new_status == "in_hand" and check.status == "endorsed"
    )
    if makes_entry:
        assert_period_open(db, check.due_date)

    journal_entry = None
    if new_status == "deposited":
        if bank_account_id is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "برای واریز چک، انتخاب حساب بانکی لازم است")
        check.bank_account_id = bank_account_id
        # هنوز اثر مالی جدیدی ثبت نمی‌شود؛ چک فقط از نظر فیزیکی به بانک سپرده شده

    elif new_status == "cleared":
        bank_account = _clearing_account(db, check, bank_account_id)
        if check.type == "receivable":
            lines = [
                JournalLine(
                    account_id=bank_account.gl_account_id,
                    analytic_id=bank_account.analytic_id,
                    debit=check.amount,
                    credit=0,
                ),
                JournalLine(account_id=get_account(db, cc.CHECKS_RECEIVABLE).id, debit=0, credit=check.amount),
            ]
        else:
            lines = [
                JournalLine(account_id=get_account(db, cc.CHECKS_PAYABLE).id, debit=check.amount, credit=0),
                JournalLine(
                    account_id=bank_account.gl_account_id,
                    analytic_id=bank_account.analytic_id,
                    debit=0,
                    credit=check.amount,
                ),
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

    elif new_status == "in_hand":
        if check.status == "endorsed":
            # **برگشت از خرج کردن** (§۱۷) — دقیقاً معکوسِ سندِ خرج: برگ دوباره نزدِ
            # ماست و بدهیِ ما به کسی که به او داده بودیم هم برمی‌گردد.
            #
            # با `bounced` یکی نیست: آن‌جا بانک واخواست کرده و چک بی‌اعتبار است،
            # این‌جا برگ سالم است و فقط دستِ ما برگشته.
            lines = [
                JournalLine(account_id=get_account(db, cc.CHECKS_RECEIVABLE).id, debit=check.amount, credit=0),
                JournalLine(account_id=get_account(db, cc.ACCOUNTS_PAYABLE).id, debit=0, credit=check.amount),
            ]
            journal_entry = _make_journal_entry(
                db, check.due_date, f"برگشت از خرج کردن چک شماره {check.number}", "check", user, lines
            )
        else:
            # بازگشت از بانک: خودِ واگذاری هم سندی نزده بود، پس این هم نمی‌زند.
            # سندِ بی‌اثر دفتر را شلوغ می‌کند بی‌آنکه چیزی بگوید.
            check.bank_account_id = None

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
# تسویه‌ی کارتخوان
# ---------------------------------------------------------------------------
#
# فروشِ کارتی در لحظه‌ی رسید به حسابِ بانک بدهکار می‌شود، ولی پول همان لحظه نمی‌نشیند:
# شرکتِ پرداخت چند روز بعد جمعِ چند تراکنش را **منهای کارمزد** واریز می‌کند. پس تسویه
# اینجا یعنی «این تراکنش‌های کارتی در آن واریز آمدند» + ثبتِ کارمزد به‌عنوانِ هزینه.
# خودِ مبلغِ ناخالص دوباره ثبت نمی‌شود؛ وگرنه درآمد دوبار می‌آمد.


def pos_pending_settlements(
    db: Session,
    *,
    terminal_no: str | None,
    date_from: date_ | None,
    date_to: date_ | None,
    pos_terminal_id: UUID | None = None,
) -> list[dict]:
    """رسیدهای کارتیِ تسویه‌نشده، گروه‌بندی‌شده بر اساسِ پایانه و روز.

    `pos_terminal_id` راهِ درست است: دامنه از خودِ دستگاه می‌آید و شاملِ رسیدهای
    قدیمیِ همان شماره هم می‌شود. `terminal_no` برای سازگاری می‌ماند.
    """
    from app.services import card_terminals

    query = db.query(TreasuryTransaction).filter(
        TreasuryTransaction.paid_via == "pos_terminal",
        TreasuryTransaction.settled_at.is_(None),
        TreasuryTransaction.voided_at.is_(None),
    )
    if pos_terminal_id is not None:
        query = query.filter(card_terminals._owned_transactions(card_terminals.resolve(db, pos_terminal_id)))
    elif terminal_no:
        query = query.filter(TreasuryTransaction.terminal_no == terminal_no)
    if date_from is not None:
        query = query.filter(TreasuryTransaction.transaction_date >= date_from)
    if date_to is not None:
        query = query.filter(TreasuryTransaction.transaction_date <= date_to)

    #: برچسبِ دستگاه یک‌بار خوانده می‌شود، نه به‌ازای هر ردیف.
    labels = {t.id: t.label for t in db.query(PosTerminal).all()}

    groups: dict[tuple[str, date_], dict] = {}
    for txn in query.order_by(TreasuryTransaction.transaction_date).all():
        key = (txn.terminal_no or "", txn.transaction_date)
        row = groups.setdefault(
            key,
            {
                "terminal_no": txn.terminal_no or "",
                "pos_terminal_id": txn.pos_terminal_id,
                "terminal_label": labels.get(txn.pos_terminal_id),
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

    from app.services import card_terminals

    #: دستگاه، اگر داده شده، هم دامنه‌ی تسویه را تعیین می‌کند هم حسابِ کارمزد را —
    #: به‌جای تطبیقِ رشته‌ایِ شماره‌ای که کاربر تایپ کرده و یک فاصله‌ی اضافی‌اش
    #: بی‌صدا صفر نتیجه می‌داد.
    terminal = card_terminals.resolve(db, data.pos_terminal_id) if data.pos_terminal_id else None

    query = db.query(TreasuryTransaction).filter(
        TreasuryTransaction.paid_via == "pos_terminal",
        TreasuryTransaction.settled_at.is_(None),
        TreasuryTransaction.voided_at.is_(None),
        TreasuryTransaction.transaction_date >= data.date_from,
        TreasuryTransaction.transaction_date <= data.date_to,
    )
    if terminal is not None:
        query = query.filter(card_terminals._owned_transactions(terminal))
    elif data.terminal_no:
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
        #: حسابِ کارمزد از خودِ دستگاه می‌آید تا با حسابی که ناخالص آنجا نشسته یکی
        #: بماند؛ فقط مسیرِ قدیمی (بدونِ دستگاه) هنوز حساب را از ورودی می‌گیرد.
        if terminal is not None:
            bank = card_terminals.settlement_account(db, terminal)
        else:
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
                JournalLine(
                    account_id=bank.gl_account_id,
                    analytic_id=bank.analytic_id,
                    debit=0,
                    credit=fee,
                ),
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
