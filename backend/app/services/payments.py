"""اعلامیه‌ی پرداخت چندابزاری؛ ابزارها واقعی‌اند و سند حسابداری یکی است."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models.accounting import Account, JournalEntry, JournalLine
from app.models.banking import BankAccount, BankTransaction, Check
from app.models.cashbox import Cashbox
from app.models.counters import DOC_PAYMENT
from app.models.currency import Currency
from app.models.inventory import Contact
from app.models.payment import Payment, PaymentChequeTransfer, PaymentRelatedDocument
from app.models.invoices import PurchaseInvoice, WarehouseReceipt
from app.models.treasury import TreasuryTransaction
from app.models.user import User
from app.schemas.banking import CheckIn
from app.schemas.payments import PaymentIn
from app.services import bank_accounts, banking, cashboxes, check_ops
from app.services import chart_codes as cc
from app.services.common import get_account, make_journal_entry
from app.services.numbering import next_document_number
from app.services.period_close import assert_period_open
from app.services.voiding import reverse_journal_entry


PAYMENT_TYPE_LABELS = {
    "supplier": "پرداخت به تأمین‌کننده",
    "customer": "پرداخت به مشتری",
    "other": "سایر پرداخت‌ها",
}
COUNTERPARTY_ROLE = {
    "supplier": cc.ACCOUNTS_PAYABLE,
    "customer": cc.ACCOUNTS_RECEIVABLE,
    "other": cc.ACCOUNTS_PAYABLE,
}
KIND_LABELS = {
    "cash": "نقد",
    "bank_withdrawal": "برداشت بانکی",
    "payable_cheque": "چک پرداختنی",
    "endorsed_cheque": "خرج کردن چک",
}
KIND_ORDER = tuple(KIND_LABELS)


def type_label(payment_type: str) -> str:
    return PAYMENT_TYPE_LABELS.get(payment_type, payment_type)


def _money(value) -> Decimal:
    """مبلغِ ارز پایه در Cubita واحدِ کامل است (Numeric(18,0))."""
    return Decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def _base(value: Decimal, rate: Decimal) -> Decimal:
    return _money(Decimal(value) * Decimal(rate))


def _transaction(value: Decimal, rate: Decimal) -> Decimal:
    return (Decimal(value) / Decimal(rate)).quantize(Decimal("0.0001"))


def _postable_account(db: Session, account_id: UUID, label: str) -> Account:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{label} یافت نشد")
    if account.is_group:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{label} باید حسابِ قابل ثبت باشد")
    return account


def _counterparty_account(db: Session, data: PaymentIn) -> Account:
    if data.counterparty_account_id is not None:
        return _postable_account(db, data.counterparty_account_id, "حساب معین")
    role = COUNTERPARTY_ROLE.get(data.payment_type)
    if role is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "نوع پرداخت معتبر نیست")
    return get_account(db, role)


def _validate_contact(contact: Contact, payment_type: str) -> None:
    expected = "supplier" if payment_type == "supplier" else "customer" if payment_type == "customer" else None
    if expected and contact.type not in (expected, "both"):
        label = "تأمین‌کننده" if expected == "supplier" else "مشتری"
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"طرف حساب «{contact.name}» نقشِ {label} ندارد؛ نقش طرف حساب را اصلاح کنید یا نوع پرداخت را تغییر دهید",
        )


def _assert_currency(actual: str, expected: str, label: str) -> None:
    if (actual or "IRR").upper() != expected.upper():
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"ارزِ {label} ({actual or 'IRR'}) با ارز اعلامیه ({expected}) یکی نیست",
        )


def _eligible_endorsed_check(db: Session, check_id: UUID) -> Check:
    check = db.query(Check).filter(Check.id == check_id).with_for_update().first()
    if check is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "چک دریافتنی یافت نشد")
    if check.voided_at is not None or check.type != "receivable" or check.status != "in_hand":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"چک شماره‌ی {check.number} قابل خرج کردن نیست (وضعیت فعلی: {check.status})",
        )
    return check


def create_payment(db: Session, data: PaymentIn, user: User) -> Payment:
    """همه‌ی اجزا را اتمیک می‌سازد؛ retry بیرونی با Idempotency-Key مهار می‌شود."""
    #: شناسه پیش از ساختِ ردیف تولید می‌شود چون **ردیف‌های چک زودتر از خودِ
    #: اعلامیه ساخته می‌شوند** و رویدادِ صدورشان باید همین‌جا به اعلامیه اشاره کند.
    #: `check_events` فقط‌افزودنی است، پس «بعداً پُرش می‌کنیم» ممکن نیست (§۱۶).
    payment_id = uuid4()
    assert_period_open(db, data.payment_date)
    contact = db.get(Contact, data.contact_id)
    if contact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "طرف حساب یافت نشد")
    _validate_contact(contact, data.payment_type)

    if data.currency_code == "IRR":
        if Decimal(data.exchange_rate) != 1:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "نرخ ارز پایه (ریال) باید یک باشد")
    elif db.query(Currency.id).filter(Currency.code == data.currency_code).first() is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"ارز «{data.currency_code}» در موتور ارز Cubita تعریف نشده است",
        )

    counterparty = _counterparty_account(db, data)
    rate = Decimal(data.exchange_rate)
    pending: list[tuple[str, object, Decimal, Decimal]] = []
    credit_lines: list[JournalLine] = []
    payment_amount = Decimal(0)
    base_payment = Decimal(0)
    bank_fee_amount = sum((Decimal(row.bank_fee) for row in data.bank_withdrawals), Decimal(0))
    base_bank_fee = Decimal(0)

    for row in data.cash:
        box = cashboxes.resolve_cashbox(db, row.cashbox_id)
        cashboxes.assert_usable(db, box, data.payment_date)
        _assert_currency(box.currency_code, data.currency_code, f"صندوق «{box.name}»")
        amount = _base(row.amount, rate)
        payment_amount += row.amount
        base_payment += amount
        credit_lines.append(
            JournalLine(
                account_id=cashboxes.gl_account_id(db, box), analytic_id=box.analytic_id,
                debit=0, credit=amount, description=row.description or f"پرداخت نقدی از {box.name}",
            )
        )
        pending.append(("cash", (row, box), amount, Decimal(0)))

    for row in data.bank_withdrawals:
        effective_date = row.withdrawal_date or data.payment_date
        assert_period_open(db, effective_date)
        bank = bank_accounts.resolve(db, row.bank_account_id)
        bank_accounts.assert_usable(db, bank, effective_date)
        _assert_currency(bank.currency_code, data.currency_code, f"حساب «{bank.name}»")
        principal = _base(row.amount, rate)
        fee = _base(row.bank_fee, rate)
        payment_amount += row.amount
        base_payment += principal
        base_bank_fee += fee
        credit_lines.append(
            JournalLine(
                account_id=bank.gl_account_id, analytic_id=bank.analytic_id,
                debit=0, credit=principal + fee,
                description=row.description or f"برداشت از {bank.name}", tracking_no=row.number.strip() or None,
                tracking_date=effective_date,
            )
        )
        pending.append(("bank_withdrawal", (row, bank, effective_date), principal, fee))

    for row in data.payable_cheques:
        amount = _base(row.amount, rate)
        selected_bank = bank_accounts.resolve(db, row.bank_account_id) if row.bank_account_id else None
        if selected_bank is not None:
            bank_accounts.assert_usable(db, selected_bank, data.payment_date)
            _assert_currency(selected_bank.currency_code, data.currency_code, f"حساب «{selected_bank.name}»")
        check = check_ops.new_check_row(
            db,
            CheckIn(
                type="payable", number=row.number, amount=amount,
                issue_date=data.payment_date, due_date=row.due_date,
                contact_id=data.contact_id, description=row.description,
                description2=row.description2, checkbook_id=row.checkbook_id,
                sayad_id=row.sayad_id, back_number=row.back_number,
            ),
            user,
            #: §۱۴ — از رویدادِ «صدور» بتوان همین اعلامیه را باز کرد.
            source_type="payment",
            source_id=payment_id,
        )
        if check.bank_account_id and selected_bank and check.bank_account_id != selected_bank.id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "حساب بانکیِ انتخاب‌شده با حسابِ دسته‌چک یکی نیست",
            )
        if selected_bank is not None:
            check.bank_account_id = selected_bank.id
            check.bank_name = selected_bank.bank_name
            check.account_number = selected_bank.account_number
        payment_amount += row.amount
        base_payment += amount
        credit_lines.append(
            JournalLine(
                account_id=get_account(db, cc.CHECKS_PAYABLE).id, debit=0, credit=amount,
                description=row.description or f"صدور چک شماره‌ی {row.number}",
                tracking_no=row.number, tracking_date=row.due_date,
            )
        )
        pending.append(("payable_cheque", check, amount, Decimal(0)))

    endorsed_seen: set[UUID] = set()
    for row in data.endorsed_cheques:
        if row.check_id in endorsed_seen:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "یک چک دریافتنی در یک اعلامیه دوبار انتخاب شده است")
        endorsed_seen.add(row.check_id)
        check = _eligible_endorsed_check(db, row.check_id)
        amount = _money(check.amount)
        payment_amount += _transaction(amount, rate)
        base_payment += amount
        credit_lines.append(
            JournalLine(
                account_id=get_account(db, cc.CHECKS_RECEIVABLE).id, debit=0, credit=amount,
                description=f"خرج کردن چک شماره‌ی {check.number}",
                tracking_no=check.number, tracking_date=check.due_date,
            )
        )
        pending.append(("endorsed_cheque", check, amount, Decimal(0)))

    if base_payment <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "مبلغ پرداخت باید بزرگ‌تر از صفر باشد")

    discount_base = _base(data.discount_amount, rate)
    fee_account = (
        _postable_account(db, data.bank_fee_account_id, "حساب کارمزد بانکی")
        if data.bank_fee_account_id else None
    )
    if fee_account is not None and fee_account.type != "expense":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "حساب کارمزد بانکی باید ماهیت هزینه داشته باشد")
    if base_bank_fee and fee_account is None:
        fee_account = get_account(db, cc.BANK_FEE)
    discount_account = None
    if discount_base:
        discount_account = _postable_account(db, data.discount_account_id, "حساب تخفیف")

    # سند مرتبط فقط منشأ/مرجع است. فصل اعلامیه صریحاً تعیینِ Allocation را به
    # موتور تسویه‌ی طرف حساب واگذار کرده؛ اینجا نباید صرفِ اشاره به یک فاکتور را
    # «تسویه‌شده» اعلام کنیم یا سیاست FIFO/جزئی را بی‌اجازه اختراع کنیم.
    for related in data.related_documents:
        #: **رسید انبار هم می‌تواند منشأِ پرداخت باشد (§۳۸).** فقط مرجع است — مبلغ
        #: قید نمی‌شود (§۴۰) و تخصیص همچنان کارِ موتورِ تسویه است. ولی مرجعی که به
        #: رسیدِ باطل یا به تحویل‌دهنده‌ی دیگری اشاره کند، ردیابی را دروغ می‌کند.
        if related.document_type == "warehouse_receipt":
            receipt = db.get(WarehouseReceipt, related.document_id)
            if receipt is None or receipt.is_voided:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "رسید انبار مرتبط معتبر نیست")
            if receipt.contact_id is not None and receipt.contact_id != contact.id:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST, "طرف حساب پرداخت با تحویل‌دهنده‌ی رسید انبار یکسان نیست"
                )
            continue
        if related.document_type != "purchase_invoice":
            continue
        invoice = db.get(PurchaseInvoice, related.document_id)
        if invoice is None or invoice.is_voided:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "فاکتور خرید مرتبط معتبر نیست")
        if invoice.contact_id != contact.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "تأمین‌کننده پرداخت با فاکتور خرید یکسان نیست")

    description = data.description.strip() or f"{type_label(data.payment_type)} — {contact.name}"
    debit_lines = [
        JournalLine(
            account_id=counterparty.id, analytic_id=contact.analytic_id,
            debit=base_payment + discount_base, credit=0, description=description,
        )
    ]
    if base_bank_fee:
        debit_lines.append(
            JournalLine(account_id=fee_account.id, debit=base_bank_fee, credit=0, description="کارمزد بانکی")
        )
    if discount_base:
        credit_lines.append(
            JournalLine(account_id=discount_account.id, debit=0, credit=discount_base, description="تخفیف تسویه")
        )

    entry = make_journal_entry(db, data.payment_date, description, "payment", user, [*debit_lines, *credit_lines])
    payment = Payment(
        id=payment_id,
        number=next_document_number(db, DOC_PAYMENT), payment_type=data.payment_type,
        contact_id=contact.id, payment_date=data.payment_date,
        counterparty_account_id=counterparty.id,
        bank_fee_account_id=fee_account.id if fee_account else None,
        discount_account_id=discount_account.id if discount_account else None,
        currency_code=data.currency_code, exchange_rate=rate,
        payment_amount=payment_amount, base_currency_amount=base_payment,
        discount_amount=data.discount_amount, settlement_total=payment_amount + data.discount_amount,
        bank_fee_amount=bank_fee_amount, description=description,
        description2=data.description2.strip(), establishment=data.establishment.strip(),
        journal_entry_id=entry.id, created_by_id=user.id, updated_by_id=user.id,
    )
    db.add(payment)
    db.flush()
    entry.source_id = payment.id

    for kind, source, principal, fee in pending:
        if kind == "cash":
            row, box = source
            db.add(TreasuryTransaction(
                type="payment", transaction_date=data.payment_date, contact_id=contact.id,
                amount=principal, method="cash", cashbox_id=box.id,
                description=row.description, payment_id=payment.id,
                journal_entry_id=entry.id, created_by_id=user.id,
            ))
        elif kind == "bank_withdrawal":
            row, bank, effective_date = source
            db.add(TreasuryTransaction(
                type="payment", transaction_date=data.payment_date, contact_id=contact.id,
                amount=principal, method="bank", bank_account_id=bank.id,
                description=row.description, reference_no=row.number.strip() or None,
                payment_id=payment.id, journal_entry_id=entry.id, created_by_id=user.id,
            ))
            db.add(BankTransaction(
                bank_account_id=bank.id, transaction_date=effective_date,
                amount=-(principal + fee), principal_amount=principal, bank_fee_amount=fee,
                reference_no=row.number.strip(), description=row.description,
                description2=row.description2, source_type="payment_withdrawal",
                source_id=payment.id, payment_id=payment.id,
                journal_entry_id=entry.id, created_by_id=user.id,
            ))
        elif kind == "payable_cheque":
            check = source
            check.payment_id = payment.id
            db.add(check)
        else:
            check = source
            db.add(PaymentChequeTransfer(
                payment_id=payment.id, check_id=check.id, previous_status=check.status, created_by_id=user.id,
            ))
            #: از تنها نقطه‌ی نوشتنِ وضعیت رد می‌شود تا رویدادِ «خرج شد، به چه کسی»
            #: در تایم‌لاین بیفتد. سند را همین اعلامیه زده، پس دوباره زده نمی‌شود.
            check_ops.update_check_status(
                db, check.id, "endorsed", None, user,
                contact_id=data.contact_id, event_date=data.payment_date,
                external_journal_entry_id=entry.id,
                #: §۱۶ — «خرج شد» بدونِ «در کدام اعلامیه» نیمی از جواب است.
                source_type="payment", source_id=payment.id,
                note=f"خرج شده با اعلامیه‌ی پرداخت شماره {int(payment.number)}",
            )

    for row in data.related_documents:
        db.add(PaymentRelatedDocument(
            payment_id=payment.id, document_type=row.document_type,
            document_id=row.document_id, allocated_amount=Decimal(0),
        ))

    db.flush()
    db.refresh(payment)
    return payment


def resolve(db: Session, payment_id: UUID) -> Payment:
    payment = db.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "اعلامیه‌ی پرداخت یافت نشد")
    return payment


def payments_query(db: Session):
    return db.query(Payment).options(joinedload(Payment.contact))


def components(db: Session, payment: Payment) -> list[dict]:
    rows: list[dict] = []
    rate = Decimal(payment.exchange_rate)
    txns = db.query(TreasuryTransaction).filter(TreasuryTransaction.payment_id == payment.id).all()
    for txn in txns:
        if txn.method != "cash":
            continue
        box = db.get(Cashbox, txn.cashbox_id) if txn.cashbox_id else None
        rows.append({
            "kind": "cash", "label": box.name if box else "صندوق پیش‌فرض",
            "amount": _transaction(Decimal(txn.amount), rate), "bank_fee": 0,
            "source_id": txn.id, "reference_no": "", "due_date": None,
            "status": "", "description": txn.description or "",
        })
    for txn in db.query(BankTransaction).filter(
        BankTransaction.payment_id == payment.id, BankTransaction.source_type == "payment_withdrawal"
    ).all():
        bank = db.get(BankAccount, txn.bank_account_id)
        principal = Decimal(txn.principal_amount) or (abs(Decimal(txn.amount)) - Decimal(txn.bank_fee_amount))
        rows.append({
            "kind": "bank_withdrawal", "label": bank.name if bank else "حساب بانکی",
            "amount": _transaction(principal, rate),
            "bank_fee": _transaction(Decimal(txn.bank_fee_amount), rate),
            "source_id": txn.id, "reference_no": txn.reference_no or "",
            "due_date": txn.transaction_date, "status": "مغایرت‌گیری‌شده" if txn.is_reconciled else "",
            "description": txn.description or "",
        })
    for check in db.query(Check).filter(Check.payment_id == payment.id).all():
        rows.append({
            "kind": "payable_cheque", "label": check.bank_name or (check.bank_account.name if check.bank_account else "چک"),
            "amount": _transaction(Decimal(check.amount), rate), "bank_fee": 0,
            "source_id": check.id, "reference_no": check.number,
            "due_date": check.due_date, "status": check.status, "description": check.description or "",
        })
    transfers = db.query(PaymentChequeTransfer).filter(PaymentChequeTransfer.payment_id == payment.id).all()
    for transfer in transfers:
        check = db.get(Check, transfer.check_id)
        if check is None:
            continue
        rows.append({
            "kind": "endorsed_cheque", "label": check.bank_name or "چک دریافتنی",
            "amount": _transaction(Decimal(check.amount), rate), "bank_fee": 0,
            "source_id": check.id, "reference_no": check.number,
            "due_date": check.due_date, "status": "برگشت از خرج" if transfer.reversed_at else check.status,
            "description": check.description or "",
        })
    rows.sort(key=lambda row: KIND_ORDER.index(row["kind"]))
    return rows


def related_documents(db: Session, payment_id: UUID) -> list[dict]:
    return [
        {"document_type": row.document_type, "document_id": row.document_id, "allocated_amount": row.allocated_amount}
        for row in db.query(PaymentRelatedDocument).filter(PaymentRelatedDocument.payment_id == payment_id).all()
    ]


def summary_label(rows: list[dict]) -> str:
    return "، ".join(KIND_LABELS[kind] for kind in KIND_ORDER if any(r["kind"] == kind for r in rows))


def to_out(db: Session, payment: Payment) -> dict:
    rows = components(db, payment)
    creator = db.get(User, payment.created_by_id)
    editor = db.get(User, payment.updated_by_id) if payment.updated_by_id else None
    return {
        "id": payment.id, "number": int(payment.number), "payment_type": payment.payment_type,
        "payment_type_label": type_label(payment.payment_type), "contact_id": payment.contact_id,
        "contact_name": payment.contact.name if payment.contact else "", "payment_date": payment.payment_date,
        "counterparty_account_id": payment.counterparty_account_id,
        "bank_fee_account_id": payment.bank_fee_account_id, "discount_account_id": payment.discount_account_id,
        "currency_code": payment.currency_code, "exchange_rate": payment.exchange_rate,
        "payment_amount": payment.payment_amount, "base_currency_amount": payment.base_currency_amount,
        "discount_amount": payment.discount_amount, "settlement_total": payment.settlement_total,
        "bank_fee_amount": payment.bank_fee_amount, "description": payment.description,
        "description2": payment.description2, "establishment": payment.establishment,
        "journal_entry_id": payment.journal_entry_id, "items_summary": summary_label(rows),
        "components": rows, "related_documents": related_documents(db, payment.id),
        "voided_at": payment.voided_at, "created_at": payment.created_at, "updated_at": payment.updated_at,
        "created_by_name": creator.name if creator else "",
        "updated_by_name": editor.name if editor else "",
    }


def eligible_received_cheques(db: Session) -> list[Check]:
    return db.query(Check).filter(
        Check.type == "receivable", Check.status == "in_hand", Check.voided_at.is_(None)
    ).order_by(Check.due_date, Check.number).all()


def void_payment(db: Session, payment_id: UUID, *, reason: str, user: User, void_date=None) -> Payment:
    payment = resolve(db, payment_id)
    if payment.voided_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "این اعلامیه قبلاً باطل شده است")
    effective_date = void_date or payment.payment_date
    assert_period_open(db, effective_date)

    issued = db.query(Check).filter(Check.payment_id == payment.id).all()
    for check in issued:
        if check.status != "issued":
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"چک شماره‌ی {check.number} پس از صدور وارد وضعیت «{check.status}» شده است؛ ابتدا عملیات بعدی را اصلاح کنید",
            )
    transfers = db.query(PaymentChequeTransfer).filter(
        PaymentChequeTransfer.payment_id == payment.id, PaymentChequeTransfer.reversed_at.is_(None)
    ).all()
    for transfer in transfers:
        check = db.get(Check, transfer.check_id)
        if check is None or check.status != "endorsed":
            raise HTTPException(status.HTTP_409_CONFLICT, "یکی از چک‌های خرج‌شده عملیات بعدی دارد و اعلامیه مستقیم باطل نمی‌شود")
    bank_rows = db.query(BankTransaction).filter(
        BankTransaction.payment_id == payment.id, BankTransaction.source_type == "payment_withdrawal"
    ).all()
    if any(row.is_reconciled for row in bank_rows):
        raise HTTPException(status.HTTP_409_CONFLICT, "برداشت بانکیِ این اعلامیه مغایرت‌گیری شده است؛ ابتدا تطبیق را باز کنید")

    entry = db.get(JournalEntry, payment.journal_entry_id)
    if entry is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "سند حسابداریِ اعلامیه یافت نشد")
    reversal = reverse_journal_entry(
        db, entry, void_date=effective_date, user=user,
        description=f"ابطال اعلامیه‌ی پرداخت شماره {int(payment.number)}" + (f" — {reason.strip()}" if reason.strip() else ""),
    )
    now = datetime.now(timezone.utc)
    for txn in db.query(TreasuryTransaction).filter(TreasuryTransaction.payment_id == payment.id).all():
        txn.voided_at = now
        txn.voided_by_id = user.id
        txn.void_reason = reason.strip()
    for row in bank_rows:
        db.add(BankTransaction(
            bank_account_id=row.bank_account_id, transaction_date=effective_date, amount=-Decimal(row.amount),
            principal_amount=-Decimal(row.principal_amount), bank_fee_amount=-Decimal(row.bank_fee_amount),
            reference_no=row.reference_no, description=f"برگشت: {row.description}", description2=row.description2,
            source_type="payment_void", source_id=payment.id, payment_id=payment.id,
            journal_entry_id=reversal.id, created_by_id=user.id,
        ))
    for check in issued:
        check.voided_at = now
        check.voided_by_id = user.id
        check.void_reason = reason.strip()
    for transfer in transfers:
        check = db.get(Check, transfer.check_id)
        #: **اول ردیف را برگشت‌خورده علامت بزن، بعد وضعیت را عوض کن.** گاردِ
        #: `assert_not_pledged_to_payment` دقیقاً همین حرکت را از مسیرهای دیگر
        #: می‌بندد؛ اگر ترتیب برعکس بود، ابطالِ خودمان را هم رد می‌کرد.
        transfer.reversed_at = now
        db.flush()
        #: همان مسیر، برعکس — تا برگشت هم رویداد بگیرد و تایم‌لاین کامل بماند.
        check_ops.update_check_status(
            db, check.id, transfer.previous_status, None, user,
            event_date=effective_date, external_journal_entry_id=reversal.id,
            note=f"برگشت با ابطالِ اعلامیه‌ی پرداخت شماره {int(payment.number)}",
        )
    payment.voided_at = now
    payment.voided_by_id = user.id
    payment.void_reason = reason.strip()
    payment.updated_by_id = user.id
    db.flush()
    db.refresh(payment)
    return payment
