from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models.accounting import Account, JournalLine
from app.models.banking import BankAccount
from app.models.inventory import Contact
from app.models.treasury import TreasuryTransaction
from app.models.user import User
from app.schemas.treasury import CardPaymentIn, TreasuryTransactionIn
from app.models.cashbox import Cashbox
from app.services import bank_accounts, cashboxes
from app.services import chart_codes as cc
from app.services.common import get_account, make_journal_entry
from app.services.period_close import assert_period_open

#: نامِ ثابتِ طرف‌حسابِ سیستمیِ فروشِ کارتیِ گذری (بدونِ طرف‌حسابِ مشخص).
WALKIN_CARD_CONTACT_NAME = "فروشِ کارتیِ گذری"


def _resolve_money_side(db: Session, data: TreasuryTransactionIn) -> tuple[Account, UUID | None, Cashbox | None]:
    """حساب مقصد/مبدأ وجه، و بُعدی که روی ردیفِ سند می‌نشیند.

    برای نقدی، صندوق تعیین می‌کند مبلغ به کدام معین و **کدام تفصیلی** برود. همین
    تفصیلی است که مانده‌ی هر صندوق را از بقیه جدا می‌کند — بدونِ آن، صندوق‌ها در
    دفتر یک عدد می‌شوند و «مانده‌ی صندوقِ شعبه» معنایی ندارد.

    **برای بانکی هم دقیقاً همین.** تا مهاجرتِ ۰۱۰۶ این شاخه `None` برمی‌گرداند و
    نتیجه‌اش این بود که همه‌ی حساب‌های بانکی در دفتر یک عدد می‌شدند.
    """
    if data.method == "cash":
        box = cashboxes.resolve_cashbox(db, getattr(data, "cashbox_id", None))
        cashboxes.assert_usable(db, box, data.transaction_date)
        return db.get(Account, cashboxes.gl_account_id(db, box)), box.analytic_id, box
    bank = bank_accounts.resolve(db, data.bank_account_id)
    bank_accounts.assert_usable(db, bank, data.transaction_date)
    return db.get(Account, bank.gl_account_id), bank.analytic_id, None


def create_receipt(
    db: Session,
    data: TreasuryTransactionIn,
    user: User,
    *,
    paid_via: str | None = None,
    reference_no: str | None = None,
    trace_no: str | None = None,
    card_mask: str | None = None,
    terminal_no: str | None = None,
    psp: str | None = None,
) -> TreasuryTransaction:
    """دریافت وجه از مشتری: بدهکار صندوق/بانک، بستانکار حساب‌های دریافتنی.

    پارامترهای اختیاریِ کارت (paid_via/reference_no/…) فقط برای رسیدِ کارتخوان پر
    می‌شوند و روی خودِ تراکنش ذخیره می‌گردند تا برای مغایرت‌گیری در دسترس بمانند.
    """
    assert_period_open(db, data.transaction_date)
    contact = db.get(Contact, data.contact_id)
    if contact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "طرف حساب یافت نشد")

    money_account, money_analytic, box = _resolve_money_side(db, data)
    receivable = get_account(db, cc.ACCOUNTS_RECEIVABLE)

    description = data.description or f"دریافت از {contact.name}"
    entry = make_journal_entry(
        db,
        data.transaction_date,
        description,
        "treasury_receipt",
        user,
        [
            JournalLine(
                account_id=money_account.id,
                #: تفصیلیِ صندوق — همین است که مانده‌ی صندوق را مشتق‌شدنی می‌کند.
                analytic_id=money_analytic,
                debit=data.amount,
                credit=0,
                description=description,
            ),
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
        cashbox_id=box.id if box else None,
        description=description,
        journal_entry_id=entry.id,
        created_by_id=user.id,
        paid_via=paid_via,
        reference_no=reference_no,
        trace_no=trace_no,
        card_mask=card_mask,
        terminal_no=terminal_no,
        psp=psp,
    )
    db.add(txn)
    db.flush()
    db.refresh(txn)
    return txn


def get_or_create_walkin_card_contact(db: Session) -> Contact:
    """طرف‌حسابِ سیستمیِ «فروشِ کارتیِ گذری» را می‌یابد یا می‌سازد (یک‌بار در هر مستأجر).

    برای فروشِ کارتیِ بدونِ طرف‌حسابِ مشخص: فاکتور علیهِ این طرف‌حساب به دریافتنی می‌رود
    و بلافاصله با رسیدِ کارت تسویه می‌شود، پس ماندهٔ آن همیشه صفر می‌ماند. با پرچمِ
    is_system از فهرستِ مشتریانِ کاربر پنهان است.
    """
    contact = (
        db.query(Contact)
        .filter(Contact.is_system.is_(True), Contact.name == WALKIN_CARD_CONTACT_NAME)
        .first()
    )
    if contact is not None:
        return contact
    contact = Contact(name=WALKIN_CARD_CONTACT_NAME, type="customer", is_system=True)
    db.add(contact)
    db.flush()
    db.refresh(contact)
    return contact


def record_card_payment(db: Session, data: CardPaymentIn, user: User) -> TreasuryTransaction:
    """رسیدِ بانکیِ یک پرداختِ کارتیِ موفق را ثبت می‌کند (کانالِ کارتخوان).

    idempotent روی RRN: اگر رسیدی با همان شماره‌ی مرجع از قبل باشد، همان برمی‌گردد و
    رسیدِ دوم ساخته نمی‌شود (کلیکِ دوباره/ارسالِ دوباره‌ی همان تراکنش).
    """
    ref = (data.reference_no or "").strip()
    if ref:
        existing = (
            db.query(TreasuryTransaction)
            .filter(TreasuryTransaction.type == "receipt", TreasuryTransaction.reference_no == ref)
            .first()
        )
        if existing is not None:
            return existing

    contact = db.get(Contact, data.contact_id) if data.contact_id else get_or_create_walkin_card_contact(db)
    if contact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "طرف حساب یافت نشد")

    tin = TreasuryTransactionIn(
        transaction_date=data.transaction_date,
        contact_id=contact.id,
        amount=data.amount,
        method="bank",
        bank_account_id=data.bank_account_id,
        description=data.description or f"پرداختِ کارتی — {contact.name}",
    )
    return create_receipt(
        db,
        tin,
        user,
        paid_via="pos_terminal",
        reference_no=ref or None,
        trace_no=data.trace_no or None,
        card_mask=data.card_mask or None,
        terminal_no=data.terminal_no or None,
        psp=data.psp or None,
    )


def create_payment(db: Session, data: TreasuryTransactionIn, user: User) -> TreasuryTransaction:
    """پرداخت وجه به تأمین‌کننده: بدهکار حساب‌های پرداختنی، بستانکار صندوق/بانک."""
    assert_period_open(db, data.transaction_date)
    contact = db.get(Contact, data.contact_id)
    if contact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "طرف حساب یافت نشد")

    money_account, money_analytic, box = _resolve_money_side(db, data)
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
            JournalLine(
                account_id=money_account.id,
                analytic_id=money_analytic,
                debit=0,
                credit=data.amount,
                description=description,
            ),
        ],
    )

    txn = TreasuryTransaction(
        type="payment",
        transaction_date=data.transaction_date,
        contact_id=data.contact_id,
        amount=data.amount,
        method=data.method,
        bank_account_id=data.bank_account_id,
        cashbox_id=box.id if box else None,
        description=description,
        journal_entry_id=entry.id,
        created_by_id=user.id,
    )
    db.add(txn)
    db.flush()
    db.refresh(txn)
    return txn


def transactions_query(db: Session):
    """کوئری پایه؛ مرتب‌سازی و صفحه‌بندی در لایه‌ی روتر اعمال می‌شود."""
    return db.query(TreasuryTransaction).options(joinedload(TreasuryTransaction.contact))
