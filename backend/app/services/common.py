from datetime import date as date_

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.counters import DOC_JOURNAL_ENTRY
from app.services.numbering import next_document_number
from app.models.accounting import Account, JournalEntry, JournalLine
from app.models.user import User
from app.services import tafsili


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


def number_lines(lines: list[JournalLine]) -> list[JournalLine]:
    """ردیف‌های سند را از ۱ شماره‌گذاری می‌کند و همان فهرست را برمی‌گرداند.

    **چرا لازم است:** پیش از مهاجرتِ ۰۱۰۰ ترتیبِ ردیف‌ها با `id` بود و `id` یک
    UUIDِ تصادفی است — یعنی ردیف‌ها به ترتیبِ ورود برنمی‌گشتند و بستانکار می‌توانست
    پیش از بدهکار بیاید.

    فهرست برگردانده می‌شود تا بتوان درجا در `JournalEntry(lines=...)` گذاشتش و
    نقطه‌ی صدا زدن از نقطه‌ی ساخت جدا نیفتد — جداییِ همان دو، همان چیزی است که
    باعث می‌شود یکی از هفت مسیر یادش برود.
    """
    for i, line in enumerate(lines, start=1):
        line.seq = i
    return lines


def make_journal_entry(
    db: Session, entry_date: date_, description: str, source_type: str, user: User, lines: list[JournalLine]
) -> JournalEntry:
    entry = JournalEntry(
        number=next_journal_number(db),
        entry_date=entry_date,
        description=description,
        source_type=source_type,
        created_by_id=user.id,
        lines=number_lines(lines),
    )
    # نقطه‌ی مشترکِ سیزده سرویس — گارد این‌جا یعنی یک بار نوشتن به‌جای سیزده بار
    # یادآوری. در حالتِ «ترکیبی» و «شناور» بی‌اثر است و فقط `strict` را اعمال می‌کند.
    tafsili.assert_entry_has_tafsili(db, entry)
    db.add(entry)
    db.flush()
    return entry


def assert_postable_account(
    db: Session,
    account_id,
    *,
    allow_role: str | None = None,
    subject: str = "این تنظیم",
) -> None:
    """حسابی که کاربر برای یک نگاشتِ خودکار انتخاب می‌کند باید واقعاً سند بپذیرد.

    دو چیز را رد می‌کند، و هر دو خطاهایی‌اند که **دیر** و **جای اشتباه** بروز
    می‌کنند اگر همین‌جا گرفته نشوند:

    **حسابِ گروه.** ردیفِ سند نمی‌گیرد. نگاشتنِ انبار یا کالا به آن یعنی اولین
    فاکتور خطا بدهد — آن‌هم جایی که کاربر اصلاً به یادِ تنظیمِ داده‌ی پایه نیست.

    **حسابی که نقشِ سیستمیِ دیگری دارد.** نگاشتنِ موجودیِ یک انبار به حسابِ
    «صندوق» یعنی دو موتور روی یک حساب می‌نویسند با دو معنی، و ماندهٔ صندوق
    بی‌صدا با بهای کالا قاطی می‌شود. هیچ ترازی هم به‌هم نمی‌خورد که خبر بدهد.

    `allow_role` همان نقشی است که *پیش‌فرضِ* این نگاشت است (موجودیِ کالا برای
    انبار، هزینه‌ی خدمت برای کالا) — انتخابِ صریحش همان چیزی است که خالی‌گذاشتن
    هم می‌دهد، پس مجاز است.

    قاعده از خودِ سازوکارِ `system_role`ِ کوبیتا می‌آید، نه از حدسِ سلسله‌مراتبِ
    چارت: کد و نامِ حساب هیچ‌جا hard-code نمی‌شود.
    """
    if account_id is None:
        return
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "حساب یافت نشد")
    if account.is_group:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"«{account.name}» حسابِ گروه است و ردیفِ سند نمی‌پذیرد؛ "
            "یکی از حساب‌های زیرِ آن را انتخاب کنید.",
        )
    if account.system_role and account.system_role != allow_role:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"«{account.name}» حسابِ سیستمیِ «{account.system_role}» است و ماژولِ دیگری "
            f"رویش سند می‌زند؛ نگاشتنِ {subject} به آن دو معنی را روی یک حساب جمع می‌کند.",
        )
