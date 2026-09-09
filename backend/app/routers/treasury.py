from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_permission
from app.models.treasury import TreasuryTransaction
from app.models.user import User
from app.pagination import Page, PageParams, paginate
from app.schemas.treasury import CardPaymentIn, TreasuryTransactionIn, TreasuryTransactionOut
from app.services import treasury as treasury_service
from app.services.idempotency import idempotent

router = APIRouter(tags=["treasury"])


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
        psp=txn.psp,
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
            run=lambda: treasury_service.create_receipt(db, data, user),
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
