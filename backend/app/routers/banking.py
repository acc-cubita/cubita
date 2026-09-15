from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.deps import Principal, get_principal, require_permission
from app.models.banking import (
    BankAccount,
    BankStatementLine,
    BankTransaction,
    PettyCashFund,
    PettyCashTransaction,
)
from app.models.tenant import Tenant
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
    CheckbookLeafOut,
    CheckbookOut,
    CheckbookUpdateIn,
    MatchStatementLineIn,
    PettyCashChargeIn,
    PettyCashExpenseIn,
    PettyCashFundIn,
    PettyCashFundOut,
    PettyCashFundPatch,
    PettyCashReturnIn,
    PettyCashTransactionOut,
    ReconciliationSummaryOut,
)
from app.services import bank_accounts as bank_accounts_service
from app.services import banking as banking_service
from app.services import checkbooks as checkbook_service
from app.services import chart_codes as cc
from app.services.common import get_account
from pydantic import BaseModel
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


@router.post("/api/petty-cash/return", response_model=PettyCashTransactionOut, status_code=201)
def petty_cash_return(
    data: PettyCashReturnIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("checks_bank", "create")),
):
    """استردادِ ماندهٔ تنخواه — مسیری که تا امروز وجود نداشت.

    **بازگشتِ وجه است، نه هزینه.** تنها راهِ قبلی ثبتِ یک «هزینه»ی جعلی بود که
    هم سود و زیان را غلط می‌کرد و هم گزارشِ تنخواه را.
    """
    return banking_service.create_petty_cash_return(db, data, user)


# ── صندوق‌های تنخواه ─────────────────────────────────────────────────────────


@router.get("/api/petty-cash-funds", response_model=list[PettyCashFundOut])
def list_petty_cash_funds(
    db: Session = Depends(get_db),
    _=Depends(require_permission("checks_bank", "view")),
):
    return db.query(PettyCashFund).order_by(PettyCashFund.name).all()


@router.post("/api/petty-cash-funds", response_model=PettyCashFundOut, status_code=201)
def create_petty_cash_fund(
    data: PettyCashFundIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("checks_bank", "create")),
):
    fund = PettyCashFund(**data.model_dump())
    db.add(fund)
    db.flush()
    db.refresh(fund)
    return fund


@router.patch("/api/petty-cash-funds/{fund_id}", response_model=PettyCashFundOut)
def update_petty_cash_fund(
    fund_id: UUID,
    data: PettyCashFundPatch,
    db: Session = Depends(get_db),
    _=Depends(require_permission("checks_bank", "update")),
):
    """ویرایشِ صندوق — **و تعویضِ تنخواه‌دار هویتِ صندوق را عوض نمی‌کند.**

    همان صندوق می‌ماند و تاریخچه‌ی تراکنش‌هایش دست‌نخورده. تا پیش از این، صندوقی
    به‌عنوان موجودیت وجود نداشت و تنخواه‌دار اصلاً جایی ثبت نمی‌شد.
    """
    fund = db.get(PettyCashFund, fund_id)
    if fund is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "صندوق تنخواه یافت نشد")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(fund, field, value)
    db.flush()
    db.refresh(fund)
    return fund


@router.get("/api/petty-cash-funds/{fund_id}/balance")
def petty_cash_fund_balance(
    fund_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("checks_bank", "view")),
):
    """ماندهٔ یک صندوق — **مشتق از رویدادها، نه ستونی ذخیره‌شده** (قاعده ۶۷)."""
    if db.get(PettyCashFund, fund_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "صندوق تنخواه یافت نشد")
    return {"balance": banking_service.get_petty_cash_balance(db, fund_id)}


# ── دسته چک ──────────────────────────────────────────────────────────────────


@router.get("/api/checkbooks", response_model=list[CheckbookOut])
def list_checkbooks(db: Session = Depends(get_db), _=Depends(require_permission("checks_bank", "view"))):
    return checkbook_service.list_checkbooks(db)


@router.post("/api/checkbooks", response_model=CheckbookOut, status_code=201)
def create_checkbook(
    data: CheckbookIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("checks_bank", "create")),
):
    book = checkbook_service.create_checkbook(db, data, user)
    db.commit()
    return _checkbook_row(db, book.id)


@router.patch("/api/checkbooks/{checkbook_id}", response_model=CheckbookOut)
def update_checkbook(
    checkbook_id: UUID,
    data: CheckbookUpdateIn,
    db: Session = Depends(get_db),
    _=Depends(require_permission("checks_bank", "update")),
):
    """ویرایشِ دسته. فیلدی که نفرستید دست نمی‌خورد؛ ساختاری فقط تا وقتی برگی خرج نشده."""
    checkbook_service.update_checkbook(db, checkbook_id, data)
    db.commit()
    return _checkbook_row(db, checkbook_id)


@router.delete("/api/checkbooks/{checkbook_id}", status_code=204)
def delete_checkbook(
    checkbook_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("checks_bank", "delete")),
):
    checkbook_service.delete_checkbook(db, checkbook_id)
    db.commit()


@router.get("/api/checkbooks/{checkbook_id}/next-number")
def next_check_number(
    checkbook_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("checks_bank", "view")),
):
    """شماره‌ی برگِ بعدی — پیشنهاد برای فرمِ صدورِ چک. رشته‌ی خالی = دسته تمام شده."""
    return {"number": checkbook_service.next_number(db, checkbook_id)}


@router.get("/api/checkbooks/{checkbook_id}/leaves", response_model=list[CheckbookLeafOut])
def checkbook_leaves(
    checkbook_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("checks_bank", "view")),
):
    """هر برگِ خرج‌شده‌ی این دسته کجا رفت — دسته ← برگ ← چک."""
    book = checkbook_service.resolve(db, checkbook_id)
    return checkbook_service.used_leaves(db, book)


def _checkbook_row(db: Session, checkbook_id: UUID) -> dict:
    """همان شکلی که فهرست می‌دهد (با نامِ بانک و شمارِ برگ‌ها) برای یک ردیف."""
    for row in checkbook_service.list_checkbooks(db):
        if row["id"] == checkbook_id:
            return row
    raise HTTPException(status.HTTP_404_NOT_FOUND, "دسته‌چک یافت نشد")


# ── سیاستِ کنترلِ شماره‌ی چک ───────────────────────────────────────────────────
#
# قرینه‌ی `/api/accounts/tafsili-mode`: یک انتخابِ سطحِ کسب‌وکار که رابط گزینه‌ها و
# پیامدشان را از سرور می‌گیرد، تا متنِ تصمیم دو جا نوشته نشود.


class ChequeControlOut(BaseModel):
    mode: str
    options: list[dict]
    #: True یعنی کاربر خودش انتخاب کرده؛ False یعنی هنوز روی پیش‌فرضِ سرویس است.
    is_explicit: bool


class ChequeControlIn(BaseModel):
    mode: str


def _cheque_control_out(tenant: Tenant) -> ChequeControlOut:
    return ChequeControlOut(
        mode=tenant.cheque_number_control or checkbook_service.DEFAULT_CONTROL_MODE,
        is_explicit=tenant.cheque_number_control is not None,
        options=[
            {
                "key": key,
                "label": checkbook_service.CONTROL_MODE_LABELS[key],
                "hint": checkbook_service.CONTROL_MODE_HINTS[key],
                "effects": checkbook_service.CONTROL_MODE_EFFECTS[key],
                "is_default": key == checkbook_service.DEFAULT_CONTROL_MODE,
            }
            for key in checkbook_service.CONTROL_MODES
        ],
    )


def _tenant(db: Session, principal: Principal) -> Tenant:
    tenant = db.get(Tenant, principal.tenant_id)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "کسب‌وکار یافت نشد")
    return tenant


@router.get("/api/cheque-number-control", response_model=ChequeControlOut)
def get_cheque_number_control(
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
    _=Depends(require_permission("checks_bank", "view")),
):
    """آیا چکِ پرداختنی باید از دسته‌چک صادر شود؟"""
    return _cheque_control_out(_tenant(db, principal))


@router.patch("/api/cheque-number-control", response_model=ChequeControlOut)
def set_cheque_number_control(
    data: ChequeControlIn,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
    #: تاپل: مالک (`approve` از «*») و حسابدار (`update`). ماژولِ چک اکشنِ
    #: `approve` در فهرستِ مجوزها ندارد، پس تنهاگذاشتنش یعنی حسابدار — همان کسی
    #: که این تصمیم را می‌گیرد — بیرون می‌ماند.
    _=Depends(require_permission("checks_bank", ("approve", "update"))),
):
    """تغییرِ سیاست.

    تصمیمی در سطحِ کلِ کسب‌وکار است که روی هر صدورِ بعدی اثر می‌گذارد، نه ویرایشِ
    یک رکورد — پس مالک و حسابدار می‌توانند، نه هر کسی که چک ثبت می‌کند.

    **روی چک‌های گذشته اثری ندارد** و عمداً هم ندارد: سختگیرتر کردنِ قاعده نباید
    چکی را که دیروز درست ثبت شده امروز نامعتبر کند.
    """
    tenant = _tenant(db, principal)
    try:
        checkbook_service.set_control_mode(tenant, data.mode)
    except ValueError as err:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(err)) from None
    db.commit()
    return _cheque_control_out(tenant)
