"""حسابِ بانکی — مانده‌اش مشتق است، مثلِ صندوق.

**چرا سرویسِ جدا از `banking.py`:** آن فایل هفتصد خط است و چک و کارت‌خوان و
صورت‌حساب و مغایرت را دارد. حسابِ بانکی *پایه‌ی* همه‌ی آن‌هاست، نه یکی از آن‌ها؛
و قرینه‌ی مستقیمِ `cashboxes.py` است. کنارِ هم بودنِ این دو فایل یعنی هر کس یکی را
عوض کرد، دیگری را هم می‌بیند.

**هیچ ستونِ `balance`ای وجود ندارد و نباید ساخته شود.** مانده = گردشِ جفتِ
`(معینِ حساب، تفصیلیِ حساب)` در دفتر. دلیلش همان دلیلِ صندوق است: هر مسیری که به
پولِ بانک دست می‌زند — رسید، پرداخت، وصولِ چک، واریز/برداشتِ دستی، کارمزد، سندِ
دستی، اصلاحِ طبقه‌بندی، و هر چیزی که فردا اضافه شود — خودبه‌خود شمرده می‌شود، و
مانده **نمی‌تواند** با تراز واگرا شود.

**«قابل استفاده» هم مشتق است، ولی مبلغِ بلوکه ذخیره می‌شود.** این تناقض نیست:
بلوکه یک *مانده* نیست که از تراکنش بیاید، یک واقعیتِ بیرونی است که بانک اعلام
می‌کند — از جنسِ `opening_date`. ذخیره‌اش درست است؛ آنچه هرگز ذخیره نمی‌شود
حاصلِ تفریق است (§۱۸).
"""
from __future__ import annotations

from datetime import date as date_
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.accounting import JournalEntry, JournalLine
from app.models.banking import BankAccount, BankStatementLine, BankTransaction, Check, Checkbook
from app.models.pos_terminal import PosTerminal
from app.models.treasury import TreasuryTransaction


def resolve(db: Session, bank_account_id: UUID | None) -> BankAccount:
    """حسابِ بانکی یا خطای روشن. برخلافِ صندوق پیش‌فرضی ساخته نمی‌شود.

    صندوق می‌تواند خودش را lazy بسازد چون «نقد» همیشه معنا دارد؛ حسابِ بانکی اما
    شماره و بانک و شبا می‌خواهد و ساختنِ خودکارش یعنی رکوردی که هیچ‌کدام را ندارد.
    """
    if bank_account_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "حساب بانکی انتخاب نشده است")
    acct = db.get(BankAccount, bank_account_id)
    if acct is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "حساب بانکی یافت نشد")
    return acct


def assert_usable(db: Session, acct: BankAccount, on: date_) -> None:
    """گاردهای §۲۲ و §۱۵ — پیش از هر عملیاتی که پول را جابه‌جا می‌کند.

    تا امروز مسیرِ پولِ بانکی **هیچ‌کدام** را نمی‌سنجید: حسابِ غیرفعال هم رسید
    می‌گرفت. سابقه دست نمی‌خورد، فقط عملیاتِ *تازه* بسته می‌شود.
    """
    if not acct.is_active:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"حساب «{acct.name}» غیرفعال است و برای عملیات تازه انتخاب نمی‌شود",
        )
    if acct.opening_date is not None and on < acct.opening_date:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"حساب «{acct.name}» از {acct.opening_date} افتتاح شده؛ "
            f"عملیات با تاریخ {on} پیش از آن است",
        )


def balance(db: Session, acct: BankAccount, *, as_of: date_ | None = None) -> Decimal:
    """مانده‌ی حساب از **دفتر**، نه از `BankTransaction`.

    این انتخاب عمدی است و مهم: `BankTransaction` دفترِ کاملِ حساب نیست — رسید و
    پرداختِ بانکی هیچ ردیفی در آن نمی‌سازند. جمع زدنش یعنی عددی که همیشه کم است.

    `is_not_distinct_from` همان ترفندِ صندوق است: فیلتر روی جفتِ (معین، تفصیلی)
    است و برای حسابِ تفکیک‌نشده تفصیلی `NULL` است. `= NULL` هرگز درست نیست، پس
    بدونِ برابریِ NULL-امن آن حساب همیشه صفر می‌خواند.

    سندِ باطل کنار گذاشته نمی‌شود چون ابطال خودش سندِ معکوس می‌زند؛ خالص از قبل درست است.
    """
    query = (
        db.query(
            func.coalesce(func.sum(JournalLine.debit), 0),
            func.coalesce(func.sum(JournalLine.credit), 0),
        )
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .filter(
            JournalLine.account_id == acct.gl_account_id,
            JournalLine.analytic_id.is_not_distinct_from(acct.analytic_id),
        )
    )
    if as_of is not None:
        query = query.filter(JournalEntry.entry_date <= as_of)
    debit, credit = query.one()
    return Decimal(debit) - Decimal(credit)


def opening_balance(db: Session, acct: BankAccount) -> Decimal:
    """موجودیِ اولیه = مانده در **ابتدای سالِ مالیِ جاری** (§۱۲).

    نه یک ستونِ ذخیره‌شده و نه عددی ابدی: با عوض شدنِ سالِ مالی خودش عوض می‌شود،
    و چون از همان `balance` می‌آید هرگز نمی‌تواند با مانده‌ی جاری ناسازگار شود —
    همان قیدِ §۱۴ که می‌گوید نباید دو منبعِ حقیقت داشته باشیم.

    `- ۱ روز` آستانه‌ی شروع است: بدونش سندهای *روزِ اولِ* سال جزوِ افتتاحیه می‌شدند.
    """
    from datetime import timedelta

    from app.models.fiscal_year import FiscalYear

    year = db.query(FiscalYear).filter(FiscalYear.is_active.is_(True)).first()
    if year is None:
        return Decimal(0)
    return balance(db, acct, as_of=year.start_date - timedelta(days=1))


def available_balance(db: Session, acct: BankAccount) -> Decimal:
    """مانده منهای بلوکه (§۱۸ §۱۹).

    **مشتق است و ذخیره نمی‌شود.** اگر ذخیره می‌شد، سومین عددی می‌شد که باید با دو
    تای دیگر بخواند. منفی شدنش مسدود نمی‌شود: بانک می‌تواند بیش از موجودی بلوکه
    کند و آن یک واقعیت است، نه خطای ورودِ داده.
    """
    return balance(db, acct) - Decimal(acct.blocked_amount or 0)


def _in_use(db: Session, acct: BankAccount) -> bool:
    """آیا این حساب جایی سابقه دارد؟

    هفت مرجع سنجیده می‌شود، چون حسابِ بانکی مرکزِ اتصالِ خزانه و چک و کارت‌خوان و
    مغایرت است (§۲۹). فراموش کردنِ هرکدام یعنی حذفی که آن زیرسیستم را می‌شکند.
    """
    referrers = (
        (TreasuryTransaction, TreasuryTransaction.bank_account_id),
        (BankTransaction, BankTransaction.bank_account_id),
        (BankStatementLine, BankStatementLine.bank_account_id),
        (Checkbook, Checkbook.bank_account_id),
        (Check, Check.bank_account_id),
        (PosTerminal, PosTerminal.bank_account_id),
    )
    for model, column in referrers:
        if db.query(model.id).filter(column == acct.id).first() is not None:
            return True
    #: ردیفِ دفتر هم سابقه است — سندِ دستی روی تفصیلیِ همین حساب هیچ‌کدام از
    #: جدول‌های بالا را لمس نمی‌کند ولی مانده‌اش را ساخته.
    if acct.analytic_id is not None:
        return (
            db.query(JournalLine.id)
            .filter(
                JournalLine.account_id == acct.gl_account_id,
                JournalLine.analytic_id == acct.analytic_id,
            )
            .first()
            is not None
        )
    return False


def _assert_analytic_free(db: Session, analytic_id: UUID | None, exclude_id: UUID | None = None) -> None:
    """یک تفصیلی، حداکثر یک حسابِ بانکی — وگرنه دو حساب یک مانده می‌خوانند."""
    if analytic_id is None:
        return
    query = db.query(BankAccount).filter(BankAccount.analytic_id == analytic_id)
    if exclude_id is not None:
        query = query.filter(BankAccount.id != exclude_id)
    other = query.first()
    if other is not None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"این تفصیلی از قبل به حساب «{other.name}» تعلق دارد"
        )
    #: صندوق‌ها هم روی همین جدولِ تفصیلی می‌نشینند. تفصیلیِ مشترکِ یک صندوق و یک
    #: حسابِ بانکی یعنی دو موجودیت که مانده‌شان از یک جا می‌آید — و اگر معینشان
    #: هم یکی شود، عملاً یک پول دو بار شمرده می‌شود.
    from app.models.cashbox import Cashbox

    box = db.query(Cashbox).filter(Cashbox.analytic_id == analytic_id).first()
    if box is not None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"این تفصیلی از قبل به صندوق «{box.name}» تعلق دارد"
        )


def _assert_analytic_change_allowed(db: Session, acct: BankAccount, new_analytic_id: UUID | None) -> None:
    """§۳۱ — تفصیلیِ حسابِ استفاده‌شده عوض نمی‌شود.

    مانده مشتقِ جفتِ (معین، تفصیلی) است. عوض کردنِ تفصیلی هیچ سندی را بازنویسی
    نمی‌کند — ولی مانده را **بی‌صدا** به مجموعه‌ی دیگری از ردیف‌ها می‌برد: پولِ
    قبلی از فهرست ناپدید می‌شود و صفر جایش می‌نشیند. در طراحیِ مشتق، این همان
    زیانی است که §۳۱ منعش می‌کند.

    راهِ درست «اصلاح طبقه‌بندی مانده» است که مانده را با یک سندِ متوازنِ تاریخ‌دار
    منتقل می‌کند و گذشته را دست نمی‌زند — پس پیام به همان ارجاع می‌دهد.
    """
    if new_analytic_id == acct.analytic_id or not _in_use(db, acct):
        return
    raise HTTPException(
        status.HTTP_409_CONFLICT,
        f"حساب «{acct.name}» سابقه دارد و تفصیلی‌اش عوض نمی‌شود؛ مانده‌اش با "
        "«اصلاح طبقه‌بندی مانده» منتقل می‌شود تا اسنادِ گذشته دست‌نخورده بمانند",
    )


def row(db: Session, acct: BankAccount) -> dict:
    """یک حساب به شکلِ خروجی — تنها جایی که این شکل ساخته می‌شود."""
    return {
        "id": acct.id,
        "name": acct.name,
        "name2": acct.name2,
        "bank_name": acct.bank_name,
        "branch_name": acct.branch_name,
        "account_number": acct.account_number,
        "account_type": acct.account_type,
        "card_number": acct.card_number,
        "iban": acct.iban,
        "analytic_id": acct.analytic_id,
        "analytic_code": acct.analytic.code if acct.analytic else None,
        "analytic_name": acct.analytic.name if acct.analytic else None,
        "gl_account_id": acct.gl_account_id,
        "currency_code": acct.currency_code,
        "opening_date": acct.opening_date,
        "holder_name": acct.holder_name,
        "holder_name2": acct.holder_name2,
        "blocked_amount": Decimal(acct.blocked_amount or 0),
        "cheque_print_format": acct.cheque_print_format,
        "is_active": acct.is_active,
        "opening_balance": opening_balance(db, acct),
        "balance": balance(db, acct),
        "available_balance": available_balance(db, acct),
    }


def list_bank_accounts(db: Session) -> list[dict]:
    """همه‌ی حساب‌ها با مانده — **بدونِ جمعِ کل**.

    جمعِ «همه‌ی حساب‌های بانکی» بینِ ارزهای مختلف بی‌معناست: دلار و ریال بدونِ نرخ
    و تاریخ جمع نمی‌شوند. رابط به تفکیکِ ارز جمع می‌زند (§۲۱).
    """
    accounts = db.query(BankAccount).order_by(BankAccount.name).all()
    return [row(db, acct) for acct in accounts]


def create_bank_account(db: Session, data: dict) -> BankAccount:
    _assert_analytic_free(db, data.get("analytic_id"))
    #: قرینه‌ی همان استثنا: فقط *یک* حساب می‌تواند تفکیک‌نشده بماند، وگرنه دو حساب
    #: عیناً یک مانده می‌خوانند و جمعشان پول را دو بار می‌شمارد.
    if data.get("analytic_id") is None and db.query(BankAccount).first() is not None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "برای حسابِ بانکیِ دوم باید تفصیلی انتخاب شود، وگرنه مانده‌اش از حسابِ اول جدا نمی‌شود",
        )
    acct = BankAccount(**data)
    db.add(acct)
    db.flush()
    db.refresh(acct)
    return acct


def update_bank_account(db: Session, bank_account_id: UUID, data: dict) -> BankAccount:
    acct = resolve(db, bank_account_id)
    if "analytic_id" in data:
        _assert_analytic_free(db, data["analytic_id"], exclude_id=acct.id)
        _assert_analytic_change_allowed(db, acct, data["analytic_id"])
    for key, value in data.items():
        setattr(acct, key, value)
    db.flush()
    db.refresh(acct)
    return acct


def delete_bank_account(db: Session, bank_account_id: UUID) -> None:
    """§۲۳ — حسابِ بی‌سابقه حذف می‌شود، حسابِ باسابقه غیرفعال.

    حذفِ حسابی که چک و کارت‌خوان و صورت‌حساب به آن اشاره می‌کنند یعنی شکستنِ
    همه‌ی آن‌ها. همان الگوی `delete_checkbook` و `delete_cashbox`.
    """
    acct = resolve(db, bank_account_id)
    if _in_use(db, acct):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"حساب «{acct.name}» در عملیات استفاده شده و حذف نمی‌شود؛ به‌جایش غیرفعالش کنید",
        )
    db.delete(acct)
    db.flush()
