from datetime import date as date_

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.counters import DOC_JOURNAL_ENTRY
from app.services.numbering import next_document_number
from app.models.accounting import Account, JournalEntry, JournalLine
from app.models.user import User


def get_account(db: Session, code: str) -> Account:
    account = db.query(Account).filter(Account.code == code).first()
    if account is None:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"حساب با کد {code} در چارت حساب یافت نشد؛ ابتدا seed اولیه را اجرا کنید",
        )
    return account


def next_journal_number(db: Session) -> int:
    return next_document_number(db, DOC_JOURNAL_ENTRY)


def make_journal_entry(
    db: Session, entry_date: date_, description: str, source_type: str, user: User, lines: list[JournalLine]
) -> JournalEntry:
    entry = JournalEntry(
        number=next_journal_number(db),
        entry_date=entry_date,
        description=description,
        source_type=source_type,
        created_by_id=user.id,
        lines=lines,
    )
    db.add(entry)
    db.flush()
    return entry
