from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

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
    CheckIn,
    CheckOut,
    CheckStatusUpdateIn,
    MatchStatementLineIn,
    PettyCashChargeIn,
    PettyCashExpenseIn,
    PettyCashTransactionOut,
    ReconciliationSummaryOut,
)
from app.services import banking as banking_service
from app.services import chart_codes as cc
from app.services.common import get_account
from uuid import UUID

router = APIRouter(tags=["banking"])


@router.get("/api/bank-accounts", response_model=list[BankAccountOut])
def list_bank_accounts(db: Session = Depends(get_db), _=Depends(require_permission("checks_bank", "view"))):
    return db.query(BankAccount).order_by(BankAccount.name).all()


@router.post("/api/bank-accounts", response_model=BankAccountOut, status_code=201)
def create_bank_account(
    data: BankAccountIn, db: Session = Depends(get_db), _=Depends(require_permission("checks_bank", "create"))
):
    gl_account_id = data.gl_account_id or get_account(db, cc.BANK).id
    account = BankAccount(
        name=data.name,
        bank_name=data.bank_name,
        account_number=data.account_number,
        iban=data.iban,
        gl_account_id=gl_account_id,
    )
    db.add(account)
    db.flush()
    db.refresh(account)
    return account


@router.patch("/api/bank-accounts/{bank_account_id}", response_model=BankAccountOut)
def update_bank_account(
    bank_account_id: UUID,
    data: BankAccountUpdateIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("checks_bank", "update")),
):
    """ویرایشِ نام/بانک/شماره/شبا یا فعال‌بودنِ حساب بانکی. حسابِ دفترِ کل ثابت می‌ماند."""
    account = db.get(BankAccount, bank_account_id)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "حساب بانکی یافت نشد")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(account, key, value)
    db.flush()
    db.refresh(account)
    return account


@router.get("/api/checks", response_model=Page[CheckOut])
def list_checks(
    db: Session = Depends(get_db),
    params: PageParams = Depends(),
    _=Depends(require_permission("checks_bank", "view")),
):
    # id به‌عنوان شکننده‌ی تساوی: تاریخ به‌تنهایی یکتا نیست و ردیف‌های هم‌تاریخ سر مرز صفحه گم می‌شوند
    items, next_cursor = paginate(
        db.query(Check),
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
    _=Depends(require_permission("checks_bank", "view")),
):
    # id به‌عنوان شکننده‌ی تساوی: تاریخ به‌تنهایی یکتا نیست و ردیف‌های هم‌تاریخ سر مرز صفحه گم می‌شوند
    items, next_cursor = paginate(
        db.query(BankTransaction),
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
