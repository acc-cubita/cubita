from datetime import date as date_

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.counters import DOC_JOURNAL_ENTRY
from app.services.numbering import next_document_number
from app.models.accounting import Account, JournalEntry, JournalLine
from app.models.user import User


def get_account(db: Session, system_role: str) -> Account:
    """حساب را با نقش معنایی‌اش پیدا می‌کند، نه با کدش.

    کد حساب متعلق به مشتری است و بازشماره‌گذاری‌اش کار رایج حسابداران است؛ نقش
    متعلق به سیستم است و ثابت می‌ماند. جست‌وجو با کد باعث می‌شد اولین مشتری‌ای که
    چارتش را مرتب می‌کند، همه‌ی ثبت‌های خودکارش بشکند.
    """
    account = db.query(Account).filter(Account.system_role == system_role).first()
    if account is None:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"هیچ حسابی با نقش «{system_role}» علامت‌گذاری نشده؛ چارت حساب این کسب‌وکار ناقص است",
        )
    return account


def get_or_create_account(
    db: Session,
    system_role: str,
    *,
    code: str,
    name: str,
    acc_type: str,
    parent_code: str,
) -> Account:
    """حسابِ نقش‌دار را برمی‌گرداند و اگر نبود همان‌جا می‌سازد.

    برخلاف get_account که چارتِ ناقص را خطا می‌داند، این برای نقش‌هایی است که بعداً
    به سیستم اضافه شده‌اند (مثل حساب‌های مالیات بر ارزش افزوده) و باید برای
    کسب‌وکارهای قدیمی هم خودکار فراهم شوند. زیر همان زمینه‌ی مستأجرِ درخواست ساخته
    می‌شود، پس RLS و مهرِ tenant_id رعایت می‌شود.
    """
    account = db.query(Account).filter(Account.system_role == system_role).first()
    if account is not None:
        return account

    parent = (
        db.query(Account).filter(Account.is_group.is_(True), Account.code == parent_code).first()
        or db.query(Account)
        .filter(Account.type == acc_type, Account.is_group.is_(True), Account.parent_id.is_(None))
        .first()
    )
    # اگر مشتری اتفاقاً همین کد را دستی گرفته باشد، برخورد نکن
    if db.query(Account).filter(Account.code == code).first() is not None:
        code = f"{code}V"
    account = Account(
        code=code,
        name=name,
        type=acc_type,
        is_group=False,
        system_role=system_role,
        parent_id=parent.id if parent else None,
    )
    db.add(account)
    db.flush()
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
