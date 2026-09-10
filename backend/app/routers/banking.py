from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.deps import require_permission
from app.models.banking import BankAccount, BankStatementLine, BankTransaction, Check, PettyCashTransaction
from app.models.user import User
from app.pagination import Page, PageParams, paginate
from app.schemas.banking import (
    BankAccountIn,
    BankAccountOut,
    BankAccountUpdateIn,
    BankDepositWithdrawIn,
    BankStatementImportIn,
    BankStatementLineOut,
    BankTransactionOut,
    CheckbookIn,
    CheckbookOut,
    CheckIn,
    CheckOut,
    CheckStatusUpdateIn,
    MatchStatementLineIn,
    PettyCashChargeIn,
    PettyCashExpenseIn,
    PettyCashTransactionOut,
    PosPendingGroupOut,
    PosSettlementIn,
    PosSettlementOut,
    ReconciliationSummaryOut,
)
from app.services import bank_accounts as bank_accounts_service
from app.services import banking as banking_service
from app.services import chart_codes as cc
from app.services.common import get_account
from uuid import UUID

router = APIRouter(tags=["banking"])


@router.get("/api/bank-accounts", response_model=list[BankAccountOut])
def list_bank_accounts(db: Session = Depends(get_db), _=Depends(require_permission("checks_bank", "view"))):
    """حساب‌ها با مانده‌ی مشتق — بدونِ جمعِ کل، چون ارزها با هم جمع نمی‌شوند (§۲۱)."""
    return bank_accounts_service.list_bank_accounts(db)


@router.post("/api/bank-accounts", response_model=BankAccountOut, status_code=201)
def create_bank_account(
    data: BankAccountIn, db: Session = Depends(get_db), _=Depends(require_permission("checks_bank", "create"))
):
    payload = data.model_dump()
    payload["gl_account_id"] = data.gl_account_id or get_account(db, cc.BANK).id
    account = bank_accounts_service.create_bank_account(db, payload)
    return bank_accounts_service.row(db, account)


@router.patch("/api/bank-accounts/{bank_account_id}", response_model=BankAccountOut)
def update_bank_account(
    bank_account_id: UUID,
    data: BankAccountUpdateIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("checks_bank", "update")),
):
    """ویرایشِ حساب بانکی. حسابِ دفترِ کل ثابت می‌ماند و تفصیلیِ حسابِ باسابقه هم (§۳۱)."""
    account = bank_accounts_service.update_bank_account(
        db, bank_account_id, data.model_dump(exclude_unset=True)
    )
    return bank_accounts_service.row(db, account)


@router.delete("/api/bank-accounts/{bank_account_id}", status_code=204)
def delete_bank_account(
    bank_account_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("checks_bank", "delete")),
):
    """حسابِ بی‌سابقه حذف می‌شود؛ حسابِ باسابقه فقط غیرفعال (§۲۳)."""
    bank_accounts_service.delete_bank_account(db, bank_account_id)


@router.get("/api/checks", response_model=Page[CheckOut])
def list_checks(
    db: Session = Depends(get_db),
    params: PageParams = Depends(),
    _=Depends(require_permission("checks_bank", "view")),
):
    # id به‌عنوان شکننده‌ی تساوی: تاریخ به‌تنهایی یکتا نیست و ردیف‌های هم‌تاریخ سر مرز صفحه گم می‌شوند
    items, next_cursor = paginate(
        db.query(Check).options(selectinload(Check.contact)),
        [Check.due_date, Check.id],
        params,
        descending=False,
    )
    return Page(items=items, next_cursor=next_cursor)


@router.post("/api/checks", response_model=CheckOut, status_code=201)
def create_check(
    data: CheckIn, db: Session = Depends(get_db), user: User = Depends(require_permission("checks_bank", "create"))
):
    return banking_service.create_check(db, data, user)


@router.patch("/api/checks/{check_id}/status", response_model=CheckOut)
def update_check_status(
    check_id: UUID,
    data: CheckStatusUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("checks_bank", "update")),
):
    return banking_service.update_check_status(db, check_id, data.status, data.bank_account_id, user)


@router.get("/api/bank-transactions", response_model=Page[BankTransactionOut])
def list_bank_transactions(
    db: Session = Depends(get_db),
    params: PageParams = Depends(),
    bank_account_id: UUID | None = Query(None, description="فقط گردشِ همین حساب"),
    _=Depends(require_permission("checks_bank", "view")),
):
    """گردشِ بانکی، اختیاری محدود به یک حساب.

    `bank_account_id` تا امروز **تعریف نشده بود** در حالی که رابط می‌فرستادش —
    یعنی صافیِ حسابِ صفحه‌ی «مرور عملیات بانکی» بی‌صدا هیچ کاری نمی‌کرد و کاربر
    گردشِ همه‌ی حساب‌ها را می‌دید.
    """
    query = db.query(BankTransaction)
    if bank_account_id is not None:
        query = query.filter(BankTransaction.bank_account_id == bank_account_id)
    # id به‌عنوان شکننده‌ی تساوی: تاریخ به‌تنهایی یکتا نیست و ردیف‌های هم‌تاریخ سر مرز صفحه گم می‌شوند
    items, next_cursor = paginate(
        query,
        [BankTransaction.transaction_date, BankTransaction.id],
        params,
    )
    return Page(items=items, next_cursor=next_cursor)


@router.post("/api/bank-transactions", response_model=BankTransactionOut, status_code=201)
def create_bank_transaction(
    data: BankDepositWithdrawIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("checks_bank", "create")),
):
    return banking_service.create_bank_transaction(db, data, user)


@router.post("/api/bank-accounts/{bank_account_id}/statement-lines", response_model=list[BankStatementLineOut], status_code=201)
def import_statement_lines(
    bank_account_id: UUID,
    data: BankStatementImportIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("checks_bank", "create")),
):
    return banking_service.import_statement_lines(db, bank_account_id, data.lines)


@router.get("/api/bank-accounts/{bank_account_id}/statement-lines", response_model=list[BankStatementLineOut])
def list_statement_lines(
    bank_account_id: UUID, db: Session = Depends(get_db), _=Depends(require_permission("checks_bank", "view"))
):
    return (
        db.query(BankStatementLine)
        .filter(BankStatementLine.bank_account_id == bank_account_id)
        .order_by(BankStatementLine.line_date.desc())
        .all()
    )


@router.post("/api/bank-accounts/{bank_account_id}/auto-match")
def auto_match_statement(
    bank_account_id: UUID, db: Session = Depends(get_db), _=Depends(require_permission("checks_bank", "update"))
):
    matched_count = banking_service.auto_match_statement(db, bank_account_id)
    return {"matched_count": matched_count}


@router.get("/api/bank-accounts/{bank_account_id}/reconciliation-summary", response_model=ReconciliationSummaryOut)
def reconciliation_summary(
    bank_account_id: UUID, db: Session = Depends(get_db), _=Depends(require_permission("checks_bank", "view"))
):
    return banking_service.get_reconciliation_summary(db, bank_account_id)


@router.post("/api/bank-statement-lines/{line_id}/match", response_model=BankStatementLineOut)
def match_statement_line(
    line_id: UUID,
    data: MatchStatementLineIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("checks_bank", "update")),
):
    return banking_service.match_statement_line(db, line_id, data.bank_transaction_id)


@router.post("/api/bank-statement-lines/{line_id}/unmatch", response_model=BankStatementLineOut)
def unmatch_statement_line(
    line_id: UUID, db: Session = Depends(get_db), _=Depends(require_permission("checks_bank", "update"))
):
    return banking_service.unmatch_statement_line(db, line_id)


@router.get("/api/petty-cash", response_model=Page[PettyCashTransactionOut])
def list_petty_cash(
    db: Session = Depends(get_db),
    params: PageParams = Depends(),
    _=Depends(require_permission("checks_bank", "view")),
):
    # id به‌عنوان شکننده‌ی تساوی: تاریخ به‌تنهایی یکتا نیست و ردیف‌های هم‌تاریخ سر مرز صفحه گم می‌شوند
    items, next_cursor = paginate(
        db.query(PettyCashTransaction),
        [PettyCashTransaction.transaction_date, PettyCashTransaction.id],
        params,
    )
    return Page(items=items, next_cursor=next_cursor)


@router.get("/api/petty-cash/balance")
def petty_cash_balance(db: Session = Depends(get_db), _=Depends(require_permission("checks_bank", "view"))):
    return {"balance": banking_service.get_petty_cash_balance(db)}


@router.post("/api/petty-cash/charge", response_model=PettyCashTransactionOut, status_code=201)
def petty_cash_charge(
    data: PettyCashChargeIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("checks_bank", "create")),
):
    return banking_service.create_petty_cash_charge(db, data, user)


@router.post("/api/petty-cash/expense", response_model=PettyCashTransactionOut, status_code=201)
def petty_cash_expense(
    data: PettyCashExpenseIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("checks_bank", "create")),
):
    return banking_service.create_petty_cash_expense(db, data, user)


# ── دسته چک ──────────────────────────────────────────────────────────────────


@router.get("/api/checkbooks", response_model=list[CheckbookOut])
def list_checkbooks(db: Session = Depends(get_db), _=Depends(require_permission("checks_bank", "view"))):
    return banking_service.list_checkbooks(db)


@router.post("/api/checkbooks", response_model=CheckbookOut, status_code=201)
def create_checkbook(
    data: CheckbookIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("checks_bank", "create")),
):
    book = banking_service.create_checkbook(db, data, user)
    db.commit()
    return _checkbook_row(db, book.id)


@router.patch("/api/checkbooks/{checkbook_id}", response_model=CheckbookOut)
def set_checkbook_active(
    checkbook_id: UUID,
    is_active: bool,
    db: Session = Depends(get_db),
    _=Depends(require_permission("checks_bank", "update")),
):
    banking_service.set_checkbook_active(db, checkbook_id, is_active)
    db.commit()
    return _checkbook_row(db, checkbook_id)


@router.delete("/api/checkbooks/{checkbook_id}", status_code=204)
def delete_checkbook(
    checkbook_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("checks_bank", "delete")),
):
    banking_service.delete_checkbook(db, checkbook_id)
    db.commit()


@router.get("/api/checkbooks/{checkbook_id}/next-number")
def next_check_number(
    checkbook_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("checks_bank", "view")),
):
    """شماره‌ی برگِ بعدی — پیشنهاد برای فرمِ صدورِ چک. رشته‌ی خالی = دسته تمام شده."""
    return {"number": banking_service.next_check_number(db, checkbook_id)}


def _checkbook_row(db: Session, checkbook_id: UUID) -> dict:
    """همان شکلی که فهرست می‌دهد (با نامِ بانک و شمارِ برگ‌ها) برای یک ردیف."""
    for row in banking_service.list_checkbooks(db):
        if row["id"] == checkbook_id:
            return row
    raise HTTPException(status.HTTP_404_NOT_FOUND, "دسته‌چک یافت نشد")


# ── تسویه‌ی کارتخوان ─────────────────────────────────────────────────────────


@router.get("/api/pos-settlements/pending", response_model=list[PosPendingGroupOut])
def pos_pending(
    terminal_no: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    _=Depends(require_permission("checks_bank", "view")),
):
    return banking_service.pos_pending_settlements(
        db, terminal_no=terminal_no, date_from=date_from, date_to=date_to
    )


@router.post("/api/pos-settlements", response_model=PosSettlementOut)
def settle_pos(
    data: PosSettlementIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("checks_bank", "create")),
):
    result = banking_service.settle_pos(db, data, user)
    db.commit()
    return result
