"""اقلامِ بازِ یک طرف حساب — چه سندهایی هنوز تسویه نشده‌اند.

**«مانده‌ی حساب» و «مانده‌ی اقلامِ باز» یکی نیستند (§۲۵ §۲۶).** مشتری می‌تواند در
دفتر ماندهٔ صفر داشته باشد و هم‌زمان یک فاکتورِ ۱۰۰ و یک دریافتِ ۱۰۰ داشته باشد که
هیچ‌کس نگفته به هم مربوط‌اند. عددِ خالص درست است؛ رابطه‌اش نامعلوم. این ماژول نیمه‌ی
دوم را می‌سازد.

**مبلغِ هر قلم از دفتر می‌آید، نه از ستونِ خودِ سند (§۸).** «فاکتور همیشه بدهکار
است» غلط است: فاکتورِ فروش دریافتنی را بدهکار می‌کند و فاکتورِ خرید پرداختنی را
بستانکار. پس به‌جای حدس‌زدن از رویِ نامِ فرم، اثرِ **واقعیِ** سندِ حسابداریِ همان
سند روی حسابِ معینِ انتخاب‌شده خوانده می‌شود: بدهکار منهای بستانکار. مثبت یعنی قلمِ
بدهکار، منفی یعنی بستانکار. همین یک قاعده هر هشت نوعِ منبع را پوشش می‌دهد و برای
نوعِ نهم هم کار می‌کند.

از همین‌جا یک خاصیتِ مهم می‌آید: جمعِ اقلامِ باز و ماندهٔ حساب هر دو از **یک**
ردیف‌های دفتر می‌آیند، پس نمی‌توانند به‌خاطرِ دو محاسبه‌ی جدا از هم جدا بیفتند
(§۴۴).

ولی برابرِ هم هم نیستند، و این را باید صریح گفت: ردیفی که سندِ منبعش در
`SETTLEABLE` نیست — سندِ دستی روی دریافتنی، ماندهٔ اول دوره، و **چکِ ثبت‌شده پیش
از مهاجرتِ ۰۱۱۰** که رویدادی ندارد تا از دفتر به آن برسیم — گردش دارد ولی
«سندِ قابلِ تسویه» ندارد. این‌ها بی‌صدا حذف نمی‌شوند: `unattributed` تفاوت را
گزارش می‌کند و «بررسی یکپارچگی» هم نشانش می‌دهد. حذفِ خاموشْ ماندهٔ گم‌شده
می‌ساخت که هیچ‌جا دیده نمی‌شد.

**مبلغِ تسویه‌شده ذخیره نمی‌شود (§۴۳).** جمعِ تخصیص‌های تسویه‌های باطل‌نشده است.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.accounting import Account, JournalEntry, JournalLine
from app.models.check_event import CheckEvent
from app.models.inventory import Contact
from app.models.invoices import PurchaseInvoice, SalesInvoice
from app.models.returns import PurchaseReturn, SalesReturn
from app.models.sales_ops import CreditDebitNote
from app.models.settlement import Settlement, SettlementAllocation
from app.models.treasury import TreasuryTransaction
from app.services import chart_codes as cc
from app.services.common import get_account

#: وضعیتِ تسویه‌ی یک قلم — مشتق، نه ذخیره‌شده (§۲۷ §۴۲).
UNSETTLED = "unsettled"
PARTIAL = "partial"
SETTLED = "settled"
#: تخصیص بیشتر از مانده‌ی سند شده — یعنی سندِ منبع **بعد از** تسویه کوچک شده
#: (§۳۹ §۴۰). حالتی که نباید بی‌صدا بماند.
OVER = "over"

STATUS_LABELS = {
    UNSETTLED: "تسویه‌نشده",
    PARTIAL: "تسویه جزئی",
    SETTLED: "تسویه کامل",
    OVER: "تخصیصِ بیش از مانده",
}


@dataclass(frozen=True)
class SettleableKind:
    """یک نوعِ سندِ قابلِ تسویه.

    `joins` برای منبع‌هایی است که خودشان `contact_id` ندارند: برگشت از فروش طرفِ
    حسابش را از فاکتورِ اصلی می‌گیرد. `filters` نوعِ ثابت و باطل‌نبودن را می‌گذارد.
    """

    key: str
    label: str
    model: type
    date_col: Any
    contact_col: Any
    number_col: Any | None = None
    joins: tuple = ()
    filters: tuple = ()


#: **رجیستریِ منبع‌های قابلِ تسویه (§۳۴).** نوعِ منبع حفظ می‌شود؛ همه‌چیز به یک
#: «قلمِ تسویه»ی بی‌هویت تبدیل نمی‌شود.
#:
#: کلیدها عمداً همان `source_type`ِ `entry_source` هستند تا برچسب و ردیابی یکی
#: بماند. سندِ دستی اینجا نیست: تسویه‌ی سندِ دستی لنگرِ سندِ منبع ندارد و «شماره‌ی
#: فاکتور»ش هم معنی ندارد — اگر روزی لازم شد، `journal_entry` نوعِ نهم می‌شود.
SETTLEABLE: dict[str, SettleableKind] = {
    "sales_invoice": SettleableKind(
        key="sales_invoice",
        label="فاکتور فروش",
        model=SalesInvoice,
        date_col=SalesInvoice.invoice_date,
        contact_col=SalesInvoice.contact_id,
        number_col=SalesInvoice.number,
        filters=(SalesInvoice.voided_at.is_(None),),
    ),
    "purchase_invoice": SettleableKind(
        key="purchase_invoice",
        label="فاکتور خرید",
        model=PurchaseInvoice,
        date_col=PurchaseInvoice.invoice_date,
        contact_col=PurchaseInvoice.contact_id,
        number_col=PurchaseInvoice.number,
        filters=(PurchaseInvoice.voided_at.is_(None),),
    ),
    "sales_return": SettleableKind(
        key="sales_return",
        label="برگشت از فروش",
        model=SalesReturn,
        date_col=SalesReturn.return_date,
        #: برگشت `contact_id`ِ خودش را ندارد؛ طرفِ حساب همان فاکتورِ اصلی است.
        contact_col=SalesInvoice.contact_id,
        number_col=SalesReturn.number,
        joins=((SalesInvoice, SalesReturn.sales_invoice_id == SalesInvoice.id),),
        filters=(SalesInvoice.voided_at.is_(None),),
    ),
    "purchase_return": SettleableKind(
        key="purchase_return",
        label="برگشت از خرید",
        model=PurchaseReturn,
        date_col=PurchaseReturn.return_date,
        contact_col=PurchaseInvoice.contact_id,
        number_col=PurchaseReturn.number,
        joins=((PurchaseInvoice, PurchaseReturn.purchase_invoice_id == PurchaseInvoice.id),),
        filters=(PurchaseInvoice.voided_at.is_(None),),
    ),
    "treasury_receipt": SettleableKind(
        key="treasury_receipt",
        label="رسید دریافت",
        model=TreasuryTransaction,
        date_col=TreasuryTransaction.transaction_date,
        contact_col=TreasuryTransaction.contact_id,
        #: رسید شماره‌ی مستقل ندارد؛ شماره‌ی سندِ حسابداری‌اش شناسه‌ی عملیِ اوست.
        #: `entry_number` در خروجی همیشه می‌آید، پس قلم بی‌شناسه نمی‌ماند.
        filters=(TreasuryTransaction.type == "receipt",),
    ),
    "treasury_payment": SettleableKind(
        key="treasury_payment",
        label="اعلامیه پرداخت",
        model=TreasuryTransaction,
        date_col=TreasuryTransaction.transaction_date,
        contact_col=TreasuryTransaction.contact_id,
        filters=(TreasuryTransaction.type == "payment",),
    ),
    "credit_debit_note": SettleableKind(
        key="credit_debit_note",
        label="اعلامیه بدهکار/بستانکار",
        model=CreditDebitNote,
        date_col=CreditDebitNote.note_date,
        contact_col=CreditDebitNote.contact_id,
        number_col=CreditDebitNote.number,
        filters=(CreditDebitNote.voided_at.is_(None),),
    ),
    #: **چک، رویداد به رویداد.** لنگر `CheckEvent` است نه `Check`: دریافتِ چک
    #: دریافتنی را بستانکار می‌کند و واخواستش دوباره بدهکار. این دو دو قلمِ بازِ
    #: جدا هستند، نه یک چکِ با علامتِ مبهم.
    "check": SettleableKind(
        key="check",
        label="چک",
        model=CheckEvent,
        date_col=CheckEvent.event_date,
        contact_col=CheckEvent.contact_id,
        number_col=CheckEvent.operation_no,
    ),
}


def counterparty_accounts(db: Session) -> list[Account]:
    """معین‌هایی که طرفِ حساب رویشان گردش دارد (§۵).

    با `system_role` پیدا می‌شوند نه با کد یا نام — همان قاعده‌ای که همه‌ی سندهای
    خودکار در کوبیتا دارند.
    """
    return [get_account(db, role) for role in (cc.ACCOUNTS_RECEIVABLE, cc.ACCOUNTS_PAYABLE)]


def assert_counterparty_account(db: Session, account_id: UUID) -> Account:
    for account in counterparty_accounts(db):
        if account.id == account_id:
            return account
    raise HTTPException(
        status.HTTP_400_BAD_REQUEST,
        "این حساب معینِ طرف مقابل نیست. تسویه فقط روی حساب‌های دریافتنی/پرداختنی تجاری انجام می‌شود.",
    )


# ─────────────────────────── اثرِ دفتریِ هر سند ───────────────────────────


def _kind_effects(
    db: Session, kind: SettleableKind, account_id: UUID, contact_id: UUID | None, as_of: date | None
) -> list[dict]:
    """اثرِ خالصِ هر سندِ این نوع روی حسابِ داده‌شده.

    یک کوئری برای کلِ نوع — نه یکی به‌ازای هر سند. `debit - credit` علامت را هم
    می‌دهد و هم سمت را: مثبت = بدهکار، منفی = بستانکار.
    """
    model = kind.model
    net = func.coalesce(func.sum(JournalLine.debit - JournalLine.credit), 0)
    #: مبلغِ ارزیِ همان ردیف‌ها. ردیفِ ریالی `NULL` دارد و در جمع صفر حساب می‌شود.
    fx_net = func.coalesce(
        func.sum(
            func.coalesce(JournalLine.fx_amount, 0)
            * func.sign(JournalLine.debit - JournalLine.credit)
        ),
        0,
    )
    #: ستون‌های گروه‌بندی جدا از تجمیع‌ها نگه داشته می‌شوند؛ گذاشتنِ `max(...)` در
    #: `GROUP BY` خطای Postgres است، نه فقط بدسلیقگی.
    group_cols = [model.id, kind.date_col, JournalEntry.number]
    if kind.number_col is not None:
        group_cols.append(kind.number_col)
    currency = func.max(JournalLine.currency_code)

    query = db.query(*group_cols, currency, net, fx_net).join(
        JournalEntry, JournalEntry.id == model.journal_entry_id
    )
    for target, onclause in kind.joins:
        query = query.join(target, onclause)
    query = (
        query.join(JournalLine, JournalLine.entry_id == JournalEntry.id)
        .filter(JournalLine.account_id == account_id)
        .filter(*kind.filters)
        .group_by(*group_cols)
    )
    if contact_id is not None:
        query = query.filter(kind.contact_col == contact_id)
    else:
        query = query.filter(kind.contact_col.isnot(None))
    if as_of is not None:
        query = query.filter(kind.date_col <= as_of)

    rows = []
    for row in query.all():
        values = list(row)
        source_id, doc_date, entry_number = values[0], values[1], values[2]
        number = values[3] if kind.number_col is not None else None
        currency_code, net_amount, fx_amount = values[-3], values[-2], values[-1]
        amount = Decimal(net_amount)
        if amount == 0:
            #: سندی که روی این معین اثرِ خالصِ صفر دارد قلمِ باز نیست. مثلاً
            #: فاکتورِ نقدی که اصلاً دریافتنی را لمس نمی‌کند.
            continue
        rows.append(
            {
                "source_type": kind.key,
                "source_id": source_id,
                "label": kind.label,
                "number": int(number) if number is not None else None,
                "entry_number": int(entry_number) if entry_number is not None else None,
                "document_date": doc_date,
                "side": "debit" if amount > 0 else "credit",
                "document_amount": abs(amount),
                "currency_code": currency_code,
                "fx_amount": abs(Decimal(fx_amount)) if fx_amount else None,
            }
        )
    return rows


def settled_amounts(db: Session, keys: list[tuple[str, UUID]]) -> dict[tuple[str, UUID], Decimal]:
    """مبلغِ تخصیص‌یافته‌ی هر سند — جمعِ تسویه‌های **باطل‌نشده**.

    تسویه‌ی برگشت‌خورده ردیف‌هایش سرِ جایشان می‌مانند ولی اینجا شمرده نمی‌شوند؛
    همین است معنیِ «آزادشدنِ تخصیص» در §۳۷.
    """
    if not keys:
        return {}
    source_ids = {source_id for _, source_id in keys}
    rows = (
        db.query(
            SettlementAllocation.source_type,
            SettlementAllocation.source_id,
            func.coalesce(func.sum(SettlementAllocation.amount), 0),
        )
        .join(Settlement, Settlement.id == SettlementAllocation.settlement_id)
        .filter(Settlement.voided_at.is_(None))
        .filter(SettlementAllocation.source_id.in_(source_ids))
        .group_by(SettlementAllocation.source_type, SettlementAllocation.source_id)
        .all()
    )
    wanted = set(keys)
    return {
        (source_type, source_id): Decimal(amount)
        for source_type, source_id, amount in rows
        if (source_type, source_id) in wanted
    }


def _status(document_amount: Decimal, settled: Decimal) -> str:
    if settled > document_amount:
        return OVER
    if settled <= 0:
        return UNSETTLED
    if settled >= document_amount:
        return SETTLED
    return PARTIAL


def open_items(
    db: Session,
    *,
    account_id: UUID,
    contact_id: UUID | None = None,
    as_of: date | None = None,
    only_open: bool = True,
    exclude_settlement_id: UUID | None = None,
) -> list[dict]:
    """اقلامِ یک طرف حساب روی یک معین، با مبلغ و تسویه‌شده و مانده‌ی قابلِ تسویه.

    `only_open=True` — حالتِ انتخابِ قلم در فرم — اقلامِ کاملاً تسویه‌شده را کنار
    می‌گذارد (§۳۳: سندی با مانده‌ی صفر نباید دوباره قابلِ تخصیص باشد). گزارشِ
    صورتِ اقلامِ باز با `False` همه را می‌خواهد تا وضعیت هم دیده شود.

    `exclude_settlement_id` برای **ویرایش** است: هنگام بازکردنِ یک تسویه‌ی موجود،
    تخصیص‌های خودش نباید مانده‌ی قلم را اشغال کنند، وگرنه کاربر نمی‌تواند همان
    مبلغی را که قبلاً داده بود دوباره بگذارد.
    """
    items: list[dict] = []
    for kind in SETTLEABLE.values():
        items.extend(_kind_effects(db, kind, account_id, contact_id, as_of))

    keys = [(item["source_type"], item["source_id"]) for item in items]
    settled = settled_amounts(db, keys)
    own = _own_allocations(db, exclude_settlement_id) if exclude_settlement_id else {}

    out = []
    for item in items:
        key = (item["source_type"], item["source_id"])
        item["settled_amount"] = settled.get(key, Decimal(0)) - own.get(key, Decimal(0))
        item["remaining_amount"] = item["document_amount"] - item["settled_amount"]
        item["status"] = _status(item["document_amount"], item["settled_amount"])
        if only_open and item["remaining_amount"] <= 0:
            continue
        out.append(item)

    #: قدیمی‌ترین اول — همان ترتیبی که حسابدار برای تخصیص انتظار دارد، و ترتیبِ
    #: پیش‌فرضِ «تخصیصِ خودکار» هم از همین می‌آید.
    out.sort(key=lambda row: (row["document_date"], row["entry_number"] or 0))
    return out


def _own_allocations(db: Session, settlement_id: UUID) -> dict[tuple[str, UUID], Decimal]:
    rows = (
        db.query(
            SettlementAllocation.source_type,
            SettlementAllocation.source_id,
            func.coalesce(func.sum(SettlementAllocation.amount), 0),
        )
        .filter(SettlementAllocation.settlement_id == settlement_id)
        .group_by(SettlementAllocation.source_type, SettlementAllocation.source_id)
        .all()
    )
    return {(t, i): Decimal(a) for t, i, a in rows}


def resolve_item(
    db: Session, *, account_id: UUID, contact_id: UUID, source_type: str, source_id: UUID
) -> dict:
    """یک قلمِ مشخص — با همان تعریفی که فهرست دارد.

    کلیدِ درستیِ §۱۴ همین است: کنترلِ «مبلغِ تسویه ≤ مانده‌ی قابلِ تسویه» باید با
    *همان* عددی انجام شود که به کاربر نشان داده شده، نه با محاسبه‌ی دوم.
    """
    kind = SETTLEABLE.get(source_type)
    if kind is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"نوعِ سندِ «{source_type}» قابلِ تسویه نیست")
    for item in _kind_effects(db, kind, account_id, contact_id, None):
        if item["source_id"] == source_id:
            return item
    raise HTTPException(
        status.HTTP_400_BAD_REQUEST,
        f"«{kind.label}» انتخاب‌شده روی این معین و این طرف حساب گردشی ندارد",
    )


# ─────────────────────────── ردیابی و سلامت ───────────────────────────


def allocation_history(db: Session, source_type: str, source_id: UUID) -> list[dict]:
    """تاریخچه‌ی تخصیص‌های یک سند (§۳۶) — نه فقط «تسویه‌شده: ۱۰۰».

    تسویه‌های باطل‌شده هم می‌آیند و علامت می‌خورند: «چرا مانده برگشت؟» بدونشان
    بی‌جواب می‌ماند.
    """
    rows = (
        db.query(SettlementAllocation, Settlement)
        .join(Settlement, Settlement.id == SettlementAllocation.settlement_id)
        .filter(
            SettlementAllocation.source_type == source_type,
            SettlementAllocation.source_id == source_id,
        )
        .order_by(Settlement.settlement_date, Settlement.number)
        .all()
    )
    out = []
    for allocation, settlement in rows:
        out.append(
            {
                "settlement_id": settlement.id,
                "number": settlement.number,
                "settlement_date": settlement.settlement_date,
                "side": allocation.side,
                "amount": Decimal(allocation.amount),
                "description": settlement.description,
                "voided": settlement.is_voided,
                #: سمتِ مقابلِ همان تسویه — جوابِ «با چه چیزی تسویه شد؟» (§۳۵).
                "counter_items": _counter_items(db, settlement, allocation.side),
            }
        )
    return out


def _counter_items(db: Session, settlement: Settlement, side: str) -> list[dict]:
    other = "credit" if side == "debit" else "debit"
    rows = (
        db.query(SettlementAllocation)
        .filter(
            SettlementAllocation.settlement_id == settlement.id,
            SettlementAllocation.side == other,
        )
        .order_by(SettlementAllocation.seq)
        .all()
    )
    return [
        {
            "source_type": row.source_type,
            "source_id": row.source_id,
            "label": SETTLEABLE[row.source_type].label if row.source_type in SETTLEABLE else row.source_type,
            "amount": Decimal(row.amount),
        }
        for row in rows
    ]


def active_allocation_total(db: Session, source_type: str, source_id: UUID) -> Decimal:
    """جمعِ تخصیص‌های *فعالِ* یک سند — گاردِ ابطالِ سندِ منبع (§۴۱) از این می‌خواند."""
    return settled_amounts(db, [(source_type, source_id)]).get((source_type, source_id), Decimal(0))


def over_allocated(db: Session) -> list[dict]:
    """سندهایی که تخصیصشان از مانده‌شان بیشتر شده (§۳۹ §۴۰).

    یعنی سندِ منبع **بعد از** تسویه کوچک شده یا باطل شده. کوبیتا نباید تخصیصِ
    نامعتبر را بی‌صدا نگه دارد؛ این تابع پیدایشان می‌کند تا «بررسی یکپارچگی»
    نشانشان بدهد و کاربر تسویه را برگرداند و درست ثبت کند.
    """
    rows = (
        db.query(
            SettlementAllocation.source_type,
            SettlementAllocation.source_id,
            func.coalesce(func.sum(SettlementAllocation.amount), 0),
        )
        .join(Settlement, Settlement.id == SettlementAllocation.settlement_id)
        .filter(Settlement.voided_at.is_(None))
        .group_by(SettlementAllocation.source_type, SettlementAllocation.source_id)
        .all()
    )
    if not rows:
        return []

    #: مبلغِ واقعیِ هر سند، دوباره از دفتر. تسویه هر دو معین را می‌تواند لمس کند،
    #: پس هر دو خوانده می‌شوند و بزرگ‌ترین اثر مبناست.
    eligible: dict[tuple[str, UUID], Decimal] = {}
    for account in counterparty_accounts(db):
        for kind in SETTLEABLE.values():
            for item in _kind_effects(db, kind, account.id, None, None):
                key = (item["source_type"], item["source_id"])
                eligible[key] = max(eligible.get(key, Decimal(0)), item["document_amount"])

    out = []
    for source_type, source_id, allocated in rows:
        key = (source_type, source_id)
        amount = Decimal(allocated)
        available = eligible.get(key, Decimal(0))
        if amount > available:
            out.append(
                {
                    "source_type": source_type,
                    "source_id": source_id,
                    "label": SETTLEABLE[source_type].label if source_type in SETTLEABLE else source_type,
                    "allocated": amount,
                    "eligible": available,
                    "excess": amount - available,
                }
            )
    return out


def ledger_balance(db: Session, account_id: UUID, as_of: date | None = None) -> Decimal:
    """ماندهٔ خامِ یک معین از خودِ دفتر — مبنای سنجشِ کاملیِ اقلامِ باز."""
    query = db.query(
        func.coalesce(func.sum(JournalLine.debit - JournalLine.credit), 0)
    ).filter(JournalLine.account_id == account_id)
    if as_of is not None:
        query = query.join(JournalEntry, JournalEntry.id == JournalLine.entry_id).filter(
            JournalEntry.entry_date <= as_of
        )
    return Decimal(query.scalar() or 0)


def unattributed(db: Session, account_id: UUID, as_of: date | None = None) -> Decimal:
    """گردشی که سندِ قابلِ تسویه‌ای پشتش نیست.

    سه منبعِ شناخته‌شده دارد و هر سه واقعی‌اند:

    * **سندِ دستی** روی دریافتنی/پرداختنی — لنگرِ سندِ منبع ندارد.
    * **ماندهٔ اول دوره** — از سندِ افتتاحیه می‌آید، نه از فاکتور.
    * **چکِ پیش از مهاجرتِ ۰۱۱۰** — `Check` ستونِ `journal_entry_id` ندارد و
      تاریخچه‌اش هم backfill نشد (جعلِ سابقه می‌شد)، پس هیچ راهی از دفتر به آن
      نیست. چک‌های تازه از راهِ `CheckEvent` دیده می‌شوند.

    نشان‌دادنش عمدی است: بدونِ آن، بخشی از ماندهٔ مشتری در «اقلامِ باز» ناپدید
    می‌شد و کاربر فرق دو عدد را نمی‌فهمید.
    """
    items = open_items(db, account_id=account_id, as_of=as_of, only_open=False)
    attributed = sum(
        (item["document_amount"] if item["side"] == "debit" else -item["document_amount"])
        for item in items
    )
    return ledger_balance(db, account_id, as_of) - Decimal(attributed)


def contact_name(db: Session, contact_id: UUID) -> str:
    contact = db.get(Contact, contact_id)
    return contact.name if contact is not None else "—"
