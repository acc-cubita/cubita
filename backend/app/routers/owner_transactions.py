from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import require_permission
from app.models.inventory import Contact
from app.models.owner_transactions import OwnerTransaction
from app.models.user import User
from app.pagination import Page, PageParams, paginate
from app.schemas.owner_transactions import (
    OwnerTransactionIn,
    OwnerTransactionOut,
    PartnerBalanceOut,
)
from app.services.idempotency import idempotent
from app.services.owner_transactions import (
    TYPE_LABELS,
    create_owner_transaction,
    partner_balance,
)

router = APIRouter(tags=["owner-transactions"])


def _row(txn: OwnerTransaction) -> OwnerTransactionOut:
    return OwnerTransactionOut(
        id=txn.id,
        type=txn.type,
        type_label=TYPE_LABELS.get(txn.type, txn.type),
        transaction_date=txn.transaction_date,
        contact_id=txn.contact_id,
        contact_name=txn.contact.name if txn.contact else "",
        amount=txn.amount,
        method=txn.method,
        bank_account_id=txn.bank_account_id,
        cashbox_id=txn.cashbox_id,
        description=txn.description or "",
        evidence_ref=txn.evidence_ref or "",
        journal_entry_id=txn.journal_entry_id,
        voided_at=txn.voided_at,
        void_reason=txn.void_reason or "",
    )


@router.get("/api/owner-transactions", response_model=Page[OwnerTransactionOut])
def list_owner_transactions(
    contact_id: UUID | None = None,
    type: str | None = None,
    db: Session = Depends(get_db),
    params: PageParams = Depends(),
    _=Depends(require_permission("accounting", "view")),
):
    """فیلتر سمتِ سرور است، نه مرورگر — همان قاعده‌ای که بقیه‌ی دفترها دارند."""
    query = db.query(OwnerTransaction).options(joinedload(OwnerTransaction.contact))
    if contact_id is not None:
        query = query.filter(OwnerTransaction.contact_id == contact_id)
    if type:
        query = query.filter(OwnerTransaction.type == type)
    items, next_cursor = paginate(
        query, [OwnerTransaction.transaction_date, OwnerTransaction.id], params
    )
    return Page(items=[_row(t) for t in items], next_cursor=next_cursor)


@router.post("/api/owner-transactions", response_model=OwnerTransactionOut, status_code=201)
def create_owner_transaction_route(
    data: OwnerTransactionIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("accounting", "create")),
):
    """ثبتِ آورده، برداشت، وام یا بازپرداختِ شریک — با نوعِ صریح (قاعده‌ی ۵۲).

    **idempotent.** تکرارِ شبکه‌ای نباید دو آورده‌ی سرمایه بسازد؛ سرمایه‌ی شرکت
    عددی نیست که دوبار ثبتش بی‌صدا بماند.
    """
    def _replay(rid):
        row = db.get(OwnerTransaction, rid)
        return _row(row) if row is not None else None

    return idempotent(
        db, request, user, operation="create_owner_transaction", payload=data,
        run=lambda: _row(create_owner_transaction(db, data, user)),
        replay=_replay,
    )


@router.get("/api/owner-transactions/partner-balances", response_model=list[PartnerBalanceOut])
def partner_balances(
    db: Session = Depends(get_db),
    _=Depends(require_permission("accounting", "view")),
):
    """ماندهٔ جاری شرکا برای هر سهامدار — مشتق از اسناد، نه ستونِ ذخیره‌شده."""
    holders = (
        db.query(Contact)
        .filter(Contact.is_shareholder.is_(True))
        .order_by(Contact.name)
        .all()
    )
    return [
        PartnerBalanceOut(
            contact_id=c.id,
            contact_name=c.name,
            share_percent=Decimal(c.share_percent or 0),
            balance=partner_balance(db, c.id),
        )
        for c in holders
    ]
