from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models.accounting import Account, JournalLine
from app.models.banking import BankAccount
from app.models.inventory import Contact
from app.models.treasury import TreasuryTransaction
from app.models.user import User
from app.schemas.treasury import TreasuryTransactionIn
from app.services import chart_codes as cc
from app.services.common import get_account, make_journal_entry
from app.services.period_close import assert_period_open


def _resolve_cash_or_bank_account(db: Session, data: TreasuryTransactionIn):
    """حساب مقصد/مبدأ وجه: صندوق برای نقدی، حساب معین بانکِ انتخاب‌شده برای بانکی."""
    if data.method == "cash":
        return get_account(db, cc.CASH)
    bank = db.get(BankAccount, data.bank_account_id)
    if bank is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "حساب بانکی یافت نشد")
    return db.get(Account, bank.gl_account_id)


def create_receipt(db: Session, data: TreasuryTransactionIn, user: User) -> TreasuryTransaction:
    """دریافت وجه از مشتری: بدهکار صندوق/بانک، بستانکار حساب‌های دریافتنی."""
    assert_period_open(db, data.transaction_date)
    contact = db.get(Contact, data.contact_id)
    if contact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "طرف حساب یافت نشد")

    money_account = _resolve_cash_or_bank_account(db, data)
    receivable = get_account(db, cc.ACCOUNTS_RECEIVABLE)

    description = data.description or f"دریافت از {contact.name}"
    entry = make_journal_entry(
        db,
        data.transaction_date,
        description,
        "treasury_receipt",
        user,
        [
            JournalLine(account_id=money_account.id, debit=data.amount, credit=0, description=description),
            JournalLine(account_id=receivable.id, debit=0, credit=data.amount, description=description),
        ],
    )

    txn = TreasuryTransaction(
        type="receipt",
        transaction_date=data.transaction_date,
        contact_id=data.contact_id,
        amount=data.amount,
        method=data.method,
        bank_account_id=data.bank_account_id,
        description=description,
        journal_entry_id=entry.id,
        created_by_id=user.id,
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


def create_payment(db: Session, data: TreasuryTransactionIn, user: User) -> TreasuryTransaction:
    """پرداخت وجه به تأمین‌کننده: بدهکار حساب‌های پرداختنی، بستانکار صندوق/بانک."""
    assert_period_open(db, data.transaction_date)
    contact = db.get(Contact, data.contact_id)
    if contact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "طرف حساب یافت نشد")

    money_account = _resolve_cash_or_bank_account(db, data)
    payable = get_account(db, cc.ACCOUNTS_PAYABLE)

    description = data.description or f"پرداخت به {contact.name}"
    entry = make_journal_entry(
        db,
        data.transaction_date,
        description,
        "treasury_payment",
        user,
        [
            JournalLine(account_id=payable.id, debit=data.amount, credit=0, description=description),
            JournalLine(account_id=money_account.id, debit=0, credit=data.amount, description=description),
        ],
    )

    txn = TreasuryTransaction(
        type="payment",
        transaction_date=data.transaction_date,
        contact_id=data.contact_id,
        amount=data.amount,
        method=data.method,
        bank_account_id=data.bank_account_id,
        description=description,
        journal_entry_id=entry.id,
        created_by_id=user.id,
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


def transactions_query(db: Session):
    """کوئری پایه؛ مرتب‌سازی و صفحه‌بندی در لایه‌ی روتر اعمال می‌شود."""
    return db.query(TreasuryTransaction).options(joinedload(TreasuryTransaction.contact))
