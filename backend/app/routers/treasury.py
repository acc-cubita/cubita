from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import Principal, get_principal, require_permission
from app.models.treasury import TreasuryTransaction
from app.models.payment import Payment
from app.models.user import User
from app.pagination import Page, PageParams, paginate
from app.schemas.treasury import CardPaymentIn, TreasuryTransactionIn, TreasuryTransactionOut
from app.schemas.banking import CheckOut
from app.schemas.payments import PaymentIn, PaymentOut, PaymentVoidIn
from app.services import receipts as receipt_service
from app.services import treasury as treasury_service
from app.models.inventory import Contact
from app.services import payments as payment_service
from app.services.printing import render_payment
from app.services.idempotency import idempotent

router = APIRouter(tags=["treasury"])


@router.get("/api/payments", response_model=Page[PaymentOut])
def list_payments(
    db: Session = Depends(get_db),
    params: PageParams = Depends(),
    _=Depends(require_permission("checks_bank", "view")),
):
    items, next_cursor = paginate(
        payment_service.payments_query(db),
        [Payment.payment_date, Payment.id],
        params,
    )
    return Page(items=[payment_service.to_out(db, item) for item in items], next_cursor=next_cursor)


@router.get("/api/payments/eligible-received-cheques", response_model=list[CheckOut])
def eligible_received_cheques(
    db: Session = Depends(get_db),
    _=Depends(require_permission("checks_bank", "view")),
):
    return payment_service.eligible_received_cheques(db)


@router.get("/api/payments/{payment_id}", response_model=PaymentOut)
def get_payment(
    payment_id: UUID,
    db: Session = Depends(get_db),
    _=Depends(require_permission("checks_bank", "view")),
):
    return payment_service.to_out(db, payment_service.resolve(db, payment_id))


@router.post("/api/payments", response_model=PaymentOut, status_code=201)
def create_payment_document(
    data: PaymentIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("checks_bank", "create")),
):
    payment = idempotent(
        db,
        request,
        user,
        operation="create_payment_document",
        payload=data,
        run=lambda: payment_service.create_payment(db, data, user),
        replay=lambda rid: db.get(Payment, rid),
    )
    return payment_service.to_out(db, payment)


@router.post("/api/payments/{payment_id}/void", response_model=PaymentOut)
def void_payment_document(
    payment_id: UUID,
    data: PaymentVoidIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("checks_bank", ("approve", "delete"))),
):
    payment = payment_service.void_payment(
        db, payment_id, reason=data.reason, void_date=data.void_date, user=user
    )
    return payment_service.to_out(db, payment)


def _to_out(txn) -> TreasuryTransactionOut:
    return TreasuryTransactionOut(
        id=txn.id,
        type=txn.type,
        transaction_date=txn.transaction_date,
        contact_id=txn.contact_id,
        contact_name=txn.contact.name if txn.contact else "",
        amount=txn.amount,
        method=txn.method,
        bank_account_id=txn.bank_account_id,
        description=txn.description,
        journal_entry_id=txn.journal_entry_id,
        paid_via=txn.paid_via,
        reference_no=txn.reference_no,
        trace_no=txn.trace_no,
        card_mask=txn.card_mask,
        terminal_no=txn.terminal_no,
        pos_terminal_id=txn.pos_terminal_id,
        psp=txn.psp,
        #: این دو از قبل در شِما بودند ولی هرگز پر نمی‌شدند — یعنی هر مصرفی از این
        #: مسیر «تسویه‌نشده» را نمی‌دید و صندوقِ رسید هم گم می‌شد.
        settled_at=txn.settled_at,
        voided_at=txn.voided_at,
        cashbox_id=txn.cashbox_id,
    )


@router.get("/api/treasury", response_model=Page[TreasuryTransactionOut])
def list_treasury(
    db: Session = Depends(get_db),
    params: PageParams = Depends(),
    _=Depends(require_permission("checks_bank", "view")),
):
    items, next_cursor = paginate(
        treasury_service.transactions_query(db),
        [TreasuryTransaction.transaction_date, TreasuryTransaction.id],
        params,
    )
    return Page(items=[_to_out(t) for t in items], next_cursor=next_cursor)


@router.post("/api/treasury/receipts", response_model=TreasuryTransactionOut, status_code=201)
def create_receipt(
    data: TreasuryTransactionIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("checks_bank", "create")),
):
    # صفِ آفلاینِ موبایل این را دوباره می‌فرستد اگر پاسخ گم شود. بدونِ کلیدِ
    # idempotency، همان یک دریافت دو بار در دفتر می‌نشیند — بی‌هیچ خطایی.
    return _to_out(
        idempotent(
            db,
            request,
            user,
            operation="create_treasury_receipt",
            payload=data,
            #: از مهاجرتِ ۰۱۰۹ این مسیر هم سربرگِ رسید می‌سازد — قرارداد عوض
            #: نشده، ولی رسیدِ موبایل هم شماره می‌گیرد و در دفتر دیده می‌شود.
            run=lambda: receipt_service.create_single_instrument(db, data, user),
            replay=lambda rid: db.get(TreasuryTransaction, rid),
        )
    )


@router.post("/api/treasury/payments", response_model=TreasuryTransactionOut, status_code=201)
def create_payment(
    data: TreasuryTransactionIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("checks_bank", "create")),
):
    return _to_out(
        idempotent(
            db,
            request,
            user,
            operation="create_treasury_payment",
            payload=data,
            run=lambda: treasury_service.create_payment(db, data, user),
            replay=lambda rid: db.get(TreasuryTransaction, rid),
        )
    )


@router.post("/api/treasury/card-payment", response_model=TreasuryTransactionOut, status_code=201)
def create_card_payment(
    data: CardPaymentIn,
    db: Session = Depends(get_db),
    # پرداختِ کارتی بخشی از «فروش» است، پس با مجوزِ فروش گیت می‌شود تا صندوق‌دار هم
    # (که checks_bank ندارد) بتواند کارت بکشد و رسیدِ بانکی خودکار ثبت شود.
    user: User = Depends(require_permission("invoices", "create")),
):
    return _to_out(treasury_service.record_card_payment(db, data, user))


@router.get("/api/payments/{payment_id}/print", response_class=HTMLResponse)
def print_payment(
    payment_id: UUID,
    db: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
    _=Depends(require_permission("checks_bank", "view")),
):
    """قرینه‌ی `/api/receipts/{id}/print` — همان موتور، همان رکورد.

    بدونِ این، اعلامیه‌ی پرداخت تنها سندِ مالیِ کوبیتا بود که چاپ نمی‌شد، در حالی
    که خواهرش (رسید دریافت) می‌شد.
    """
    payment = payment_service.resolve(db, payment_id)
    contact = db.get(Contact, payment.contact_id)
    detail = " — ".join(filter(None, [getattr(contact, "phone", ""), getattr(contact, "address", "")]))
    currency_line = ""
    if payment.currency_code and payment.currency_code != "IRR":
        currency_line = (
            f"ارز اعلامیه: {payment.currency_code} — نرخ تسعیر: {payment.exchange_rate}؛ "
            "مبالغ زیر به ریال است"
        )
    html = render_payment(
        business_name=principal.membership.tenant.name,
        number=int(payment.number),
        payment_date=payment.payment_date,
        type_label=payment_service.type_label(payment.payment_type),
        party_name=contact.name if contact else "—",
        party_detail=detail,
        description=payment.description,
        description2=payment.description2,
        components=payment_service.components(db, payment),
        payment_amount=payment.base_currency_amount,
        discount_amount=payment.discount_amount,
        bank_fee_amount=payment.bank_fee_amount,
        settlement_total=payment.base_currency_amount + payment.discount_amount,
        voided_at=payment.voided_at,
        void_reason=payment.void_reason,
        currency_line=currency_line,
    )
    return HTMLResponse(content=html, headers={"Cache-Control": "no-store"})
