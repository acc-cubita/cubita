"""تراکنشِ مالک و شریک — یک سرویس، شش نوعِ صریح.

**هسته‌ی این ماژول جدولِ `_POSTING` است.** هر نوع، دو چیز را تعیین می‌کند: پول
وارد می‌شود یا خارج، و طرفِ دیگرِ سند کدام نقشِ حساب است. هیچ‌کدام از این دو از
دیگری مشتق نمی‌شود — همان چیزی که قاعده‌ی ۵۲ صریحاً می‌خواهد:

> «Direction یا PartyRole به‌تنهایی نوعِ حسابداری را تعیین نکند.»

ورودِ پول سه معنای کاملاً متفاوت دارد — آورده‌ی سرمایه، وامِ شریک، بازپرداختِ
بدهیِ شریک — و از روی جهت نمی‌شود فهمید کدام. برای همین `type` ستونِ خودش است.

**گاردِ قاعده‌ی پایدارِ ۲** («آورده ≠ درآمد، برداشت ≠ هزینه») این‌جا ساختاری است،
نه یک بررسی: سند را خودِ سرویس از `_POSTING` می‌سازد و کاربر هیچ‌جا حسابِ مقصد را
انتخاب نمی‌کند. با سندِ دستی — تنها راهِ دیروز — هیچ چیزی جلوی نشاندنِ آورده در
حسابِ درآمد را نمی‌گرفت.
"""
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.accounting import JournalLine
from app.models.inventory import Contact
from app.models.owner_transactions import OwnerTransaction
from app.models.user import User
from app.schemas.owner_transactions import OwnerTransactionIn
from app.services import chart_codes as cc
from app.services.common import get_or_create_account, make_journal_entry
from app.services.period_close import assert_period_open
#: عمداً از خودِ خزانه وارد می‌شود و بازنویسی نمی‌شود: انتخابِ معین و **تفصیلیِ**
#: صندوق/حسابِ بانکی دو مهاجرت طول کشید تا درست شود (۰۱۰۵ و ۰۱۰۶). نسخه‌ی دوم
#: یعنی همان باگ دوباره، این بار بی‌صدا.
from app.services.treasury import _resolve_money_side

#: (پول وارد می‌شود؟، نقشِ طرفِ دیگرِ سند)
#:
#: دو جفتِ آخر از نظرِ **ثبت** با دو جفتِ میانی یکسان‌اند و از نظرِ **معنا** نه:
#: «وامِ تازه‌ی شریک» و «بازپرداختِ بدهیِ شرکت» هر دو جاری شرکا را تکان می‌دهند،
#: ولی در گزارشِ گردشِ شریک دو رویدادِ متفاوت‌اند. یکی‌کردنشان همان اطلاعاتی را
#: می‌سوزاند که این ماژول برای ساختنش آمده.
_POSTING: dict[str, tuple[bool, str]] = {
    "capital_contribution":   (True,  cc.OWNER_CAPITAL),
    "capital_withdrawal":     (False, cc.OWNER_CAPITAL),
    "loan_to_entity":         (True,  cc.PARTNER_CURRENT),
    "loan_from_entity":       (False, cc.PARTNER_CURRENT),
    "repayment_to_partner":   (False, cc.PARTNER_CURRENT),
    "repayment_from_partner": (True,  cc.PARTNER_CURRENT),
}

TYPE_LABELS: dict[str, str] = {
    "capital_contribution": "آورده‌ی سرمایه",
    "capital_withdrawal": "کاهشِ سرمایه",
    "loan_to_entity": "وامِ شریک به شرکت",
    "loan_from_entity": "برداشتِ قابلِ بازپرداخت",
    "repayment_to_partner": "بازپرداخت به شریک",
    "repayment_from_partner": "بازپرداختِ شریک",
}

#: نقش‌هایی که ممکن است در چارتِ کسب‌وکارهای قدیمی نباشند. `get_or_create_account`
#: همان لحظه می‌سازدشان، پس سرویس به اجرای backfillِ مهاجرت وابسته نیست.
_ACCOUNT_SPEC = {
    cc.OWNER_CAPITAL: dict(code="3101", name="سرمایه", acc_type="equity", parent_code="3"),
    cc.PARTNER_CURRENT: dict(code="2115", name="جاری شرکا", acc_type="liability", parent_code="21"),
}


def _counter_account(db: Session, role: str):
    return get_or_create_account(db, role, **_ACCOUNT_SPEC[role])


def assert_is_shareholder(db: Session, contact_id: UUID) -> Contact:
    """طرفِ این سند باید **سهامدار** علامت خورده باشد.

    `Contact.is_shareholder` از قبل روی مدل بود و هیچ‌کس استفاده‌اش نمی‌کرد. بی این
    گارد، «آورده‌ی سرمایه» را می‌شد به نامِ یک مشتریِ معمولی ثبت کرد و بعد هیچ
    گزارشی نمی‌توانست بگوید مالکانِ شرکت چه کسانی‌اند.
    """
    contact = db.get(Contact, contact_id)
    if contact is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "طرف حساب یافت نشد")
    if not contact.is_shareholder:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"«{contact.name}» سهامدار علامت نخورده است. در پرونده‌ی طرف حساب گزینه‌ی "
            "«سهامدار» را فعال کنید، سپس این سند را ثبت کنید.",
        )
    return contact


def create_owner_transaction(db: Session, data: OwnerTransactionIn, user: User) -> OwnerTransaction:
    assert_period_open(db, data.transaction_date)
    contact = assert_is_shareholder(db, data.contact_id)

    money_in, role = _POSTING[data.type]
    money_account, money_analytic, box = _resolve_money_side(db, data)
    counter = _counter_account(db, role)
    amount = Decimal(data.amount)

    #: تفصیلیِ شریک روی ردیفِ جاری شرکا/سرمایه می‌نشیند تا ماندهٔ **هر شریک** جدا
    #: بماند. بی آن، جاری شرکا یک عددِ سرجمع می‌شد و «شریک الف چقدر طلبکار است؟»
    #: جوابی نداشت — همان اشتباهی که صندوق‌ها پیش از مهاجرتِ ۰۱۰۵ داشتند.
    money_line = JournalLine(
        account_id=money_account.id,
        analytic_id=money_analytic,
        debit=amount if money_in else 0,
        credit=0 if money_in else amount,
    )
    counter_line = JournalLine(
        account_id=counter.id,
        analytic_id=contact.analytic_id,
        debit=0 if money_in else amount,
        credit=amount if money_in else 0,
    )
    lines = [money_line, counter_line] if money_in else [counter_line, money_line]

    entry = make_journal_entry(
        db,
        data.transaction_date,
        (data.description or f"{TYPE_LABELS[data.type]} — {contact.name}").strip(),
        "owner_transaction",
        user,
        lines,
    )

    txn = OwnerTransaction(
        type=data.type,
        transaction_date=data.transaction_date,
        contact_id=data.contact_id,
        amount=amount,
        method=data.method,
        bank_account_id=data.bank_account_id,
        cashbox_id=box.id if box else None,
        description=data.description or "",
        evidence_ref=data.evidence_ref or "",
        journal_entry_id=entry.id,
        created_by_id=user.id,
    )
    db.add(txn)
    db.flush()
    db.refresh(txn)
    return txn


def partner_balance(db: Session, contact_id: UUID) -> Decimal:
    """ماندهٔ «جاری شرکا»ی یک شریک — **مشتق از اسناد، نه ذخیره‌شده**.

    مثبت = شرکت به او بدهکار است (وام داده و پس نگرفته). منفی = او به شرکت
    بدهکار است (برداشتِ قابلِ بازپرداخت). همان قاعده‌ای که `Cashbox` دارد:
    «هرگز دو نمای یک داده نساز».
    """
    total = Decimal(0)
    rows = (
        db.query(OwnerTransaction)
        .filter(OwnerTransaction.contact_id == contact_id, OwnerTransaction.voided_at.is_(None))
        .all()
    )
    for row in rows:
        money_in, role = _POSTING[row.type]
        if role != cc.PARTNER_CURRENT:
            continue
        #: پول که وارد شد، جاری شرکا بستانکار شد ⇒ طلبِ شریک بیشتر.
        total += Decimal(row.amount) if money_in else -Decimal(row.amount)
    return total
