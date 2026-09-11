"""تسویه‌ی کارت‌خوان — بردنِ پول از «وجوهِ در راه» به بانک.

## دو رویداد، نه یکی

کارت‌کشیدنِ مشتری و رسیدنِ پول به حسابِ شرکت **یک اتفاق نیستند**. شبکه‌ی پرداخت
چند روز بعد جمعِ چند تراکنش را یک‌جا واریز می‌کند. پس:

    مشتری ← کارت‌خوان ← وجوهِ در راه ← «تسویه» ← بانک

تا مهاجرتِ ۰۱۰۹ کوبیتا مرحله‌ی اول را مستقیم روی بانک می‌نشاند و مرحله‌ی دوم
اصلاً سندی نداشت. سه پیامدِ سنجیدنی داشت:

1. **مانده‌ی بانک دقیقاً به اندازه‌ی پولِ تسویه‌نشده باد کرده بود.** مانده از دفتر
   می‌آید و دفتر پولی را روی بانک نشان می‌داد که هنوز به بانک نرسیده بود.
2. **مغایرت‌گیری نمی‌توانست واریزِ PSP را تطبیق دهد.** برای آن واریز هیچ
   `BankTransaction`ی ساخته نمی‌شد؛ تنها ردیفِ سیستمی یک «منهای کارمزد» بود که با
   هیچ خطی از صورت‌حسابِ بانک نمی‌خواند.
3. **«این رسید با کدام تسویه رفت؟» بی‌جواب بود** — تسویه رکورد نبود.

## اثرِ حسابداری (§۲۳ §۲۶)

مرحله‌ی اول، هنگامِ رسیدِ کارتی (در `services/treasury.py`):

    وجوهِ در راهِ کارت‌خوان   بدهکار              (تفصیلی: خودِ دستگاه)
        حساب‌های دریافتنی            بستانکار

مرحله‌ی دوم، همین‌جا:

    بانک                     بدهکار   خالص      (تفصیلی: حسابِ بانکی)
    کارمزدِ بانکی             بدهکار   کارمزد
        وجوهِ در راهِ کارت‌خوان       بستانکار   ناخالص

نتیجه: طلبِ مشتری یک‌بار تسویه شده، وجوهِ در راه صفر شده، بانک بالا رفته.
**هیچ‌جا فروش یا درآمدِ تازه‌ای ثبت نمی‌شود (§۲۷)** و حسابِ مشتری دوباره دست
نمی‌خورد (§۲۴) — رویدادِ فروش قبلاً ثبت شده است.

## آنچه اینجا عمداً نیست

**تسویه‌ی جزئیِ یک تراکنش (§۳۱).** مدل طوری است که بعداً بشود اضافه‌اش کرد —
`settlement_id` روی خودِ رسید می‌نشیند نه روی گروهِ روزانه — ولی امروز واحدِ تسویه
کلِ یک رسید است.

**هیچ فرضی درباره‌ی کارمزد (§۳۰).** کارمزد عددی است که کاربر وارد می‌کند؛ نه
درصدی حدس زده می‌شود نه از خالصِ واریز عقب‌گرد محاسبه می‌شود.
"""
from __future__ import annotations

from datetime import date as date_, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.accounting import Account, JournalEntry, JournalLine
from app.models.banking import BankAccount, BankTransaction
from app.models.counters import DOC_POS_SETTLEMENT
from app.models.inventory import Contact
from app.models.pos_settlement import PosSettlement
from app.models.pos_terminal import PosTerminal
from app.models.treasury import TreasuryTransaction
from app.models.user import User
from app.services import card_terminals
from app.services import chart_codes as cc
from app.services.common import get_or_create_account, make_journal_entry
from app.services.numbering import next_document_number
from app.services.period_close import assert_period_open
from app.services.voiding import reverse_journal_entry

#: نامِ حسابِ واسط. **هیچ‌جا با نام پیدا نمی‌شود** (§۲۵) — انتخابِ حساب همیشه از
#: `system_role` می‌رود؛ این فقط عنوانی است که بارِ اول با آن ساخته می‌شود.
CLEARING_ACCOUNT_NAME = "وجوهِ در راهِ کارت‌خوان"

SOURCE_TYPE = "pos_settlement"


def _label(term: PosTerminal) -> str:
    return term.label or term.terminal_no or "کارتخوان"


def clearing_account(db: Session) -> Account:
    """حسابِ «وجوهِ در راهِ کارت‌خوان» — و اگر نبود، ساختنش.

    `get_or_create` است نه `get`، چون این نقش بعد از استقرارِ کسب‌وکارهای موجود
    اضافه شده و چارتِ آن‌ها آن را ندارد. همان الگویی که حساب‌های مالیات بر ارزشِ
    افزوده گرفتند.
    """
    return get_or_create_account(
        db,
        cc.POS_CLEARING,
        code=cc.DEFAULT_CODE_BY_ROLE[cc.POS_CLEARING],
        name=CLEARING_ACCOUNT_NAME,
        acc_type="asset",
        parent_code="1",
    )


# ───────────────────────────── رسیدهای واجدِ شرایط ─────────────────────────────


def eligible_receipts(
    db: Session,
    term: PosTerminal,
    *,
    settle_through: date_,
    date_from: date_ | None = None,
) -> list[TreasuryTransaction]:
    """رسیدهای کارتیِ تسویه‌نشده‌ی این دستگاه تا تاریخِ برش (§۹).

    چهار شرط، و هر چهار لازم‌اند:

    * از کانالِ کارت‌خوان آمده باشد (`paid_via`)،
    * هنوز تسویه نشده باشد — همین است که «دوباره‌تسویه» را ناممکن می‌کند (§۱۵)،
    * تاریخش از برش جلوتر نباشد،
    * و مالِ همین دستگاه باشد؛ که شاملِ رسیدهای پیش از مهاجرتِ ۰۱۰۷ هم می‌شود که
      کلیدِ خارجی ندارند و فقط `terminal_no`شان می‌خواند.
    """
    query = db.query(TreasuryTransaction).filter(
        TreasuryTransaction.paid_via == card_terminals.PAID_VIA_TERMINAL,
        TreasuryTransaction.settled_at.is_(None),
        TreasuryTransaction.transaction_date <= settle_through,
        card_terminals._owned_transactions(term),
    )
    if date_from is not None:
        query = query.filter(TreasuryTransaction.transaction_date >= date_from)
    return query.order_by(
        TreasuryTransaction.transaction_date, TreasuryTransaction.created_at
    ).all()


def _contact_names(db: Session, rows: list[TreasuryTransaction]) -> dict[UUID, tuple[str, str]]:
    """نامِ طرف‌حساب‌ها یک‌بار خوانده می‌شود، نه به‌ازای هر ردیف.

    نامِ دوم از `first_name2`/`last_name2` ساخته می‌شود — همان جفتی که کوبیتا برای
    اسنادِ دوزبانه دارد. طرف‌حساب ستونِ `name2`ِ یک‌تکه ندارد (برخلافِ صندوق و حساب
    بانکی)، پس ساختنش اینجا انجام می‌شود نه اختراعِ ستونِ تازه.
    """
    ids = {r.contact_id for r in rows}
    if not ids:
        return {}
    found = (
        db.query(Contact.id, Contact.name, Contact.first_name2, Contact.last_name2)
        .filter(Contact.id.in_(ids))
        .all()
    )
    return {
        cid: (name or "", f"{first2 or ''} {last2 or ''}".strip())
        for cid, name, first2, last2 in found
    }


def receipt_rows(db: Session, rows: list[TreasuryTransaction]) -> list[dict]:
    """رسیدهای منبع، با همان ستون‌هایی که §۱۰ می‌خواهد.

    «طرفِ مقابلِ دوم» همان `name2`ِ طرف‌حساب است — عنوانِ دومی که کوبیتا از قبل
    برای اشخاص دارد؛ مفهومِ تازه‌ای ساخته نمی‌شود.
    """
    names = _contact_names(db, rows)
    out = []
    for txn in rows:
        name, name2 = names.get(txn.contact_id, ("", ""))
        out.append(
            {
                "id": txn.id,
                "transaction_date": txn.transaction_date,
                "contact_id": txn.contact_id,
                "contact_name": name,
                "contact_name2": name2,
                "amount": Decimal(txn.amount),
                "reference_no": txn.reference_no,
                "trace_no": txn.trace_no,
                "card_mask": txn.card_mask,
                "description": txn.description,
            }
        )
    return out


def preview(
    db: Session,
    *,
    pos_terminal_id: UUID,
    settle_through: date_,
    date_from: date_ | None = None,
) -> dict:
    """آنچه با این برش تسویه خواهد شد — پیش از ثبت (§۱۲).

    کاربر باید *پیش از* زدنِ دکمه ببیند مبلغ از کدام رسیدها ساخته می‌شود؛ وگرنه
    عددِ تسویه یک جمعِ توضیح‌ناپذیر است.
    """
    term = card_terminals.resolve(db, pos_terminal_id)
    rows = eligible_receipts(db, term, settle_through=settle_through, date_from=date_from)
    bank = db.get(BankAccount, term.bank_account_id) if term.bank_account_id else None
    return {
        "pos_terminal_id": term.id,
        "terminal_no": term.terminal_no,
        "terminal_label": _label(term),
        "bank_account_id": term.bank_account_id,
        "bank_account_name": bank.name if bank else "",
        "bank_account_name2": bank.name2 if bank else "",
        "gross_amount": sum((Decimal(r.amount) for r in rows), Decimal(0)),
        "receipt_count": len(rows),
        "receipts": receipt_rows(db, rows),
    }


def related_receipts(db: Session, settlement: PosSettlement) -> list[dict]:
    """رسیدهایی که این تسویه مصرفشان کرد — جهتِ معکوسِ §۱۱."""
    rows = (
        db.query(TreasuryTransaction)
        .filter(TreasuryTransaction.settlement_id == settlement.id)
        .order_by(TreasuryTransaction.transaction_date)
        .all()
    )
    return receipt_rows(db, rows)


def pending_groups(
    db: Session,
    *,
    terminal_no: str | None = None,
    pos_terminal_id: UUID | None = None,
    date_from: date_ | None = None,
    date_to: date_ | None = None,
) -> list[dict]:
    """نمای کلی: هر دستگاه در هر روز چقدر پولِ نرسیده دارد.

    این با `preview` یکی نیست و هر دو لازم‌اند — یکی می‌گوید «کجا پول مانده»،
    دیگری «اگر این برش را بزنم دقیقاً چه چیزی تسویه می‌شود».

    `pos_terminal_id` راهِ درست است: دامنه از خودِ دستگاه می‌آید و شاملِ رسیدهای
    قدیمیِ همان شماره هم می‌شود. `terminal_no` برای سازگاری می‌ماند.
    """
    query = db.query(TreasuryTransaction).filter(
        TreasuryTransaction.paid_via == card_terminals.PAID_VIA_TERMINAL,
        TreasuryTransaction.settled_at.is_(None),
    )
    if pos_terminal_id is not None:
        query = query.filter(
            card_terminals._owned_transactions(card_terminals.resolve(db, pos_terminal_id))
        )
    elif terminal_no:
        query = query.filter(TreasuryTransaction.terminal_no == terminal_no)
    if date_from is not None:
        query = query.filter(TreasuryTransaction.transaction_date >= date_from)
    if date_to is not None:
        query = query.filter(TreasuryTransaction.transaction_date <= date_to)

    #: برچسبِ دستگاه یک‌بار خوانده می‌شود، نه به‌ازای هر ردیف.
    labels = {t.id: _label(t) for t in db.query(PosTerminal).all()}

    groups: dict[tuple[str, date_], dict] = {}
    for txn in query.order_by(TreasuryTransaction.transaction_date).all():
        key = (txn.terminal_no or "", txn.transaction_date)
        group = groups.setdefault(
            key,
            {
                "terminal_no": txn.terminal_no or "",
                "pos_terminal_id": txn.pos_terminal_id,
                "terminal_label": labels.get(txn.pos_terminal_id),
                "transaction_date": txn.transaction_date,
                "count": 0,
                "gross_amount": Decimal(0),
            },
        )
        group["count"] += 1
        group["gross_amount"] += Decimal(txn.amount)
    return sorted(groups.values(), key=lambda r: (r["transaction_date"], r["terminal_no"]))


# ───────────────────────────────── ثبتِ تسویه ─────────────────────────────────


def create(
    db: Session,
    user: User,
    *,
    pos_terminal_id: UUID,
    settlement_date: date_,
    settle_through: date_,
    date_from: date_ | None = None,
    fee_amount: Decimal = Decimal(0),
    note: str = "",
) -> PosSettlement:
    """یک واریزِ شرکتِ پرداخت را ثبت می‌کند."""
    assert_period_open(db, settlement_date)

    term = card_terminals.resolve(db, pos_terminal_id)
    #: حساب از خودِ دستگاه می‌آید، نه از ورودی (§۶ §۷) — وگرنه واریز می‌توانست به
    #: حسابی بخورد که وجوهِ در راهش آنجا نیست.
    bank = card_terminals.settlement_account(db, term)
    card_terminals.assert_currency_match(db, term.currency_code, bank.id)

    rows = eligible_receipts(db, term, settle_through=settle_through, date_from=date_from)
    if not rows:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"رسیدِ کارتیِ تسویه‌نشده‌ای برای دستگاه «{_label(term)}» تا این تاریخ نیست",
        )

    gross = sum((Decimal(r.amount) for r in rows), Decimal(0))
    fee = Decimal(fee_amount or 0)
    if fee < 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "کارمزد نمی‌تواند منفی باشد")
    if fee > gross:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "کارمزد از جمعِ تراکنش‌ها بیشتر است")
    net = gross - fee

    number = next_document_number(db, DOC_POS_SETTLEMENT)
    description = f"تسویه‌ی کارت‌خوان {number} — {_label(term)}"

    clearing = clearing_account(db)
    lines: list[JournalLine] = []
    if net > 0:
        lines.append(
            JournalLine(
                account_id=bank.gl_account_id,
                #: تفصیلیِ حسابِ بانکی — همان چیزی که مانده‌ی «بانک سامان» را از
                #: «بانک ملت» جدا می‌کند.
                analytic_id=bank.analytic_id,
                debit=net,
                credit=0,
                description=description,
            )
        )
    if fee > 0:
        fee_account = get_or_create_account(
            db,
            cc.BANK_FEE,
            code=cc.DEFAULT_CODE_BY_ROLE[cc.BANK_FEE],
            name="کارمزد و هزینه‌های بانکی",
            acc_type="expense",
            parent_code="5",
        )
        lines.append(
            JournalLine(
                account_id=fee_account.id,
                debit=fee,
                credit=0,
                description=f"کارمزدِ {description}",
            )
        )
    lines.append(
        JournalLine(
            account_id=clearing.id,
            #: تفصیلیِ دستگاه — بدونِ آن، وجوهِ در راهِ همه‌ی دستگاه‌ها یک عدد می‌شود.
            analytic_id=term.analytic_id,
            debit=0,
            credit=gross,
            description=description,
        )
    )
    entry = make_journal_entry(db, settlement_date, description, SOURCE_TYPE, user, lines)

    settlement = PosSettlement(
        number=number,
        settlement_date=settlement_date,
        settle_through=settle_through,
        date_from=date_from,
        pos_terminal_id=term.id,
        bank_account_id=bank.id,
        gross_amount=gross,
        fee_amount=fee,
        net_amount=net,
        journal_entry_id=entry.id,
        note=note or "",
        created_by_id=user.id,
    )
    db.add(settlement)
    db.flush()

    #: ردیفِ بانکیِ خودِ واریز — چیزی که در مغایرت‌گیری مقابلِ خطِ صورت‌حسابِ بانک
    #: می‌نشیند (§۳۶). مبلغش **خالص** است، چون بانک هم خالص را واریز می‌کند.
    bank_txn = None
    if net > 0:
        bank_txn = BankTransaction(
            bank_account_id=bank.id,
            transaction_date=settlement_date,
            amount=net,
            description=description,
            source_type=SOURCE_TYPE,
            journal_entry_id=entry.id,
            created_by_id=user.id,
        )
        db.add(bank_txn)
        db.flush()
        settlement.bank_transaction_id = bank_txn.id

    now = datetime.now(timezone.utc)
    for txn in rows:
        txn.settled_at = now
        txn.settlement_id = settlement.id
        txn.settlement_txn_id = bank_txn.id if bank_txn is not None else None
    db.flush()
    db.refresh(settlement)
    return settlement


# ───────────────────────────────── ابطال (§۳۳) ─────────────────────────────────


def void(db: Session, settlement_id: UUID, user: User, reason: str) -> PosSettlement:
    """ابطال با سندِ معکوس — رکورد و سندِ اصلی سرِ جایشان می‌مانند.

    **چرا حذفِ فیزیکی نه.** تسویه سند و ردیفِ بانکی صادر کرده است؛ پاک‌کردنشان
    یعنی بازنویسیِ بی‌صدای تاریخچه‌ی مالی. رسیدها دوباره «تسویه‌نشده» می‌شوند و
    می‌توانند در تسویه‌ی درست بیایند.

    **اگر بانک از قبل تطبیق داده باشد، رد می‌شود.** ردیفِ تطبیق‌شده یعنی این واریز
    روی صورت‌حسابِ بانک دیده شده؛ باطل‌کردنش بدونِ برداشتنِ تطبیق، مغایرت‌گیری را
    با یک ارجاعِ آویزان رها می‌کند.
    """
    settlement = get(db, settlement_id)
    if settlement.voided_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "این تسویه قبلاً باطل شده")
    if not (reason or "").strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "دلیلِ ابطال لازم است")

    today = date_.today()
    assert_period_open(db, today)

    bank_txn = (
        db.get(BankTransaction, settlement.bank_transaction_id)
        if settlement.bank_transaction_id
        else None
    )
    if bank_txn is not None and bank_txn.is_reconciled:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"واریزِ تسویه‌ی {settlement.number} با صورت‌حسابِ بانک تطبیق داده شده؛ "
            "اول تطبیق را بردارید",
        )

    entry = db.get(JournalEntry, settlement.journal_entry_id)
    description = f"ابطالِ تسویه‌ی کارت‌خوان {settlement.number} — {reason.strip()}"
    reversal = reverse_journal_entry(
        db, entry, void_date=today, user=user, description=description
    )

    if bank_txn is not None:
        #: ردیفِ منفیِ قرینه، نه حذفِ ردیفِ قبلی: جمعشان صفر می‌شود و هر دو در
        #: گردشِ حساب می‌مانند.
        db.add(
            BankTransaction(
                bank_account_id=bank_txn.bank_account_id,
                transaction_date=today,
                amount=-Decimal(bank_txn.amount),
                description=description,
                source_type=SOURCE_TYPE,
                journal_entry_id=reversal.id,
                created_by_id=user.id,
            )
        )

    for txn in db.query(TreasuryTransaction).filter(
        TreasuryTransaction.settlement_id == settlement.id
    ):
        txn.settled_at = None
        txn.settlement_id = None
        txn.settlement_txn_id = None

    settlement.voided_at = datetime.now(timezone.utc)
    settlement.void_reason = reason.strip()
    db.flush()
    db.refresh(settlement)
    return settlement


# ─────────────────────────────────── خواندن ───────────────────────────────────


def get(db: Session, settlement_id: UUID) -> PosSettlement:
    settlement = db.query(PosSettlement).filter(PosSettlement.id == settlement_id).first()
    if settlement is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "تسویه یافت نشد")
    return settlement


def row(db: Session, settlement: PosSettlement) -> dict:
    """یک تسویه به شکلِ خروجی — ستون‌هایی که §۲۸ می‌خواهد، و شمارِ رسیدها."""
    term = db.get(PosTerminal, settlement.pos_terminal_id)
    bank = db.get(BankAccount, settlement.bank_account_id)
    count = (
        db.query(func.count(TreasuryTransaction.id))
        .filter(TreasuryTransaction.settlement_id == settlement.id)
        .scalar()
        or 0
    )
    return {
        "id": settlement.id,
        "number": settlement.number,
        "settlement_date": settlement.settlement_date,
        "settle_through": settlement.settle_through,
        "date_from": settlement.date_from,
        "pos_terminal_id": settlement.pos_terminal_id,
        "terminal_no": term.terminal_no if term else "",
        "terminal_label": _label(term) if term else "",
        "bank_account_id": settlement.bank_account_id,
        "bank_account_name": bank.name if bank else "",
        "bank_account_name2": bank.name2 if bank else "",
        "gross_amount": Decimal(settlement.gross_amount),
        "fee_amount": Decimal(settlement.fee_amount),
        "net_amount": Decimal(settlement.net_amount),
        "receipt_count": int(count),
        "journal_entry_id": settlement.journal_entry_id,
        "bank_transaction_id": settlement.bank_transaction_id,
        "voided_at": settlement.voided_at,
        "void_reason": settlement.void_reason,
        "note": settlement.note,
    }


def list_settlements(
    db: Session,
    *,
    pos_terminal_id: UUID | None = None,
    date_from: date_ | None = None,
    date_to: date_ | None = None,
    include_voided: bool = True,
) -> list[dict]:
    query = db.query(PosSettlement)
    if pos_terminal_id is not None:
        query = query.filter(PosSettlement.pos_terminal_id == pos_terminal_id)
    if date_from is not None:
        query = query.filter(PosSettlement.settlement_date >= date_from)
    if date_to is not None:
        query = query.filter(PosSettlement.settlement_date <= date_to)
    if not include_voided:
        query = query.filter(PosSettlement.voided_at.is_(None))
    rows = query.order_by(PosSettlement.settlement_date.desc(), PosSettlement.number.desc()).all()
    return [row(db, s) for s in rows]
