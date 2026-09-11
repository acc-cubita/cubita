"""رسید دریافت — یک رویداد، چند ابزار، **یک** سند.

تا مهاجرتِ ۰۱۰۹ رسید سربرگ نداشت، پس `TreasuryTransaction.method` عملاً می‌گفت
«یک رسید، یک ابزار». حالا سربرگ بالای اجزا نشسته و هر جزء همان چیزی مانده که بود:
نقد و حواله و کارت‌خوان یک `TreasuryTransaction`اند، چک یک `Check` با چرخه‌ی عمرِ
مستقلِ خودش (§۱۰ §۱۳).

**سند یکی است** (§۳۰ §۳۱). سربرگ می‌سازدش: به‌ازای هر جزء یک ردیفِ بدهکار با
حسابِ *ماهیتِ خودش* (§۳۳) — صندوق، بانک، چک‌های دریافتنی — و یک ردیفِ بستانکار
روی حسابِ طرفِ مقابل. اجزا همان `journal_entry_id` را به اشتراک می‌گذارند؛
`entry_source._ref` از قبل `count` دارد و چند ردیف به یک سند را می‌فهمد.

**هیچ حسابی این‌جا با کد پیدا نمی‌شود.** همه با `get_account(db, system_role)`،
چون کدِ حساب مالِ مشتری است و عوض می‌شود ولی نقش نه (§۵ §۳۳).
"""
from __future__ import annotations

from datetime import date as date_, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.accounting import Account, JournalEntry, JournalLine
from app.models.banking import BankAccount, Check
from app.models.cashbox import Cashbox
from app.models.counters import DOC_RECEIPT
from app.models.inventory import Contact
from app.models.pos_terminal import PosTerminal
from app.models.currency import Currency
from app.models.invoices import SalesInvoice
from app.models.receipt import RECEIPT_TYPES, Receipt, ReceiptRelatedDocument
from app.models.treasury import TreasuryTransaction
from app.models.user import User
from app.schemas.banking import CheckIn
from app.schemas.receipts import ReceiptCashIn, ReceiptIn, ReceiptTransferIn
from app.services import bank_accounts, card_terminals, cashboxes, check_ops
from app.services import chart_codes as cc
from app.services.common import get_account, make_journal_entry
from app.services.numbering import next_document_number
from app.services.period_close import assert_period_open
from app.services.voiding import reverse_journal_entry

RECEIPT_TYPE_LABELS = {
    "customer": "دریافت از مشتری",
    "supplier": "دریافت از تأمین‌کننده",
    "intermediary": "دریافت از واسط",
    "other": "سایر دریافت‌ها",
    "petty_holder": "دریافت از تنخواه‌دار",
}

#: §۲ — نوعِ دریافت فقط برچسب نیست: تعیین می‌کند کدام حساب بستانکار شود.
#:
#: **این یک اشکالِ واقعی را هم می‌بندد:** تا امروز هر رسیدی — حتی برگشتِ پول از
#: تأمین‌کننده — «حساب‌های دریافتنی» را بستانکار می‌کرد. پیش‌فرضِ `customer`
#: دقیقاً رفتارِ امروز است، پس هیچ داده‌ی مستقری معنایش عوض نمی‌شود؛ فقط
#: انتخاب‌های تازه درست ثبت می‌شوند.
COUNTERPARTY_ROLE = {
    "customer": cc.ACCOUNTS_RECEIVABLE,
    "supplier": cc.ACCOUNTS_PAYABLE,
    "intermediary": cc.ACCOUNTS_RECEIVABLE,
    "other": cc.ACCOUNTS_RECEIVABLE,
    #: تنخواه‌دار پولِ خرج‌نشده را برمی‌گرداند، پس حسابِ تنخواه بستانکار می‌شود.
    #: منطقِ کاملِ گردشِ تنخواه این‌جا نیست و نباید باشد (§۱۹) — همان صفحه‌های
    #: «تنخواه‌دار» و «صورت هزینه تنخواه» جای خودشان می‌مانند.
    "petty_holder": cc.PETTY_CASH,
}

KIND_LABELS = {"cash": "وجه نقد", "transfer": "حواله", "cheque": "چک", "card": "کارت‌خوان"}
#: ترتیبِ ثابتِ نمایش — تا «اقلام» در فهرست همیشه یک شکل خوانده شود (§۳۵).
KIND_ORDER = ("cash", "transfer", "cheque", "card")


def type_label(receipt_type: str) -> str:
    return RECEIPT_TYPE_LABELS.get(receipt_type, receipt_type)


def _money(value) -> Decimal:
    """مبلغِ ارزِ پایه در کوبیتا واحدِ کامل است (`Numeric(18, 0)`)."""
    return Decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def _base(value: Decimal, rate: Decimal) -> Decimal:
    return _money(Decimal(value) * Decimal(rate))


def _postable_account(db: Session, account_id: UUID, label: str) -> Account:
    """حسابی که واقعاً می‌شود رویش سند زد.

    حسابِ گروه ردیف نمی‌پذیرد و حسابِ غیرفعال نباید انتخاب شود؛ هر دو خطای
    انتخابِ کاربرند نه حالتِ ممکن.
    """
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{label} یافت نشد")
    if account.is_group:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{label} حسابِ گروه است و سند نمی‌پذیرد")
    if not account.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{label} غیرفعال است")
    return account


def _assert_currency(actual: str, expected: str, label: str) -> None:
    """ارزِ ابزار باید با ارزِ سند بخواند — مثلِ گاردِ کارت‌خوان در فصلِ قبل.

    **رد می‌شود، نه هشدار.** هیچ گزارشی در کوبیتا بینِ دو ارز جمع نمی‌زند، پس
    صندوقِ دلاری داخلِ رسیدِ ریالی عددی می‌سازد که هیچ‌جا درست خوانده نمی‌شود.
    """
    if (actual or "IRR") != expected:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"ارزِ {label} ({actual}) با ارزِ رسید ({expected}) نمی‌خواند",
        )


def _assert_currency_known(db: Session, code: str, rate: Decimal) -> None:
    """§۹ — از موتورِ ارزِ خودِ کوبیتا استفاده کن، موتورِ دومِ رسید نساز."""
    if code == "IRR":
        if Decimal(rate) != 1:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "نرخ ارز پایه (ریال) باید یک باشد")
        return
    if db.query(Currency.id).filter(Currency.code == code).first() is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"ارز «{code}» در موتور ارز Cubita تعریف نشده است",
        )


# ───────────────────────────── ساخت ─────────────────────────────


def _counterparty_account(db: Session, receipt_type: str):
    role = COUNTERPARTY_ROLE.get(receipt_type)
    if role is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "نوع رسید معتبر نیست")
    return get_account(db, role)


def assert_reference_free(db: Session, reference_no: str) -> None:
    """شماره‌ی مرجع (کد پیگیریِ کارت یا شماره‌ی حواله) تکراری نباشد.

    ایندکسِ `uq_treasury_tenant_reference` از قبل در سطحِ پایگاه‌داده این را
    می‌گیرد؛ این‌جا فقط زودتر و با پیامِ فارسی می‌شکنیم تا کاربر بداند کدام عدد
    مقصر است، نه یک خطای خامِ پستگرس.
    """
    ref = (reference_no or "").strip()
    if not ref:
        return
    twin = db.query(TreasuryTransaction).filter(TreasuryTransaction.reference_no == ref).first()
    if twin is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"شماره‌ی مرجع {ref} قبلاً روی یک دریافتِ دیگر ثبت شده است",
        )


def _component_rows(
    db: Session, data: ReceiptIn, user: User, rate: Decimal
) -> tuple[list[dict], list[JournalLine], Decimal, Decimal]:
    """اجزا را می‌سنجد و برای هرکدام یک ردیفِ بدهکار می‌سازد (§۳۳).

    خروجی: (نقشه‌ی ساختِ ردیف‌ها، ردیف‌های سند، جمع به ارزِ سند، جمع به ارزِ پایه).
    ردیف‌های پایگاه‌داده این‌جا ساخته **نمی‌شوند** چون شناسه‌ی سربرگ و سند هنوز
    وجود ندارند و چیزی نباید نیمه‌ساخته `flush` شود.
    """
    pending: list[dict] = []
    lines: list[JournalLine] = []
    document_total = Decimal(0)
    base_total = Decimal(0)

    for row in data.cash:
        box = cashboxes.resolve_cashbox(db, row.cashbox_id)
        cashboxes.assert_usable(db, box, data.receipt_date)
        _assert_currency(box.currency_code, data.currency_code, f"صندوق «{box.name}»")
        amount = _base(row.amount, rate)
        document_total += row.amount
        base_total += amount
        lines.append(
            JournalLine(
                account_id=cashboxes.gl_account_id(db, box),
                analytic_id=box.analytic_id,
                debit=amount,
                credit=0,
                description=row.description or f"دریافت نقدی — {box.name}",
            )
        )
        pending.append(
            {
                "kind": "cash",
                "txn": {
                    "method": "cash",
                    "cashbox_id": box.id,
                    "amount": amount,
                    "description": row.description,
                },
            }
        )

    for row in data.transfers:
        bank = bank_accounts.resolve(db, row.bank_account_id)
        bank_accounts.assert_usable(db, bank, data.receipt_date)
        _assert_currency(bank.currency_code, data.currency_code, f"حساب «{bank.name}»")
        assert_reference_free(db, row.reference_no)
        amount = _base(row.amount, rate)
        document_total += row.amount
        base_total += amount
        lines.append(
            JournalLine(
                account_id=bank.gl_account_id,
                analytic_id=bank.analytic_id,
                debit=amount,
                credit=0,
                description=row.description or f"حواله به {bank.name}",
                #: شماره‌ی حواله روی ردیفِ سند هم می‌نشیند — مغایرتِ بانکی از
                #: همین‌جا پیدایش می‌کند، نه از متنِ شرح.
                tracking_no=(row.reference_no or "").strip() or None,
                tracking_date=data.receipt_date,
            )
        )
        pending.append(
            {
                "kind": "transfer",
                "txn": {
                    "method": "bank",
                    "bank_account_id": bank.id,
                    "amount": amount,
                    "reference_no": (row.reference_no or "").strip() or None,
                    "description": row.description,
                },
            }
        )

    for row in data.cards:
        term = card_terminals.resolve(db, row.pos_terminal_id)
        card_terminals.assert_usable(db, term, data.receipt_date)
        bank = card_terminals.settlement_account(db, term)
        card_terminals.assert_currency_match(db, term.currency_code, bank.id)
        _assert_currency(term.currency_code, data.currency_code, f"دستگاه «{term.label or term.terminal_no}»")
        assert_reference_free(db, row.reference_no)
        amount = _base(row.amount, rate)
        document_total += row.amount
        base_total += amount
        lines.append(
            JournalLine(
                account_id=bank.gl_account_id,
                analytic_id=bank.analytic_id,
                debit=amount,
                credit=0,
                description=row.description or f"کارت‌خوان {term.label or term.terminal_no}",
                tracking_no=row.reference_no,
                tracking_date=data.receipt_date,
            )
        )
        pending.append(
            {
                "kind": "card",
                "txn": {
                    "method": "bank",
                    "bank_account_id": bank.id,
                    "amount": amount,
                    "paid_via": card_terminals.PAID_VIA_TERMINAL,
                    "reference_no": row.reference_no,
                    "trace_no": row.trace_no or None,
                    "card_mask": row.card_mask or None,
                    "pos_terminal_id": term.id,
                    "terminal_no": term.terminal_no or None,
                    "psp": term.psp or None,
                    "description": row.description,
                },
            }
        )

    if data.cheques:
        cheque_account = get_account(db, cc.CHECKS_RECEIVABLE)
        for row in data.cheques:
            amount = _base(row.amount, rate)
            document_total += row.amount
            base_total += amount
            cheque_in = CheckIn(
                type="receivable",
                number=row.number,
                bank_name=row.bank_name,
                amount=amount,
                issue_date=row.issue_date or data.receipt_date,
                due_date=row.due_date,
                contact_id=data.contact_id,
                description=row.description,
                description2=row.description2,
                sayad_id=row.sayad_id,
                back_number=row.back_number,
                branch_name=row.branch_name,
                branch_code=row.branch_code,
                account_number=row.account_number,
                owner_name=row.owner_name,
            )
            #: ردیفِ چک این‌جا ساخته می‌شود ولی **سندِ جدا نمی‌زند** — اثرش در
            #: همین سندِ رسید است. `new_check_row` همان گاردهای مسیرِ مستقیم را
            #: اجرا می‌کند (برگ، صیادی)، تا دو مسیر یکسان بسنجند.
            check = check_ops.new_check_row(db, cheque_in, user)
            lines.append(
                JournalLine(
                    account_id=cheque_account.id,
                    debit=amount,
                    credit=0,
                    description=row.description or f"چک شماره {row.number}",
                    tracking_no=row.number,
                    tracking_date=row.due_date,
                )
            )
            pending.append({"kind": "cheque", "check": check})

    return pending, lines, document_total, base_total


def _validate_related_documents(db: Session, data: ReceiptIn, contact: Contact, rate: Decimal) -> None:
    """§۲۰ — پیوند باید واقعی باشد، و تخصیص از جمعِ تسویه بیشتر نشود.

    **این تسویه‌ی فاکتور‌به‌فاکتور نیست.** مانده‌ی طرف‌حساب و گزارشِ سنی همچنان
    در سطحِ شخص حساب می‌شوند؛ عوض‌کردنش تصمیمِ فصلِ تسویه است. این‌جا فقط
    نمی‌گذاریم پیوندی ثبت شود که از همان روزِ اول با واقعیت نمی‌خواند.
    """
    if not data.related_documents:
        return
    allocated = sum((Decimal(r.allocated_amount) for r in data.related_documents), Decimal(0))
    settlement = sum(
        (Decimal(r.amount) for r in (*data.cash, *data.transfers, *data.cards, *data.cheques)), Decimal(0)
    ) + Decimal(data.discount_amount)
    if allocated > settlement:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "جمع تخصیص اسناد مرتبط از جمع تسویه بیشتر است")
    for related in data.related_documents:
        if related.document_type != "sales_invoice":
            continue
        invoice = db.get(SalesInvoice, related.document_id)
        if invoice is None or invoice.is_voided:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "فاکتور فروش مرتبط معتبر نیست")
        if invoice.contact_id != contact.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "مشتریِ رسید با مشتریِ فاکتور فروش یکسان نیست")
        previously = Decimal(
            db.query(
                func.coalesce(func.sum(ReceiptRelatedDocument.allocated_amount * Receipt.exchange_rate), 0)
            )
            .join(Receipt, Receipt.id == ReceiptRelatedDocument.receipt_id)
            .filter(
                ReceiptRelatedDocument.document_type == "sales_invoice",
                ReceiptRelatedDocument.document_id == invoice.id,
                Receipt.voided_at.is_(None),
            )
            .scalar()
        )
        invoice_total = Decimal(invoice.total_amount) + Decimal(invoice.tax_amount)
        if previously + _base(related.allocated_amount, rate) > invoice_total:
            raise HTTPException(status.HTTP_409_CONFLICT, "تخصیص رسید از مانده فاکتور فروش بیشتر است")


def create_receipt(db: Session, data: ReceiptIn, user: User) -> Receipt:
    """رسیدِ دریافت با یک تا چند ابزار (§۶) و یک سند (§۳۰)."""
    assert_period_open(db, data.receipt_date)

    contact = db.get(Contact, data.contact_id)
    if contact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "طرف حساب یافت نشد")

    rate = Decimal(data.exchange_rate)
    _assert_currency_known(db, data.currency_code, rate)

    pending, debit_lines, document_total, base_total = _component_rows(db, data, user, rate)
    if base_total <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "مبلغ دریافت باید بزرگ‌تر از صفر باشد")

    _validate_related_documents(db, data, contact, rate)

    discount_base = _base(data.discount_amount, rate)
    discount_account = None
    if discount_base:
        discount_account = _postable_account(db, data.discount_account_id, "حساب تخفیف")
        #: §۲۳ — تخفیف **دریافتِ نقدی نیست**: پولی وارد صندوق نشده. پس ردیفِ
        #: بدهکارِ جدا می‌گیرد و فقط مطالبه را می‌بندد.
        debit_lines.append(
            JournalLine(
                account_id=discount_account.id, debit=discount_base, credit=0, description="تخفیف تسویه"
            )
        )

    counterparty = _counterparty_account(db, data.receipt_type)
    description = data.description.strip() or f"{type_label(data.receipt_type)} — {contact.name}"

    entry = make_journal_entry(
        db,
        data.receipt_date,
        description,
        "receipt",
        user,
        [
            *debit_lines,
            JournalLine(
                account_id=counterparty.id,
                #: تفصیلیِ طرف‌حساب روی سمتِ مقابل — همان کاری که سمتِ پرداخت
                #: می‌کند. بدونش دفترِ تفصیلیِ دریافتنی گردشِ رسید را نمی‌بیند.
                analytic_id=contact.analytic_id,
                debit=0,
                credit=base_total + discount_base,
                description=description,
            ),
        ],
    )

    receipt = Receipt(
        number=next_document_number(db, DOC_RECEIPT),
        receipt_type=data.receipt_type,
        contact_id=contact.id,
        receipt_date=data.receipt_date,
        counterparty_account_id=counterparty.id,
        discount_account_id=discount_account.id if discount_account else None,
        currency_code=data.currency_code,
        exchange_rate=rate,
        receipt_amount=document_total,
        base_currency_amount=base_total,
        discount_amount=data.discount_amount,
        settlement_total=document_total + Decimal(data.discount_amount),
        description=description,
        description2=data.description2,
        establishment=data.establishment,
        journal_entry_id=entry.id,
        created_by_id=user.id,
    )
    db.add(receipt)
    db.flush()

    for item in pending:
        if item["kind"] == "cheque":
            check = item["check"]
            check.receipt_id = receipt.id
            db.add(check)
            continue
        db.add(
            TreasuryTransaction(
                type="receipt",
                transaction_date=data.receipt_date,
                contact_id=contact.id,
                receipt_id=receipt.id,
                journal_entry_id=entry.id,
                created_by_id=user.id,
                **item["txn"],
            )
        )

    for related in data.related_documents:
        db.add(
            ReceiptRelatedDocument(
                receipt_id=receipt.id,
                document_type=related.document_type,
                document_id=related.document_id,
                allocated_amount=related.allocated_amount,
            )
        )

    db.flush()
    db.refresh(receipt)
    return receipt


# ───────────────────────────── خواندن ─────────────────────────────


def treasury_components(db: Session, receipt_id: UUID) -> list[TreasuryTransaction]:
    return (
        db.query(TreasuryTransaction)
        .filter(TreasuryTransaction.receipt_id == receipt_id)
        .order_by(TreasuryTransaction.created_at, TreasuryTransaction.id)
        .all()
    )


def cheque_components(db: Session, receipt_id: UUID) -> list[Check]:
    return (
        db.query(Check)
        .filter(Check.receipt_id == receipt_id)
        .order_by(Check.due_date, Check.id)
        .all()
    )


def _txn_kind(txn: TreasuryTransaction) -> str:
    if txn.paid_via == card_terminals.PAID_VIA_TERMINAL:
        return "card"
    return "cash" if txn.method == "cash" else "transfer"


def components(db: Session, receipt: Receipt) -> list[dict]:
    """اجزای رسید با یک شکلِ مشترک — همان چیزی که §۲۴ «قابلِ توضیح» می‌خواندش."""
    rows: list[dict] = []
    for txn in treasury_components(db, receipt.id):
        kind = _txn_kind(txn)
        if kind == "cash":
            box = db.get(Cashbox, txn.cashbox_id) if txn.cashbox_id else None
            label = box.name if box else "صندوق پیش‌فرض"
        else:
            bank = db.get(BankAccount, txn.bank_account_id) if txn.bank_account_id else None
            label = bank.name if bank else "حساب بانکی"
            if kind == "card":
                term = db.get(PosTerminal, txn.pos_terminal_id) if txn.pos_terminal_id else None
                label = (term.label if term else None) or txn.terminal_no or label
        rows.append(
            {
                "kind": kind,
                "label": label,
                "amount": txn.amount,
                "description": txn.description or "",
                "source_id": txn.id,
                "reference_no": txn.reference_no or "",
                "due_date": None,
                "status": "تسویه‌شده" if txn.settled_at else "",
            }
        )
    for check in cheque_components(db, receipt.id):
        rows.append(
            {
                "kind": "cheque",
                "label": check.bank_name or "چک",
                "amount": check.amount,
                "description": check.description or "",
                "source_id": check.id,
                "reference_no": check.number,
                "due_date": check.due_date,
                "status": check.status,
            }
        )
    rows.sort(key=lambda r: KIND_ORDER.index(r["kind"]))
    return rows


def summary_label(rows: list[dict]) -> str:
    """§۳۵ — «وجه نقد، حواله، چک». **مشتق**، نه متنی که کاربر تایپ کند."""
    seen = [k for k in KIND_ORDER if any(r["kind"] == k for r in rows)]
    return "، ".join(KIND_LABELS[k] for k in seen)


def related_documents(db: Session, receipt_id: UUID) -> list[dict]:
    rows = (
        db.query(ReceiptRelatedDocument)
        .filter(ReceiptRelatedDocument.receipt_id == receipt_id)
        .order_by(ReceiptRelatedDocument.created_at)
        .all()
    )
    return [
        {
            "document_type": r.document_type,
            "document_id": r.document_id,
            "allocated_amount": r.allocated_amount,
        }
        for r in rows
    ]


def to_out(db: Session, receipt: Receipt) -> dict:
    rows = components(db, receipt)
    creator = db.get(User, receipt.created_by_id)
    editor = db.get(User, receipt.updated_by_id) if receipt.updated_by_id else None
    return {
        "id": receipt.id,
        "number": int(receipt.number),
        "receipt_type": receipt.receipt_type,
        "receipt_type_label": type_label(receipt.receipt_type),
        "contact_id": receipt.contact_id,
        "contact_name": receipt.contact.name if receipt.contact else "",
        "receipt_date": receipt.receipt_date,
        "counterparty_account_id": receipt.counterparty_account_id,
        "discount_account_id": receipt.discount_account_id,
        "currency_code": receipt.currency_code,
        "exchange_rate": receipt.exchange_rate,
        "receipt_amount": receipt.receipt_amount,
        "base_currency_amount": receipt.base_currency_amount,
        "discount_amount": receipt.discount_amount,
        "settlement_total": receipt.settlement_total,
        "description": receipt.description,
        "description2": receipt.description2,
        "establishment": receipt.establishment,
        "journal_entry_id": receipt.journal_entry_id,
        "items_summary": summary_label(rows),
        "components": rows,
        "related_documents": related_documents(db, receipt.id),
        "voided_at": receipt.voided_at,
        "created_at": receipt.created_at,
        "updated_at": receipt.updated_at,
        "created_by_name": creator.name if creator else "",
        "updated_by_name": editor.name if editor else "",
    }


def create_single_instrument(db: Session, data, user: User) -> TreasuryTransaction:
    """رسیدِ تک‌ابزاری از قراردادِ قدیمیِ `TreasuryTransactionIn`.

    اپِ موبایل و صفِ آفلاین همین شکل را می‌فرستند و نباید بشکنند. پس بدنه و
    پاسخ دست‌نخورده می‌مانند و فقط پشتِ صحنه یک سربرگ هم ساخته می‌شود — وگرنه
    رسیدِ موبایل شماره نمی‌گرفت و در دفترِ رسیدها دیده نمی‌شد، یعنی دو جور داده
    برای یک رویداد.

    `receipt_type` این‌جا همیشه `customer` است: قراردادِ قدیمی نوعی نمی‌فرستد و
    همین **دقیقاً** رفتارِ امروز است (بستانکارِ حساب‌های دریافتنی).
    """
    payload = ReceiptIn(
        receipt_type="customer",
        contact_id=data.contact_id,
        receipt_date=data.transaction_date,
        description=data.description,
        cash=(
            [ReceiptCashIn(amount=data.amount, cashbox_id=data.cashbox_id, description=data.description)]
            if data.method == "cash"
            else []
        ),
        transfers=(
            [
                ReceiptTransferIn(
                    amount=data.amount,
                    bank_account_id=data.bank_account_id,
                    description=data.description,
                )
            ]
            if data.method == "bank"
            else []
        ),
    )
    receipt = create_receipt(db, payload, user)
    txn = (
        db.query(TreasuryTransaction)
        .filter(TreasuryTransaction.receipt_id == receipt.id)
        .order_by(TreasuryTransaction.created_at)
        .first()
    )
    if txn is None:  # pragma: no cover - ساختِ رسید همیشه یک جزء می‌سازد
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "جزءِ رسید ساخته نشد")
    return txn


def receipts_query(db: Session):
    return db.query(Receipt)


def resolve(db: Session, receipt_id: UUID) -> Receipt:
    receipt = db.get(Receipt, receipt_id)
    if receipt is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "رسید یافت نشد")
    return receipt


# ───────────────────────────── ابطال ─────────────────────────────


def _guard_components_untouched(db: Session, receipt: Receipt) -> None:
    """جزئی که اثرِ بعدی گرفته، با ابطالِ رسید برنمی‌گردد.

    دو حالت، و هر دو یعنی پول یا تعهد جای دیگری رفته:

    * **چکی که دیگر «نزد شرکت» نیست** — واگذار، وصول، خرج یا برگشت شده. هرکدام
      سندِ خودش را زده و ابطالِ رسید آن را نمی‌داند.
    * **کارتی که تسویه شده** — کارمزدش ثبت و ردیفِ بانکی‌اش ساخته شده.

    پس به‌جای اینکه بی‌صدا نصفه ابطال کنیم، می‌گوییم اول کدام را برگرداند.
    """
    for check in cheque_components(db, receipt.id):
        if check.voided_at is not None:
            continue
        if check.status != "in_hand":
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"چکِ شماره‌ی {check.number} دیگر نزد شرکت نیست (وضعیت: {check.status})؛ "
                "اول وضعیتِ چک را برگردانید، بعد رسید را باطل کنید",
            )
    for txn in treasury_components(db, receipt.id):
        if txn.settled_at is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "جزءِ کارت‌خوانِ این رسید تسویه شده است؛ اول تسویه را برگردانید",
            )


def void_receipt(
    db: Session,
    receipt_id: UUID,
    *,
    reason: str,
    user: User,
    void_date: date_ | None = None,
) -> JournalEntry:
    """رسید را باطل می‌کند — با سندِ معکوس، نه با حذف.

    همان فلسفه‌ی `voiding.py`: دفتر باید نشان دهد چه شد و بعد چطور اصلاح شد.
    تا امروز رسیدِ اشتباه **هیچ** راهِ اصلاحی نداشت؛ نه حذف بود نه ابطال، و
    `void_journal_entry` سندِ غیر‌دستی را رد می‌کند.

    ویرایش عمداً ساخته نشد: در کوبیتا هر رسید بلافاصله سند می‌زند، پس حالتِ
    «هنوز اثر رسمی ندارد» که §۳۹ ویرایش را مشروط به آن می‌کند هرگز پیش نمی‌آید.
    اصلاح = ابطال + ثبتِ دوباره، و «تکثیر» ثبتِ دوباره را یک کلیک می‌کند.
    """
    receipt = resolve(db, receipt_id)
    if receipt.voided_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "این رسید قبلاً باطل شده است")

    on = void_date or receipt.receipt_date
    assert_period_open(db, on)
    _guard_components_untouched(db, receipt)

    entry = db.get(JournalEntry, receipt.journal_entry_id)
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "سندِ این رسید یافت نشد")

    reversal = reverse_journal_entry(
        db,
        entry,
        void_date=on,
        user=user,
        description=f"ابطال رسید دریافت شماره {int(receipt.number)}",
    )

    #: `reversal.created_at` بعد از `flush` هنوز `None` است (server_default است و
    #: تا `refresh` خوانده نمی‌شود)، پس لحظه را خودمان می‌گیریم — وگرنه
    #: `voided_at` خالی می‌ماند و «باطل است یا نه» بی‌صدا غلط می‌شود.
    stamp = {"voided_at": datetime.now(timezone.utc), "void_reason": reason, "voided_by_id": user.id}
    for txn in treasury_components(db, receipt.id):
        for field, value in stamp.items():
            setattr(txn, field, value)
    for check in cheque_components(db, receipt.id):
        for field, value in stamp.items():
            setattr(check, field, value)
    for field, value in stamp.items():
        setattr(receipt, field, value)

    db.flush()
    return reversal


# ───────────────────────────── تکثیر ─────────────────────────────

#: §۳۷ — شناسه‌هایی که هرگز کپی نمی‌شوند. هرکدام یک هویتِ یکتای بیرونی است و
#: کپی‌شدنشان یعنی یا خطای یکتایی یا — بدتر — دو رکوردِ مالی با یک هویت.
NEVER_DUPLICATED = ("شماره‌ی چک", "کد صیادی", "کد پیگیری", "شماره‌ی حواله", "پیوندِ سند")


def duplicate_draft(db: Session, receipt_id: UUID) -> dict:
    """پیش‌نویسِ یک رسیدِ تازه از روی یکی موجود — **بدونِ نوشتن** در پایگاه‌داده.

    مبالغ و ساختار کپی می‌شوند؛ شناسه‌های یکتا **نه** (§۳۷). تاریخ هم کپی
    نمی‌شود: رسیدِ تازه رویدادِ امروز است، نه تکرارِ روزِ قبل.
    """
    receipt = resolve(db, receipt_id)
    draft: dict = {
        "receipt_type": receipt.receipt_type,
        "contact_id": receipt.contact_id,
        "currency_code": receipt.currency_code,
        "exchange_rate": receipt.exchange_rate,
        "discount_amount": receipt.discount_amount,
        "discount_account_id": receipt.discount_account_id,
        "establishment": receipt.establishment,
        "description": receipt.description,
        "description2": receipt.description2,
        "cash": [],
        "transfers": [],
        "cards": [],
        "cheques": [],
        #: اسناد مرتبط عمداً کپی نمی‌شوند: تخصیصِ رسیدِ قبلی به یک فاکتور مالِ
        #: همان رسید است و تکرارش یعنی همان فاکتور دوبار تسویه‌شده به‌نظر برسد.
        "related_documents": [],
        "cleared_fields": list(NEVER_DUPLICATED),
    }
    for txn in treasury_components(db, receipt.id):
        kind = _txn_kind(txn)
        if kind == "cash":
            draft["cash"].append({"cashbox_id": txn.cashbox_id, "amount": txn.amount, "description": txn.description})
        elif kind == "transfer":
            draft["transfers"].append(
                {
                    "bank_account_id": txn.bank_account_id,
                    "amount": txn.amount,
                    "reference_no": "",
                    "description": txn.description,
                }
            )
        else:
            draft["cards"].append(
                {
                    "pos_terminal_id": txn.pos_terminal_id,
                    "amount": txn.amount,
                    "reference_no": "",
                    "trace_no": "",
                    "card_mask": "",
                    "description": txn.description,
                }
            )
    for check in cheque_components(db, receipt.id):
        draft["cheques"].append(
            {
                "number": "",
                "sayad_id": "",
                "back_number": "",
                "amount": check.amount,
                "due_date": check.due_date,
                "bank_name": check.bank_name,
                "branch_name": check.branch_name,
                "branch_code": check.branch_code,
                "account_number": check.account_number,
                "owner_name": check.owner_name,
                "description": check.description,
                "description2": check.description2,
            }
        )
    return draft


# ───────────────────────────── راس‌گیری ─────────────────────────────


def weighted_maturity(
    rows: list[tuple[Decimal, date_]],
    base_date: date_,
    *,
    include_same_day: bool = True,
) -> dict:
    """تاریخِ متوسطِ وزنیِ مجموعه‌ی دریافتی‌ها — «راس» (§۲۷ §۲۸).

    فرمول یک‌بار این‌جا تعریف می‌شود و هیچ‌جای دیگر تکرار نمی‌شود؛ خودِ فصل
    صریحاً هشدار می‌دهد که چند نسخه‌ی متفاوت از این فرمول نسازیم.

        راس = تاریخِ مبنا + Σ(مبلغ × فاصله‌ی روز) ÷ Σ(مبلغ)

    **هیچ ردیفی نمی‌نویسد.** راس یک محاسبه است نه تراکنش — پس نه سند می‌زند نه
    چیزی ذخیره می‌کند.

    `include_same_day=False` قلم‌هایی را که سررسیدشان **همان** تاریخِ مبناست کنار
    می‌گذارد: آن‌ها عملاً نقدند و میانگین را بی‌دلیل به صفر می‌کشند. اگر همه‌ی
    قلم‌ها هم‌تاریخ باشند، کنارگذاشتنشان چیزی باقی نمی‌گذارد — آن‌وقت راس همان
    تاریخِ مبناست، نه خطا.
    """
    counted: list[tuple[Decimal, int]] = []
    skipped = 0
    for amount, due in rows:
        days = (due - base_date).days
        if days == 0 and not include_same_day:
            skipped += 1
            continue
        counted.append((Decimal(amount), days))

    total = sum((amount for amount, _ in counted), Decimal(0))
    if total <= 0:
        return {
            "ras_date": base_date,
            "average_days": Decimal(0),
            "total_amount": Decimal(0),
            "counted_rows": 0,
            "skipped_rows": skipped + len(counted),
        }

    weighted = sum((amount * days for amount, days in counted), Decimal(0))
    average = weighted / total
    return {
        "ras_date": base_date + _round_days(average),
        "average_days": average.quantize(Decimal("0.01")),
        "total_amount": total,
        "counted_rows": len(counted),
        "skipped_rows": skipped,
    }


def _round_days(average: Decimal) -> timedelta:
    return timedelta(days=int(average.to_integral_value(rounding=ROUND_HALF_UP)))


__all__ = [
    "RECEIPT_TYPES",
    "RECEIPT_TYPE_LABELS",
    "COUNTERPARTY_ROLE",
    "KIND_LABELS",
    "components",
    "create_receipt",
    "create_single_instrument",
    "related_documents",
    "to_out",
    "duplicate_draft",
    "receipts_query",
    "resolve",
    "summary_label",
    "type_label",
    "void_receipt",
    "weighted_maturity",
]
